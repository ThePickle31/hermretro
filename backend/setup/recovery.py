"""What survives a page reload or a broker restart for the page's toolchain install, and what the page can do next.

* A small journal (``<deps root>/page-install.json``) of the last install the page started: its state, times, error
  and the broker that ran it. The broker writes it at start and at the end; a reader that finds ``running`` from a
  broker that no longer runs reports the install as ``interrupted`` instead of starting over silently.
* ``classify``: a ``toolchain_prepare`` result's code and the one next step for it, from the engine's structured
  fields (its error codes, bounded diagnostics and its plan's lock), before any message is shortened for display.
  ``explain`` does the same from words alone, for failures that carry no result.
* ``settled``: whether the engine's own setup run has let go of its lock, which is what a cancel waits for.
* ``worker_left``: an installer worker whose exit was never confirmed, recorded so a new broker (or Remove
  downloaded tools) waits for it too.

Stdlib only; no Hermes imports (the broker imports it through the front door).
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from ..system import paths
from .progress import download_bytes

JOURNAL_NAME = "page-install.json"
TERMINAL = frozenset({"done", "failed", "cancelled", "interrupted"})
# Kept in the journal; everything else in the broker's install state is progress, recomputed on each read.
_KEPT = (
    "state",
    "started_at",
    "finished_at",
    "code",
    "error",
    "hint",
    "broker",
    "run_id",
    "cancel_requested_at",
    "worker_pgid",
)
LOCK_DIR = ".setup-lock"
# A fresh install needs about the measured size on disk. Only a folder with evidence of reusable parts (a finished
# component's receipt, or cached downloads) may need less, and that lower figure is an estimate, never a promise.
FRESH_HEADROOM = 2_300_000_000
REPAIR_HEADROOM = 500_000_000


def journal_path() -> Path:
    return paths.DEPS_ROOT / JOURNAL_NAME


def write_journal(state: dict) -> None:
    """Record the install's lasting facts. Never raises: a journal that cannot be written only costs the reload."""
    try:
        path = journal_path()
        path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        paths.write_json_atomic(path, {key: state.get(key) for key in _KEPT if key in state})
    except OSError:
        pass


def read_journal() -> dict | None:
    try:
        data = json.loads(journal_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("state"), str):
        return None
    return data if data["state"] in TERMINAL | {"running"} else None


def lock_path(root: Path) -> Path:
    return Path(root) / LOCK_DIR


def recovered(root: Path, current_broker: str | None) -> dict | None:
    """The last install as the journal tells it, for a broker (or a Hermes process with no broker) that did not
    run it. ``running`` from another broker is displayed as ``interrupted``. Do not write this interpretation
    back: a passive status call can race a new broker starting an install. The engine's lock is never removed."""
    journal = read_journal()
    if journal is None:
        return None
    if journal.get("state") == "running" and journal.get("broker") != current_broker:
        locked = lock_path(root).exists()
        journal.update(
            state="interrupted",
            code="INTERRUPTED",
            error="The install stopped when hermretro's background process ended (for example when Hermes quit).",
            hint=(
                f"The engine's setup lock is still at {lock_path(root)}. Check that the owner recorded in its "
                "owner.json has stopped, then quit Hermes and move that folder aside (never delete a lock a running "
                "setup holds) and install again. Finished parts are kept."
                if locked
                else "Finished parts are kept. Install again to continue."
            ),
        )
    return journal


_NETWORK = re.compile(
    r"ENOTFOUND|EAI_AGAIN|ECONNREFUSED|ECONNRESET|ETIMEDOUT|ENETUNREACH|EHOSTUNREACH|getaddrinfo|"
    r"certificate|CERT_|self.signed|socket hang up|fetch failed|network",
    re.IGNORECASE,
)
_SPACE = re.compile(r"ENOSPC|EDQUOT|no space left|disk quota exceeded", re.IGNORECASE)
# The engine's own error codes (scripts/setup-io.mjs, Node's system errors) for the same two causes.
_NETWORK_CODES = frozenset(
    {
        "DOWNLOAD_FAILED",
        "DOWNLOAD_TIMEOUT",
        "ENOTFOUND",
        "EAI_AGAIN",
        "ECONNREFUSED",
        "ECONNRESET",
        "ETIMEDOUT",
        "ENETUNREACH",
        "EHOSTUNREACH",
        "UND_ERR_CONNECT_TIMEOUT",
        "UND_ERR_SOCKET",
    }
)
_SPACE_CODES = frozenset({"ENOSPC", "EDQUOT"})
_TAIL = 4096  # bytes of each captured output stream that classification reads (the engine keeps 8 KiB)

NETWORK_HINT = (
    "A download source could not be reached. Check the internet connection (and any proxy or firewall), "
    "then try again: finished parts are kept, so it picks up where it stopped."
)
SPACE_HINT = "The disk filled up. Free some space, then try again: finished parts are kept."


def foreign_lock_hint(root: Path) -> str:
    """The next step for a setup lock this install never held: its recorded owner must be seen to have stopped."""
    lock = lock_path(root)
    return (
        f"Another installer holds the setup lock at {lock} (a chat, another app such as Codex, or a setup that "
        f"stopped without cleaning up). Its owner is recorded in {lock / 'owner.json'}. Wait for it to finish; "
        "only once you have checked that the recorded owner has stopped, move the folder aside (never delete a "
        "lock a running setup holds), then try again."
    )


def explain(code: str | None, error: str | None, root: Path) -> tuple[str | None, str | None]:
    """A failure's specific code and its next step, from the engine's own words. ``(code, None)`` when nothing
    more specific is known. ``classify`` reads a tool result's structured fields first."""
    text = error or ""
    if code == "SETUP_LOCKED" or "Another setup owns" in text:
        return "SETUP_LOCKED", foreign_lock_hint(root)
    if (code or "").upper() in _SPACE_CODES or _SPACE.search(text):
        return "NO_SPACE", SPACE_HINT
    if (code or "").upper() in _NETWORK_CODES or _NETWORK.search(text):
        return "NETWORK", NETWORK_HINT
    return code, None


def _errors(structured: dict) -> list[dict]:
    """Every serialized engine error in a toolchain_prepare result: failed components first, then the run's own."""
    run = structured.get("result") if isinstance(structured.get("result"), dict) else {}
    found = [
        component.get("error")
        for component in run.get("components") or []
        if isinstance(component, dict) and component.get("status") in ("failed", "blocked", "cancelled")
    ]
    found += [run.get(name) for name in ("error", "preparationError", "readinessError", "cleanupError")]
    return [error for error in found if isinstance(error, dict)]


def _evidence(error: dict) -> tuple[str, str]:
    """One serialized engine error's code and its bounded words: message plus captured output tails."""
    execution = error.get("execution") if isinstance(error.get("execution"), dict) else {}
    words = [str(error.get("message") or "")[:_TAIL]]
    words += [str(execution.get(name) or "")[-_TAIL:] for name in ("stderrTail", "stdoutTail")]
    return str(error.get("code") or "").upper(), "\n".join(words)


def classify(result: dict, root: Path) -> dict:
    """``{"code", "hint", "foreign_lock"}`` for a toolchain_prepare result that did not succeed, from the pinned
    engine's structured fields: the preflight plan's ``lock`` and ``rootIssue`` (stage ``blocked``), a thrown
    ``SETUP_LOCKED``, each failed component's ``code`` and its ``execution`` output tails. ``code`` is None when
    nothing more specific than the engine's stage is known."""
    structured = result.get("structuredContent") if isinstance(result.get("structuredContent"), dict) else {}
    plan = structured.get("plan") if isinstance(structured.get("plan"), dict) else {}
    if structured.get("stage") == "blocked" and isinstance(plan.get("lock"), dict):
        return {"code": "SETUP_LOCKED", "hint": foreign_lock_hint(root), "foreign_lock": True}
    if str(structured.get("code") or "") == "SETUP_LOCKED":  # the lock appeared between the plan and the apply
        return {"code": "SETUP_LOCKED", "hint": foreign_lock_hint(root), "foreign_lock": True}
    evidence = [_evidence(error) for error in _errors(structured)]
    if structured.get("code") or structured.get("error"):
        evidence.append((str(structured.get("code") or "").upper(), str(structured.get("error") or "")[:_TAIL]))
    for codes, pattern, code, hint in (
        (_SPACE_CODES, _SPACE, "NO_SPACE", SPACE_HINT),
        (_NETWORK_CODES, _NETWORK, "NETWORK", NETWORK_HINT),
    ):
        if any(found in codes for found, _ in evidence) or any(pattern.search(words) for _, words in evidence):
            return {"code": code, "hint": hint, "foreign_lock": False}
    return {"code": None, "hint": None, "foreign_lock": False}


def lock_started(root: Path) -> float | None:
    """When the setup lock's recorded owner took it (its ``owner.json`` ``startedAt``), or None when unknown."""
    try:
        owner = json.loads((lock_path(root) / "owner.json").read_text(encoding="utf-8"))
        return datetime.fromisoformat(str(owner["startedAt"]).replace("Z", "+00:00")).timestamp()
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def _reusable(root: Path) -> bool:
    """Evidence that an install here reuses finished work: a component receipt that says ready, or cached
    downloads. A folder holding only the engine's marker, run records or empty staging needs the full install."""
    try:
        with os.scandir(Path(root) / "receipts") as entries:
            for entry in entries:
                try:
                    if json.loads(Path(entry.path).read_text(encoding="utf-8")).get("status") == "ready":
                        return True
                except (OSError, ValueError, AttributeError):
                    continue
    except OSError:
        pass
    return download_bytes(Path(root)) > 0


def free_space(root: Path) -> dict:
    """Free bytes where the toolchain goes and what an install there needs. ``enough`` is False only when even
    the estimate cannot fit; ``warning`` says when the fit is uncertain (a lowered estimate, or no measurement)."""
    probe = Path(root)
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    try:
        free = shutil.disk_usage(probe).free
    except OSError:
        return {
            "free_bytes": None,
            "needed_bytes": FRESH_HEADROOM,
            "enough": True,
            "estimate": "unknown",
            "warning": "The free disk space could not be measured; the game tools need up to about 2.3 GB.",
        }
    if not _reusable(root):
        return {
            "free_bytes": free,
            "needed_bytes": FRESH_HEADROOM,
            "enough": free >= FRESH_HEADROOM,
            "estimate": "fresh",
        }
    answer = {
        "free_bytes": free,
        "needed_bytes": REPAIR_HEADROOM,
        "enough": free >= REPAIR_HEADROOM,
        "estimate": "reuse",
    }
    if answer["enough"] and free < FRESH_HEADROOM:
        answer["warning"] = (
            "Finished parts are reused, so this may fit, but a full install needs about 2.3 GB and less is free. "
            "If it stops with a full disk, free some space and try again."
        )
    return answer


def worker_left(journal: dict | None) -> bool:
    """An installer worker recorded as not confirmed exited (``worker_pgid``) whose process group still exists."""
    pgid = (journal or {}).get("worker_pgid")
    if not isinstance(pgid, int) or pgid <= 1:
        return False
    try:
        os.killpg(pgid, 0)  # signal 0: only asks whether the group exists (Linux and macOS)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # it exists, under another user


def settled(root: Path, since: float | None) -> bool:
    """The engine's setup run has finished with the toolchain folder: no lock, and its run record (when it wrote
    one during this install) no longer says running."""
    if lock_path(root).exists():
        return False
    try:
        record = Path(root) / "last-run.json"
        if since is not None and record.stat().st_mtime >= since - 2:
            return json.loads(record.read_text(encoding="utf-8")).get("status") != "running"
    except (OSError, ValueError, AttributeError):
        pass
    return True


def activity_mark(root: Path) -> tuple:
    """Something that changes while the engine works on the toolchain folder (any top-level entry, its staging
    and run records). Used to tell "quiet for a while" from "stuck"; bytes alone are not enough, as compiling
    writes little."""
    marks = []
    for folder in (Path(root), Path(root) / "staging", Path(root) / "toolchain", Path(root) / "runs"):
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    try:
                        marks.append((entry.name, entry.stat(follow_symlinks=False).st_mtime_ns))
                    except OSError:
                        continue
        except OSError:
            continue
    return tuple(sorted(marks))

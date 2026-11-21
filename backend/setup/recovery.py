"""What survives a page reload or a broker restart for the page's toolchain install, and what the page can do next.

* A small journal (``<deps root>/page-install.json``) of the last install the page started: its state, times, error
  and the broker that ran it. The broker writes it at start and at the end; a reader that finds ``running`` from a
  broker that no longer runs reports the install as ``interrupted`` instead of starting over silently.
* ``explain``: a failure's code and the one next step for it (no network, no space, the engine's setup lock).
* ``settled``: whether the engine's own setup run has let go of its lock, which is what a cancel waits for.

Stdlib only; no Hermes imports (the broker imports it through the front door).
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from ..system import paths

JOURNAL_NAME = "page-install.json"
TERMINAL = frozenset({"done", "failed", "cancelled", "interrupted"})
# Kept in the journal; everything else in the broker's install state is progress, recomputed on each read.
_KEPT = ("state", "started_at", "finished_at", "code", "error", "hint", "broker", "cancel_requested_at")
LOCK_DIR = ".setup-lock"
# A fresh install needs about the measured size on disk; a folder that already holds tools needs headroom only.
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
                f"The engine's setup lock is still at {lock_path(root)}. If no other setup is running, quit Hermes "
                "and move that folder aside (do not delete a lock a running setup holds), then install again. "
                "Finished parts are kept."
                if locked
                else "Finished parts are kept. Install again to continue."
            ),
        )
    return journal


_NETWORK = re.compile(
    r"ENOTFOUND|EAI_AGAIN|ECONNREFUSED|ECONNRESET|ETIMEDOUT|ENETUNREACH|EHOSTUNREACH|getaddrinfo|"
    r"certificate|CERT_|self.signed|socket hang up|network",
    re.IGNORECASE,
)
_SPACE = re.compile(r"ENOSPC|no space left", re.IGNORECASE)


def explain(code: str | None, error: str | None, root: Path) -> tuple[str | None, str | None]:
    """A failure's specific code and its next step, from the engine's own words. ``(code, None)`` when nothing
    more specific is known."""
    text = error or ""
    if code == "SETUP_LOCKED" or "Another setup owns" in text:
        return "SETUP_LOCKED", (
            f"Another setup holds {lock_path(root)} (a chat, another app such as Codex, or a run that stopped "
            "without cleaning up). Wait for it to finish. If nothing else is installing, quit Hermes and move that "
            "folder aside, then try again. Do not delete it while a setup runs."
        )
    if _SPACE.search(text):
        return "NO_SPACE", "The disk filled up. Free some space, then try again: finished parts are kept."
    if _NETWORK.search(text):
        return "NETWORK", (
            "A download source could not be reached. Check the internet connection (and any proxy or firewall), "
            "then try again: finished parts are kept, so it picks up where it stopped."
        )
    return code, None


def free_space(root: Path) -> dict:
    """Free bytes where the toolchain goes and what an install there needs. Cheap: one statvfs."""
    probe = Path(root)
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    try:
        free = shutil.disk_usage(probe).free
    except OSError:
        return {"free_bytes": None, "needed_bytes": None, "enough": True}
    needed = REPAIR_HEADROOM if Path(root).exists() else FRESH_HEADROOM
    return {"free_bytes": free, "needed_bytes": needed, "enough": free >= needed}


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

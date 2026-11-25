"""hermretro's published releases, for the page's update card: each stable release's version, date, address and what
it changed for users, read from GitHub's releases. The notes are the squash-merged pull request titles
(`type(scope): what it does`, .github/release.yml): `feat` lines are new, `fix` lines fixed, and the rest (chores,
docs, the development tools) are left out."""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.request

from ..system import paths

RELEASES_URL = "https://api.github.com/repos/ThePickle31/hermretro/releases?per_page=30"
CACHE_SECONDS = 600  # GitHub answers 60 unsigned requests an hour; every open page asks every 30 minutes
FETCH_TIMEOUT = 10.0

# `* feat(build): what it does by @someone in https://github.com/.../pull/123`
_NOTE = re.compile(r"^\s*[*-]\s+(feat|fix)(?:\(([^)]*)\))?!?:\s*(.+?)(?:\s+by\s+@\S+\s+in\s+\S+)?\s*$")
_KINDS = {"feat": "new", "fix": "fixed"}
_HIDDEN_SCOPES = {"dev", "ci", "test", "tests", "docs", "release"}
_STABLE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")

_lock = threading.Lock()
_cache: dict = {"at": 0.0, "answer": None}


def notes(body: str | None) -> list[dict]:
    """What a release changed for users, in its notes' order: `{"kind": "new" | "fixed", "text": ...}`."""
    found = []
    for line in (body or "").splitlines():
        match = _NOTE.match(line)
        if not match or (match.group(2) or "").strip().lower() in _HIDDEN_SCOPES:
            continue
        text = match.group(3).strip()
        found.append({"kind": _KINDS[match.group(1)], "text": text[:1].upper() + text[1:]})
    return found


def parse(rows: list) -> list[dict]:
    """GitHub's release rows → the stable, published ones, newest first."""
    out = []
    for row in rows if isinstance(rows, list) else ():
        if not isinstance(row, dict) or row.get("draft") or row.get("prerelease"):
            continue
        tag = str(row.get("tag_name") or "")
        if not _STABLE.match(tag):
            continue
        out.append(
            {
                "version": tag.removeprefix("v"),
                "date": row.get("published_at"),
                "url": row.get("html_url"),
                "notes": notes(row.get("body")),
            }
        )
    return sorted(
        out, key=lambda release: tuple(int(n) for n in _STABLE.match(release["version"]).groups()), reverse=True
    )


def _fetch(opener) -> list:
    request = urllib.request.Request(
        RELEASES_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": f"hermretro/{paths.PLUGIN_VERSION}"},
    )
    with opener(request, timeout=FETCH_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def latest(opener=urllib.request.urlopen, now=time.monotonic) -> dict:
    """`{"ok": True, "releases": [...]}` (parse), kept for CACHE_SECONDS; `{"ok": False, "error"}` when GitHub
    cannot be read (the page then shows the update without its notes). A failure is not kept. One request at a time:
    callers that arrive while it runs wait for it and share its answer."""
    with _lock:
        if _cache["answer"] is not None and now() - _cache["at"] < CACHE_SECONDS:
            return _cache["answer"]
        try:
            answer = {"ok": True, "releases": parse(_fetch(opener))}
        except Exception as error:
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}
        _cache.update(at=now(), answer=answer)
        return answer


def forget() -> None:
    """Drop the kept answer (tests)."""
    with _lock:
        _cache.update(at=0.0, answer=None)

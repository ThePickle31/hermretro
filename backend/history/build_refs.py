"""Build occurrences and their durable snapshot references."""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

_BUILD_REF_PREFIX = re.compile(r'^\{\s*"buildRef"\s*:\s*"([0-9a-f]{32})"\s*[,}]')
_SPILL_PREVIEW = re.compile(r"^Preview \(first [0-9]+ chars\):\n", re.MULTILINE)


def build_history(meta: dict, key: str) -> list:
    values = meta.get(key)
    return values if isinstance(values, list) else []


def public_snapshot(meta: dict, identifier: str, stored: str | None = None) -> dict:
    answer = {
        "id": identifier,
        "at": meta.get("at"),
        "builds": build_history(meta, "builds"),
        "files": meta.get("files"),
        "bytes": meta.get("bytes"),
        "reason": meta.get("reason"),
    }
    refs = build_history(meta, "buildRefs")
    if refs:
        answer["buildRefs"] = refs
    if stored:
        calls = [
            {"id": call["id"], "ref": call["ref"]}
            for call in build_history(meta, "buildCalls")
            if isinstance(call, dict)
            and call.get("stored") == stored
            and isinstance(call.get("id"), str)
            and isinstance(call.get("ref"), str)
            and call["ref"] in refs
        ]
        if calls:
            answer["buildCalls"] = calls
    if meta.get("from"):
        answer["from"] = meta["from"]
    if isinstance(meta.get("backup"), dict):
        answer["backup"] = meta["backup"]
    return answer


def record_build(meta: dict, at: int, build_ref: str | None, build_call: tuple[str, str] | None) -> None:
    # Older builds only have occurrence times. Keeping the new references separate prevents a legacy lookup
    # from picking the files of an unrelated new build whose time happens to fall in its turn.
    if build_ref:
        refs = build_history(meta, "buildRefs")
        if build_ref not in refs:
            meta["buildRefs"] = [*refs, build_ref]
        if build_call:
            stored, call_id = build_call
            call = {"stored": stored, "id": call_id, "ref": build_ref}
            calls = build_history(meta, "buildCalls")
            if call not in calls:
                meta["buildCalls"] = [*calls, call]
    else:
        meta["builds"] = [*build_history(meta, "builds"), at][-200:]


def _result_ref(content: str | None) -> str | None:
    # Hermes may store only a spill preview. The encoder puts the unique reference first
    # so both the result and that preview identify the occurrence without opening the spill file.
    if not isinstance(content, str):
        return None
    if content.startswith("<persisted-output>\n"):
        preview = _SPILL_PREVIEW.search(content)
        content = content[preview.end() :] if preview else ""
    match = _BUILD_REF_PREFIX.match(content)
    return match[1] if match else None


def confirm_build_calls(database: Path, stored: str, listed: list[dict]) -> None:
    """Add a result's exact Hermes timestamp to each corroborated call, dropping unconfirmed associations."""
    ids = {call["id"] for snapshot in listed for call in snapshot.get("buildCalls", [])}
    if not ids:
        return

    results = {}
    if database.is_file():
        try:
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=1.0)) as db:
                rows = db.execute(
                    """
                    WITH RECURSIVE lineage(id) AS (
                        SELECT ?
                        UNION
                        SELECT s.id FROM sessions AS s JOIN lineage AS l ON s.parent_session_id = l.id
                    )
                    SELECT m.tool_call_id, m.timestamp, m.tool_name, substr(m.content, 1, 8192)
                    FROM lineage AS l JOIN messages AS m ON m.session_id = l.id
                    WHERE m.role = 'tool' AND m.tool_call_id IN (SELECT value FROM json_each(?))
                    """,
                    (stored, json.dumps(sorted(ids))),
                )
                for call_id, timestamp, tool, content in rows:
                    if not isinstance(timestamp, (float, int)) or not 0 < timestamp < float("inf"):
                        continue
                    ref = _result_ref(content) if tool in {"chromatic_rom_build", "tool_call"} else None
                    key = (call_id, timestamp)
                    # Rotated segments can contain copies of a row. Conflicting bodies at
                    # the same timestamp leave no way to tell which one the page received.
                    results[key] = ref if results.get(key, ref) == ref else None
        except sqlite3.Error:
            results.clear()  # older or unreadable stores still support references in tool results

    confirmed = {}
    for (call_id, timestamp), ref in results.items():
        if ref:
            confirmed.setdefault((call_id, ref), []).append(timestamp)
    for snapshot in listed:
        calls = [
            {**call, "timestamp": timestamp}
            for call in snapshot.pop("buildCalls", [])
            for timestamp in confirmed.get((call["id"], call["ref"]), [])
        ]
        if calls:
            snapshot["buildCalls"] = calls

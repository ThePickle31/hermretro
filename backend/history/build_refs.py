"""Build occurrences and their durable snapshot references."""

from __future__ import annotations


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

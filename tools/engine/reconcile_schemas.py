#!/usr/bin/env python3
"""B00 / A01: compare the live engine's tool contracts with the pinned baseline.

Starts one private engine process, enumerates every tool, and diffs name,
description, inputSchema, outputSchema and annotations against the pinned file.
Exits non-zero on any missing, extra, duplicate or altered contract.

    python tools/engine/reconcile_schemas.py engine/pins/1.0.34/tools.json [report.json]
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_dev import EngineProcess, dev_engine_root, paths  # noqa: E402

FIELDS = ("description", "inputSchema", "outputSchema", "annotations", "title")


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        return 2
    pinned_path = Path(sys.argv[1])
    pinned_doc = json.loads(pinned_path.read_text())
    pinned = pinned_doc["tools"]
    with EngineProcess(
        dev_engine_root(), node=paths.find_node()["path"], client_name="chromatic-studio-baseline"
    ) as engine:
        live, pages = engine.list_tools()
        server_info, ready = engine.server_info, engine.ready_seconds

    pinned_names = [t["name"] for t in pinned]
    live_names = [t["name"] for t in live]
    pinned_by = {t["name"]: t for t in pinned}
    live_by = {t["name"]: t for t in live}
    altered = {}
    for name in sorted(set(pinned_by) & set(live_by)):
        fields = [f for f in FIELDS if pinned_by[name].get(f) != live_by[name].get(f)]
        extra_keys = sorted(set(pinned_by[name]) ^ set(live_by[name]))
        if fields or extra_keys:
            altered[name] = {"fields": fields, "key_difference": extra_keys}
    report = {
        "pinned_file": pinned_path.as_posix(),
        "pinned_file_sha256": hashlib.sha256(pinned_path.read_bytes()).hexdigest(),
        "pinned_tools_canonical_sha256": canonical_hash(pinned),
        "live_tools_canonical_sha256": canonical_hash(live),
        "live_server_info": server_info,
        "pinned_server_info": pinned_doc.get("initialize", {}).get("serverInfo"),
        "engine_ready_seconds": round(ready, 3) if ready else None,
        "pages": pages,
        "pinned_count": len(pinned_names),
        "live_count": len(live_names),
        "live_unique": len(set(live_names)),
        "duplicates": sorted({n for n in live_names if live_names.count(n) > 1}),
        "missing_from_live": sorted(set(pinned_names) - set(live_names)),
        "extra_in_live": sorted(set(live_names) - set(pinned_names)),
        "order_identical": pinned_names == live_names,
        "altered": altered,
    }
    report["passed"] = (
        not report["duplicates"]
        and not report["missing_from_live"]
        and not report["extra_in_live"]
        and not altered
        and report["live_server_info"] == report["pinned_server_info"]
    )
    text = json.dumps(report, indent=2)
    print(text)
    if len(sys.argv) == 3:
        Path(sys.argv[2]).write_text(text + "\n")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

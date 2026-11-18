#!/usr/bin/env python3
"""B00: record or verify a reproducible manifest of the audited engine package.

Records relative path, size, mode and SHA-256 for every file. It copies nothing:
the manifest identifies the baseline without redistributing it.

    python tools/engine/manifest.py write  engine/pins/1.0.34/manifest.json
    python tools/engine/manifest.py verify engine/pins/1.0.34/manifest.json
"""

from __future__ import annotations

import hashlib
import json
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_dev import dev_engine_root  # noqa: E402 - the repository root goes on sys.path first


def scan(root: Path) -> list[dict]:
    entries = []
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        rel = path.relative_to(root).as_posix()
        if stat.S_ISLNK(info.st_mode):
            entries.append({"path": rel, "type": "symlink", "target": str(path.readlink())})
        elif stat.S_ISREG(info.st_mode):
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(1 << 20), b""):
                    digest.update(block)
            entries.append(
                {
                    "path": rel,
                    "type": "file",
                    "size": info.st_size,
                    "mode": oct(stat.S_IMODE(info.st_mode)),
                    "sha256": digest.hexdigest(),
                }
            )
    return entries


def aggregate(entries: list[dict]) -> str:
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def build(root: Path) -> dict:
    entries = scan(root)
    package = json.loads((root / "package.json").read_text())
    files = [e for e in entries if e["type"] == "file"]
    suffixes: dict[str, int] = {}
    for entry in files:
        suffix = Path(entry["path"]).suffix or "(none)"
        suffixes[suffix] = suffixes.get(suffix, 0) + 1
    return {
        "manifest_schema": 1,
        "package_name": package.get("name"),
        "package_version": package.get("version"),
        "distribution_directory_name": root.name,
        "file_count": len(files),
        "symlink_count": len(entries) - len(files),
        "total_bytes": sum(e["size"] for e in files),
        "suffix_counts": dict(sorted(suffixes.items(), key=lambda kv: (-kv[1], kv[0]))),
        "aggregate_sha256": aggregate(entries),
        "entries": entries,
    }


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in ("write", "verify"):
        print(__doc__)
        return 2
    target = Path(sys.argv[2])
    current = build(dev_engine_root())
    if sys.argv[1] == "write":
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(current, indent=1) + "\n")
        print(json.dumps({k: v for k, v in current.items() if k != "entries"}, indent=2))
        return 0
    recorded = json.loads(target.read_text())
    old = {e["path"]: e for e in recorded["entries"]}
    new = {e["path"]: e for e in current["entries"]}
    report = {
        "matches": recorded["aggregate_sha256"] == current["aggregate_sha256"],
        "recorded_aggregate": recorded["aggregate_sha256"],
        "current_aggregate": current["aggregate_sha256"],
        "missing": sorted(set(old) - set(new)),
        "added": sorted(set(new) - set(old)),
        "changed": sorted(p for p in set(old) & set(new) if old[p] != new[p]),
    }
    print(json.dumps(report, indent=2))
    return 0 if report["matches"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""The page's own toolchain install: what gets downloaded, and how far the install has got.

The broker runs the engine's ``toolchain_prepare`` itself (no chat, no model) when the desktop page
asks; this module describes the downloads beforehand and reads the engine's own run record while it
works. Stdlib only; no Hermes imports.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..system import host as host_os

# What the engine's managed setup fetches for ["build", "emulator"]. Versions are the pins in
# engine/scripts/dependency-catalog.mjs (tests/backend/setup/test_onboarding.py keeps them in
# step). Sizes were measured on linux-x64; other platforms differ a little, so the page shows them
# as approximate there.
MEASURED_ON = "linux-x64"
MANIFEST = (
    {
        "id": "gbdk",
        "component": "gbdk",
        "name": "GBDK compiler",
        "version": "4.5.0",
        "source": "github.com/gbdk-2020/gbdk-2020",
        "bytes": 6_870_728,
        "purpose": "Compiles C for the Game Boy CPU",
    },
    {
        "id": "gbstudio",
        "component": "cli",
        "name": "GB Studio CLI",
        "version": "4.3.2",
        "source": "github.com/chrismaltby/gb-studio",
        "bytes": 18_130_254,
        "purpose": "Builds your game into a ROM",
    },
    {
        "id": "gbvm",
        "component": "cli",
        "name": "GBVM",
        "version": "bd6f41c",
        "source": "github.com/chrismaltby/gbvm",
        "bytes": 3_995_554,
        "purpose": "GB Studio's runtime, built into every ROM",
    },
    {
        "id": "packages",
        "component": "cli",
        "name": "GB Studio packages",
        "version": "yarn 4.4.1",
        "source": "registry.npmjs.org",
        "bytes": 551_000_000,
        "approx": True,
        "purpose": "The libraries GB Studio needs",
    },
    {
        "id": "uv",
        "component": "uv",
        "name": "uv",
        "version": "0.12.6",
        "source": "github.com/astral-sh/uv",
        "bytes": 20_274_889,
        "purpose": "Installs the Python parts",
    },
    {
        "id": "emulator",
        "component": "emulator",
        "name": "Python, PyBoy and Pillow",
        "version": "3.13.12 · 2.7.0 · 12.3.0",
        "source": "python-build-standalone · pypi.org",
        "bytes": 108_000_000,
        "approx": True,
        "purpose": "The emulator Hermes playtests with",
    },
)
COMPONENTS = ("gbdk", "cli", "uv", "emulator")  # the engine's install order
DISK_BYTES = 2_300_000_000  # measured on linux-x64 after a full install

DONE = frozenset({"prepared", "reused", "not-needed"})
RUNNING = frozenset({"checking", "installing"})
FAILED = frozenset({"failed", "blocked", "cancelled", "not-run"})

# Where the engine writes what it downloads (archives, then package caches).
_DOWNLOAD_DIRS = ("downloads", "cache")


def host_target() -> str:
    return f"{host_os.system_name()}-{host_os.native_arch()}"


def manifest() -> dict:
    exact = host_target() == MEASURED_ON
    items = [{**item, "approx": bool(item.get("approx")) or not exact} for item in MANIFEST]
    return {
        "items": items,
        "bytes": sum(item["bytes"] for item in MANIFEST),
        "disk_bytes": DISK_BYTES,
        "measured_on": MEASURED_ON,
        "exact": exact,
    }


def download_bytes(root: Path) -> int:
    """Bytes under a toolchain root's ``downloads/`` and ``cache/`` only (what an install adds while it runs; the
    whole folder is ``provision.folder_bytes``). Cheap enough to call every poll (a few thousand files)."""
    total = 0
    stack = [root / name for name in _DOWNLOAD_DIRS]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def _checks(component: dict) -> list[dict]:
    """The checksum lines a finished component proves: archive name and its verified SHA-256."""
    provenance = component.get("provenance")
    if not isinstance(provenance, dict):
        return []
    archives = provenance.get("archives")
    if not isinstance(archives, list):
        archives = [provenance]
    found = []
    for archive in archives:
        if isinstance(archive, dict) and isinstance(archive.get("sha256"), str):
            found.append(
                {
                    "file": str(archive.get("archive") or archive.get("source") or component.get("id")),
                    "sha256": archive["sha256"],
                    "reused": bool(archive.get("cacheReused")),
                }
            )
    if provenance.get("pythonExecutableSha256"):
        found.append(
            {
                "file": f"python {provenance.get('pythonVersion') or ''}".strip(),
                "sha256": provenance["pythonExecutableSha256"],
                "reused": False,
            }
        )
    if provenance.get("requirementsSha256"):
        packages = provenance.get("resolvedPackages")
        count = len(packages) if isinstance(packages, list) else 0
        found.append(
            {
                "file": f"{count} pinned PyPI packages" if count else "PyPI requirements",
                "sha256": provenance["requirementsSha256"],
                "reused": False,
            }
        )
    return found


def read_run(root: Path, run_id: str | None = None, since: float | None = None) -> dict | None:
    """The engine's record of the current (or last) setup run, reduced to what the page shows."""
    try:
        path = root / "last-run.json"
        if since is not None and path.stat().st_mtime < since - 2:
            return None  # a run from before this install started
        run = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(run, dict) or (run_id and run.get("runId") != run_id):
        return None
    components = {}
    for item in run.get("components") or []:
        if not isinstance(item, dict) or item.get("id") not in COMPONENTS:
            continue
        raw = str(item.get("status") or "")
        state = "done" if raw in DONE else "running" if raw in RUNNING else "failed" if raw in FAILED else "pending"
        error = item.get("error")
        if isinstance(error, dict):
            error = error.get("message") or error.get("code")
        components[item["id"]] = {
            "state": state,
            "status": raw,
            "version": item.get("version"),
            "reused": raw in ("reused", "not-needed"),
            "error": str(error or item.get("reason") or "")[:400] or None,
            "checks": _checks(item),
        }
    return {"run_id": run.get("runId"), "status": run.get("status"), "components": components}


def progress(state: dict, root: Path) -> dict:
    """Merge the broker's install state with the engine's run record and bytes on disk."""
    answer = {**state}
    started = state.get("started_at")
    run = read_run(root, since=started) if started else None
    answer["run"] = run
    sizes = {name: 0 for name in COMPONENTS}
    for item in MANIFEST:
        sizes[item["component"]] += item["bytes"]
    total = sum(sizes.values())
    grown = max(0, download_bytes(root) - int(state.get("baseline_bytes") or 0)) if started else 0
    answer["downloaded_bytes"] = grown
    components = (run or {}).get("components") or {}
    finished = sum(sizes[name] for name in COMPONENTS if components.get(name, {}).get("state") == "done")
    running = next((name for name in COMPONENTS if components.get(name, {}).get("state") == "running"), None)
    partial = min(sizes[running], max(0, grown - finished)) if running else 0
    fraction = 1.0 if state.get("state") == "done" else min(0.99, (finished + partial) / total) if total else 0.0
    answer["fraction"] = round(fraction, 4)
    answer["current"] = running
    return answer

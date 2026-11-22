"""Keeping the sandbox on current code: the checkout up to date with `dev` (all development lands there), the
sandbox's gateway restarted when the backend or Hermes changed, and the snapshots seeded again when what made them
changed.

Standard library only; development only; Linux and macOS.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

TOP = Path(__file__).resolve().parents[2]
DEV = "dev"
# What the sandbox's gateway runs (a change means a restart) and what the seeded snapshots were made by (a change
# means seeding again). Page changes need neither: the page reloads.
BACKEND = ("__init__.py", "plugin.yaml", "backend", "engine/pins")
SEED_INPUTS = (*BACKEND, "tools/dev/scripts")


def git(*args: str, cwd: Path = TOP) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=120, check=False)


def sync_checkout(top: Path = TOP) -> bool:
    """Bring the checkout up to `origin/dev` when it is the `dev` branch with nothing of its own (a fast-forward
    only), or say how far behind a feature branch is. True when the checkout moved."""
    if git("fetch", "--quiet", "origin", DEV, cwd=top).returncode:
        print("could not reach origin to check dev; the sandbox runs this checkout as it is")
        return False
    behind = int(git("rev-list", "--count", f"HEAD..origin/{DEV}", cwd=top).stdout.strip() or 0)
    if not behind:
        return False
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=top).stdout.strip()
    if branch != DEV:
        print(f"{branch} is {behind} commits behind dev; the sandbox runs it as it is\nFIX: git rebase origin/{DEV}")
        return False
    if git("status", "--porcelain", "--untracked-files=no", cwd=top).stdout.strip():
        print(f"dev is {behind} commits behind origin/dev and has local changes, so it was not updated")
        return False
    merged = git("merge", "--ff-only", "--quiet", f"origin/{DEV}", cwd=top)
    if merged.returncode:
        print(f"dev could not be fast-forwarded to origin/dev: {merged.stderr.strip()}")
        return False
    print(f"this checkout is now at origin/dev ({git('rev-parse', '--short', 'HEAD', cwd=top).stdout.strip()})")
    return True


def stamp(paths: tuple[str, ...], desktop: Path) -> str:
    """A hash of the files under ``paths`` (committed or not) and of the Hermes the sandbox runs."""
    digest = hashlib.sha256(git("rev-parse", "HEAD", cwd=desktop.parents[1]).stdout.encode())
    for part in paths:
        root = TOP / part
        for file in sorted([root] if root.is_file() else (item for item in root.rglob("*") if item.is_file())):
            if "__pycache__" not in file.parts:
                digest.update(str(file.relative_to(TOP)).encode() + b"\0" + file.read_bytes())
    return digest.hexdigest()

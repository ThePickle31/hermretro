"""python tools/dev remote HOST [CHECK ...]: this checkout's HEAD checked on another machine over ssh (by default the
unit tests), for a change that has to hold on a system this one is not (macOS from Linux, or the other way).

The commit is pushed into one checkout on the host (`~/.cache/hermretro-dev/checkout`, made the first time), which is
set to it exactly, keeping only its git-ignored tools (`.dev/`, `node_modules/`). Then `python3 tools/dev setup` and
`python3 tools/check.py CHECK ...` run there in the user's login shell, which finds the host's own Python and Node.
Uncommitted changes stay here: commit first. One run at a time per host.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

FOLDER = ".cache/hermretro-dev/checkout"  # from the host's home folder, where ssh and git's ssh paths start
BRANCH = "remote-check"


def host_script(checks: list[str]) -> str:
    """What runs on the host, from its home folder."""
    return " && ".join(
        [
            f"cd {FOLDER}",
            f"git checkout -q -f --detach {BRANCH}",
            "git clean -q -f -d -x -e .dev -e node_modules",
            "python3 tools/dev setup",
            shlex.join(["python3", "tools/check.py", *checks]),
        ]
    )


def run(top: Path, host: str, checks: list[str]) -> int:
    if subprocess.run(["git", "status", "--porcelain"], cwd=top, capture_output=True, text=True).stdout.strip():
        print("note: uncommitted changes stay here; the host checks HEAD", file=sys.stderr)
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=top, capture_output=True, text=True)
    for step in (
        ["ssh", host, f"git init -q {FOLDER}"],
        ["git", "push", "-q", "-f", "--no-verify", f"{host}:{FOLDER}", f"HEAD:refs/heads/{BRANCH}"],
    ):
        if subprocess.run(step, cwd=top).returncode:
            print(f"{shlex.join(step)} failed (above)\nFIX: check that `ssh {host}` works", file=sys.stderr)
            return 1
    print(f"{host}: {shlex.join(['tools/check.py', *checks])} on {head.stdout.strip()}", flush=True)
    # A login, interactive shell: the one that sets up PATH (Homebrew, nvm) as the user's terminal does.
    return subprocess.run(["ssh", host, f'exec "$SHELL" -lic {shlex.quote(host_script(checks))}']).returncode

"""python tools/dev remote HOST [CHECK ...]: this checkout's HEAD checked on another machine over ssh (by default the
unit tests), for a change that has to hold on a system this one is not (macOS from Linux, or the other way).

The commit is pushed into one checkout on the host (`~/.cache/hermretro-dev/checkout`, made and marked as this tool's
the first time: a link or a folder it did not make there is refused, never overwritten). Holding a
lock beside it (`checkout.lock`), so a second run waits for the first, the host sets that checkout to exactly this
commit, keeping only its git-ignored tools (`.dev/`, `node_modules/`), then runs `python3 tools/dev setup` and
`python3 tools/check.py CHECK ...` in the user's login shell, which finds the host's own Python and Node.
Uncommitted changes stay here: commit first.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

FOLDER = ".cache/hermretro-dev/checkout"  # from the host's home folder, where ssh and git's ssh paths start
LOCK = f"{FOLDER}.lock"
BRANCH = "remote-check"
MARK = "hermretro.remotecheck"  # in the checkout's own git config: the folder is this tool's
# Makes the checkout, or proves the one there is this tool's, before anything in it is overwritten.
PREPARE = (
    f'if [ -L {FOLDER} ]; then echo "{FOLDER} is a link; tools/dev remote uses only a folder of its own"; exit 3; fi; '
    f'if [ -e {FOLDER} ] && [ "$(git config --file {FOLDER}/.git/config --get {MARK})" != true ]; then '
    f'echo "{FOLDER} was not made by tools/dev remote; move it away"; exit 3; fi; '
    f"git init -q {FOLDER} && git config --file {FOLDER}/.git/config {MARK} true"
)
# Runs the rest of its arguments while it holds the lock (an exclusive flock, let go when it exits).
HOLD = (
    "import fcntl, subprocess, sys\n"
    "lock = open(sys.argv[1], 'w')\n"
    "try:\n"
    "    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
    "except BlockingIOError:\n"
    "    print('waiting for the run before this one on this host', flush=True)\n"
    "    fcntl.flock(lock, fcntl.LOCK_EX)\n"
    "sys.exit(subprocess.call(sys.argv[2:]))\n"
)


def host_script(commit: str, checks: list[str]) -> str:
    """What runs on the host, from its home folder, with the lock held."""
    steps = " && ".join(
        [
            f"cd {FOLDER}",
            f"git checkout -q -f --detach {commit}",
            "git clean -q -f -d -x -e .dev -e node_modules",
            "python3 tools/dev setup",
            shlex.join(["python3", "tools/check.py", *checks]),
        ]
    )
    return shlex.join(["python3", "-c", HOLD, LOCK, "sh", "-c", steps])


def run(top: Path, host: str, checks: list[str]) -> int:
    if host.startswith("-"):
        print(f"{host} is not a host name (ssh would read it as an option)\nFIX: name the host", file=sys.stderr)
        return 2
    if subprocess.run(["git", "status", "--porcelain"], cwd=top, capture_output=True, text=True).stdout.strip():
        print("note: uncommitted changes stay here; the host checks HEAD", file=sys.stderr)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=top, capture_output=True, text=True).stdout.strip()
    for step in (
        ["ssh", host, PREPARE],
        ["git", "push", "-q", "-f", "--no-verify", f"{host}:{FOLDER}", f"{commit}:refs/heads/{BRANCH}"],
    ):
        if subprocess.run(step, cwd=top).returncode:
            print(
                f"{step[0]} {step[1]} failed (above)\nFIX: what it says, or check that `ssh {host}` works",
                file=sys.stderr,
            )
            return 1
    print(f"{host}: {shlex.join(['tools/check.py', *checks])} on {commit[:10]}", flush=True)
    # A login, interactive shell: the one that sets up PATH (Homebrew, nvm) as the user's terminal does.
    return subprocess.run(["ssh", host, f'exec "$SHELL" -lic {shlex.quote(host_script(commit, checks))}']).returncode

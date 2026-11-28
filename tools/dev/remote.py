"""python tools/dev remote HOST: the unit tests of this checkout's HEAD on another machine over ssh, for a change that
has to hold on a system this one is not (macOS from Linux, or the other way). Only the unit tests: each of their
processes gets an empty temporary home and TMPDIR, so the host's own hermretro is never read or written (the acceptance
run would use the host's installed toolchain and its prepared engines).

The commit is pushed into one checkout on the host (`~/.cache/hermretro-dev/checkout`, made and marked as this tool's
the first time: a link or a folder it did not make there is refused, never overwritten). Holding a
lock beside it (`checkout.lock`), so a second run waits for the first, the host sets that checkout to exactly this
commit, keeping only its git-ignored tools (`.dev/`, `node_modules/`), then runs `python3 tools/dev setup` and
`python3 tools/check.py unit` in the user's login shell, which finds the host's own Python and Node.
Uncommitted changes stay here: commit first.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
import uuid
from pathlib import Path

FOLDER = ".cache/hermretro-dev/checkout"  # from the host's home folder, where ssh and git's ssh paths start
LOCK = f"{FOLDER}.lock"
REFS = "refs/remote-check"  # one ref per run, so runs pushing at once never race for one ref
MARK = "hermretro.remotecheck"  # in the checkout's own git config: the folder is this tool's
# Proves the checkout there is this tool's, or makes it when there is none, before anything in it is overwritten. A
# checkout already made is only read, so runs started at once never write its config together.
PREPARE = (
    f'if [ -L {FOLDER} ]; then echo "{FOLDER} is a link; tools/dev remote uses only a folder of its own"; exit 3; fi; '
    f"if [ -e {FOLDER} ]; then "
    f'[ "$(git config --file {FOLDER}/.git/config --get {MARK})" = true ] || '
    f'{{ echo "{FOLDER} was not made by tools/dev remote; move it away"; exit 3; }}; '
    f"else git init -q {FOLDER} && git config --file {FOLDER}/.git/config {MARK} true; fi"
)
# Runs the rest of its arguments while it holds the lock (an exclusive flock, let go when it exits).
HOLD = (
    "import fcntl, os, subprocess, sys\n"
    "try:\n"
    "    lock = os.open(sys.argv[1], os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)\n"
    "except OSError as error:\n"
    "    sys.exit(f'{sys.argv[1]}: {error.strerror}; tools/dev remote uses only a lock of its own, never a link')\n"
    "try:\n"
    "    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
    "except BlockingIOError:\n"
    "    print('waiting for the run before this one on this host', flush=True)\n"
    "    fcntl.flock(lock, fcntl.LOCK_EX)\n"
    "sys.exit(subprocess.call(sys.argv[2:]))\n"
)


def host_script(commit: str, ref: str) -> str:
    """What runs on the host, from its home folder, with the lock held. Once checked out, the commit is held by
    HEAD, and this run's ref goes."""
    steps = " && ".join(
        [
            f"cd {FOLDER}",
            f"git checkout -q -f --detach {commit}",
            f"git update-ref -d {ref}",
            "git clean -q -f -d -x -e .dev -e node_modules",
            "python3 tools/dev setup",
            "python3 tools/check.py unit",
        ]
    )
    return shlex.join(["python3", "-c", HOLD, LOCK, "sh", "-c", steps])


def run(top: Path, host: str) -> int:
    if host.startswith("-"):
        print(f"{host} is not a host name (ssh would read it as an option)\nFIX: name the host", file=sys.stderr)
        return 2
    if subprocess.run(["git", "status", "--porcelain"], cwd=top, capture_output=True, text=True).stdout.strip():
        print("note: uncommitted changes stay here; the host checks HEAD", file=sys.stderr)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=top, capture_output=True, text=True).stdout.strip()
    ref = f"{REFS}/{uuid.uuid4().hex}"
    for step in (
        ["ssh", host, shlex.join(["sh", "-c", PREPARE])],  # POSIX sh, whatever the account's shell
        ["git", "push", "-q", "-f", "--no-verify", f"{host}:{FOLDER}", f"{commit}:{ref}"],
    ):
        if subprocess.run(step, cwd=top).returncode:
            print(
                f"{step[0]} {step[1]} failed (above)\nFIX: what it says, or check that `ssh {host}` works",
                file=sys.stderr,
            )
            return 1
    print(f"{host}: tools/check.py unit on {commit[:10]}", flush=True)
    # A login, interactive shell: the one that sets up PATH (Homebrew, nvm) as the user's terminal does.
    return subprocess.run(["ssh", host, f'exec "$SHELL" -lic {shlex.quote(host_script(commit, ref))}']).returncode

"""Set up the pinned Python development tools (ruff) in .dev/py. Stdlib only; development only.

    python tools/py/setup.py           create .dev/py (a venv of this Python) and install tools/py/requirements.txt
    python tools/py/setup.py --force   start again from an empty .dev/py

pip installs with --require-hashes --only-binary=:all:, so only the exact published wheels whose SHA-256 is
listed in requirements.txt can land, and nothing is built or run at install time. Running it again is quick:
it does nothing while requirements.txt is unchanged and the tools still start. .dev/ is git-ignored.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = ROOT / "tools" / "py" / "requirements.txt"
VENV = ROOT / ".dev" / "py"
STAMP = VENV / "requirements.sha256"
RUFF = VENV / "bin" / "ruff"


def wanted() -> str:
    return hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()


def ready() -> bool:
    """The venv holds exactly what requirements.txt pins, and ruff starts."""
    if not STAMP.is_file() or STAMP.read_text().strip() != wanted() or not RUFF.is_file():
        return False
    try:
        return subprocess.run([str(RUFF), "--version"], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# What a failed ensurepip/venv subprocess says, mapped to its cause; anything else gets the generic advice.
MISSING_VENV = ("no module named ensurepip", "ensurepip is not available", "no module named venv")
DISK_FULL = ("no space left on device", "enospc", "disk quota exceeded")
NO_PERMISSION = ("permission denied", "operation not permitted", "read-only file system")


def said(error: BaseException) -> str:
    """What the failed subprocess printed (stdout and stderr; venv captures ensurepip's into ``output``)."""
    if not isinstance(error, subprocess.CalledProcessError):
        return ""
    parts = []
    for stream in (error.output, error.stderr):
        if isinstance(stream, bytes):
            stream = stream.decode(errors="replace")
        if stream and stream not in parts:
            parts.append(stream)
    return "\n".join(part.strip() for part in parts)


def venv_fix(error: BaseException) -> str:
    """The FIX for a failed venv creation, from the error itself: only a missing venv/ensurepip is the package."""
    again = "then run python tools/py/setup.py again"
    code = getattr(error, "errno", None)
    text = said(error).lower()
    if code in (errno.ENOSPC, errno.EDQUOT) or any(words in text for words in DISK_FULL):
        return (
            f"the disk holding {VENV.parent} (or the temporary folder) is full: free space on that filesystem "
            f"(or put the checkout on another one), {again}"
        )
    if code in (errno.EACCES, errno.EPERM, errno.EROFS) or any(words in text for words in NO_PERMISSION):
        where = getattr(error, "filename", None) or VENV.parent
        return f"this user cannot write {where}: check the permissions on that path (ls -ld {where}), {again}"
    if any(words in text or words in str(error).lower() for words in MISSING_VENV):
        return f"install your Python's venv module (on Debian and Ubuntu: the python3-venv package), {again}"
    return f"read the error above (it names the path and the cause), fix that, {again}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").strip().splitlines()[0])
    parser.add_argument("--force", action="store_true", help="remove .dev/py and install again")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):  # noqa: UP036 — an older python3 may start this script
        print("hermretro needs Python 3.11 or newer for development\nFIX: run this with python3.11 or newer")
        return 1
    if not args.force and ready():
        print(f"ok: {VENV.relative_to(ROOT)} is up to date")
        return 0
    if VENV.exists():
        shutil.rmtree(VENV)
    print(f"creating {VENV.relative_to(ROOT)} with {sys.executable}", flush=True)
    try:
        venv.EnvBuilder(with_pip=True, clear=True).create(VENV)
    except (OSError, subprocess.CalledProcessError) as error:
        output = said(error)
        shown = f"\n{output}" if output else ""
        print(f"could not create the venv: {error}{shown}\nFIX: {venv_fix(error)}")
        return 1
    python = VENV / "bin" / "python"
    result = subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-input",
            "--require-hashes",
            "--only-binary=:all:",
            "-r",
            str(REQUIREMENTS),
        ]
    )
    if result.returncode:
        print(
            "pip could not install the pinned tools\nFIX: read pip's message above (network, or no wheel for "
            "this system); then run python tools/py/setup.py --force"
        )
        return 1
    STAMP.write_text(wanted() + "\n")
    if not ready():
        print(f"{RUFF.relative_to(ROOT)} does not start\nFIX: python tools/py/setup.py --force")
        return 1
    version = subprocess.run([str(RUFF), "--version"], capture_output=True, text=True).stdout.strip()
    print(f"ok: {version} in {VENV.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

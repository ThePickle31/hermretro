"""A clean install of this checkout into a throwaway Hermes home, the way a user installs hermretro.

    python tools/ci/clean_install_check.py                       # with the `hermes` on PATH
    python tools/ci/clean_install_check.py --hermes-python /path/to/hermes/runtime/python
    python tools/ci/clean_install_check.py --update-from <tag>  # an installed release updates to this commit
    python tools/ci/clean_install_check.py --update-from          # from the newest release on origin/main

Creates the `hermretro` profile, installs the committed checkout into it and into the default profile
(Hermes's install scanner runs on both; a caution or a block fails here, because nothing can confirm), then
checks the agent side registers only in `hermretro`. Needs no model, no network beyond Git and touches no
real Hermes home (HOME is a temp folder too). Every failure ends with a "FIX:" line.

--update-from: see tools/ci/update_check.py.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").strip().splitlines()[0])
    parser.add_argument("--hermes-python", help="a Python that can import hermes_cli (default: `hermes` on PATH)")
    parser.add_argument(
        "--update-from",
        nargs="?",
        const="latest-release",  # the newest v* release tag on origin/main
        metavar="REF",
        help="install this release (tag or commit) first, then update to the checkout's HEAD "
        "(no REF: the newest v* release tag on origin/main)",
    )
    parser.add_argument("--inside", nargs=2, metavar=("PHASE", "OUT"), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.inside:  # run by Hermes's own Python inside the throwaway home
        return _update_check().inside(*args.inside)
    hermes = [args.hermes_python, "-I", "-m", "hermes_cli.main"] if args.hermes_python else ["hermes"]

    # Never under ~/.hermes: Hermes treats a home inside its real root as the real root itself.
    real_root = Path.home() / ".hermes"
    with tempfile.TemporaryDirectory(prefix="hermretro-clean-install-", dir="/tmp") as tmp:
        root = Path(tmp).resolve() / "hermes-home"
        if root.is_relative_to(real_root.resolve()):
            print(f"refusing to use {root}: it is inside the real Hermes home", file=sys.stderr)
            return 1
        root.mkdir()
        (Path(tmp) / "home").mkdir()
        if args.update_from:
            return _update_check().update(args, hermes, Path(tmp).resolve(), root)
        studio = root / "profiles" / "hermretro"
        run = runner(hermes, Path(tmp), {"HERMRETRO_HOME": str(Path(tmp) / "hermretro")})

        source = f"file://{ROOT}"
        run(root, "profile", "create", "hermretro", "--no-alias", "--no-skills")
        for home in (studio, root):
            run(home, "plugins", "install", source, "--enable", "--yes-deps")
        problems = registers_only_in_studio(run, root, studio)
        if problems:
            print("\n".join(problems) + "\nFIX: check __init__.register and studio_profile.is_studio", file=sys.stderr)
            return 1
    print("ok: installs cleanly; the agent side registers only in the hermretro profile")
    return 0


def _update_check():
    sys.path.insert(0, str(Path(__file__).resolve().parent))  # python -I leaves the script's folder out
    import update_check

    return update_check


def environment(tmp: Path, home: Path, extra: dict | None = None) -> dict:
    # Nothing from a surrounding Hermes or hermretro session (profile pins, session ids, real home), and no
    # systemd unit id (a broker would ask systemd for a scope of its own).
    kept = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("HERMRETRO_", "HERMES_")) and key not in ("INVOCATION_ID", "PYTHONPATH")
    }
    return {**kept, "HOME": str(tmp / "home"), "HERMES_HOME": str(home), **(extra or {})}


def runner(hermes: list[str], tmp: Path, extra: dict | None = None, fix: str = ""):
    def run(home: Path, *command: str) -> str:
        done = subprocess.run(
            [*hermes, *command],
            env=environment(tmp, home, extra),
            cwd=tmp,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=600,
        )
        output = done.stdout + done.stderr
        print(f"$ hermes {' '.join(command)}  [{home.name}] -> {done.returncode}", flush=True)
        if done.returncode:
            raise SystemExit(
                output[-3000:] + f"\nFIX: `hermes {' '.join(command)}` failed in a clean Hermes home; "
                f"reproduce with python tools/ci/clean_install_check.py{fix}"
            )
        return output

    return run


def _lists_chromatic(listing: str) -> bool:  # a toolset row, not a mention in some message
    return any(re.match(r"^\W*(enabled|disabled)?\W*chromatic\b", line.strip()) for line in listing.splitlines())


def registers_only_in_studio(run, root: Path, studio: Path) -> list[str]:
    problems = []
    if not _lists_chromatic(run(studio, "tools", "list")):
        problems.append("the hermretro profile does not list the chromatic toolset")
    if _lists_chromatic(run(root, "tools", "list")):
        problems.append("the default profile lists the chromatic toolset (it must exist only in hermretro)")
    return problems


if __name__ == "__main__":
    sys.exit(main())

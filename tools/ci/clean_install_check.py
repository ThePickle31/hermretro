"""A clean install of this checkout into a throwaway Hermes home, the way a user installs hermretro.

    python tools/ci/clean_install_check.py                       # with the `hermes` on PATH
    python tools/ci/clean_install_check.py --hermes-python /path/to/hermes/runtime/python

Creates the `hermretro` profile, installs the committed checkout into it and into the default profile
(Hermes's install scanner runs on both; a caution or a block fails here, because nothing can confirm), then
checks the agent side registers only in `hermretro`. Needs no model, no network beyond Git and touches no
real Hermes home. Every failure ends with a "FIX:" line.
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
    args = parser.parse_args(argv)
    hermes = [args.hermes_python, "-I", "-m", "hermes_cli.main"] if args.hermes_python else ["hermes"]

    # Never under ~/.hermes: Hermes treats a home inside its real root as the real root itself.
    real_root = Path.home() / ".hermes"
    with tempfile.TemporaryDirectory(prefix="hermretro-clean-install-", dir="/tmp") as tmp:
        root = Path(tmp).resolve() / "hermes-home"
        if root.is_relative_to(real_root.resolve()):
            print(f"refusing to use {root}: it is inside the real Hermes home", file=sys.stderr)
            return 1
        root.mkdir()
        studio = root / "profiles" / "hermretro"

        def run(home: Path, *command: str) -> str:
            # Nothing from a surrounding Hermes or hermretro session (profile pins, session ids, real home).
            env = {**{k: v for k, v in os.environ.items() if not k.startswith(("HERMRETRO_", "HERMES_"))},
                   "HERMES_HOME": str(home), "HERMRETRO_HOME": str(Path(tmp) / "hermretro")}
            done = subprocess.run([*hermes, *command], env=env, cwd=tmp, stdin=subprocess.DEVNULL,
                                  capture_output=True, text=True, timeout=600)
            output = done.stdout + done.stderr
            print(f"$ hermes {' '.join(command)}  [{home.name}] -> {done.returncode}", flush=True)
            if done.returncode:
                raise SystemExit(output[-3000:] + f"\nFIX: `hermes {' '.join(command)}` failed in a clean Hermes home; "
                                 "reproduce with python tools/ci/clean_install_check.py")
            return output

        source = f"file://{ROOT}"
        run(root, "profile", "create", "hermretro", "--no-alias", "--no-skills")
        for home in (studio, root):
            run(home, "plugins", "install", source, "--enable", "--yes-deps")
        in_studio = run(studio, "tools", "list")
        in_default = run(root, "tools", "list")
        def lists_chromatic(listing: str) -> bool:  # a toolset row, not a mention in some message
            return any(re.match(r"^\W*(enabled|disabled)?\W*chromatic\b", line.strip()) for line in listing.splitlines())

        problems = []
        if not lists_chromatic(in_studio):
            problems.append("the hermretro profile does not list the chromatic toolset")
        if lists_chromatic(in_default):
            problems.append("the default profile lists the chromatic toolset (it must exist only in hermretro)")
        if problems:
            print("\n".join(problems) + "\nFIX: check __init__.register and studio_profile.is_studio", file=sys.stderr)
            return 1
    print("ok: installs cleanly; the agent side registers only in the hermretro profile")
    return 0


if __name__ == "__main__":
    sys.exit(main())

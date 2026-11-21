"""A clean install of this checkout into a throwaway Hermes home, the way a user installs hermretro.

    python tools/ci/clean_install_check.py                       # with the `hermes` on PATH
    python tools/ci/clean_install_check.py --hermes-python /path/to/hermes/runtime/python
    python tools/ci/clean_install_check.py --update-from <tag>  # an installed release updates to this commit
    python tools/ci/clean_install_check.py --update-from          # from the newest release on origin/main

As a user does: installs the committed checkout once, into the ordinary (default) profile (Hermes's install scanner
runs; a caution or a block fails here, because nothing can confirm), then onboards the way the page does, through
the throwaway home's real Hermes gateway (tools/ci/onboarding_check.py): Hermes's `profiles.create` makes the
`hermretro` profile and the plugin's own `studio_profile` RPC finishes it, linking that one install. Then
`hermes tools list` must show the chromatic toolset enabled in `hermretro` and absent from the default profile.
Needs no model, no credentials, no network beyond Git and touches no real Hermes home (HOME is a temp folder too).
Every failure ends with a "FIX:" line.

Its throwaway folder goes in HERMRETRO_CLEAN_INSTALL_TMP, else TMPDIR, else /tmp (`work_parent`): never inside the
real Hermes home, and short enough for the broker's socket path (a TMPDIR that is not is passed over; such a
HERMRETRO_CLEAN_INSTALL_TMP is refused).

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
    try:
        parent = work_parent(os.environ, real_root)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory(prefix=PREFIX, dir=str(parent)) as tmp:
        root = Path(tmp).resolve() / "hermes-home"
        if root.is_relative_to(real_root.resolve()):
            print(f"refusing to use {root}: it is inside the real Hermes home", file=sys.stderr)
            return 1
        root.mkdir()
        (Path(tmp) / "home").mkdir()
        if args.update_from:
            return _update_check().update(args, hermes, Path(tmp).resolve(), root)
        studio = root / "profiles" / "hermretro"
        onboarding = _onboarding_check()
        extra = {
            "HERMRETRO_HOME": str(Path(tmp) / "hermretro"),
            **onboarding.hermes_on_path(Path(tmp), args.hermes_python),
        }
        run = runner(hermes, Path(tmp), extra)

        run(root, "plugins", "install", f"file://{ROOT}", "--enable", "--yes-deps")  # once, in the ordinary profile
        problems = onboarding.onboard(
            args.hermes_python, Path(tmp).resolve(), root, environment(Path(tmp), root, extra)
        )
        if problems:  # the profile is not there to list: the onboarding's own finding is the one to read
            print("\n".join(problems), file=sys.stderr)
            return 1
        problems = registers_only_in_studio(run, root, studio)
        if problems:
            print("\n".join(problems) + "\nFIX: check __init__.register and studio_profile.is_studio", file=sys.stderr)
            return 1
    print(
        "ok: installs cleanly once; the page's onboarding on a real gateway makes the hermretro profile, which links "
        "that install, and the agent side registers only there"
    )
    return 0


PREFIX = "hermretro-clean-install-"
# What the throwaway folder (PREFIX + 8 random characters) holds below it, at its longest: the update check's broker
# socket, under the throwaway HOME (update_check.py leaves HERMRETRO_HOME unset).
SOCKET_BELOW = "/" + "/".join(("home", ".hermes", "hermretro", "run", "broker.sock"))
SOCKET_PATH_LIMIT = 100  # backend/system/paths.py SOCKET_PATH_LIMIT


def work_parent(env, real_root: Path) -> Path:
    """The folder the throwaway folder goes in: HERMRETRO_CLEAN_INSTALL_TMP, else TMPDIR, else /tmp. A
    HERMRETRO_CLEAN_INSTALL_TMP inside ``real_root`` or too long for the broker's socket path raises ValueError (with
    a FIX line); a TMPDIR like that is passed over."""
    for name in ("HERMRETRO_CLEAN_INSTALL_TMP", "TMPDIR"):
        value = env.get(name)
        if not value:
            continue
        folder = Path(value).expanduser().resolve()
        longest = len(os.fsencode(folder)) + 1 + len(PREFIX) + 8 + len(SOCKET_BELOW)
        inside = folder.is_relative_to(real_root.expanduser().resolve())
        if not inside and longest <= SOCKET_PATH_LIMIT:
            return folder
        if name == "TMPDIR":  # an agent's scratch TMPDIR is often both
            continue
        why = (
            f"it is inside the real Hermes home {real_root}"
            if inside
            else f"the broker's socket under it would be {longest} bytes (at most {SOCKET_PATH_LIMIT})"
        )
        raise ValueError(
            f"refusing {name}={value}: {why}\nFIX: point {name} at a short folder outside the Hermes home, such "
            "as $XDG_RUNTIME_DIR or /tmp, or unset it"
        )
    return Path("/tmp")


def _update_check():
    sys.path.insert(0, str(Path(__file__).resolve().parent))  # python -I leaves the script's folder out
    import update_check

    return update_check


def _onboarding_check():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import onboarding_check

    return onboarding_check


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


def _chromatic_rows(listing: str) -> list[str]:  # toolset rows, not a mention in some message
    return [
        line.strip()
        for line in listing.splitlines()
        if re.match(r"^\W*(enabled|disabled)?\W*chromatic\b", line.strip())
    ]


def _lists_chromatic(listing: str) -> bool:
    return bool(_chromatic_rows(listing))


def registers_only_in_studio(run, root: Path, studio: Path) -> list[str]:
    problems = []
    rows = _chromatic_rows(run(studio, "tools", "list"))
    for row in rows:
        print(f"  hermretro: {row}")
    if not rows:
        problems.append("the hermretro profile does not list the chromatic toolset")
    elif not any("enabled" in row and "disabled" not in row for row in rows):
        problems.append(f"the hermretro profile lists the chromatic toolset but not enabled: {rows}")
    if _lists_chromatic(run(root, "tools", "list")):
        problems.append("the default profile lists the chromatic toolset (it must exist only in hermretro)")
    return problems


if __name__ == "__main__":
    sys.exit(main())

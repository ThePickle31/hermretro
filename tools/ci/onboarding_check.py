"""The clean install's onboarding: what the page does after a user installs hermretro, through a real Hermes gateway.

Run by tools/ci/clean_install_check.py after its one install into the ordinary (default) profile. `onboard` runs
`inside` with Hermes's own Python in the throwaway home; that attaches to the home's gateway the way every Hermes
client does (`hermes_cli.gateway_client.connect_gateway`, which starts an unmanaged gateway that ends itself when
idle) and makes the page's calls on it, in the page's order (page/pages/setup/install/installer.js):
`plugin.hermretro.status`, Hermes's own `profiles.create` with the parameters that status names, the plugin's
`plugin.hermretro.studio_profile` (its real handler: links the install, runs the `hermes` config commands in the new
profile), `plugin.hermretro.status` again, and Hermes's `profiles.describe` of the new profile. `onboard` then
stops that gateway and judges the answers; the caller checks `hermes tools list` in both profiles.

No model, no credentials, no hardware, no toolchain download: `status` and `studio_profile` never start the
broker. Every problem ends with a "FIX:" line.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDIO = "hermretro"  # backend/setup/studio_profile.STUDIO_PROFILE
REPRODUCE = "reproduce with python tools/ci/clean_install_check.py"


def hermes_on_path(tmp: Path, hermes_python: str | None) -> dict:
    """With --hermes-python, a `hermes` first on PATH that runs that same Hermes: the plugin's studio_profile handler
    runs `hermes` from PATH (as on a user's machine, where the installer puts it there), and another Hermes found
    there would configure the profile instead of the one under test. Without it, `hermes` is already that Hermes."""
    if not hermes_python:
        return {}
    folder = tmp / "bin"
    folder.mkdir(exist_ok=True)
    launcher = folder / "hermes"
    launcher.write_text(f'#!/bin/sh\nexec {shlex.quote(hermes_python)} -I -m hermes_cli.main "$@"\n', encoding="utf-8")
    launcher.chmod(0o755)
    return {"PATH": f"{folder}{os.pathsep}{os.environ.get('PATH', '')}"}


def onboard(hermes_python: str | None, tmp: Path, root: Path, env: dict) -> list[str]:
    """Run the page's onboarding calls through the gateway of ``root`` and return what is wrong (empty: all good)."""
    out = tmp / "onboarding.json"
    script = str(Path(__file__).resolve())
    if hermes_python:
        command = [hermes_python, "-I", script]
    else:  # the `hermes` launcher runs only modules in its environment; cProfile is one that runs a script
        command = ["hermes", "--run-module", "cProfile", "-o", os.devnull, script]
    started = time.monotonic()
    try:
        done = subprocess.run(
            [*command, "--inside", str(out)],
            env=env,
            cwd=tmp,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=600,
        )
        code, output = done.returncode, done.stdout + done.stderr
    except subprocess.TimeoutExpired:
        code, output = "timed out after 600 s", ""
    finally:
        stopped = stop_gateway(root)
    print(
        f"$ page onboarding through the Hermes gateway  [{root.name}] -> {code} "
        f"({time.monotonic() - started:.0f} s; gateway {stopped})",
        flush=True,
    )
    found = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}
    problems = []
    if code or "fatal" in found or not found:
        problems.append(
            (found.get("fatal") or output[-3000:] or str(code))
            + f"\nFIX: the page's onboarding failed on a real Hermes gateway in a clean home; {REPRODUCE}"
        )
    else:
        problems += judge(found, root)
    if stopped.startswith("still running"):
        problems.append(f"the throwaway home's gateway is {stopped}\nFIX: stop it by hand (kill <pid>); {REPRODUCE}")
    return problems


def judge(found: dict, root: Path) -> list[str]:
    """What is wrong with the answers `inside` recorded (``found``) for the throwaway home ``root``."""
    problems = []
    studio = root / "profiles" / STUDIO

    def wrong(message: str, fix: str) -> None:
        problems.append(f"{message}\nFIX: {fix}; {REPRODUCE}")

    before = (found.get("before") or {}).get("profile") or {}
    if before.get("is_studio") or (before.get("studio") or {}).get("exists"):
        wrong(f"before onboarding the status RPC reported {before}", "describe() must report no studio profile yet")
    created = found.get("created") or {}
    if not created.get("ok") or Path(str(created.get("path"))).resolve() != studio.resolve():
        wrong(f"Hermes's profiles.create with the plugin's parameters answered {created}", "check create_params()")
    finished = found.get("finished") or {}
    if not finished.get("ok") or finished.get("plugin") != "linked":
        wrong(f"plugin.hermretro.studio_profile answered {finished}", "check studio_profile.finish")
    link = studio / "plugins" / STUDIO
    install = root / "plugins" / STUDIO
    if not link.is_symlink() or link.resolve() != install.resolve():
        wrong(
            f"{link} is not a link to the one install {install}",
            "the studio profile must link the install the user made, never copy or reinstall it",
        )
    after = ((found.get("after") or {}).get("profile") or {}).get("studio") or {}
    if not (after.get("exists") and after.get("installed") and after.get("ours")):
        wrong(f"after onboarding the status RPC reports the studio profile as {after}", "check describe() and finish")
    if not (studio / "SOUL.md").is_file() or not (studio / "workspace").is_dir():
        wrong(f"{studio} has no SOUL.md or workspace after onboarding", "check studio_profile.finish")
    chromatic = [row for row in found.get("toolsets") or [] if row.get("name") == "chromatic"]
    if found.get("toolsets") is not None and not (chromatic and chromatic[0].get("enabled")):
        wrong(
            f"the gateway's profiles.describe of {STUDIO} lists no enabled chromatic toolset: {chromatic}",
            "the plugin's tools must register in the studio profile (studio_profile.is_studio, __init__.register)",
        )
    elif chromatic and chromatic[0].get("tool_count") != len(declared_tools()):
        wrong(
            f"the gateway counts {chromatic[0].get('tool_count')} chromatic tools in {STUDIO}; plugin.yaml declares "
            f"{len(declared_tools())}",
            "__init__.register must add exactly plugin.yaml's provides_tools",
        )
    if chromatic:
        print(f"gateway profiles.describe {STUDIO}: chromatic {chromatic[0]}")
    elif "describe_error" in found:
        print(f"gateway profiles.describe {STUDIO} unavailable on this Hermes: {found['describe_error']}")
    return problems


def declared_tools(manifest: Path = ROOT / "plugin.yaml") -> list[str]:
    """plugin.yaml's provides_tools (a block list of plain names; read without a YAML library)."""
    names, inside_list = [], False
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if line.startswith("provides_tools:"):
            inside_list = True
        elif inside_list and re.match(r"^\s+-\s*", line):
            names.append(re.sub(r"^\s+-\s*", "", line).split("#")[0].strip().strip("\"'"))
        elif inside_list and line.strip() and not line.startswith((" ", "#")):
            break
    return names


def stop_gateway(root: Path) -> str:
    """Stop the gateway the onboarding started for ``root``, by the pid it recorded (only when that record names
    ``root``: never another home's gateway). SIGTERM, then SIGKILL after 20 s. Says what happened."""
    try:
        record = json.loads((root / "gateway.pid").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "not recorded"
    pid = record.get("pid") if isinstance(record, dict) else None
    home = record.get("hermes_home") if isinstance(record, dict) else None
    if not isinstance(pid, int) or pid <= 1 or not home or Path(home).resolve() != root.resolve():
        return f"left alone (its record names {home})"
    for sent, wait in ((signal.SIGTERM, 20.0), (signal.SIGKILL, 5.0)):
        try:
            os.kill(pid, sent)
        except ProcessLookupError:
            return "stopped"
        except PermissionError:
            return "not ours"
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            if not _alive(pid):
                return "stopped"
            time.sleep(0.2)
    return f"still running (pid {pid})"


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(state) and not state.startswith("Z")  # a zombie has exited; its parent has not reaped it yet


# -- run inside Hermes (Hermes's own Python, HERMES_HOME = the throwaway home's ordinary profile) -----------------


def inside(out: str) -> int:
    # Every outcome goes into `out`: the cProfile launcher swallows SystemExit, and with it the exit code.
    import asyncio

    try:
        result = asyncio.run(_page_calls())
    except BaseException as error:  # noqa: BLE001 - reported to the caller, whatever it was
        import traceback

        result = {"fatal": "".join(traceback.format_exception(error))[-3000:]}
    Path(out).write_text(json.dumps(result, default=str), encoding="utf-8")
    return 0


async def _page_calls() -> dict:
    from hermes_cli.gateway_client import connect_gateway  # type: ignore[import-not-found]

    async def call(client, method: str, timeout: float, **params) -> dict:
        try:
            answer = await client.rpc(method, _timeout=timeout, **params)
        except Exception as error:  # noqa: BLE001 - a refusal is the finding, with its code and data
            detail = {k: getattr(error, k, None) for k in ("code", "data")}
            raise SystemExit(f"{method} {params or ''} failed on the gateway: {type(error).__name__}: {error} {detail}")
        if not isinstance(answer, dict) or answer.get("ok") is False:
            raise SystemExit(f"{method} {params or ''} answered {answer}")
        return answer

    found: dict = {}
    async with connect_gateway() as client:  # this home's gateway, started if none runs (as Desktop's would be)
        found["before"] = await call(client, f"plugin.{STUDIO}.status", 120)
        create = (found["before"].get("profile") or {}).get("create")
        if not isinstance(create, dict):
            raise SystemExit(f"the status RPC names no profiles.create parameters: {found['before'].get('profile')}")
        found["created"] = await call(client, "profiles.create", 300, **create)
        found["finished"] = await call(client, f"plugin.{STUDIO}.studio_profile", 300)
        found["after"] = await call(client, f"plugin.{STUDIO}.status", 120)
        try:  # the toolsets as Hermes's profile editor shows them; informative where a Hermes lacks the method
            described = await client.rpc("profiles.describe", _timeout=120, name=STUDIO)
            found["toolsets"] = described.get("toolsets") if isinstance(described, dict) else None
        except Exception as error:  # noqa: BLE001 - recorded; the CLI's tools list still decides
            found["describe_error"] = f"{type(error).__name__}: {error}"
    return found


if __name__ == "__main__":
    if sys.argv[1:2] == ["--inside"] and len(sys.argv) == 3:
        sys.exit(inside(sys.argv[2]))
    sys.exit("usage: run by tools/ci/clean_install_check.py\nFIX: run python tools/ci/clean_install_check.py")

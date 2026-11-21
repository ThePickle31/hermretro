"""The clean install's onboarding: what the page does after a user installs hermretro, through a real Hermes gateway.

Run by tools/ci/clean_install_check.py after its one install into the ordinary (default) profile. `onboard` owns
the throwaway home's gateway as a foreground child (`hermes gateway run`, the host gateway that serves every profile;
stopped and reaped when done: nothing is ever signalled by a PID read from disk) and runs `inside` with Hermes's own
Python. `inside` refuses any home but the throwaway one, only discovers that child (`discover_gateway_endpoint`) and
dials it with Hermes's own client (`hermes_cli.gateway_client.connect_gateway(endpoint)`, which then never starts a
gateway), and makes the page's calls in the page's order (page/pages/setup/install/installer.js):

- on the default profile's gateway: `plugin.hermretro.status` (which must offer setup: no studio yet), Hermes's own
  `profiles.create` with the parameters that status names, the plugin's `plugin.hermretro.studio_profile` (its real
  handler: links the install, runs the `hermes` config commands in the new profile) within Desktop's 240 s,
  `plugin.hermretro.status` again, `profiles.list` (the inventory Desktop's profile routes come from) and
  `profiles.describe` of the new profile (only a method-not-found answer may skip it);
- on the hermretro profile's route (discovered by its home, as Desktop's profile route is; page/app/routing.js
  adoptStudioRoute): `plugin.hermretro.status`, which must answer ok as the studio itself.

`onboard` then judges the answers; the caller checks `hermes tools list` in both profiles. No model, no
credentials, no hardware, no toolchain download: `status` and `studio_profile` never start the broker. Every
problem ends with a "FIX:" line.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDIO = "hermretro"  # backend/setup/studio_profile.STUDIO_PROFILE
REPRODUCE = "reproduce with python tools/ci/clean_install_check.py"
# Desktop's deadline for the studio_profile call (page/pages/setup/install/installer.js createStudioProfile).
FINISH_TIMEOUT = 240
PHASES = ("default", "studio")


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


def phase_home(root: Path, phase: str) -> Path:
    """The Hermes home a phase discovers its gateway route by: the ordinary profile, or the studio profile."""
    return root if phase == "default" else root / "profiles" / STUDIO


@contextmanager
def own_gateway(cli: list[str], home: Path, env: dict, log: Path, grace: float = 20):
    """`hermes gateway run` for ``home`` as this process's child; on exit SIGTERM, SIGKILL after ``grace`` seconds,
    always reaped. Yields a dict that then says how it stopped."""
    state: dict = {}
    with log.open("w") as out:
        child = subprocess.Popen(
            [*cli, "gateway", "run"],
            env={**env, "HERMES_HOME": str(home)},
            cwd=env["HOME"],
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.STDOUT,
        )
        try:
            yield state
        finally:
            state["exited_early"] = child.poll()
            child.terminate()
            try:
                child.wait(grace)
                state["stopped"] = "stopped"
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
                state["stopped"] = f"killed after {grace:g} s"


def run_inside(command: list[str], phase: str, tmp: Path, env: dict, timeout: float) -> tuple[object, str, dict]:
    out = tmp / f"onboarding-{phase}.json"
    try:
        done = subprocess.run(
            [*command, "--inside", phase, str(out)],
            env={**env, "HERMES_HOME": str(phase_home(Path(env["HERMES_HOME"]), phase))},
            cwd=tmp,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        code, output = done.returncode, done.stdout + done.stderr
    except subprocess.TimeoutExpired:
        code, output = f"timed out after {timeout:.0f} s", ""
    found = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}
    return code, output, found


def onboard(hermes_python: str | None, tmp: Path, root: Path, env: dict) -> list[str]:
    """Run the page's onboarding calls through the gateways of ``root`` and return what is wrong (empty: all good).
    ``env`` is the throwaway environment (clean_install_check.environment) with HERMES_HOME = ``root``."""
    script = str(Path(__file__).resolve())
    if hermes_python:
        command, cli = [hermes_python, "-I", script], [hermes_python, "-I", "-m", "hermes_cli.main"]
    else:  # the `hermes` launcher runs only modules in its environment; cProfile is one that runs a script
        command, cli = ["hermes", "--run-module", "cProfile", "-o", os.devnull, script], ["hermes"]
    found: dict = {}
    log = tmp / "gateway.log"
    started = time.monotonic()
    # One gateway, the default profile's, for both phases: Hermes serves every profile from that host gateway (and
    # refuses a profile's own `gateway run`), so the studio's route is that gateway too, discovered by its home.
    with own_gateway(cli, root, env, log) as gateway:
        for phase in PHASES:
            code, output, answers = run_inside(command, phase, tmp, env, 600 if phase == "default" else 300)
            if code or "fatal" in answers or not answers:
                break
            found.update(answers)
    print(
        f"$ page onboarding through the Hermes gateway  [{root.name}] -> {code} "
        f"({time.monotonic() - started:.0f} s; gateway {gateway['stopped']})",
        flush=True,
    )
    if code or "fatal" in answers or not answers:
        tail = log.read_text(encoding="utf-8", errors="replace")[-2000:] if log.is_file() else ""
        return [
            f"{phase} phase: "
            + (answers.get("fatal") or output[-3000:] or str(code))
            + (f"\nthe gateway's log ends:\n{tail}" if tail else "")
            + f"\nFIX: the page's onboarding failed on a real Hermes gateway in a clean home; {REPRODUCE}"
        ]
    return judge(found, root)


def initial_refusal(status: object) -> str | None:
    """Why the page would not offer setup on this first status answer (None: it would). installer.js makes the profile
    only for `ok` and `!profile.is_studio && !profile.studio.installed`, and creates it only when `!studio.exists`."""
    status = status if isinstance(status, dict) else {}
    profile = status.get("profile") if isinstance(status.get("profile"), dict) else {}
    studio = profile.get("studio")
    if (
        not isinstance(studio, dict)
        or status.get("ok") is not True
        or profile.get("is_studio") is not False
        or studio.get("exists") is not False
        or studio.get("installed") is not False
        or not isinstance(profile.get("create"), dict)
    ):
        return (
            f"before onboarding the status RPC answered {status}: the page offers setup only for ok=true with "
            "is_studio=false, studio.exists=false, studio.installed=false and the profiles.create parameters\n"
            f"FIX: describe() must report no studio profile yet in a clean home; {REPRODUCE}"
        )
    return None


def method_not_found(error: BaseException) -> bool:
    """The gateway has no such method (it predates it): JSON-RPC -32601, or only that reason from an owner that sends
    no code. Mirrors Hermes's GatewayRPCError.unknown_method, which older Hermes lacks."""
    return getattr(error, "code", None) == -32601 or str(error) == "unknown_method"


def judge(found: dict, root: Path) -> list[str]:
    """What is wrong with the answers `inside` recorded (``found``) for the throwaway home ``root``."""
    problems = []
    studio = root / "profiles" / STUDIO

    def wrong(message: str, fix: str) -> None:
        problems.append(f"{message}\nFIX: {fix}; {REPRODUCE}")

    refusal = initial_refusal(found.get("before"))
    if refusal:
        problems.append(refusal)
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
    listed = [
        row
        for row in (found.get("profiles") or {}).get("profiles") or []
        if isinstance(row, dict) and row.get("name") == STUDIO
    ]
    if len(listed) != 1 or Path(str(listed[0].get("path"))).resolve() != studio.resolve():
        wrong(
            f"Hermes's profiles.list (Desktop's profile routes) lists {listed} for {STUDIO}, not {studio}",
            "the created profile must be the one Desktop discovers",
        )
    return problems + _judge_studio_route(found, studio) + _judge_toolsets(found)


def _judge_studio_route(found: dict, studio: Path) -> list[str]:
    """The hermretro profile's route must serve the plugin as the studio (adoptStudioRoute's test)."""
    served = found.get("studio_endpoint")
    status = found.get("studio_status") or {}
    profile = status.get("profile") if isinstance(status.get("profile"), dict) else {}
    if not served or Path(str(served)).resolve() != studio.resolve():
        return [
            f"the gateway route discovered for the {STUDIO} profile serves {served}, not {studio}\nFIX: the studio "
            f"route must reach the {STUDIO} profile; {REPRODUCE}"
        ]
    if status.get("ok") is not True or profile.get("is_studio") is not True or profile.get("name") != STUDIO:
        return [
            f"the {STUDIO} profile's route answered plugin.hermretro.status with {status}: Desktop would stay on "
            '"Waiting for Hermes to start it"\nFIX: the plugin must load in the studio profile and describe() must '
            f"report is_studio there (studio_profile.is_studio, __init__.register); {REPRODUCE}"
        ]
    print(f"{STUDIO} route (served by {found.get('studio_served_by')}): status ok, is_studio, name {STUDIO}")
    return []


def _judge_toolsets(found: dict) -> list[str]:
    if "describe_unavailable" in found:  # only an explicit method-not-found gets here
        print(f"gateway profiles.describe {STUDIO} unavailable on this Hermes: {found['describe_unavailable']}")
        return []
    toolsets = found.get("toolsets")
    fix = f"the plugin's tools must register in the studio profile (studio_profile.is_studio, __init__.register); {REPRODUCE}"
    if not isinstance(toolsets, list):
        return [f"the gateway's profiles.describe of {STUDIO} answered no toolsets list: {toolsets!r}\nFIX: {fix}"]
    chromatic = [row for row in toolsets if isinstance(row, dict) and row.get("name") == "chromatic"]
    if not (chromatic and chromatic[0].get("enabled")):
        return [
            f"the gateway's profiles.describe of {STUDIO} lists no enabled chromatic toolset: {chromatic}\nFIX: {fix}"
        ]
    print(f"gateway profiles.describe {STUDIO}: chromatic {chromatic[0]}")
    if chromatic[0].get("tool_count") != len(declared_tools()):
        return [
            f"the gateway counts {chromatic[0].get('tool_count')} chromatic tools in {STUDIO}; plugin.yaml declares "
            f"{len(declared_tools())}\nFIX: __init__.register must add exactly plugin.yaml's provides_tools; {REPRODUCE}"
        ]
    return []


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


# -- run inside Hermes (Hermes's own Python, HERMES_HOME = the phase's home in the throwaway folder) ---------------


def inside_refusal(phase: str, out: str, environ) -> str | None:
    """Why `--inside` must not run here (None: it may). Only the layout onboard() makes is accepted: ``out`` is
    <throwaway>/onboarding-<phase>.json in a folder named like clean_install_check's, HOME is <throwaway>/home and
    HERMES_HOME is that phase's home under <throwaway>/hermes-home, so the mutating calls never reach a real home."""
    from clean_install_check import PREFIX

    if phase not in PHASES:
        return f"unknown phase {phase!r}"
    target = Path(out).resolve()
    base = target.parent
    home = Path(environ.get("HOME") or "/nonexistent").resolve()
    hermes_home = Path(environ.get("HERMES_HOME") or "/nonexistent").resolve()
    expected = phase_home(base / "hermes-home", phase)
    if target.name != f"onboarding-{phase}.json" or not base.name.startswith(PREFIX) or ".hermes" in base.parts:
        return f"{target} is not in a throwaway folder made by clean_install_check.py"
    if home != base / "home" or hermes_home != expected or not expected.is_dir():
        return f"HOME={home} and HERMES_HOME={hermes_home} are not {base / 'home'} and {expected}"
    return None


def inside(phase: str, out: str) -> int:
    refusal = inside_refusal(phase, out, os.environ)
    if refusal:  # before any gateway contact, and nothing written: the target may not be ours
        print(f"refusing to run the onboarding calls: {refusal}", file=sys.stderr)
        print("FIX: run python tools/ci/clean_install_check.py, which makes its own throwaway home", file=sys.stderr)
        return 2
    # Every other outcome goes into `out`: the cProfile launcher swallows SystemExit, and with it the exit code.
    import asyncio

    try:
        result = asyncio.run(_page_calls(phase))
    except BaseException as error:  # noqa: BLE001 - reported to the caller, whatever it was
        import traceback

        result = {"fatal": "".join(traceback.format_exception(error))[-3000:]}
    Path(out).write_text(json.dumps(result, default=str), encoding="utf-8")
    return 0


async def _ready_endpoint(home: Path, deadline_s: float = 120):
    """The gateway onboard() started for ``home``, once it is ready; discovery never starts one."""
    import asyncio

    from hermes_cli.gateway_runtime import discover_gateway_endpoint  # type: ignore[import-not-found]

    deadline = time.monotonic() + deadline_s
    while True:
        found = await asyncio.to_thread(discover_gateway_endpoint, home)
        if found.state == "ready" and found.endpoint is not None:
            return found.endpoint
        if time.monotonic() > deadline:
            raise SystemExit(f"the gateway for {home} did not come up: {found.state} ({found.reason_code})")
        await asyncio.sleep(0.25)


async def _page_calls(phase: str) -> dict:
    from hermes_cli.gateway_client import GatewayRPCError, connect_gateway  # type: ignore[import-not-found]

    async def call(client, method: str, timeout: float, **params) -> dict:
        try:
            answer = await client.rpc(method, _timeout=timeout, **params)
        except Exception as error:  # noqa: BLE001 - a refusal is the finding, with its code and data
            detail = {k: getattr(error, k, None) for k in ("code", "data")}
            raise SystemExit(f"{method} {params or ''} failed on the gateway: {type(error).__name__}: {error} {detail}")
        if not isinstance(answer, dict) or answer.get("ok") is False:
            raise SystemExit(f"{method} {params or ''} answered {answer}")
        return answer

    endpoint = await _ready_endpoint(Path(os.environ["HERMES_HOME"]))
    found: dict = {}
    async with connect_gateway(
        endpoint
    ) as client:  # the dialled owner only: connect_gateway(endpoint) never starts one
        if phase == "studio":  # Desktop's adoptStudioRoute: the studio's own route must answer as the studio
            found["studio_endpoint"] = getattr(endpoint, "profile_id", None)
            found["studio_served_by"] = getattr(endpoint, "control_home", None) or "its own owner"
            found["studio_status"] = await call(client, f"plugin.{STUDIO}.status", 120)
            return found
        found["before"] = await call(client, f"plugin.{STUDIO}.status", 120)
        refusal = initial_refusal(found["before"])
        if refusal:  # the page would not offer setup: never create the profile on its behalf
            raise SystemExit(refusal)
        found["created"] = await call(client, "profiles.create", 120, **found["before"]["profile"]["create"])
        found["finished"] = await call(client, f"plugin.{STUDIO}.studio_profile", FINISH_TIMEOUT)
        found["after"] = await call(client, f"plugin.{STUDIO}.status", 120)
        found["profiles"] = await call(client, "profiles.list", 120, include_sessions=False)
        try:  # the toolsets as Hermes's profile editor shows them
            described = await client.rpc("profiles.describe", _timeout=120, name=STUDIO)
        except GatewayRPCError as error:
            if not method_not_found(error):  # any other refusal is a failure, not a skip (a timeout is not caught)
                raise SystemExit(f"profiles.describe failed on the gateway: {error} {error.code} {error.data}")
            found["describe_unavailable"] = f"{error} ({error.code})"
        else:
            found["toolsets"] = described.get("toolsets") if isinstance(described, dict) else None
    return found


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))  # python -I leaves the script's folder out
    if sys.argv[1:2] == ["--inside"] and len(sys.argv) == 4:
        sys.exit(inside(sys.argv[2], sys.argv[3]))
    sys.exit("usage: run by tools/ci/clean_install_check.py\nFIX: run python tools/ci/clean_install_check.py")

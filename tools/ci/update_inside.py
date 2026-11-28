"""The half of `python tools/ci/clean_install_check.py --update-from` that runs inside Hermes (Hermes's own Python,
HERMES_HOME the throwaway home), and the helpers update_check.py uses to start it and to hold an old broker open.

Run as `clean_install_check.py --inside PHASE OUT` (`inside_command`, `inside_environment`), each phase uses the
installed plugin the way the page does and writes what it finds into OUT as JSON for update_check.py to judge: `old`
and `new` call the page's RPCs through Hermes's plugin loader and start its broker; `kept`, the gateway of a published
release still running after the update (`OldGateway`), waits for the go, then calls `doctor` and reads which broker
answered. Outside Hermes, update_check.py holds a silent connection to the old broker with `hold_open` and lets it go
with `drive_holding`, which `old_broker_gone` and `alive` judge.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from clean_install_check import environment


def inside_command(args, phase: str, out: Path) -> list[str]:
    """The command that runs `inside` with Hermes's own Python."""
    script = str(Path(__file__).resolve().with_name("clean_install_check.py"))
    if args.hermes_python:
        command = [args.hermes_python, "-I", script]
    else:  # the `hermes` launcher runs only modules in its environment; cProfile is one that runs a script
        command = ["hermes", "--run-module", "cProfile", "-o", os.devnull, script]
    return [*command, "--inside", phase, str(out)]


def inside_environment(tmp: Path, root: Path) -> dict:
    # A broker this leaves behind (a failed run) stops by itself within a minute.
    return environment(tmp, root, {"HERMRETRO_BROKER_IDLE_SECONDS": "60"})


PNG = (
    "data:image/png;base64,"
    + base64.b64encode(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000d4944415478da63f8cfc0f01f0005000201a5f7a1a40000000049454e44ae426082"
        )
    ).decode()
)


def inside(phase: str, out: str) -> int:
    # Every outcome goes into `out`: the cProfile launcher swallows SystemExit, and with it the exit code.
    try:
        result = _keep_the_old_code() if phase == "kept" else _use_the_plugin(phase, Path(out))
    except BaseException as error:  # noqa: BLE001 - reported to the caller, whatever it was
        import traceback

        result = {"fatal": "".join(traceback.format_exception(error))[-3000:]}
    Path(out).write_text(json.dumps(result))
    return 0


# Where each module the check drives lives, newest layout first (releases before the reorganization used adapter/).
LAYOUTS = {
    "paths": (".backend.system.paths", ".adapter.paths"),
    "client": (".backend.broker.client", ".adapter.client"),
    "host": (".backend.hermes.host", ".adapter.hermes_host"),
    "studio_profile": (".backend.setup.studio_profile", ".adapter.studio_profile"),
}


def rpc(name: str, params: dict | None = None) -> dict:
    """A page RPC of the loaded plugin, through Hermes's plugin loader (the first one loads the plugin)."""
    from hermes_cli.plugin_rpc import plugin_rpc_handler  # type: ignore[import-not-found]

    handler = plugin_rpc_handler(f"plugin.hermretro.{name}")
    if handler is None:
        raise SystemExit(f"the plugin registered no {name} RPC in this profile")
    answer = handler(dict(params or {}), session_id=None)
    if not isinstance(answer, dict) or not answer.get("ok"):
        raise SystemExit(f"plugin.hermretro.{name} {params or ''} answered {answer}")
    return answer


def module(role: str):
    """One of the loaded plugin's modules. Either version may be installed in either phase: a release from before the
    reorganization keeps its code in adapter/, every later one in backend/. Found by what the loaded version has."""
    for suffix in LAYOUTS[role]:
        found = [m for name, m in list(sys.modules.items()) if name.endswith(suffix)]
        if found:
            return found[0]
    raise SystemExit(f"the installed version has none of {LAYOUTS[role]}: add its layout to LAYOUTS")


def _keep_the_old_code() -> dict:
    """A gateway of the old version that Hermes has not restarted: its code loaded before the update, its first call
    after it. It must keep the broker the new version's drive started, not shut it down for its own each time."""
    rpc("status")  # loads the plugin
    rpc("doctor")  # what the page calls, with the old broker, so its code is loaded too
    print(READY, flush=True)
    if sys.stdin.readline().strip() != GO:  # the caller updates the plugin folder and runs the new drive first
        raise SystemExit("the check ended before the old gateway's turn")
    rpc("doctor")
    client, error = module("client").try_connect(module("paths").runtime_dir())
    if client is None:
        raise SystemExit(f"no broker answers the old gateway after its doctor RPC: {error}")
    with client:
        return {"broker_pid": client.hello.get("pid")}


def _use_the_plugin(phase: str, out: Path) -> dict:
    rpc("status")  # loads the plugin
    result: dict = {"problems": []}
    paths, client_module = module("paths"), module("client")
    if phase == "old":
        host = module("host")
        # The page's studio_profile RPC without its Hermes config commands (the caller enables the plugin). The
        # page creates the profile with the plugin's description, which the CLI cannot set: mark it as ours.
        studio_profile = module("studio_profile")
        marker = studio_profile.studio_dir() / studio_profile.MARKER
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("{}")
        studio_profile.finish(Path(os.environ["HERMES_HOME"]), enabled=[], run=lambda *_: None)
        project = paths.games_dir(create=True) / "update-check"
        project.mkdir()
        (project / "update-check.gbsproj").write_text(json.dumps({"name": "Update Check"}))
        entry = host._registry().upsert(str(project))
        rpc("game_thumb", {"id": entry["id"], "png": PNG})
        rpc("build", {"action": "start", "stored": "update-check-chat", "name": "Second Game"})
        paths.DEPS_ROOT.mkdir(parents=True, exist_ok=True)
        (paths.DEPS_ROOT / "update-check.txt").write_text("downloads stay")
    else:
        for kept in (paths.library_dir() / "thumbs", paths.DEPS_ROOT / "update-check.txt"):
            if not (any(kept.iterdir()) if kept.is_dir() else kept.is_file()):
                result["problems"].append(f"{kept} is gone after the update")
                result["fix"] = "the user's folder (games, library, downloads) must survive an update"
    games = rpc("games")
    result["games"] = [{"id": game["id"], "title": game.get("title")} for game in games["games"]]
    result["pending"] = [item.get("storedId") for item in games.get("pending", [])]
    result["hermretro_home"] = str(paths.hermretro_home())
    rpc("doctor")  # the first call that needs the broker: starts one, or replaces one running other code
    client, error = client_module.try_connect(paths.runtime_dir())
    if client is None:
        raise SystemExit(f"no broker answers after the doctor RPC: {error}")
    with client:
        result["broker_socket"] = str(paths.runtime_dir() / "broker.sock")
        result["broker_pid"] = client.hello.get("pid")
        result["broker_code"] = client.hello.get("code_fingerprint")
        result["code"] = paths.code_fingerprint() if hasattr(paths, "code_fingerprint") else None
        if phase == "new" and client.hello.get("code_fingerprint") != paths.code_fingerprint():
            result["problems"].append(f"the broker answering runs other code: {client.hello}")
            result["fix"] = "backend/broker/client.ensure_broker must replace a broker from another build"
    old_run = json.loads((out.parent / "old.json").read_text()) if phase == "new" else {}
    if phase == "new" and old_run.get("broker_code") != result["code"]:
        old_pid = old_run["broker_pid"]
        for _ in range(50):  # the replaced broker exits on the shutdown, with the caller's held connection open
            if not alive(old_pid):
                break
            time.sleep(0.1)
        else:
            result["problems"].append(f"the old version's broker (pid {old_pid}) is still running")
            result["fix"] = "a broker from another build must exit when asked to shut down while idle"
    return result


READY, GO = "the old gateway is running", "go"


class OldGateway:
    """A gateway of the old version that Hermes has not restarted (`_keep_the_old_code`), run beside the check: started
    before the update, it makes its next call after the new version's drive."""

    def __init__(self, args, tmp: Path, root: Path, fix: str):
        self.fix = fix
        self.out = tmp / "kept.json"
        self.process = subprocess.Popen(
            inside_command(args, "kept", self.out),
            env=inside_environment(tmp, root),
            cwd=tmp,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.said: list[str] = []
        self.ready = threading.Event()  # set when it says READY, or when it ends without saying it
        self.ended = threading.Event()  # its output is read to the end by a thread, so no line waits in a buffer
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self) -> None:
        for line in self.process.stdout:
            self.said.append(line)
            if line.strip() == READY:
                self.ready.set()
        self.ended.set()
        self.ready.set()

    def wait_ready(self) -> None:
        """Wait until its code is loaded and it has used the old broker."""
        if not self.ready.wait(300) or self.ended.is_set():
            self.stop()
            raise SystemExit(
                f"the old version's gateway did not start: {self._failure()}\nFIX: reproduce with "
                f"python tools/ci/clean_install_check.py{self.fix}"
            )

    def problems(self, after: dict) -> list[str]:
        """Let it make its call after the update: it must have kept the broker the new version started."""
        try:
            self.process.stdin.write(GO + "\n")
            self.process.stdin.close()
            self.process.wait(timeout=300)
        except (OSError, subprocess.TimeoutExpired):
            self.stop()
        self.reader.join(5)
        found = json.loads(self.out.read_text()) if self.out.is_file() else {"fatal": self._failure()}
        if "fatal" in found:
            return [
                found["fatal"] + "\nFIX: a gateway of the old version, still running after the update, must work "
                "with the broker the new files start (paths.release_fingerprint); reproduce with "
                f"python tools/ci/clean_install_check.py{self.fix}"
            ]
        if found.get("broker_pid") != after.get("broker_pid"):
            return [
                f"the old version's gateway replaced the new broker (pid {after.get('broker_pid')}) with pid "
                f"{found.get('broker_pid')}: the two name the same code differently\nFIX: the broker's "
                "loaded_fingerprint must follow the released clients' rule (paths.release_fingerprint); reproduce "
                f"with python tools/ci/clean_install_check.py{self.fix}"
            ]
        return []

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait()

    def _failure(self) -> str:
        found = json.loads(self.out.read_text()).get("fatal", "") if self.out.is_file() else ""
        return ("".join(self.said)[-2000:] + found) or "(no output)"


def hold_open(socket_path: str) -> socket.socket:
    """A connection to the broker that sends nothing: while it is open the broker never exits for idleness."""
    held = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        held.connect(socket_path)
    except OSError as error:
        held.close()
        raise SystemExit(
            f"the old version's broker no longer listens at {socket_path} right after its drive: {error}\n"
            "FIX: the old drive must leave its broker running; reproduce with "
            "python tools/ci/clean_install_check.py --update-from"
        ) from error
    return held


def drive_holding(held: socket.socket, pid: int, alive, drive, fix: str):
    """Run the new drive while `held` still holds the old broker, then let go of it.

    Closed only afterwards: closed before, the old broker could idle out between this liveness check and the new
    client's connect, and a broker started from nothing would look like a replaced one. Holding it does not stop
    the replacement: the broker exits on an explicit shutdown with connections open (a silent one included;
    tests/backend/broker/test_broker_socket.py pins that)."""
    try:
        gone = old_broker_gone(pid, alive(pid), fix)
        if gone:
            raise SystemExit(gone)
        return drive()
    finally:
        held.close()


def old_broker_gone(pid: int, alive: bool, fix: str) -> str | None:
    """None while the old broker still runs; otherwise why the replacement it was to prove cannot be shown."""
    if alive:
        return None
    return (
        f"the old version's broker (pid {pid}) exited before the new version's first call, so the check cannot "
        "show whether the update replaces it or keeps it\nFIX: keep the old broker running until the new drive "
        "(update_inside.hold_open must hold a connection to it); reproduce with "
        f"python tools/ci/clean_install_check.py{fix}"
    )


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(state) and not state.startswith("Z")  # a zombie has exited; its parent has not reaped it yet

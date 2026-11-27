"""`python tools/ci/clean_install_check.py --update-from [REF]`: an installed release updated to this commit.
How to run it and what it needs: .agents/skills/hermretro-dev-testing/references/testing.md, "The clean install and update checks".

Installs REF (default: the newest v* release tag on origin/main, the version users have) from a local copy of this
repository into a throwaway Hermes home and uses it the way the page does: the studio profile linked to the
install, a game in the library with a thumbnail, a New Game conversation, a running broker. Then it moves the
copy's default branch to HEAD, runs `hermes plugins update hermretro` and checks: the update needed no prompt,
the new code registers its agent side only in hermretro and still matches plugin.yaml, it reads the user's
games and library back, the old broker is replaced on the first call, a gateway of the old version still running
(Hermes not yet restarted) keeps the broker the new version started, and nothing the old version left in the plugin
folder gets in the way. The page calls run in Hermes's own Python (`inside`), through its plugin loader.
"""

from __future__ import annotations

import base64
import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from clean_install_check import ROOT, environment, registers_only_in_studio, runner


def _git(*args: str, cwd: Path = ROOT) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120
    )
    if done.returncode:
        raise SystemExit(
            f"git {' '.join(args)} failed in {cwd}:\n{done.stderr.strip()}\n"
            "FIX: the checkout needs its history and tags (CI: actions/checkout with fetch-depth: 0)"
        )
    return done.stdout.strip()


def latest_release() -> str:
    """The newest stable `v*` tag on origin/main (local main without an origin): the version users have now."""
    base = "origin/main"
    if subprocess.run(["git", "rev-parse", "-q", "--verify", base], cwd=ROOT, capture_output=True).returncode:
        base = "main"
    tags = [tag for tag in _git("tag", "--merged", base, "--list", "v*", "--sort=-v:refname").split() if "-" not in tag]
    if not tags:
        raise SystemExit(f"no v* release tag is reachable from {base}\nFIX: git fetch --tags origin, or pass a REF")
    return tags[0]


def update(args, hermes: list[str], tmp: Path, root: Path) -> int:
    started = time.monotonic()
    ref = latest_release() if args.update_from == "latest-release" else args.update_from
    old = _git("rev-parse", "--verify", f"{ref}^{{commit}}")
    new = _git("rev-parse", "HEAD")
    if _git("merge-base", old, new) != old:
        raise SystemExit(
            f"{ref} is not an ancestor of HEAD, so `hermes plugins update` (a pull) cannot reach HEAD from it"
            "\nFIX: pass a REF that HEAD contains"
        )
    # A copy of this repository whose default branch is the release, as GitHub's main is before a release.
    # Pushed, not cloned: CI checks out a detached merge commit that no branch holds.
    origin = tmp / "hermretro.git"
    _git("init", "--quiet", "--bare", str(origin))
    _git("symbolic-ref", "HEAD", "refs/heads/main", cwd=origin)
    _git("push", "--quiet", "--no-verify", str(origin), f"{old}:refs/heads/main")

    fix = f" --update-from {ref}"
    run = runner(hermes, tmp, fix=fix)
    studio = root / "profiles" / "hermretro"
    plugin = root / "plugins" / "hermretro"
    brokers: list[int] = []
    held = kept = None
    print(f"updating from {ref} ({old[:10]}) to HEAD ({new[:10]})", flush=True)
    try:
        # As a user does: install into their own profile; the page then creates the studio profile, which
        # links to that install (one copy; `hermes plugins update` runs where it was installed).
        run(root, "plugins", "install", f"file://{origin}", "--enable", "--yes-deps")
        run(root, "profile", "create", "hermretro", "--no-alias", "--no-skills")
        before = _drive(args, tmp, root, "old")
        brokers.append(before["broker_pid"])
        # The old broker idles out a minute after its last connection closes (the drive sets that), which
        # the steps up to the new drive can outlast: a broker gone by itself proves no replacement. An open,
        # silent connection holds it (an idle exit waits for none) until the new drive has replaced it.
        held = hold_open(before["broker_socket"])
        kept = OldGateway(args, tmp, root, fix)  # a gateway of the old version that Hermes has not restarted
        kept.wait_ready()
        run(studio, "plugins", "enable", "hermretro")  # what the page's studio_profile RPC runs in the profile
        problems = []
        dirty = _git("status", "--porcelain", cwd=plugin)
        if dirty:
            problems.append(
                f"using {ref} left files git does not ignore in the plugin folder, so an update may refuse:\n"
                f"{dirty}\nFIX: ignore them in .gitignore, or stop writing them into the plugin folder"
            )

        # Bytecode of the old modules, as a Python that writes it leaves: git keeps the ignored files of folders
        # the update removes, so the new code must load (and the next update work) with them around. Not for
        # adapter/: with that folder gone, the release's broker fails its own handshake, the harder case.
        compile_all = [sys.executable, "-m", "compileall", "-q", "-x", "/(engine|adapter)/", str(plugin)]
        subprocess.run(compile_all, capture_output=True, timeout=300)

        _git("push", "--quiet", "--no-verify", str(origin), f"{new}:refs/heads/main")  # the release reaches main
        run(root, "plugins", "update", "hermretro")
        if _git("rev-parse", "HEAD", cwd=plugin) != new:
            problems.append(
                "`hermes plugins update hermretro` did not move the plugin folder to HEAD"
                f"\nFIX: reproduce with python tools/ci/clean_install_check.py{fix}"
            )
        problems += _leftovers(plugin, fix)
        problems += registers_only_in_studio(run, root, studio)
        # Registers the agent side as in the hermretro profile; the counts must still match plugin.yaml.
        report = runner(hermes, tmp, {"HERMRETRO_EVERY_PROFILE": "1"}, fix)(root, "plugins", "validate", str(plugin))
        if "matches registrations" not in report or re.search(
            r"register\(\) did not|declared (tools|hooks) .*(undeclared|not)", report
        ):
            problems.append(
                report[-2000:] + "\nFIX: after the update `hermes plugins validate` no longer matches plugin.yaml; "
                "check __init__.register and provides_tools / provides_hooks"
            )
        after = drive_holding(held, before["broker_pid"], _alive, lambda: _drive(args, tmp, root, "new"), fix)
        brokers.append(after.get("broker_pid") or 0)
        problems += _compare(before, after, fix)
        problems += kept.problems(after)
    finally:
        if held is not None:
            held.close()
        if kept is not None:
            kept.stop()
        for pid in brokers:  # whatever happened, leave no broker of the throwaway home running
            if pid:
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    broker_fate = "kept (same code)" if before.get("broker_code") == after.get("code") else "replaced (new code)"
    print(
        f"ok: {ref} updates cleanly to HEAD with `hermes plugins update` ({time.monotonic() - started:.0f} s): "
        f"games and library kept, the broker {broker_fate}, the agent side only in hermretro"
    )
    return 0


def _leftovers(plugin: Path, fix: str) -> list[str]:
    """What the old version left that git does not track any more. Untracked and not ignored: this or the next
    update may refuse. Ignored is fine only for bytecode caches (Python never imports those without sources)."""
    problems = []
    untracked = _git("status", "--porcelain", cwd=plugin)
    if untracked:
        problems.append(
            f"after the update the plugin folder has files git does not ignore:\n{untracked}\n"
            "FIX: ignore them in .gitignore, or stop writing them into the plugin folder" + fix
        )
    # Every ignored path on its own: plain --ignored folds a folder holding only ignored files into `!! dir/`,
    # which hides what is inside. With these flags a folder is listed only when an ignore rule names it.
    listing = _git("status", "--porcelain", "-z", "--ignored=matching", "--untracked-files=all", cwd=plugin)
    return problems + ignored_problems(listing, fix)


def ignored_problems(listing: str, fix: str) -> list[str]:
    """Judge each ignored entry of `git status --porcelain -z --ignored=matching --untracked-files=all`."""
    problems = []
    for entry in listing.split("\0"):
        if not entry.startswith("!! "):
            continue
        path = entry[3:]
        if not is_bytecode(path):
            problems.append(
                f"after the update the plugin folder holds {path} (ignored by git, not a bytecode cache)\n"
                "FIX: make sure the new code never reads it, or keep it out of the plugin folder" + fix
            )
    return problems


def is_bytecode(path: str) -> bool:
    """A bytecode cache folder, a file inside one, or a compiled module."""
    return "__pycache__" in path.rstrip("/").split("/") or path.endswith((".pyc", ".pyo"))


def _compare(before: dict, after: dict, fix: str) -> list[str]:
    problems = [f"{problem}\nFIX: {after.get('fix')}{fix}" for problem in after.get("problems", [])]
    if after.get("hermretro_home") != before["hermretro_home"]:
        problems.append(
            f"the user's folder moved: {before['hermretro_home']} -> {after.get('hermretro_home')}"
            "\nFIX: keep backend/system/paths.hermretro_home() where the release kept it, or migrate it"
        )
    kept = {game["id"]: game.get("title") for game in after.get("games", [])}
    for game in before["games"]:
        if kept.get(game["id"]) != game.get("title"):
            problems.append(
                f"the library lost or renamed {game}; the new games RPC lists {kept}"
                "\nFIX: read the library (games.json) the way the release wrote it"
            )
    if sorted(after.get("pending", [])) != sorted(before["pending"]):
        problems.append(
            f"New Game conversations changed: {before['pending']} -> {after.get('pending')}"
            "\nFIX: read the library's pending records the way the release wrote them"
        )
    # The broker is replaced only when its code changed (a different fingerprint); with the same code it is kept.
    replaced = after.get("broker_pid") != before["broker_pid"]
    if before.get("broker_code") != after.get("code") and not replaced:
        problems.append(
            "the broker the release started still answers after the update"
            "\nFIX: backend/broker/client.ensure_broker must replace a broker whose code_fingerprint differs"
        )
    elif before.get("broker_code") == after.get("code") and replaced:
        problems.append(
            "the broker was restarted although its code did not change"
            "\nFIX: backend/broker/client.ensure_broker must keep a broker whose code_fingerprint matches"
        )
    return problems


def _inside(args, phase: str, out: Path) -> list[str]:
    """The command that runs `inside` with Hermes's own Python."""
    script = str(Path(__file__).resolve().with_name("clean_install_check.py"))
    if args.hermes_python:
        command = [args.hermes_python, "-I", script]
    else:  # the `hermes` launcher runs only modules in its environment; cProfile is one that runs a script
        command = ["hermes", "--run-module", "cProfile", "-o", os.devnull, script]
    return [*command, "--inside", phase, str(out)]


def _inside_environment(tmp: Path, root: Path) -> dict:
    # A broker this leaves behind (a failed run) stops by itself within a minute.
    return environment(tmp, root, {"HERMRETRO_BROKER_IDLE_SECONDS": "60"})


def _drive(args, tmp: Path, root: Path, phase: str) -> dict:
    """Run `inside` with Hermes's own Python in the throwaway home and return what it found."""
    out = tmp / f"{phase}.json"
    done = subprocess.run(
        _inside(args, phase, out),
        env=_inside_environment(tmp, root),
        cwd=tmp,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=300,
    )
    print(f"$ page RPCs of the {phase} version through Hermes's plugin loader  [{root.name}] -> {done.returncode}")
    found = json.loads(out.read_text()) if out.is_file() else {"fatal": (done.stdout + done.stderr)[-3000:]}
    if done.returncode or "fatal" in found:
        raise SystemExit(
            found.get("fatal", "") + f"\nFIX: the {phase} version's page calls failed in a clean Hermes home "
            f"after {'installing' if phase == 'old' else 'updating'}; "
            f"reproduce with python tools/ci/clean_install_check.py --update-from {args.update_from}"
        )
    return found


# -- run inside Hermes (Hermes's own Python, HERMES_HOME = the throwaway home) -----------------------------------

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
    sys.stdin.readline()  # the caller has updated the plugin folder and run the new version's drive
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
            if not _alive(old_pid):
                break
            time.sleep(0.1)
        else:
            result["problems"].append(f"the old version's broker (pid {old_pid}) is still running")
            result["fix"] = "a broker from another build must exit when asked to shut down while idle"
    return result


READY = "the old gateway is running"


class OldGateway:
    """A gateway of the old version that Hermes has not restarted (`_keep_the_old_code`), run beside the check: started
    before the update, it makes its next call after the new version's drive."""

    def __init__(self, args, tmp: Path, root: Path, fix: str):
        self.fix = fix
        self.out = tmp / "kept.json"
        self.process = subprocess.Popen(
            _inside(args, "kept", self.out),
            env=_inside_environment(tmp, root),
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
            self.process.communicate("go\n", timeout=300)
        except subprocess.TimeoutExpired:
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
        "(update_check.hold_open must hold a connection to it); reproduce with "
        f"python tools/ci/clean_install_check.py{fix}"
    )


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(state) and not state.startswith("Z")  # a zombie has exited; its parent has not reaped it yet

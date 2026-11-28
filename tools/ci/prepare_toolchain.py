"""Install the game toolchain the way the hermretro page does (the broker's install), and wait for it.

    python tools/ci/prepare_toolchain.py                                # on a developer machine, or in CI
    HERMRETRO_DEPS_ROOT=<folder> python tools/ci/prepare_toolchain.py   # into a folder of your choosing

For CI and fresh checkouts that need the toolchain for `python tools/check.py acceptance`. Downloads about
700 MB the first time (pinned, every archive checked against its SHA-256); does nothing when it is already
installed. Touches no hardware. Exits non-zero, with the reason, when the install fails.

The install runs in a broker of its own, started in a new private folder and stopped at the end: a broker that is
already running (the one an installed hermretro's chats use) is never reused, replaced or stopped. This process keeps
the broker's own process and stops it on every way out (the end, a failure, Ctrl-C, SIGTERM or SIGHUP), confirming it
exited before removing its folder. Everything the install writes (the toolchain, its journal, the prepared engine)
lands in the destination: in GitHub Actions the hermretro home's `.cache` (a throwaway machine's), anywhere else this
machine's development toolchain (tools/py/dev_toolchain.py), which `python tools/check.py acceptance` finds by itself,
never the installed plugin's `.cache`, which its page installs. HERMRETRO_DEPS_ROOT names another; the acceptance run is
then given the same one. GB_STUDIO_SETUP_ROOT, which would move the toolchain out of the destination, is refused.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "py"))

import dev_toolchain  # noqa: E402 - tools/py/ goes on sys.path first
import backend.hermes  # noqa: E402, F401 - tells backend.system how to ask Hermes for its home
from backend.broker import client  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first

LIMIT_SECONDS = 1200
STALL_SECONDS = 420  # no new bytes downloaded and no growth on disk (npm unpacking counts as progress)
START_SECONDS = 60
# The broker closes its workers (the installer's included) on SIGTERM; one that takes longer than this is killed.
STOP_SECONDS = 30
KILL_SECONDS = 10
# Where the private broker's folder is made: /tmp, since a macOS TMPDIR is too long for the broker's Unix socket.
STATE_PARENT = Path("/tmp")


class Interrupted(BaseException):
    """Ctrl-C, SIGTERM or SIGHUP: unwinds like KeyboardInterrupt, so the run's broker is still stopped."""

    def __init__(self, signum: int):
        super().__init__(signal.Signals(signum).name)
        self.signum = signum


class Signals:
    """While entered, SIGINT, SIGTERM and SIGHUP are recorded (``received``, the first one) and raise Interrupted only
    inside ``released()``: everywhere else (starting the broker and keeping its process, stopping it) they wait, so
    neither is cut short."""

    CAUGHT = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)

    def __init__(self):
        self.received: int | None = None
        self._released = False
        self._previous = {}

    def __enter__(self) -> Signals:
        self._previous = {signum: signal.signal(signum, self._receive) for signum in self.CAUGHT}
        return self

    def __exit__(self, *exc) -> None:
        for signum, handler in self._previous.items():
            signal.signal(signum, handler)

    def _receive(self, signum, _frame) -> None:
        self.received = self.received or signum
        if self._released:
            raise Interrupted(signum)

    @contextlib.contextmanager
    def released(self):
        if self.received:
            raise Interrupted(self.received)
        self._released = True
        try:
            yield
        finally:
            self._released = False


def folder_bytes(folder: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(folder):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def destination(environ) -> Path:
    """The folder the install writes: HERMRETRO_DEPS_ROOT, resolved from this process's folder; with none, in
    GitHub Actions the default (a throwaway machine's home is the run's own), anywhere else the development one."""
    named = environ.get("HERMRETRO_DEPS_ROOT")
    if named:
        return Path(named).resolve()
    return paths.DEPS_ROOT if environ.get("GITHUB_ACTIONS") == "true" else dev_toolchain.DEPS_ROOT


def refusal(environ, deps: Path) -> str | None:
    """Why this run must not start, or None: nothing may move the toolchain out of the destination."""
    if environ.get("GB_STUDIO_SETUP_ROOT"):
        return (
            f"refusing to install into {environ['GB_STUDIO_SETUP_ROOT']}: GB_STUDIO_SETUP_ROOT would move the "
            f"toolchain out of {deps}\nFIX: unset GB_STUDIO_SETUP_ROOT (the toolchain goes in {deps / 'toolchain'})"
        )
    return None


def find_node() -> str:
    node = paths.find_node()
    if not node.get("ok"):
        raise client.BrokerUnavailable(f"Node.js {paths.NODE_REQUIRED_MAJOR} or newer is required but was not found")
    return node["path"]


def connect(state: Path, process: subprocess.Popen) -> client.BrokerClient:
    """This run's broker, once it answers; nothing else can be in its new folder."""
    deadline = time.monotonic() + START_SECONDS
    while True:
        broker, error = client.try_connect(state, deadline=deadline)
        if broker is not None:
            # The start deadline bounds connecting only, as in client.ensure_broker; the install runs for minutes.
            broker.startup_deadline = None
            return broker
        if process.poll() is not None:
            raise client.BrokerUnavailable(f"the broker exited with {process.returncode}: {error}")
        if time.monotonic() >= deadline:
            raise client.BrokerUnavailable(f"the broker did not answer in {START_SECONDS} s: {error}")
        time.sleep(0.1)


def wait_for_install(broker, toolchain: Path) -> int:
    started = broker.request({"op": "install_start"})
    if not started.get("ok"):
        print("install did not start: " + json.dumps(started)[:600], file=sys.stderr)
        return 1
    began = time.monotonic()
    last = None
    progress, moved = None, time.monotonic()
    while True:
        status = broker.request({"op": "install_status"})
        install = status.get("install") or {}
        state = install.get("state")
        line = f"{state} {round(100 * (install.get('fraction') or 0))}% {install.get('current') or ''}".strip()
        if line != last:
            print(f"{time.monotonic() - began:6.0f} s  {line}", flush=True)
            last = line
        if state in ("done", "failed"):
            break
        now = (
            install.get("fraction"),
            install.get("downloaded_bytes"),
            install.get("current"),
            folder_bytes(toolchain) // 1_000_000,
        )
        if now != progress:
            progress, moved = now, time.monotonic()
        elif time.monotonic() - moved > STALL_SECONDS:
            print(f"install made no progress for {STALL_SECONDS} s: " + json.dumps(install)[:1500], file=sys.stderr)
            return 1
        if time.monotonic() - began > LIMIT_SECONDS:
            print("install did not finish in time", file=sys.stderr)
            return 1
        time.sleep(5)
    if state != "done":
        print("install failed: " + json.dumps(install)[:1500], file=sys.stderr)
        return 1
    return 0


def stop(process: subprocess.Popen | None) -> str | None:
    """Stop this run's broker and confirm it exited: None, or what went wrong. SIGTERM, which it answers the way
    it answers any polite signal (it closes its workers, an unfinished installer included, then exits), whether or
    not it is busy; SIGKILL after STOP_SECONDS."""
    if process is None or process.poll() is not None:
        return None
    process.terminate()
    try:
        process.wait(STOP_SECONDS)
        return None
    except subprocess.TimeoutExpired:
        process.kill()
    try:
        process.wait(KILL_SECONDS)
    except subprocess.TimeoutExpired:
        return f"the broker (pid {process.pid}) is still running after SIGKILL"
    return f"the broker did not stop in {STOP_SECONDS} s and was killed; its workers may still be running"


def prepare(toolchain: Path, signals: Signals) -> int:
    state = Path(tempfile.mkdtemp(prefix="hermretro-prepare-", dir=STATE_PARENT))
    process = broker = None
    code = 1
    try:
        with signals.released():
            node = find_node()
        process = client.spawn_broker(state, node, deadline=time.monotonic() + START_SECONDS)
        with signals.released():
            broker = connect(state, process)
            code = wait_for_install(broker, toolchain)
    except Interrupted as stopped:
        print(f"stopped by {stopped}", file=sys.stderr)
    except (client.BrokerUnavailable, OSError, ValueError) as error:
        print(f"the install could not be followed: {type(error).__name__}: {error}", file=sys.stderr)
    finally:
        if broker is not None:
            broker.close()
        problem = stop(process)
        if problem:
            print(problem, file=sys.stderr)
            code = 1
        if code == 0 and not signals.received:
            shutil.rmtree(state, ignore_errors=True)
        else:
            print(f"the broker's trace and logs: {state}", file=sys.stderr)
    return code


def main() -> int:
    deps = destination(os.environ)
    reason = refusal(os.environ, deps)
    if reason:
        print(reason, file=sys.stderr)
        return 2
    if os.environ.get("HERMRETRO_DEPS_ROOT") or deps != paths.DEPS_ROOT:
        # Absolute, as this process resolved it: the broker runs from the plugin folder and reads it again.
        os.environ["HERMRETRO_DEPS_ROOT"] = str(deps)
    print(f"toolchain: {deps / 'toolchain'}", flush=True)
    with Signals() as signals:
        code = prepare(deps / "toolchain", signals)
    return 128 + signals.received if signals.received else code


if __name__ == "__main__":
    sys.exit(main())

"""The sandbox: a private Hermes that loads this checkout, a scripted model and a headless browser on its Webapp.

Everything lives in `.dev/sandbox/` of this checkout: `hermes/` is the sandbox's Hermes home (its default profile
and a `hermretro` profile made by the plugin's own setup), with the toolchain reused from the real Hermes home
through a link. Nothing in the real Hermes home is changed, no sign-in is copied and no window is opened: the
processes get no display and the browser is headless.
Standard library only; development only; Linux and macOS.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import local_hermes as hermes
import studio_sync

TOP = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SANDBOX = TOP / ".dev" / "sandbox"
HOME = SANDBOX / "hermes"
PROFILE = HOME / "profiles" / hermes.STUDIO
CONFIG = SANDBOX / "sandbox.json"  # ports and the browser's token; also what marks the folder as the sandbox
PROCESSES = SANDBOX / "processes.json"
SCRIPTS = HERE / "scripts"
# Hermes's own dependency environment and caches for the sandbox's home (about 1.2 GB, made on first use): kept when
# the sandbox's state is cleared or restored, and never put in a snapshot.
HEAVY = ("installs", "cache")
# The only parts of the caller's environment the sandbox's processes get: no keys or tokens, and no display, so
# nothing they start can open a window.
KEEP_ENV = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TERM", "TMPDIR", "XDG_RUNTIME_DIR", "SHELL")
# What each process's command line contains, checked before it is stopped.
MARKERS = {"model": "script_model.py", "gateway": "gateway run", "browser": "studio_browser.mjs"}


class StudioError(Exception):
    """Something the sandbox cannot do; the message ends with what to run."""


def runtime_dir() -> Path:
    """The sandbox broker's folder: its own under the sandbox's home, or a short private one when that path is too
    long for a socket (the plugin's limit)."""
    run = HOME / hermes.PLUGIN / "run"
    if len(os.fsencode(run / "broker.sock")) <= 100:
        return run
    return Path(f"/tmp/hermretro-sandbox-{os.getuid()}-{hashlib.sha256(str(SANDBOX).encode()).hexdigest()[:10]}")


def environment(**extra: str) -> dict[str, str]:
    env = {key: os.environ[key] for key in KEEP_ENV if key in os.environ}
    return {**env, "HERMES_HOME": str(HOME), "HERMRETRO_RUNTIME_DIR": str(runtime_dir()), **extra}


def run_hermes(*args: str, home: Path = HOME, timeout: float = 600, check: bool = True) -> str:
    done = subprocess.run(
        ["hermes", *args],
        env=environment(HERMES_HOME=str(home)),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if done.returncode and check:
        tail = (done.stderr or done.stdout).strip().splitlines()[-3:]
        raise StudioError(f"`hermes {' '.join(args[:3])}` failed in the sandbox: {' '.join(tail)}")
    return done.stdout + done.stderr


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def settings() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.is_file() else {}


def create(desktop: Path) -> None:
    """A new sandbox: the two profiles set up the way a user's are, with the scripted model and the Webapp."""
    if shutil.which("hermes") is None:
        raise StudioError("Hermes is not installed here.\nFIX: install Hermes Agent, then run this again")
    # Hermes also loads its source checkout's .env whatever HERMES_HOME says: keys there would reach the sandbox.
    if (desktop.parents[1] / ".env").is_file():
        raise StudioError(
            f"{desktop.parents[1] / '.env'} would give the sandbox its keys\nFIX: move them to ~/.hermes/.env"
        )
    print("creating the sandbox (once)…", flush=True)
    HOME.mkdir(parents=True, exist_ok=True)
    ports = {"model": free_port(), "webapp": free_port()}
    run_hermes(
        "profile", "create", hermes.STUDIO, "--no-alias", "--no-skills", "--no-credentials", "--description",
        "hermretro: Game Boy Color development for the ModRetro Chromatic",
    )  # fmt: skip
    # The plugin's own setup of its profile (the step the page runs after Hermes creates it).
    sys.path.insert(0, str(TOP))
    from backend.setup import studio_profile

    studio_profile.finish(HOME, target=PROFILE, enabled=[], run=lambda home, *args: run_hermes(*args, home=home))
    # Installed in the default profile too, as a user's is: the page asks the profile the app is on first.
    (HOME / "plugins").mkdir(exist_ok=True)
    (HOME / "plugins" / hermes.PLUGIN).symlink_to(TOP, target_is_directory=True)
    run_hermes("plugins", "enable", hermes.PLUGIN)
    for home in (HOME, PROFILE):
        for key, value in (
            ("model.provider", "custom"),
            ("model.default", "script"),
            ("model.base_url", f"http://127.0.0.1:{ports['model']}/v1"),
            ("model.context_length", "128000"),
            ("auxiliary.title_generation.enabled", "false"),
        ):
            run_hermes("config", "set", key, value, home=home)
        with (home / ".env").open("a", encoding="utf-8") as env_file:
            env_file.write("OPENAI_API_KEY=sandbox\n")  # the custom endpoint wants a key; the model ignores it
    for key, value in (("webapp.enabled", "true"), ("webapp.port", str(ports["webapp"])), ("onboarding.run", "false")):
        run_hermes("config", "set", key, value)
    # The toolchain (2.4 GB) is the real one's, read through a link; the sandbox's own install records stay in its
    # own .cache. Without a real toolchain the Setup page offers to install one, which then lands in the sandbox.
    toolchain = hermes.hermes_root() / hermes.PLUGIN / ".cache" / "toolchain"
    (HOME / hermes.PLUGIN / ".cache").mkdir(parents=True, exist_ok=True)
    if toolchain.is_dir():
        (HOME / hermes.PLUGIN / ".cache" / "toolchain").symlink_to(toolchain, target_is_directory=True)
    (SANDBOX / "model.port").write_text(str(ports["model"]), encoding="utf-8")
    CONFIG.write_text(json.dumps({"ports": ports, "token": secrets.token_urlsafe(24)}, indent=2), encoding="utf-8")
    os.chmod(CONFIG, 0o600)


# -- processes ----------------------------------------------------------------------------------------------------


def process(pid: int) -> tuple[str | None, str]:
    """An exact mark of when ``pid`` started, and its command line now; None and "" when it is gone (an exited child
    nobody reaped yet, a zombie, counts as gone). Linux: the start tick in /proc (ps's lstart is the clock minus the
    uptime there, so one process can read a second apart). macOS: ps's lstart in the C locale, which it reads from the
    process's own start time."""
    proc = Path(f"/proc/{pid}")
    if proc.is_dir():
        try:
            state, *fields = (proc / "stat").read_text().rsplit(")", 1)[1].split()
            command = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace").strip()
        except (OSError, ValueError):
            return None, ""
        return (f"tick:{fields[18]}", command) if state != "Z" and len(fields) > 18 else (None, "")
    plain = {**os.environ, "LC_ALL": "C"}
    row = subprocess.run(
        ["ps", "-ww", "-o", "lstart=", "-o", "stat=", "-o", "command=", "-p", str(pid)],
        capture_output=True,
        text=True,
        env=plain,
    )
    fields = row.stdout.split()
    if len(fields) < 7 or fields[5].startswith("Z"):
        return None, ""
    return f"lstart:{' '.join(fields[:5])}", " ".join(fields[6:])


def legacy_started(pid: int) -> str:
    """ps's lstart as the sandbox recorded it before marks were exact: in the caller's locale, as printed."""
    return subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()


def tracked() -> dict:
    return json.loads(PROCESSES.read_text(encoding="utf-8")) if PROCESSES.is_file() else {}


def alive(name: str, entry: dict | None = None) -> bool:
    """Whether the process the sandbox started as ``name`` (its record, else the one in processes.json) still runs.
    An exact start mark identifies it, together with the marker in its command line; that line may read empty for a
    moment while Node starts (it moves its arguments), which still counts as ours. The `hermes` launcher replaces
    itself, so only the marker is checked, not the whole line."""
    entry = entry if entry is not None else tracked().get(name)
    if not entry or not isinstance(entry.get("started"), str):
        return False
    started, command = process(entry["pid"])
    if started is None or (command and MARKERS[name] not in command):
        return False
    recorded = entry["started"]
    if recorded.startswith(("tick:", "lstart:")):
        return started == recorded
    # A record from before the marks were exact holds ps's lstart text, a second apart at best: compare it the way it
    # was made, and only with the marker actually seen.
    return bool(command) and legacy_started(entry["pid"]) == recorded


def start(name: str, argv: list[str], record: dict | None = None, **extra: str) -> None:
    (SANDBOX / "logs").mkdir(exist_ok=True)
    with open(SANDBOX / "logs" / f"{name}.log", "ab") as log:
        child = subprocess.Popen(
            argv,
            cwd=TOP,
            env=environment(**extra),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    entries = tracked()
    entries[name] = {"pid": child.pid, "started": process(child.pid)[0], **(record or {})}
    PROCESSES.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def stop(name: str) -> None:
    """Stop the process (and its process group) only when it is still the one the sandbox started."""
    entry = tracked().get(name)
    if alive(name, entry):
        pid = entry["pid"]
        os.killpg(pid, signal.SIGTERM)
        for _ in range(40):
            if process(pid)[0] is None:
                break
            time.sleep(0.25)
        else:
            if alive(name, entry):  # still the same process, not a new one that took its pid
                os.killpg(pid, signal.SIGKILL)
    entries = tracked()
    entries.pop(name, None)
    if SANDBOX.is_dir():
        PROCESSES.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def stop_broker() -> None:
    """The plugin's broker starts in its own session: stop the sandbox's, the one whose command line names the
    sandbox's broker folder (its engine workers exit with it)."""
    rows = subprocess.run(["ps", "-A", "-ww", "-o", "pid=,command="], capture_output=True, text=True).stdout
    for row in rows.splitlines():
        pid, _, command = row.strip().partition(" ")
        if "-m backend.broker " in command and f" --state-dir {runtime_dir()} " in f"{command} ":
            try:
                os.kill(int(pid), signal.SIGTERM)
            except ProcessLookupError:
                pass


def wait_for(check, what: str, timeout: float = 90) -> None:
    end = time.monotonic() + timeout
    while not check():
        if time.monotonic() > end:
            raise StudioError(f"{what} did not come up within {timeout:.0f} s\nFIX: read {SANDBOX / 'logs'}")
        time.sleep(0.5)


def answers(url: str) -> bool:
    try:
        urllib.request.urlopen(url, timeout=2).close()
    except urllib.error.HTTPError:
        return True  # it answered
    except OSError:
        return False
    return True


def up(desktop: Path, sync: bool = True) -> None:
    """Start what is not running, on current code: this checkout brought up to dev when it is the dev branch, Hermes's
    Webapp rebuilt when Hermes changed, and the gateway restarted when the backend or Hermes changed since it started."""
    moved = studio_sync.sync_checkout() if sync else False
    if not CONFIG.is_file():
        create(desktop)
    link = HOME / "plugins" / hermes.PLUGIN
    if link.is_symlink() and link.resolve() != TOP.resolve():
        hermes.point(link, TOP)  # a mockup round that stopped early left its overlay linked
    ports = settings()["ports"]
    # A no-op (about a second) when the Webapp matches the Hermes on disk; the first build takes a few minutes.
    run_hermes("webapp", "--build-only", timeout=1800)
    backend = studio_sync.stamp(studio_sync.BACKEND, desktop)
    restarted = alive("gateway") and tracked()["gateway"].get("code") != backend
    if restarted:
        print("the backend or Hermes changed since the sandbox's gateway started: restarting it")
        stop("gateway")
        stop_broker()
    if not alive("model"):
        names = [
            f"GAMES={HOME / hermes.PLUGIN / 'games'}",
            f"ART={SCRIPTS / 'art'}",
            f"ENGINE={TOP / 'engine' / 'modretro-chromatic'}",
        ]
        start(
            "model", [sys.executable, str(HERE / "script_model.py"), str(SANDBOX / "model.port"), str(SCRIPTS), *names]
        )
    if not alive("gateway"):
        start("gateway", ["hermes", "gateway", "run", "--external-supervisor"], record={"code": backend})
    wait_for(lambda: answers(f"http://127.0.0.1:{ports['webapp']}/"), "the sandbox's gateway")
    if alive("browser") and (moved or restarted):
        call("reload")
    if not alive("browser"):
        (SANDBOX / "browser.port").unlink(missing_ok=True)
        start(
            "browser",
            ["node", str(HERE / "studio_browser.mjs"), str(SANDBOX), str(desktop)],
            STUDIO_TOKEN=settings()["token"],
        )
        wait_for(lambda: (SANDBOX / "browser.port").is_file() or not alive("browser"), "the sandbox's browser")
        if not alive("browser"):
            log = (SANDBOX / "logs" / "browser.log").read_text(encoding="utf-8", errors="replace")
            raise StudioError(f"the sandbox's browser stopped:\n{log.strip()[-1500:]}")
    print(f"sandbox up: Webapp on 127.0.0.1:{ports['webapp']}, model on {ports['model']} ({SANDBOX})")


def down() -> None:
    for name in ("browser", "gateway", "model"):
        stop(name)
    stop_broker()


def reset() -> None:
    """Stop everything and remove the sandbox: only the folder this tool made (it holds sandbox.json)."""
    down()
    if SANDBOX.is_dir():
        if not CONFIG.is_file():
            raise StudioError(f"{SANDBOX} has no sandbox.json, so it is not removed\nFIX: look at it, then remove it")
        shutil.rmtree(SANDBOX)  # links (the toolchain, the plugin) are removed, never followed
    print("sandbox removed")


def remove(path: Path) -> None:
    """A file, a link (never followed) or a folder with everything in it."""
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)  # links inside are removed, never followed
    else:
        path.unlink()


def clear_state() -> None:
    """Stop everything and remove the sandbox's state, keeping Hermes's dependency environment (HEAVY) and the
    snapshots, so the next `up` creates it again quickly."""
    down()
    if not CONFIG.is_file():
        return
    for path in SANDBOX.iterdir():
        if path.name not in {HOME.name, "snapshots"}:
            remove(path)
    for path in HOME.iterdir():
        if path.name not in HEAVY:
            remove(path)


def reload() -> None:
    """The backend half: re-import the plugin in the sandbox's gateway (both profiles), then reopen the page."""
    for profile in ("default", hermes.STUDIO):
        hermes.reload(HOME, profile)
    call("reload")


def call(verb: str, **args) -> dict:
    """One browser command (`python tools/dev ui`)."""
    port_file = SANDBOX / "browser.port"
    if not (alive("browser") and port_file.is_file()):
        raise StudioError("the sandbox is not up\nFIX: python tools/dev studio up")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port_file.read_text().strip()}/do",
        data=json.dumps({"verb": verb, **args}).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-studio-token": settings()["token"]},
    )
    try:
        with urllib.request.urlopen(request, timeout=float(args.get("timeout", 600)) + 30) as answer:
            return json.loads(answer.read())
    except urllib.error.HTTPError as error:
        raise StudioError(json.loads(error.read() or b"{}").get("error", str(error))) from error


def release() -> None:
    """End a scripted turn that waits (`"hold": true`), such as the `working` scenario's."""
    port = settings()["ports"]["model"]
    urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/control/release", data=b"{}"), timeout=5)

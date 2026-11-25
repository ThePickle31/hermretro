"""python tools/dev <command>: the development loop against the Hermes on this machine.

  setup             make this checkout ready: the pinned npm tools and ruff (does only what is missing)
  status            which checkout each profile loads, and whether a gateway is running
  live [PATH|main]  make this checkout (or PATH, or the main checkout) the one Hermes loads, and reload it
  reload            reload the plugin in the running gateway after a backend change (no restart)
  rpc METHOD [JSON] call one gateway RPC; a bare name means plugin.hermretro.<name>
  watch             rebuild the page on every save, keep Hermes Desktop's copy current and serve the
                    browser preview, live against the real gateway (prints its address)
  studio VERB       the sandbox: a private Hermes on this checkout with a scripted model and a headless
                    browser (up, down, reset, status, reload, seed, save, load, scenario, release)
  ui VERB           drive the sandbox's page and take screenshots (shot, text, go, click, type, say, ...)
  mockup FOLDER     shoot a round of mockups in the sandbox, in every state, width and theme, and write
                    FOLDER/gallery.html
  bench VERB        the benchmark: every game in tools/dev/bench_games/ made at once by a one-shot chat in the
                    studio profile (run, which waits for them all), what each cost (report), and each game against
                    an earlier run's (compare: exit 1 when one got clearly worse, 2 when one could not be judged)

Standard library only; Linux and macOS.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench  # noqa: E402 - this folder, put on the path just above
import bench_compare  # noqa: E402
import local_hermes as hermes  # noqa: E402
import mockup  # noqa: E402
import studio  # noqa: E402
import studio_states  # noqa: E402

TOP = Path(__file__).resolve().parents[2]
BUNDLE = TOP / "desktop" / "plugin.js"


def main_checkout() -> Path:
    """The checkout whose `.git` the worktrees share."""
    common = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=TOP,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return Path(common).parent


def desktop_source(given: str | None) -> Path:
    """Hermes Desktop's source folder, whose built stylesheet and esbuild the preview uses."""
    if given:
        return Path(given).expanduser().resolve()
    return (
        Path(os.environ.get("HERMES_SOURCE", Path.home() / ".hermes" / "hermes-agent")).expanduser()
        / "apps"
        / "desktop"
    ).resolve()


def cmd_setup(args) -> int:
    lock = TOP / "tools" / "npm" / "package-lock.json"
    installed = TOP / "tools" / "npm" / "node_modules" / ".package-lock.json"
    if not installed.is_file() or installed.stat().st_mtime < lock.stat().st_mtime:
        subprocess.run(
            ["npm", "ci", "--prefix", "tools/npm", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=TOP, check=True
        )
    subprocess.run([sys.executable, "tools/py/setup.py"], cwd=TOP, check=True)
    print(f"ready: {TOP}")
    return 0


def cmd_status(args) -> int:
    root = hermes.hermes_root()
    links = hermes.plugin_links(root)
    for profile in hermes.loading_profiles(root):
        print(f"{profile}: {links[profile].resolve() if profile in links else 'an installed copy'}")
    print(f"gateway: {'running' if hermes.control_socket(root, root) else 'not running'}")
    return 0


def cmd_live(args) -> int:
    root = hermes.hermes_root()
    target = main_checkout() if args.path == "main" else Path(args.path).expanduser().resolve() if args.path else TOP
    if not hermes.is_checkout(target):
        print(f"{target} is not a hermretro checkout (plugin.yaml, __init__.py and desktop/plugin.js)", file=sys.stderr)
        return 1
    links = hermes.plugin_links(root)
    if hermes.STUDIO not in links:
        print(f"the {hermes.STUDIO} profile does not load hermretro through a link: nothing to point", file=sys.stderr)
        return 1
    # Every linked profile moves together (two backends in one gateway would fight over the one broker), or none does.
    before = {profile: link.resolve() for profile, link in links.items()}
    try:
        for link in links.values():
            hermes.point(link, target)
    except OSError as error:
        for profile, link in links.items():
            hermes.point(link, before[profile])
        print(f"could not move the links, so none moved: {error}", file=sys.stderr)
        return 1
    print(f"live: {target}")
    # Every linked profile reloads, also when it was already linked here: a reload an earlier run missed is redone.
    failed = reload_profiles(root, list(links))
    if hermes.refresh_desktop(root, target):
        print("Hermes Desktop: page updated")
    return failed


def reload_profiles(root: Path, profiles: list[str]) -> int:
    failed = 0
    for profile in profiles:
        try:
            result = hermes.reload(root, profile)
        except hermes.GatewayError as error:
            print(f"{profile}: {error}", file=sys.stderr)
            failed = 1
            continue
        if hermes.PLUGIN not in result.get("plugins", []):
            print(
                f"{profile}: reloaded, but hermretro did not load there (enabled? hermes -p {profile} plugins list)",
                file=sys.stderr,
            )
            failed = 1
            continue
        # The gateway's summary of what applies now and what waits for the next chat (tools and the prompt).
        ours = next((item for item in result.get("activations", []) if item.get("name") == hermes.PLUGIN), {})
        deferred = ours.get("deferred", {})
        waiting = [f"{len(names)} {kind}" for kind, names in deferred.items() if names]
        print(f"{profile}: reloaded" + (f"; from the next chat: {', '.join(waiting)}" if waiting else ""))
    return failed


def cmd_reload(args) -> int:
    root = hermes.hermes_root()
    return reload_profiles(root, args.profile or hermes.loading_profiles(root))


def cmd_rpc(args) -> int:
    method = args.method if "." in args.method else f"plugin.hermretro.{args.method}"
    script = TOP / "tools" / "debug" / "gateway_rpc.mjs"
    return subprocess.run(["node", str(script), args.profile, method, args.params]).returncode


def build_preview(out: Path, desktop: Path) -> bool:
    done = subprocess.run(
        ["node", "tests/page/preview/build.mjs", str(out), str(desktop)], cwd=TOP, capture_output=True, text=True
    )
    if done.returncode:
        print(f"preview build failed:\n{(done.stderr or done.stdout).strip()[-1500:]}", file=sys.stderr)
    return done.returncode == 0


def settled_mtime(path: Path) -> float:
    """``path``'s modification time once it has stopped changing (the bundler writes two files in turn)."""
    while True:
        first = path.stat().st_mtime
        time.sleep(0.3)
        if path.stat().st_mtime == first:
            return first


def cmd_watch(args) -> int:
    root = hermes.hermes_root()
    desktop = desktop_source(args.desktop)
    if not (desktop / "dist" / "assets").is_dir():
        print(f"{desktop} is not a built Hermes Desktop source (pass --desktop or set HERMES_SOURCE)", file=sys.stderr)
        return 1
    out = TOP / ".dev" / "preview"
    subprocess.run(["node", "tools/bundle/bundle.mjs"], cwd=TOP, check=True)
    if not build_preview(out, desktop):
        return 1
    # Stopped with SIGTERM too (a background job's stop), the children go with it.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    children: list[subprocess.Popen] = []
    try:
        children.append(subprocess.Popen(["node", "tools/bundle/bundle.mjs", "--watch"], cwd=TOP))
        server = ["node", "tools/dev/preview_server.mjs", str(out), str(desktop / "dist" / "assets"), str(args.port)]
        children.append(subprocess.Popen(server, cwd=TOP))
        seen = BUNDLE.stat().st_mtime
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
            if BUNDLE.stat().st_mtime == seen:
                continue
            seen = settled_mtime(BUNDLE)
            built = build_preview(out, desktop)
            live = hermes.live_checkout(root) == TOP and hermes.refresh_desktop(root, TOP)
            print(
                f"rebuilt: {'preview' if built else 'preview failed'}{', Hermes Desktop updated' if live else ''}",
                flush=True,
            )
        print(
            "a child stopped: " + ", ".join(f"{' '.join(child.args[:2])} exited {child.poll()}" for child in children),
            file=sys.stderr,
        )
        return 1
    except (KeyboardInterrupt, SystemExit):
        return 0
    finally:
        for child in children:
            child.terminate()
        for child in children:
            child.wait(10)


def cmd_studio(args) -> int:
    desktop = desktop_source(args.desktop)
    verb, name = args.verb, args.name
    if verb in {"save", "load", "scenario"} and not name:
        print(f"studio {verb} needs a name", file=sys.stderr)
        return 1
    if verb == "up":
        studio.up(desktop)
    elif verb == "down":
        studio.down()
        print("sandbox stopped")
    elif verb == "reset":
        studio.reset()
    elif verb == "reload":
        studio.reload()
    elif verb == "release":
        studio.release()
    elif verb == "seed":
        studio_states.seed(desktop)
    elif verb == "save":
        studio_states.save(name, desktop)
    elif verb == "load":
        studio_states.load(name, desktop)
        print(f"loaded {name}")
    elif verb == "scenario":
        studio_states.scenario(name, desktop)
    else:  # status
        print(f"sandbox: {studio.SANDBOX if studio.CONFIG.is_file() else 'not created'}")
        for process in studio.MARKERS:
            print(f"{process}: {'running' if studio.alive(process) else 'stopped'}")
        print(f"snapshots: {', '.join(studio_states.snapshots()) or 'none'}")
        for scenario, (_, _, _, what) in studio_states.SCENARIOS.items():
            print(f"  scenario {scenario}: {what}")
    return 0


def cmd_ui(args) -> int:
    rest = args.args
    verb = args.verb
    if verb == "shot":
        result = studio.call("shot", name=rest[0] if rest else None, full=args.full, target=args.of)
    elif verb == "text":
        result = studio.call("text", target=rest[0] if rest else None)
    elif verb in {"go", "click"}:
        result = studio.call(verb, **{"page" if verb == "go" else "target": " ".join(rest)})
    elif verb == "type":
        result = studio.call("type", text=" ".join(rest), target=args.into, submit=args.submit)
    elif verb == "say":
        result = studio.call("say", text=" ".join(rest), wait=not args.no_wait)
    elif verb == "wait":
        result = studio.call("wait", target=" ".join(rest) or None, ms=args.ms)
    elif verb == "eval":
        result = studio.call("eval", js=" ".join(rest))
    elif verb == "resize":
        result = studio.call("resize", width=int(rest[0]), height=int(rest[1]) if len(rest) > 1 else None)
    elif verb == "theme":
        result = studio.call("theme", mode=rest[0] if rest else "dark")
    else:
        result = studio.call(verb)
    for key in ("file", "text", "url"):
        if key in result:
            print(result[key])
            return 0
    if result:
        print(json.dumps(result, indent=2))
    return 0


def listed(value: str | None) -> list[str]:
    """A comma-separated option as a list (empty when not given)."""
    return [item for item in (value or "").split(",") if item]


def cmd_mockup(args) -> int:
    folder = Path(args.folder).expanduser().resolve()
    if not (folder / "round.json").is_file():
        print(f"{folder} has no round.json", file=sys.stderr)
        return 1
    settings = json.loads((folder / "round.json").read_text(encoding="utf-8"))
    mockup.shoot(
        folder,
        desktop_source(args.desktop),
        states=listed(args.states) or settings.get("states") or ["builds"],
        widths=[int(width) for width in listed(args.widths) or settings.get("widths") or [1440]],
        themes=listed(args.themes) or settings.get("themes") or ["dark"],
        only=listed(args.only),
    )
    return 0


def cmd_bench(args) -> int:
    root = hermes.hermes_root()
    profile = root / "profiles" / hermes.STUDIO
    if args.verb == "report":
        if args.games:
            raise bench.BenchError("bench report takes no games (--run FOLDER or --sessions ID ...)")
        if args.against:
            raise bench.BenchError("--against is for bench compare")
        folder = None if args.sessions else Path(args.folder).resolve() if args.folder else bench.latest_run(bench.RUNS)
        print(bench.table(bench.reports(profile, folder, args.sessions)))
        return 0
    if args.verb == "compare":
        if args.games or args.sessions:
            raise bench.BenchError("bench compare takes no games or sessions (--run FOLDER, --against FOLDER)")
        folder = Path(args.folder).resolve() if args.folder else bench.latest_run(bench.RUNS)
        against = Path(args.against).resolve() if args.against else bench_compare.previous_run(folder)
        text, code = bench_compare.compare(profile, folder, against)
        print(text)
        return code
    if args.folder or args.sessions or args.against:
        raise bench.BenchError("--run and --sessions are for bench report, --run and --against for bench compare")
    prompts = bench.games(args.games)  # a bad name ends it before the gateway is asked or reloaded
    for needed in ("hermes", "node"):  # node asks the gateway which code it runs
        if shutil.which(needed) is None:
            raise bench.BenchError(f"needs {needed} on PATH")
    bench.current_gateway(root, hermes.STUDIO, TOP, lambda: reload_profiles(root, hermes.loading_profiles(root)))
    folder = bench.run(prompts, hermes.STUDIO, profile, bench.RUNS, TOP)
    try:
        print(bench.table(bench.reports(profile, folder)))
    except (bench.BenchError, sqlite3.Error) as error:
        raise bench.BenchError(f"{error}; the run is kept in {folder} (bench report --run {folder})") from error
    return 0


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(
        prog="python tools/dev", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = top.add_subparsers(dest="command", required=True)
    commands.add_parser("setup").set_defaults(run=cmd_setup)
    commands.add_parser("status").set_defaults(run=cmd_status)
    live = commands.add_parser("live")
    live.add_argument("path", nargs="?", help="a checkout, or `main` for the main checkout (default: this one)")
    live.set_defaults(run=cmd_live)
    reload = commands.add_parser("reload")
    reload.add_argument(
        "--profile", action="append", help="only this profile (repeatable; default: every one that loads hermretro)"
    )
    reload.set_defaults(run=cmd_reload)
    rpc = commands.add_parser("rpc")
    rpc.add_argument("method")
    rpc.add_argument("params", nargs="?", default="{}")
    rpc.add_argument("--profile", default=hermes.STUDIO)
    rpc.set_defaults(run=cmd_rpc)
    watch = commands.add_parser("watch")
    watch.add_argument("--port", type=int, default=0, help="the preview's port (default: a free one)")
    watch.add_argument("--desktop", help="Hermes Desktop's source folder (default $HERMES_SOURCE/apps/desktop)")
    watch.set_defaults(run=cmd_watch)
    sandbox = commands.add_parser("studio")
    sandbox.add_argument(
        "verb", choices=["up", "down", "reset", "status", "reload", "seed", "save", "load", "scenario", "release"]
    )
    sandbox.add_argument("name", nargs="?", help="the snapshot or scenario (save, load, scenario)")
    sandbox.add_argument("--desktop", help="Hermes Desktop's source folder (default $HERMES_SOURCE/apps/desktop)")
    sandbox.set_defaults(run=cmd_studio)
    ui = commands.add_parser("ui")
    ui.add_argument(
        "verb",
        choices=["shot", "text", "go", "click", "type", "say", "wait", "idle", "eval", "resize", "theme", "reload",
                 "errors", "url"],
    )  # fmt: skip
    ui.add_argument("args", nargs="*", help="what the verb takes: a name, a target, text, a size")
    ui.add_argument("--full", action="store_true", help="shot: the whole scrolling page")
    ui.add_argument("--of", help="shot: only this element (a selector, a button's name or text)")
    ui.add_argument("--into", help="type: the field to type into (default the message box)")
    ui.add_argument("--submit", action="store_true", help="type: press Enter after")
    ui.add_argument("--no-wait", action="store_true", help="say: return once sent, not when the turn ends")
    ui.add_argument("--ms", type=int, help="wait: this many milliseconds")
    ui.set_defaults(run=cmd_ui)
    round_ = commands.add_parser("mockup")
    round_.add_argument("folder", help="a round: round.json and mockups/*.jsx")
    round_.add_argument("--states", help="scenarios, comma-separated (default: round.json's, else builds)")
    round_.add_argument("--widths", help="page widths, comma-separated (default: round.json's, else 1440)")
    round_.add_argument("--themes", help="dark, light or both (default: round.json's, else dark)")
    round_.add_argument("--only", help="these mockups only (ids, comma-separated); today's page is always shot")
    round_.add_argument("--desktop", help="Hermes Desktop's source folder (default $HERMES_SOURCE/apps/desktop)")
    round_.set_defaults(run=cmd_mockup)
    benchmark = commands.add_parser("bench")
    benchmark.add_argument("verb", choices=["run", "report", "compare"])
    benchmark.add_argument("games", nargs="*", help="run: only the games whose name contains one of these")
    which = benchmark.add_mutually_exclusive_group()
    which.add_argument(
        "--run", dest="folder", help="report, compare: this run folder (default: the newest in notes/bench/)"
    )
    which.add_argument("--sessions", nargs="+", help="report: these session ids instead of a run")
    benchmark.add_argument(
        "--against",
        help="compare: this earlier run (default: the newest finished one before it with exactly its games)",
    )
    benchmark.set_defaults(run=cmd_bench)
    return top


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if shutil.which("node") is None and args.command in {"rpc", "watch", "setup", "studio", "ui", "mockup"}:
        print("needs Node.js 22 or newer on PATH", file=sys.stderr)
        return 1
    try:
        return args.run(args)
    except (studio.StudioError, bench.BenchError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

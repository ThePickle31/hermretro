"""python tools/dev <command>: the development loop against the Hermes on this machine.

  setup             make this checkout ready: the pinned npm tools and ruff (does only what is missing)
  status            which checkout each profile loads, and whether a gateway is running
  live [PATH|main]  make this checkout (or PATH, or the main checkout) the one Hermes loads, and reload it
  reload            reload the plugin in the running gateway after a backend change (no restart)
  rpc METHOD [JSON] call one gateway RPC; a bare name means plugin.hermretro.<name>
  watch             rebuild the page on every save, keep Hermes Desktop's copy current and serve the
                    browser preview, live against the real gateway (prints its address)

Docs: docs/dev/DEBUGGING.md, "The development loop". Standard library only; Linux and macOS.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import local_hermes as hermes  # noqa: E402 - this folder, put on the path just above

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
    return top


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if shutil.which("node") is None and args.command in {"rpc", "watch", "setup"}:
        print("needs Node.js 22 or newer on PATH", file=sys.stderr)
        return 1
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())

"""preview [--serve] [--out DIR] [--desktop DIR]: the page's browser preview, built, and served if asked.

Runs `node tests/page/preview/build.mjs <out> <desktop>` (docs/dev/TESTING.md, "Looking at the page"): the page
drawn with the installed Hermes Desktop's stylesheet, fonts and icons, from a stand-in SDK. <desktop> is a Hermes
Desktop source with its build (`apps/desktop` of $HERMES_SOURCE, default ~/.hermes/hermes-agent). The output goes
to <state>/preview unless --out names another folder; the path of its index.html is printed.
--serve serves it on 127.0.0.1 on a free port (the standard library's http.server, loopback only) until Ctrl+C;
the stylesheets the build links by their absolute path in the Desktop's dist/assets are served from there.
"""

from __future__ import annotations

import functools
import http.server
import posixpath
import urllib.parse
from pathlib import Path

from . import repo, state
from .doctor import hermes_source
from .output import OK, Failure

SCRIPT = "tests/page/preview/build.mjs"


def desktop_dir(given: str | None, source: Path | None = None) -> Path:
    """The Desktop folder, symlinks resolved either way: the build links its stylesheets by this path, and the
    server serves only the resolved assets folder, so both must name the same one."""
    folder = Path(given).expanduser() if given else (source or hermes_source()) / "apps" / "desktop"
    return folder.resolve()


class Handler(http.server.SimpleHTTPRequestHandler):
    """Files of the preview folder, plus the Desktop's built stylesheets at their absolute paths."""

    assets: Path = Path("/nonexistent")

    def translate_path(self, path: str) -> str:
        clean = posixpath.normpath(urllib.parse.unquote(urllib.parse.urlsplit(path).path))
        target = Path(clean)
        if self.assets.is_dir() and target.is_relative_to(self.assets) and ".." not in target.parts:
            return str(target)
        return super().translate_path(path)

    def log_message(self, format, *args):  # noqa: A002 — the base class's name; quiet: no line per request
        pass


def make_server(folder: Path, assets: Path) -> http.server.ThreadingHTTPServer:
    """A loopback server on a free port for ``folder`` (its port: server.server_address[1])."""
    handler = type("PreviewHandler", (Handler,), {"assets": assets.resolve()})
    return http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(handler, directory=str(folder)))


def build(ctx, out: Path, desktop: Path) -> Path:
    if not (desktop / "package.json").is_file() or not (desktop / "dist" / "assets").is_dir():
        raise Failure(
            f"{desktop} is not a built Hermes Desktop source (the preview uses its stylesheet and esbuild)",
            "set HERMES_SOURCE to a hermes-agent checkout and build its desktop app (cd apps/desktop && npm ci && "
            "npm run build), or pass --desktop <apps/desktop folder>",
        )
    command = ["node", SCRIPT, str(out), str(desktop)]
    runner = ctx.fakes.get("preview_run") or (lambda words, cwd: repo.run(words, cwd, timeout=300))
    code, stdout, stderr = runner(command, ctx.top)
    index = out / "index.html"
    if code or not index.is_file():
        text = (stderr or stdout).strip()
        fix = (
            "node tools/bundle/bundle.mjs (the preview draws the built bundle), then preview again"
            if "bundle.mjs" in text
            else f"run it yourself to see the whole error: {' '.join(command)}"
        )
        raise Failure(f"the preview build failed: {text[-600:] or f'exit {code}, no index.html'}", fix)
    return index


def run(ctx, serve: bool = False, out_dir: str | None = None, desktop: str | None = None) -> int:
    out = Path(out_dir).expanduser().resolve() if out_dir else state.root(ctx.top) / "preview"
    folder = desktop_dir(desktop, ctx.fakes.get("hermes_source"))
    index = build(ctx, out, folder)
    ctx.out.say(str(index))
    ctx.out.say(f"open: file://{index}?s=choice&mode=dark&p=home (p = home, setup, prompts, games, emulator)")
    ctx.out.set(path=str(index), out=str(out), desktop=str(folder))
    if not serve:
        return OK
    server = make_server(out, folder / "dist" / "assets")
    url = f"http://127.0.0.1:{server.server_address[1]}/index.html?s=choice&mode=dark&p=home"
    ctx.out.set(url=url)
    ctx.out.say(f"serving {out} on {url} (loopback only; Ctrl+C stops)")
    try:
        (ctx.fakes.get("preview_serve") or (lambda running: running.serve_forever()))(server)
    except KeyboardInterrupt:
        ctx.out.say("stopped")
    finally:
        server.server_close()
    return OK

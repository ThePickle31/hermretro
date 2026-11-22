"""Mockups shot in the sandbox: `python tools/dev mockup <round folder>`.

A round folder holds `round.json` and `mockups/*.jsx` (tools/dev/mockup_build.mjs says what they export). For every
state (a sandbox scenario), mockup (and today's page, `current`), width and theme, the page with that mockup in it
is shot in the sandbox's headless browser into `<round>/shots/`, and `<round>/gallery.html` shows them all (one
file, the pictures inside it). The sandbox's real page is put back at the end, also when a shot fails.

Standard library only; development only; Linux and macOS.
"""

from __future__ import annotations

import base64
import contextlib
import fcntl
import json
import re
import shutil
import subprocess
from pathlib import Path

import local_hermes as hermes
import studio
import studio_states

GALLERY = studio.HERE / "mockup_gallery.html"
# Hermes serves the page from the default profile's plugin link (its desktop/ folder) and copies it again whenever
# the bytes differ, so the mockups go in as an overlay: links to this checkout, except desktop/plugin.js.
LINK = studio.HOME / "plugins" / hermes.PLUGIN
OVERLAY = studio.SANDBOX / "mockup-plugin"
SWITCH = (
    "localStorage.setItem('hermes.plugin.hermretro.mockup', JSON.stringify({id}));"
    "window.dispatchEvent(new CustomEvent('hermretro-mockup', {{ detail: {id} }}))"
)


def titles(folder: Path, ids: list[str]) -> dict[str, str]:
    """Each mockup's `export const title = '…'`, else its id."""
    found = {"current": "Today"}
    for mockup in ids:
        source = next(folder.joinpath("mockups").glob(f"{mockup}.*")).read_text(encoding="utf-8")
        match = re.search(r"export const title\s*=\s*(['\"`])(.+?)\1", source)
        found[mockup] = match.group(2) if match else mockup
    return found


def label(mockup: str) -> str:
    """`b2-dock` -> `B2`: the short name before the first dash, as the gallery and the reply call it."""
    return "Now" if mockup == "current" else mockup.split("-")[0].upper()


def build(folder: Path) -> list[str]:
    out = studio.SANDBOX / "mockup-plugin.js"
    done = subprocess.run(
        ["node", str(studio.HERE / "mockup_build.mjs"), str(folder), str(out)], capture_output=True, text=True
    )
    if done.returncode:
        raise studio.StudioError(f"the mockups did not build:\n{(done.stderr or done.stdout).strip()[-2000:]}")
    return json.loads(done.stdout.strip().splitlines()[-1])["mockups"]


def install(page: Path) -> None:
    """Serve ``page`` as hermretro's page in the sandbox, and reopen it."""
    shutil.rmtree(OVERLAY, ignore_errors=True)
    OVERLAY.mkdir()
    for entry in studio.TOP.iterdir():
        if entry.name not in {"desktop", ".dev", ".git"}:
            (OVERLAY / entry.name).symlink_to(entry, target_is_directory=entry.is_dir())
    (OVERLAY / "desktop").mkdir()
    shutil.copyfile(page, OVERLAY / "desktop" / "plugin.js")
    hermes.point(LINK, OVERLAY)
    studio.call("reload")


def restore() -> None:
    """The sandbox serves this checkout's page again (also when the browser is gone: `up` reopens it)."""
    if LINK.is_symlink():
        hermes.point(LINK, studio.TOP)
    if studio.alive("browser"):
        studio.call("reload")
        studio.call("resize", width=1440, height=900)
        studio.call("theme", mode="dark")


@contextlib.contextmanager
def one_round():
    """One round at a time per checkout: rounds share the sandbox's browser, page and overlay."""
    lock = studio.TOP / ".dev" / "mockup.lock"
    lock.parent.mkdir(exist_ok=True)
    with lock.open("w") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise studio.StudioError("another mockup round is running in this checkout's sandbox") from error
        yield


def shoot(folder: Path, desktop: Path, *, states: list[str], widths: list[int], themes: list[str], only: list[str]):
    with one_round():
        # The round's one sync with dev: the bundle and every shot come from the same code.
        studio.up(desktop)
        if not studio_states.current(desktop):  # seeding clears the sandbox's folder: before the build lands in it
            studio_states.seed(desktop)
        ids = build(folder)
        unknown = sorted(set(only) - set(ids))
        if unknown:
            raise studio.StudioError(
                f"no mockup {', '.join(unknown)} in {folder / 'mockups'} (there: {', '.join(ids)})"
            )
        variants = ["current", *[mockup for mockup in ids if not only or mockup in only]]
        names = titles(folder, ids)
        # Shot into a folder of their own; the last round's pictures are replaced only once every shot is taken.
        staged = folder / "shots.new"
        shutil.rmtree(staged, ignore_errors=True)
        staged.mkdir()
        entries = []
        page = studio.SANDBOX / "mockup-plugin.js"
        try:
            for state in states:
                studio_states.scenario(state, desktop, before_turn=lambda: install(page), sync=False)
                for variant in variants:
                    studio.call("eval", js=SWITCH.format(id=json.dumps(variant)))
                    for theme in themes:
                        studio.call("theme", mode=theme)
                        for width in widths:
                            studio.call("resize", width=width, height=900)
                            studio.call("wait", ms=700)
                            name = f"{variant}.{state}.{width}.{theme}"
                            shutil.move(studio.call("shot", name=f"mockup-{name}")["file"], staged / f"{name}.png")
                            entries.append(
                                {"file": f"{name}.png", "mockup": variant, "label": label(variant),
                                 "title": names[variant], "state": state, "width": width, "theme": theme}
                            )  # fmt: skip
                            print(folder / "shots" / f"{name}.png", flush=True)
        finally:
            restore()
        shutil.rmtree(folder / "shots", ignore_errors=True)
        staged.rename(folder / "shots")
        gallery(folder, [{**entry, "file": str(folder / "shots" / entry["file"])} for entry in entries])
        return entries


def gallery(folder: Path, entries: list[dict]) -> Path:
    """One HTML file with every picture inside it: a grid by mockup and state, and a viewer to page and zoom."""
    shown = [
        {**entry, "src": "data:image/png;base64," + base64.b64encode(Path(entry["file"]).read_bytes()).decode()}
        for entry in entries
    ]
    page = GALLERY.read_text(encoding="utf-8")
    page = page.replace("__ROUND__", folder.name).replace("__DATA__", json.dumps(shown).replace("</", "<\\/"))
    out = folder / "gallery.html"
    out.write_text(page, encoding="utf-8")
    print(out)
    return out

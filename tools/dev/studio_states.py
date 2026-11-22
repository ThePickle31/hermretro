"""The sandbox's saved states: snapshots of its Hermes home and browser storage, the seed that makes them from the
scripts in `scripts/`, and the scenarios built on them (some end with a live turn: working, a question).

Standard library only; development only; Linux and macOS.
"""

from __future__ import annotations

import shutil
import tarfile
from pathlib import Path

import studio

SNAPSHOTS = studio.SANDBOX / "snapshots"
BROWSER_STATE = studio.SANDBOX / "browser-state.json"
# The seed: messages sent in order (each matches a script in scripts/), and the snapshot saved after each group.
SEED = (
    ("new-game", ()),
    ("first-build", ("Make a cozy workshop where a little robot fixes toys.",)),
    ("builds", ("Make the robot brighter.", "Add calm background music.")),
)
# name -> (snapshot, message sent live after loading it or None, text to wait for, what it shows)
SCENARIOS = {
    "new-game": ("new-game", None, None, "Build's New Game screen, no games yet"),
    "first-build": ("first-build", None, None, "one game, built once and ready to play"),
    "builds": ("builds", None, None, "three builds: an art edit (before/after) and a failed build last"),
    "working": ("builds", "Give the robot a dash.", "Working", "a turn under way (ends with `studio release`)"),
    "question": ("builds", "Add a morning bell.", "When should the bell ring?", "a question card waiting"),
}


def snapshots() -> list[str]:
    return sorted(path.name.removesuffix(".tar.gz") for path in SNAPSHOTS.glob("*.tar.gz"))


def save(name: str, desktop: Path) -> None:
    """Stop the gateway (its database is then settled), pack the home and the browser storage, start again."""
    studio.call("save")
    studio.stop("browser")
    studio.stop("gateway")
    studio.stop_strays()
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    with tarfile.open(SNAPSHOTS / f"{name}.tar.gz", "w:gz") as archive:
        for path in studio.HOME.iterdir():
            if path.name not in studio.HEAVY:  # links (toolchain, plugin) are stored as links
                archive.add(path, arcname=f"hermes/{path.name}")
        if BROWSER_STATE.is_file():
            archive.add(BROWSER_STATE, arcname=BROWSER_STATE.name)
    studio.up(desktop)
    print(f"saved {name}")


def load(name: str, desktop: Path) -> None:
    archive_path = SNAPSHOTS / f"{name}.tar.gz"
    if not archive_path.is_file():
        known = ", ".join(snapshots()) or "none yet"
        raise studio.StudioError(f"no snapshot {name!r} (saved: {known})\nFIX: python tools/dev studio seed")
    if studio.alive("model"):
        studio.release()  # a held scripted turn (the working scenario) ends instead of waiting forever
    studio.stop("browser")
    studio.stop("gateway")
    studio.stop_strays()
    for path in studio.HOME.iterdir():
        if path.name not in studio.HEAVY:
            studio.remove(path)
    BROWSER_STATE.unlink(missing_ok=True)
    with tarfile.open(archive_path) as archive:
        archive.extractall(studio.SANDBOX, filter="tar")
    studio.up(desktop)


def scenario(name: str, desktop: Path) -> None:
    if name not in SCENARIOS:
        raise studio.StudioError(f"no scenario {name!r}; one of: {', '.join(SCENARIOS)}")
    snapshot, message, wait_for, _ = SCENARIOS[name]
    load(snapshot, desktop)
    if message:
        studio.call("say", text=message, wait=False)
        studio.call("wait", target=wait_for, timeout=120)
    print(f"scenario {name} ready")


def seed(desktop: Path) -> None:
    """A fresh sandbox, then every seed message through the real page, tools and engine, saving as it goes."""
    studio.clear_state()
    shutil.rmtree(SNAPSHOTS, ignore_errors=True)
    studio.up(desktop)
    # Onboarding is done and the Chromatic skipped, as after "Start making games".
    studio.call("storage", key="setup", value={"onboarded": True, "hardwareSkipped": True})
    studio.call("reload")
    for name, messages in SEED:
        for message in messages:
            print(f"sending: {message}", flush=True)
            studio.call("say", text=message, timeout=900)
        save(name, desktop)
    print(f"seeded: {', '.join(snapshots())}")

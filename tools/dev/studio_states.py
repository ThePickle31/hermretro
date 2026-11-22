"""The sandbox's saved states: snapshots of its Hermes home and browser storage, the seed that makes them from the
scripts in `scripts/`, and the scenarios built on them (some end with a live turn: working, a question).

Standard library only; development only; Linux and macOS.
"""

from __future__ import annotations

import json
import re
import shutil
import tarfile
from pathlib import Path

import studio
import studio_sync

SNAPSHOTS = studio.SANDBOX / "snapshots"
BROWSER_STATE = studio.SANDBOX / "browser-state.json"
SEEDED = SNAPSHOTS / "seed.json"  # what made the snapshots (studio_sync.SEED_INPUTS): seeded again when it changes
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,40}")
# The seed: messages sent in order (each matches a script in scripts/), the snapshot saved after them, and text the
# page must then show (so a failed step stops the seed where it happened).
SEED = (
    ("new-game", (), "What are we making?"),
    ("first-build", ("Make a cozy workshop where a little robot fixes toys.",), "Build #1"),
    ("builds", ("Make the robot brighter.", "Add calm background music."), "A brighter robot"),
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


def checked(name: str) -> str:
    if not NAME.fullmatch(name):
        raise studio.StudioError(f"{name!r} is not a snapshot name: lowercase letters, digits and dashes")
    return name


def save(name: str, desktop: Path) -> None:
    """Stop the gateway (its database is then settled), pack the home and the browser storage, start again."""
    checked(name)
    studio.call("save")
    studio.stop("browser")
    studio.stop("gateway")
    studio.stop_broker()
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    with tarfile.open(SNAPSHOTS / f"{name}.tar.gz", "w:gz") as archive:
        for path in studio.HOME.iterdir():
            if path.name not in studio.HEAVY:  # links (toolchain, plugin) are stored as links
                archive.add(path, arcname=f"hermes/{path.name}")
        if BROWSER_STATE.is_file():
            archive.add(BROWSER_STATE, arcname=BROWSER_STATE.name)
    studio.up(desktop)
    print(f"saved {name}")


def current(desktop: Path) -> bool:
    """Whether the snapshots were made by the backend, Hermes and seed scripts there are now."""
    try:
        made_by = json.loads(SEEDED.read_text(encoding="utf-8"))["code"]
    except (OSError, ValueError, KeyError):
        return False
    return made_by == studio_sync.stamp(studio_sync.SEED_INPUTS, desktop)


def load(name: str, desktop: Path) -> None:
    archive_path = SNAPSHOTS / f"{checked(name)}.tar.gz"
    if snapshots() and not current(desktop):
        print("the snapshots were made by older code (backend, Hermes or the seed scripts changed): seeding again")
        seed(desktop)
    if not archive_path.is_file():
        known = ", ".join(snapshots()) or "none yet"
        raise studio.StudioError(f"no snapshot {name!r} (saved: {known})\nFIX: python tools/dev studio seed")
    if studio.alive("model"):
        studio.release()  # a held scripted turn (the working scenario) ends instead of waiting forever
    # Unpacked aside first: a damaged snapshot fails here and the current state stays as it is.
    restore = studio.SANDBOX / ".restore"
    shutil.rmtree(restore, ignore_errors=True)
    with tarfile.open(archive_path) as archive:
        archive.extractall(restore, filter="tar")
    if not (restore / "hermes").is_dir():
        raise studio.StudioError(f"{archive_path} holds no Hermes home\nFIX: python tools/dev studio seed")
    studio.stop("browser")
    studio.stop("gateway")
    studio.stop_broker()
    for path in studio.HOME.iterdir():
        if path.name not in studio.HEAVY:
            studio.remove(path)
    for path in (restore / "hermes").iterdir():
        path.replace(studio.HOME / path.name)
    BROWSER_STATE.unlink(missing_ok=True)
    if (restore / BROWSER_STATE.name).is_file():
        (restore / BROWSER_STATE.name).replace(BROWSER_STATE)
    shutil.rmtree(restore)
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
    for name, messages, shows in SEED:
        for message in messages:
            print(f"sending: {message}", flush=True)
            studio.call("say", text=message, timeout=900)
        try:
            studio.call("wait", target=shows, timeout=30)
        except studio.StudioError as error:
            raise studio.StudioError(f"seeding {name}: the page does not show {shows!r} ({error})") from error
        save(name, desktop)
    SEEDED.write_text(json.dumps({"code": studio_sync.stamp(studio_sync.SEED_INPUTS, desktop)}), encoding="utf-8")
    print(f"seeded: {', '.join(snapshots())}")

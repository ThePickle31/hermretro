"""The game folder: one layout every game has from the moment it is made, so it can later be published (the game
alone, or the game with its source) and updated without being reshaped. Standard library only.

    <games>/<Name>/
      game.json  cover.png  README.md  CHANGELOG.md  LICENSE  .gitignore   game: every publish
      build/game.gbc  (build/game.gb for a monochrome project)              game: its one ROM
      <name>.gbsproj  project/  assets/  plugins/  art/                     source: a publish with the source
      .hermretro/                                                           this machine's record, never published
      docs/ scratch/ and everything else (build/'s other files, captures/, …)  local, never published

A game installed without its source holds only the game files; ``game.json``'s ``rom`` names its ROM.

``ensure`` fills in what a game lacks and never moves or deletes anything; ``check`` reports what is wrong with it.
``.hermretro/identity.json`` keeps the game's id, so a hand edit of ``game.json`` cannot change it. What a publish
holds and records is ``release.py``'s.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

from ..system import paths
from . import game_card, licence
from .project import GAME_FILES, ROM_STEM, _json, canonical_rom, file_sha256, project_file, project_title

# What a publish with the source adds: the folders below and the project's .gbsproj.
SOURCE_FOLDERS = ("project", "assets", "plugins", "art")
# Folders hermretro, the engine and the agent write that stay on this machine (docs/ holds the agent's plans,
# scratch/ its helper scripts and working files).
LOCAL_FOLDERS = ("build", "captures", "save-states", "artifacts", "node_modules", "docs", "scratch", ".hermretro")
# The only names a game's ROM has.
GAME_ROMS = (ROM_STEM + ".gbc", ROM_STEM + ".gb")

STATE_DIR = game_card.RECORD_DIR
IDENTITY_FILE = "identity.json"
PUBLISH_FILE = "publish.json"  # release.record_publish
INSTALL_FILE = "install.json"  # release.record_install
LICENCE_FILE = "licence.json"  # every LICENSE ensure wrote: {sha256: [...]}, the newest last
MAX_LICENCE_RECORDS = 32
FIRST_VERSION = "0.1.0"
# The game folder's format (``game.json``'s ``format``): a game of a newer format is not installed by this hermretro.
FORMAT_VERSION = 1
# The fields of ``game.json`` hermretro itself writes as it lays out and builds a game: never the user's edit.
MANAGED_FIELDS = ("format", "romSha256", "builtWith")
VERSION_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
# The first line of every file ensure writes and may rewrite; a file without it is left as it is.
GENERATED = "made by hermretro from game.json; edits here are replaced"
CHANGELOG_HEAD = "# Changelog\n"
# The exact first lines of the files ensure writes (the README's and the .gitignore's).
MARKERS = (f"<!-- {GENERATED} -->", f"# {GENERATED}")


# -- what is where ------------------------------------------------------------------------


def kind_of(root: Path, name: str) -> str:
    """``game``, ``source`` or ``local`` for a top-level entry of the game folder. Anything unknown is local: it is
    never published."""
    if name in GAME_FILES:
        return "game"
    if name in SOURCE_FOLDERS or (name.lower().endswith(".gbsproj") and Path(root, name) == project_file(Path(root))):
        return "source"
    return "local"


def game_rom(root: Path) -> str:
    """The game's ROM, relative to its folder: ``canonical_rom`` for a game with its project, else (a game installed
    without its source) the one ``game.json``'s ``rom`` names."""
    if project_file(Path(root)) is None:
        named = game_card.load(Path(root)).get("rom")
        if named in GAME_ROMS:
            return named
    return canonical_rom(Path(root))


# -- the game's identity ------------------------------------------------------------------


def state(root: Path, name: str) -> dict:
    """One of the game's records in ``.hermretro/`` ({} when it is missing or unreadable)."""
    try:
        data = json.loads((Path(root) / STATE_DIR / name).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return {}
    return data if isinstance(data, dict) else {}


def write_state(root: Path, name: str, data: dict) -> None:
    folder = Path(root) / STATE_DIR
    folder.mkdir(exist_ok=True)
    paths.write_json_atomic(folder / name, data)


def game_identity(root: Path) -> str | None:
    """The game's id (32 hex digits): the same on every machine and through every publish, unlike the library's
    path-based id. None before ``ensure`` gave the game one."""
    value = state(root, IDENTITY_FILE).get("id")
    return value if isinstance(value, str) and ID_PATTERN.match(value) else None


@game_card.locked
def new_identity(root: Path, *, fresh_changelog: bool = True) -> str:
    """Make the folder a game of its own, for a remix (a copy of another game): a new id, the first version, a fresh
    changelog (unless ``fresh_changelog`` is False: an installed game the user edited keeps theirs), no publish or
    install record, and ``remixOf`` in ``game.json`` naming the game and version it came from. So it never publishes
    over the original."""
    root = Path(root)
    card = game_card.load(root)
    original = {"id": card.get("id"), "version": card.get("gameVersion")} if card.get("id") else None
    identifier = uuid.uuid4().hex
    write_state(root, IDENTITY_FILE, {"id": identifier})
    for record in (PUBLISH_FILE, INSTALL_FILE):
        (root / STATE_DIR / record).unlink(missing_ok=True)
    if card:
        game_card.set_fields(root, {"id": identifier, "gameVersion": FIRST_VERSION, "remixOf": original})
    if fresh_changelog:
        write_text(root / "CHANGELOG.md", CHANGELOG_HEAD)
    ensure(root)
    return identifier


# -- keeping the layout -------------------------------------------------------------------


@game_card.locked
def ensure(root: Path) -> list[str]:
    """Fill in what the game lacks: its id (kept in ``.hermretro/``, copied into ``game.json``), ``gameVersion``,
    ``rom`` and ``format`` in ``game.json`` (never lowering a newer format), a README made from the card,
    ``CHANGELOG.md``, ``.gitignore`` and the ``LICENSE`` of the card's licence. Rewrites only files it made itself (a
    ``.gitignore`` of the user's own only gains ``/scratch/``) and changes nothing that is already right; never moves
    or deletes anything. A game installed without its source only has its id kept. Returns the names it wrote."""
    root = Path(root)
    card = game_card.load(root)
    project = project_file(root) is not None
    if not project and not card:
        return []
    written = []
    if project and not (root / game_card.CARD_FILE).exists():
        card = game_card.scaffold(root, project_title(root))  # a game made before every game had its card
        written.append(game_card.CARD_FILE)
    identifier = game_identity(root)
    if identifier is None:
        carried = card.get("id")
        if not project and not (isinstance(carried, str) and ID_PATTERN.match(carried)):
            return []
        identifier = carried if isinstance(carried, str) and ID_PATTERN.match(carried) else uuid.uuid4().hex
        write_state(root, IDENTITY_FILE, {"id": identifier})
        written.append(f"{STATE_DIR}/{IDENTITY_FILE}")
    if not project:
        return written
    if card:
        version = card.get("gameVersion")
        wanted = {
            "id": identifier,
            "gameVersion": version if isinstance(version, str) and VERSION_PATTERN.match(version) else FIRST_VERSION,
            "rom": canonical_rom(root),
            "format": card["format"] if card_format(card) is not None else FORMAT_VERSION,
        }
        if any(not same(card.get(key), value) for key, value in wanted.items()):
            card = game_card.set_fields(root, wanted)
            written.append(game_card.CARD_FILE)
        if replaceable(root / "README.md") and write_text(root / "README.md", readme(root, card)):
            written.append("README.md")
        if _write_licence(root, card):
            written.append(licence.LICENSE_FILE)
    if not (root / "CHANGELOG.md").exists() and write_text(root / "CHANGELOG.md", CHANGELOG_HEAD):
        written.append("CHANGELOG.md")
    ignore = root / ".gitignore"
    wrote = write_text(ignore, gitignore(root)) if replaceable(ignore) else _ignore_scratch(ignore)
    if wrote:
        written.append(".gitignore")
    return written


def card_format(card: dict) -> int | None:
    """The card's ``format`` when it is one (a whole number from 1), else None."""
    value = card.get("format")
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 1 else None


def same(stored, wanted) -> bool:
    """Whether a stored card value is the wanted one, type and all (``True`` is not the format ``1``)."""
    return type(stored) is type(wanted) and stored == wanted


def licence_owned(root: Path, path: Path) -> bool:
    """Whether the ``LICENSE`` at ``path`` is one ensure wrote (its digest is on record in ``.hermretro/``; a history
    restore can bring back an older one) or the engine's template one every new game starts with (GB Studio's own
    licence, not the game's): only such a file is ever rewritten, never one of the user's own."""
    try:
        if path.is_symlink() or not path.is_file():
            return False
        return file_sha256(path) in _licence_records(root) or _template_text(path) in _template_files("LICENSE")
    except OSError:
        return False


def _licence_records(root: Path) -> list[str]:
    value = state(root, LICENCE_FILE).get("sha256")
    values = value if isinstance(value, list) else [value]
    return [item for item in values if isinstance(item, str)]


def _write_licence(root: Path, card: dict) -> bool:
    """Write the ``LICENSE`` of the card's licence when the game has none or has one ensure wrote (``licence_owned``).
    A ``LICENSE`` of the user's own is never replaced. Returns whether it wrote."""
    wanted = licence.text(root, card)
    path = root / licence.LICENSE_FILE
    if wanted is None or path.is_symlink() or (path.exists() and not licence_owned(root, path)):
        return False
    if not write_text(path, wanted):
        return False
    written = file_sha256(path)
    kept = [item for item in _licence_records(root) if item != written][-(MAX_LICENCE_RECORDS - 1) :]
    write_state(root, LICENCE_FILE, {"sha256": [*kept, written]})
    return True


def _ignore_scratch(path: Path) -> bool:
    """Add ``/scratch/`` to a ``.gitignore`` of the user's own that has no line for ``scratch`` (a link or an unreadable
    file is left alone). Returns whether it wrote."""
    if path.is_symlink():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return False
    if any(line.strip().lstrip("!").strip("/") == "scratch" for line in text.splitlines()):
        return False
    return write_text(path, text + ("\n" if text and not text.endswith("\n") else "") + "/scratch/\n")


def replaceable(path: Path) -> bool:
    """Whether ensure may write ``path``: it is missing, ensure made it, or it is the README a template project
    starts with."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return True
    except (OSError, ValueError):
        return False
    return text.split("\n", 1)[0] in MARKERS or (path.name == "README.md" and text in _template_files("README.md"))


def _template_files(name: str) -> frozenset[str]:
    """The ``name`` files (``README.md``, ``LICENSE``) of the engine's project templates, which every new game starts
    with."""
    texts = set()
    for template_file in (paths.ENGINE_ROOT / "examples").glob(f"*/{name}"):
        try:
            texts.add(template_file.read_text(encoding="utf-8"))
        except OSError:
            continue
    return frozenset(texts)


def _template_text(path: Path) -> str | None:
    """``path``'s text when it is small enough to be a template file, else None."""
    if path.stat().st_size > 64 * 1024:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except ValueError:
        return None


def write_text(path: Path, text: str) -> bool:
    """Write ``text`` atomically unless the file already holds it. Returns whether it wrote."""
    try:
        if path.read_text(encoding="utf-8") == text:
            return False
    except (OSError, ValueError):
        pass
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def readme(root: Path, card: dict) -> str:
    """The game's README, made from its card."""

    def text(key: str) -> str:
        value = card.get(key)
        return value.strip() if isinstance(value, str) else ""

    def strings(key: str) -> list[str]:
        values = card.get(key)
        return [value for value in values if isinstance(value, str)] if isinstance(values, list) else []

    title = text("title") or Path(root).name
    lines = [f"<!-- {GENERATED} -->", f"# {title}", ""]
    if text("tagline"):
        lines += [f"*{text('tagline')}*", ""]
    if (Path(root) / game_card.COVER_FILE).is_file():
        lines += [f"![{title}]({game_card.COVER_FILE})", ""]
    for key in ("description", "about"):
        if text(key):
            lines += [text(key), ""]
    controls = card.get("controls")
    if isinstance(controls, dict) and controls:
        lines += ["## Controls", "", "| Button | Action |", "| --- | --- |"]
        lines += [f"| {button} | {action} |" for button, action in controls.items() if isinstance(action, str)]
        lines.append("")
    rom = canonical_rom(Path(root))
    details = [("Genres", ", ".join(strings("genres"))), ("Tags", ", ".join(strings("tags")))]
    details += [("Version", text("gameVersion")), ("ROM", f"[{rom}]({rom})")]
    lines += [f"- {label}: {value}" for label, value in details if value]
    return "\n".join(lines) + "\n"


def gitignore(root: Path) -> str:
    """What a repository of the game leaves out: everything local, keeping the game's ROM in ``build/``."""
    rom = canonical_rom(Path(root))
    lines = [f"# {GENERATED}", f"/{STATE_DIR}/", "/build/*", f"!/{rom}"]
    lines += [f"/{folder}/" for folder in LOCAL_FOLDERS if folder not in ("build", STATE_DIR)]
    return "\n".join(lines) + "\n"


# -- checking the layout ------------------------------------------------------------------


def check(root: Path) -> dict:
    """``{ok, problems, warnings}``, each a list of ``{code, path, message}``. A problem stops the game from being
    shown or published until it is fixed; a warning does not (what it names stays on this machine)."""
    root = Path(root)
    problems, warnings = [], []
    card = game_card.load(root)
    descriptor = project_file(root)
    if descriptor is None and not card:
        problems.append(_finding("NO_PROJECT", "", "The game has no .gbsproj project file."))
    elif descriptor is None and not (root / game_rom(root)).is_file():
        problems.append(_finding("NO_ROM", game_rom(root), "The game has neither its project nor its ROM."))
    # An older single-file .gbsproj holds its scenes itself, with no project/ folder.
    elif descriptor is not None and not (root / "project").is_dir() and "scenes" not in _json(descriptor):
        problems.append(_finding("NO_SOURCE", "project", "The game's project/ folder is missing."))
    identifier = game_identity(root)
    if (root / game_card.CARD_FILE).exists() and not card:
        problems.append(_finding("CARD_UNREADABLE", game_card.CARD_FILE, "game.json cannot be read."))
    elif card and identifier and card.get("id") != identifier:
        problems.append(_finding("ID_CHANGED", game_card.CARD_FILE, "game.json's id is not this game's id."))
    elif descriptor is not None and not (
        identifier and card.get("rom") == canonical_rom(root) and VERSION_PATTERN.match(str(card.get("gameVersion")))
    ):
        problems.append(_finding("NOT_LAID_OUT", game_card.CARD_FILE, "The game folder could not be given its layout."))
    newer = card_format(card)
    if newer is not None and newer > FORMAT_VERSION:
        problems.append(
            _finding(
                "FORMAT_NEWER",
                game_card.CARD_FILE,
                f"The game is format {newer}; this hermretro reads up to {FORMAT_VERSION}.",
            )
        )
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        entries = []
    for name in entries:
        if kind_of(root, name) == "local" and name not in LOCAL_FOLDERS:
            warnings.append(_finding("UNKNOWN_ENTRY", name, f"{name} is not part of the game layout; it stays local."))
    if descriptor is not None and not replaceable(root / "README.md"):
        warnings.append(_finding("OWN_README", "README.md", "README.md was written by hand; it is kept as it is."))
    return {"ok": not problems, "problems": problems, "warnings": warnings}


def _finding(code: str, path: str, message: str) -> dict:
    return {"code": code, "path": path, "message": message}

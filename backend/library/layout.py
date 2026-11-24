"""The game folder: one layout every game has from the moment it is made, so it can later be published (the game
alone, or the game with its source) and updated without being reshaped. Standard library only.

    <games>/<Name>/
      game.json  cover.png  README.md  CHANGELOG.md  LICENSE  .gitignore   game: every publish
      build/game.gbc  (build/game.gb for a monochrome project)              game: its one ROM
      <name>.gbsproj  project/  assets/  plugins/  art/  docs/              source: a publish with the source
      .hermretro/                                                           this machine's record, never published
      everything else (build/'s other files, captures/, save-states/, …)   local, never published

``ensure`` fills in what a game lacks and never moves or deletes anything; ``check`` reports what is wrong with it;
``files`` lists what a publish would contain. ``.hermretro/identity.json`` keeps the game's id, so a hand edit of
``game.json`` cannot change it; ``.hermretro/publish.json`` records the last publish (``record_publish``).
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path

from ..system import paths
from . import game_card
from .freshness import source_digest
from .project import GAME_FILES, canonical_rom, file_sha256, project_file

# What a publish with the source adds: the folders below and the project's .gbsproj.
SOURCE_FOLDERS = ("project", "assets", "plugins", "art", "docs")
# Folders hermretro and the engine write that stay on this machine.
LOCAL_FOLDERS = ("build", "captures", "save-states", "artifacts", "node_modules", ".hermretro")

STATE_DIR = ".hermretro"
IDENTITY_FILE = "identity.json"
PUBLISH_FILE = "publish.json"
FIRST_VERSION = "0.1.0"
VERSION_PATTERN = re.compile(r"^(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})$")
ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
# The first line of every file ensure writes and may rewrite; a file without it is left as it is.
GENERATED = "made by hermretro from game.json; edits here are replaced"
CHANGELOG_HEAD = "# Changelog\n"


# -- what is where ------------------------------------------------------------------------


def kind_of(root: Path, name: str) -> str:
    """``game``, ``source`` or ``local`` for a top-level entry of the game folder. Anything unknown is local: it is
    never published."""
    if name in GAME_FILES:
        return "game"
    if name in SOURCE_FOLDERS or (name.lower().endswith(".gbsproj") and Path(root, name) == project_file(Path(root))):
        return "source"
    return "local"


def files(root: Path, *, source: bool) -> list[str]:
    """Every file a publish would contain, relative and sorted: the game files that exist and the game's ROM, and
    with ``source`` the ``.gbsproj`` and every file under the source folders. Symbolic links and hidden files are
    never included."""
    root = Path(root)
    found = [name for name in GAME_FILES if _regular(root / name)]
    rom = canonical_rom(root)
    if _regular(root / rom):
        found.append(rom)
    if source:
        descriptor = project_file(root)
        if descriptor is not None and _regular(descriptor):
            found.append(descriptor.name)
        for folder in SOURCE_FOLDERS:
            for directory, folders, names in os.walk(root / folder):
                folders[:] = sorted(name for name in folders if not name.startswith("."))
                for name in names:
                    path = Path(directory, name)
                    if not name.startswith(".") and _regular(path):
                        found.append(path.relative_to(root).as_posix())
    return sorted(found)


def _regular(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


# -- the game's identity ------------------------------------------------------------------


def _state(root: Path, name: str) -> dict:
    try:
        data = json.loads((Path(root) / STATE_DIR / name).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_state(root: Path, name: str, data: dict) -> None:
    folder = Path(root) / STATE_DIR
    folder.mkdir(exist_ok=True)
    paths.write_json_atomic(folder / name, data)


def game_identity(root: Path) -> str | None:
    """The game's id (32 hex digits): the same on every machine and through every publish, unlike the library's
    path-based id. None before ``ensure`` gave the game one."""
    value = _state(root, IDENTITY_FILE).get("id")
    return value if isinstance(value, str) and ID_PATTERN.match(value) else None


def new_identity(root: Path) -> str:
    """Make the folder a game of its own: a new id, the first version and no publish record. For a remix, a copy
    of another game, so it never publishes over the original."""
    root = Path(root)
    identifier = uuid.uuid4().hex
    _write_state(root, IDENTITY_FILE, {"id": identifier})
    (root / STATE_DIR / PUBLISH_FILE).unlink(missing_ok=True)
    card = game_card.load(root)
    if card:
        game_card.set_fields(root, {"id": identifier, "gameVersion": FIRST_VERSION})
    ensure(root)
    return identifier


# -- keeping the layout -------------------------------------------------------------------


def ensure(root: Path) -> list[str]:
    """Fill in what the game lacks: its id (kept in ``.hermretro/``, copied into ``game.json``), ``gameVersion``
    and ``rom`` in ``game.json``, a README made from the card, ``CHANGELOG.md`` and ``.gitignore``. Rewrites only
    files it made itself and changes nothing that is already right; never moves or deletes anything. Returns the
    names it wrote."""
    root = Path(root)
    if project_file(root) is None:
        return []
    written = []
    card = game_card.load(root)
    identifier = game_identity(root)
    if identifier is None:
        carried = card.get("id")
        identifier = carried if isinstance(carried, str) and ID_PATTERN.match(carried) else uuid.uuid4().hex
        _write_state(root, IDENTITY_FILE, {"id": identifier})
        written.append(f"{STATE_DIR}/{IDENTITY_FILE}")
    if card:
        version = card.get("gameVersion")
        wanted = {
            "id": identifier,
            "gameVersion": version if isinstance(version, str) and VERSION_PATTERN.match(version) else FIRST_VERSION,
            "rom": canonical_rom(root),
        }
        if any(card.get(key) != value for key, value in wanted.items()):
            card = game_card.set_fields(root, wanted)
            written.append(game_card.CARD_FILE)
        if _replaceable(root / "README.md") and _write_text(root / "README.md", readme(root, card)):
            written.append("README.md")
    if not (root / "CHANGELOG.md").exists() and _write_text(root / "CHANGELOG.md", CHANGELOG_HEAD):
        written.append("CHANGELOG.md")
    if _replaceable(root / ".gitignore") and _write_text(root / ".gitignore", gitignore(root)):
        written.append(".gitignore")
    return written


def _replaceable(path: Path) -> bool:
    """Whether ensure may write ``path``: it is missing, ensure made it, or it is the README a template project
    starts with."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return True
    except (OSError, ValueError):
        return False
    return GENERATED in text.split("\n", 1)[0] or (path.name == "README.md" and text in _template_readmes())


def _template_readmes() -> frozenset[str]:
    """The READMEs of the engine's project templates, which every new game starts with."""
    texts = set()
    for readme_file in (paths.ENGINE_ROOT / "examples").glob("*/README.md"):
        try:
            texts.add(readme_file.read_text(encoding="utf-8"))
        except OSError:
            continue
    return frozenset(texts)


def _write_text(path: Path, text: str) -> bool:
    """Write ``text`` unless the file already holds it. Returns whether it wrote."""
    try:
        if path.read_text(encoding="utf-8") == text:
            return False
    except (OSError, ValueError):
        pass
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)
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
    details = [("Genres", ", ".join(strings("genres"))), ("Tags", ", ".join(strings("tags")))]
    details += [("Version", text("gameVersion")), ("ROM", f"`{canonical_rom(root)}`")]
    lines += [f"- {label}: {value}" for label, value in details if value]
    return "\n".join(lines) + "\n"


def gitignore(root: Path) -> str:
    """What a repository of the game leaves out: everything local, keeping the game's ROM in ``build/``."""
    rom = canonical_rom(root)
    lines = [f"# {GENERATED}", f"/{STATE_DIR}/", "/build/*", f"!/{rom}"]
    lines += [f"/{folder}/" for folder in LOCAL_FOLDERS if folder not in ("build", STATE_DIR)]
    return "\n".join(lines) + "\n"


# -- checking the layout ------------------------------------------------------------------


def check(root: Path) -> dict:
    """``{ok, problems, warnings}``, each a list of ``{code, path, message}``. A problem stops the game from being
    shown or published until it is fixed; a warning does not (what it names stays on this machine)."""
    root = Path(root)
    problems, warnings = [], []
    if project_file(root) is None:
        problems.append(_finding("NO_PROJECT", "", "The game has no .gbsproj project file."))
    if not (root / "project").is_dir():
        problems.append(_finding("NO_SOURCE", "project", "The game's project/ folder is missing."))
    card_file = root / game_card.CARD_FILE
    card = game_card.load(root)
    if card_file.exists() and not card:
        problems.append(_finding("CARD_UNREADABLE", game_card.CARD_FILE, "game.json cannot be read."))
    identifier = game_identity(root)
    if card and identifier and card.get("id") != identifier:
        problems.append(_finding("ID_CHANGED", game_card.CARD_FILE, "game.json's id is not this game's id."))
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        entries = []
    for name in entries:
        if kind_of(root, name) == "local" and name not in LOCAL_FOLDERS:
            warnings.append(_finding("UNKNOWN_ENTRY", name, f"{name} is not part of the game layout; it stays local."))
    if not _replaceable(root / "README.md"):
        warnings.append(_finding("OWN_README", "README.md", "README.md was written by hand; it is kept as it is."))
    return {"ok": not problems, "problems": problems, "warnings": warnings}


def _finding(code: str, path: str, message: str) -> dict:
    return {"code": code, "path": path, "message": message}


# -- publishing ---------------------------------------------------------------------------


def published(root: Path) -> dict | None:
    """The last publish (``record_publish``), or None when the game was never published."""
    record = _state(root, PUBLISH_FILE)
    return record or None


def unpublished_changes(root: Path) -> bool | None:
    """Whether the game changed since its last publish: its ROM or its source. None when it was never published."""
    record = published(root)
    if record is None:
        return None
    rom = Path(root) / canonical_rom(root)
    try:
        rom_sha = file_sha256(rom) if rom.is_file() else None
    except OSError:
        rom_sha = None
    return rom_sha != record.get("romSha256") or source_digest(Path(root)) != record.get("sources")


def next_version(version: str, part: str = "patch") -> str:
    """The version after ``version``: ``part`` is ``major``, ``minor`` or ``patch``."""
    match = VERSION_PATTERN.match(version or "")
    major, minor, patch = (int(number) for number in match.groups()) if match else (0, 1, 0)
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def record_publish(root: Path, *, repo: str, commit: str, version: str, notes: str = "") -> dict:
    """Record a publish: ``.hermretro/publish.json`` (what was published, where), the card's ``gameVersion`` and a
    ``CHANGELOG.md`` entry. Returns the record."""
    root = Path(root)
    if not VERSION_PATTERN.match(version):
        raise ValueError(f"Not a version: {version!r}.")
    rom = root / canonical_rom(root)
    record = {
        "repo": repo,
        "commit": commit,
        "version": version,
        "romSha256": file_sha256(rom) if rom.is_file() else None,
        "sources": source_digest(root),
        "t": time.time(),
    }
    _write_state(root, PUBLISH_FILE, record)
    if game_card.load(root):
        game_card.set_fields(root, {"gameVersion": version})
    try:
        changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    except FileNotFoundError:
        changelog = CHANGELOG_HEAD
    head, _, rest = changelog.partition("\n")
    entry = f"\n## {version} ({time.strftime('%Y-%m-%d')})\n" + (f"\n{notes.strip()}\n" if notes.strip() else "")
    _write_text(root / "CHANGELOG.md", head + "\n" + entry + rest)
    ensure(root)
    return record

"""Whether a game may be published as it stands: ``readiness``. Standard library only; nothing reaches the network.

A game is ready when its layout has no problem; its card is complete and names a licence whose ``LICENSE`` text it
has; its ROM is the last build of its sources (for a game with its source, ``pipeline.rom_state``: digests, never file
times), fits a Chromatic cartridge and is the one ``game.json``'s ``romSha256`` names; a publish with the source has
the project; the pre-publish scan (``publish_scan``) blocks nothing; and the files a publish would hold pass the very
checks an install of them runs (``installable``: ``install_git.tree_problems``, ``install_check.take_payload`` and
``install_check.check``), so a ready game is one others can install.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from . import cartridge, game_card, install_check, install_git, layout, licence, pipeline, publish_scan, release
from .project import file_sha256, project_file


def readiness(root: Path, *, source: bool, last_build: dict | None = None) -> dict:
    """``{ok, problems, warnings}`` (module docstring). ``last_build`` is the library's record of the game's last build
    (``games.json``'s ``lastBuild``), which says what a game with its source was built from. Each finding is ``{code,
    path, message}``; the warnings are the scan's."""
    root = Path(root)
    problems = list(layout.check(root)["problems"])
    card = game_card.status(root, strict=True)
    if not card["complete"]:
        problems.append(_finding("CARD", game_card.CARD_FILE, "The game card is missing " + ", ".join(card["missing"])))
    stored = game_card.load(root)
    problems += licence_problems(root, stored)
    relative = layout.game_rom(root)
    rom = root / relative
    if not (rom.is_file() and not rom.is_symlink()):
        problems.append(_finding("NO_ROM", relative, "The game has not been built."))
    else:
        if project_file(root) is not None and (why := pipeline.rom_state(root, last_build)["problem"]):
            problems.append(_finding("ROM_OLD", relative, why))
        info = cartridge.inspect(rom)
        for problem in info["problems"] + cartridge.check_name(info, relative):
            problems.append(_finding("ROM_UNFIT", relative, problem["message"]))
        if stored.get("romSha256") != file_sha256(rom):
            problems.append(_finding("ROM_SHA_STALE", relative, "game.json's romSha256 is not this ROM; build again."))
    if source and project_file(root) is None:
        problems.append(_finding("NO_SOURCE", "", "The game has no source to publish."))
    found = scan(root, source=source)
    problems += found["blocking"]
    if not problems:
        problems += installable(root, source=source)
    return {"ok": not problems, "problems": problems, "warnings": found["warnings"]}


def scan(root: Path, *, source: bool) -> dict:
    """``{blocking, warnings}``: what a publish of the game would carry that it must not (``publish_scan``)."""
    return publish_scan.scan(Path(root), release.files(root, source=source))


def licence_problems(root: Path, card: dict) -> list[dict]:
    """``NO_LICENSE`` (the card names none), ``NO_LICENSE_TEXT`` (the game has no ``LICENSE``) or ``LICENSE_STALE``
    (the ``LICENSE`` hermretro wrote is not the card's licence: ``layout.ensure`` writes it again). A ``LICENSE`` of the
    user's own is theirs to keep in step with the card."""
    if licence.chosen(card) is None:
        return [_finding("NO_LICENSE", game_card.CARD_FILE, "The game names no licence; choose one first.")]
    path = Path(root) / licence.LICENSE_FILE
    if not (path.is_file() and not path.is_symlink()):
        return [_finding("NO_LICENSE_TEXT", licence.LICENSE_FILE, "The game has no LICENSE file for its licence.")]
    if layout.licence_replaceable(root, path) and path.read_text(encoding="utf-8", errors="replace") != licence.text(
        root, card
    ):
        return [
            _finding("LICENSE_STALE", licence.LICENSE_FILE, "LICENSE is not the card's licence; save the card again.")
        ]
    return []


def installable(root: Path, *, source: bool) -> list[dict]:
    """What an install of exactly the files a publish holds would refuse, each as ``INSTALL_<its code>``: the files go
    through the install's own tree, payload and folder checks, in a copy made for them."""
    root = Path(root)
    names = release.files(root, source=source)
    entries = [{"path": name, "mode": "100644", "kind": "blob", "size": (root / name).stat().st_size} for name in names]
    problems = install_git.tree_problems(
        entries, max_files=install_check.MAX_FILES, max_total=install_check.MAX_TOTAL_BYTES
    )
    if not problems:
        with tempfile.TemporaryDirectory(prefix="hermretro-publish-") as folder:
            checkout, game = Path(folder) / "checkout", Path(folder) / "game"
            for name in names:
                (checkout / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / name, checkout / name, follow_symlinks=False)
            mode, problems = install_check.take_payload(checkout, game)
            if not problems:
                report = install_check.check(game)
                problems = report["problems"]
                if report["mode"] != ("game+source" if source else "game"):
                    problems.append(_finding("MODE", "", f"An install of these files would be {report['mode']}."))
    return [{**item, "code": f"INSTALL_{item['code']}"} for item in problems]


def _finding(code: str, path: str, message: str) -> dict:
    return {"code": code, "path": path, "message": message}

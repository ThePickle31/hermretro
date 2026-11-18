"""Every file has a known home, and source files stay small enough to read.

tools/layout.toml maps every top-level folder and its areas with a one-line purpose; docs/dev/ARCHITECTURE.md
("Map") lists the same folders. These tests keep the tree, the map and the docs in agreement, so a newcomer
(person or agent) can trust the map to say where a change belongs. Warnings (printed, never failing) mark
what should be fixed soon: files over the warning size and every deliberate exception (``retrodev: allow``
comments, tests/repo/allowances.py). The README rules for backend features and pages are in
tests/repo/test_readmes.py, so work on one area never shares a test file with the map's rules.

Run alone: python -m unittest tests.repo.test_layout
"""

import re
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.repo import allowances  # noqa: E402 - the repository root goes on sys.path first

LAYOUT = tomllib.loads((ROOT / "tools" / "layout.toml").read_text(encoding="utf-8"))


def warn(message: str) -> None:
    print("layout warning: " + message, file=sys.stderr)


def files() -> list[str]:
    """What a commit of this tree would hold: tracked files plus new files git does not ignore."""
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode()
    return sorted(name for name in out.split("\0") if name and (ROOT / name).is_file())


def mapped_folders() -> set[str]:
    folders = set()
    for top, spec in LAYOUT["folders"].items():
        folders.add(top + "/")
        folders.update(f"{top}/{area}/" for area in spec.get("areas", {}))
    return folders


def measured(name: str) -> bool:
    size = LAYOUT["size"]
    return (
        name.endswith(tuple(size["extensions"]))
        and not name.startswith(tuple(size["exempt"]))
        and not (name.startswith("engine/pins/") and name.endswith(".json"))
    )


class Layout(unittest.TestCase):
    def test_every_file_sits_in_a_mapped_folder(self):
        root_files, folders = LAYOUT["root"], LAYOUT["folders"]
        stray = []
        for name in files():
            parts = name.split("/")
            if len(parts) == 1:
                if name not in root_files:
                    stray.append(f"{name}: not an allowed root file")
            elif parts[0] not in folders:
                stray.append(f"{name}: {parts[0]}/ is not a mapped folder")
            elif len(parts) > 2 and folders[parts[0]].get("areas") and parts[1] not in folders[parts[0]]["areas"]:
                stray.append(f"{name}: {parts[0]}/{parts[1]}/ is not a mapped area of {parts[0]}/")
        self.assertEqual(
            stray,
            [],
            "\nThe map (tools/layout.toml) says where every kind of file belongs, so the "
            "tree stays navigable:\n  " + "\n  ".join(stray) + "\nFIX: move the file into the folder "
            "that owns it (see the Map in docs/dev/ARCHITECTURE.md), or, for a genuinely new folder, add "
            "it with a one-line purpose to tools/layout.toml and the same line to the Map",
        )

    def test_the_architecture_map_lists_the_same_folders(self):
        text = (ROOT / "docs" / "dev" / "ARCHITECTURE.md").read_text(encoding="utf-8")
        match = re.search(r"^## Map\n(.*?)(?=^## )", text, re.S | re.M)
        self.assertIsNotNone(
            match,
            "docs/dev/ARCHITECTURE.md has no '## Map' section\nFIX: add it back, one "
            "table row per folder in tools/layout.toml",
        )
        assert match
        documented = set(re.findall(r"^\| `([^`]+/)` \|", match.group(1), re.M))
        mapped = mapped_folders()
        self.assertEqual(
            sorted(mapped - documented),
            [],
            "folders in tools/layout.toml missing from the Map in "
            "docs/dev/ARCHITECTURE.md (the docs must not drift from the tree)\nFIX: add a row for each",
        )
        self.assertEqual(
            sorted(documented - mapped),
            [],
            "folders in the Map of docs/dev/ARCHITECTURE.md that "
            "tools/layout.toml does not have\nFIX: remove the rows, or add the folders to tools/layout.toml",
        )

    def test_source_files_stay_readable(self):
        size, exceptions = LAYOUT["size"], LAYOUT.get("exceptions", {})
        too_big = []
        for name in filter(measured, files()):
            lines = (ROOT / name).read_text(encoding="utf-8", errors="replace").count("\n")
            if lines > size["fail"] and name not in exceptions:
                too_big.append(f"{name}: {lines} lines")
            elif lines > size["warn"]:
                warn(
                    f"{name} has {lines} lines (warning above {size['warn']}, failure above {size['fail']})"
                    + (f"; allowed: {exceptions[name]}" if name in exceptions else "")
                )
        missing = [name for name in exceptions if not (ROOT / name).is_file()]
        self.assertEqual(
            missing, [], "tools/layout.toml [exceptions] names files that no longer exist\nFIX: remove those lines"
        )
        self.assertEqual(
            too_big,
            [],
            f"\nSource files over {size['fail']} lines are hard to review and usually "
            "hold more than one concern:\n  " + "\n  ".join(too_big) + "\nFIX: split the file by "
            "concern inside its feature folder; if it must stay whole, add it to [exceptions] in "
            "tools/layout.toml with the reason",
        )

    def test_every_allowance_has_a_reason_and_stays_visible(self):
        found = allowances.in_files(ROOT, files())
        allowances.warn(found)
        problems = [item.problem() for item in found if item.problem()]
        self.assertEqual(
            problems,
            [],
            "\nAn exception to a structure rule needs its reason, so the next person "
            "knows whether it still holds:\n  " + "\n  ".join(problems) + "\nFIX: write it as "
            "'# retrodev: allow <rule> — <reason>' (rules: " + ", ".join(sorted(allowances.RULES)) + ")",
        )


if __name__ == "__main__":
    unittest.main()

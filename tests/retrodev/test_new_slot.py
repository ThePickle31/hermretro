"""The trial rounds' regressions for this area (RoundEightNew, RoundElevenNew, RoundFourteen, RoundSixteen), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_new_slot
"""

import shutil
import unittest
from tests.retrodev.fixture import git, parallel, write
from tests.retrodev.test_scaffold import ROOT, ScaffoldCase
from tests.retrodev.fixture import retrodev_docs
from retrodev import scaffold_readme

load_tests = parallel


def joined(out) -> str:
    return " ".join(out["next"])


def steps(out) -> list[str]:
    return [line.removeprefix("next: ") for line in out.splitlines() if line.startswith("next: ")]


README = """# {Label}

**Shows:** the page.

**Tabs:** none.

**Slots:** declares none, contributes none.

**Tests:** `tests/page/page-{page}.test.mjs`.

## Adding a tab here

Make a folder `page/pages/{page}/<tab>/`{taken} with an `index.js` exporting `{{ id, label, Page }}`.
"""


class SlotRoundEightNew(ScaffoldCase):
    def test_the_readme_line_ends_the_doc_before_contributes(self):
        self.new("page", "rdprobe-shelf")
        out = self.new("slot", "rdprobe-shelf", "more", "--doc", "Buttons after the lede. Props: { ctx }")
        line = next(r for r in self.read("page/pages/rdprobe-shelf/README.md").splitlines() if "**Slots:**" in r)
        self.assertEqual(
            line,
            "**Slots:** declares `rdprobe-shelf.more`: buttons after the lede. Props: `{ ctx }`. Contributes none.",
        )
        steps = joined(out)
        self.assertIn("add a HOSTS recipe for 'rdprobe-shelf.more' in tests/page/slots.test.mjs", steps)
        self.assertIn("a contribution changes the `filled` assertion in tests/page/registry.test.mjs", steps)
        self.assertIn("'Events and slots today' line of docs/dev/STUDIO-PAGES.md", steps)
        self.assertIn("const filled =", (ROOT / "tests/page/registry.test.mjs").read_text())
        self.assertIn("HOSTS", (ROOT / "tests/page/slots.test.mjs").read_text())


class SlotRoundElevenNew(ScaffoldCase):
    def test_the_readme_line_reads_as_the_emulator_page_s(self):
        self.new("page", "rdprobe-shelf")
        self.new("slot", "rdprobe-shelf", "more", "--doc", "Buttons after the lede (one per page). Props: { ctx }")
        line = next(r for r in self.read("page/pages/rdprobe-shelf/README.md").splitlines() if "**Slots:**" in r)
        self.assertEqual(
            line,
            "**Slots:** declares `rdprobe-shelf.more`: buttons after the lede (one per page). Props: `{ ctx }`. "
            "Contributes none.",
        )
        emulator = (ROOT / "page/pages/emulator/README.md").read_text()
        self.assertIn("**Slots:** declares `emulator.barActions`: ", emulator)


class ScaffoldsRoundFourteen(ScaffoldCase):
    def real(self, *names: str) -> None:
        for name in names:
            (self.tree / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, self.tree / name)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def files(self, files: dict) -> None:
        for name, text in files.items():
            write(self.tree, name, text)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Known files")

    def readmes(self) -> None:
        taken = " (`install` and `onboarding` are taken: pick another id)"
        self.real("page/pages/setup/index.js")
        self.files(
            {
                "page/pages/build/README.md": README.format(Label="Build", page="build", taken=""),
                "page/pages/setup/README.md": README.format(Label="Setup", page="setup", taken=taken),
            }
        )

    def test_new_slot_backticks_props_and_identifiers_and_wraps_at_120(self):
        self.readmes()
        doc = (
            "Below the quick start buttons, under the hero band, for the own extras of plugins. Props { ctx, game, "
            "hardwareOn }, plus go(pageId) on the page only"
        )
        self.new("slot", "build", "rdfourteenExtras", "--doc", doc)
        text = self.read("page/pages/build/README.md")
        block = text[text.index("**Slots:**") :].split("\n\n")[0]
        flat = " ".join(block.split())
        self.assertIn("Props `{ ctx, game, hardwareOn }`, plus `go(pageId)` on the page only", flat)
        self.assertTrue(all(len(line) <= 120 for line in block.split("\n")), block)


class SlotOnADeclaringPageRoundSixteen(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def test_new_slot_adds_its_sentence_to_the_existing_slots_line(self):
        self.real("page/pages/games/**/*.js", "page/pages/emulator/*.md")
        write(
            self.tree,
            "page/pages/games/README.md",
            "# Games\n\n**Slots:** declares `games.cardMenu`: extra items at the end of a game's arrow menu, props\n"
            "`{ ctx, game, item(icon, label, run, { disabled, why }) }` (return `item(...)`; starts empty).\n"
            "Contributes `InstallButton` to `emulator.barActions`.\n",
        )
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "A README of the shape a declaring page has")
        out = self.new("slot", "games", "cardBadge", "--doc", "A badge on each game card. Props: { ctx, game }")
        self.assertFalse([note for note in out.get("notes", []) if "under **Slots:**" in note], out)
        block = " ".join(
            self.read("page/pages/games/README.md").split("**Slots:**")[1].strip().split("\n\n")[0].split()
        )
        self.assertIn(
            "(return `item(...)`; starts empty). Also declares `games.cardBadge`: a badge on each game card. Props: "
            "`{ ctx, game }`. Contributes `InstallButton` to `emulator.barActions`",
            block,
        )
        slots = self.read("page/pages/games/README.md").split("**Slots:**")[1].split("\n\n")[0]
        self.assertTrue(all(len(line) <= 120 for line in slots.splitlines()), slots)
        self.assertIn("Also declares `<page>.<name>`: <doc>.", retrodev_docs("REFERENCE.md"))


class WrappedSlotsRoundSixteen(unittest.TestCase):
    def test_each_fills_sentence_follows_its_own_slot_when_wrapping_split_the_boundary(self):
        for gap in ("Also\ndeclares `games.cardBadge`", "Also declares\n`games.cardBadge`"):
            text = (
                "# Games\n\n**Slots:** declares `games.cardActions`: buttons on a card. "
                + gap
                + ": a badge on a card. Contributes `X` to `emulator.barActions`.\n\nMore.\n"
            )
            text = scaffold_readme.filled_by(text, "games.cardActions", "Setup", "Install")
            text = scaffold_readme.filled_by(text, "games.cardBadge", "Library", "Badge")
            flat = " ".join(text.split())
            self.assertIn(
                "buttons on a card. Setup fills it with `Install`. Also declares `games.cardBadge`", flat, gap
            )
            self.assertIn("a badge on a card. Library fills it with `Badge`. Contributes `X`", flat, gap)
            said = "declares `games.cardBadge`: a badge on a card"
            self.assertEqual(scaffold_readme.also_declares(text, said), text, gap)

"""The trial rounds' regressions for this area (RoundEighteen, RoundFourteen, RoundNine, RoundSeven, RoundSeventeen, RoundSix, RoundTen, RoundTenNew, RoundTwenty, RoundTwentyOne, RoundTwo), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_retrodev_docs
"""

import io
import re
import unittest
from retrodev import config, output
from tests.retrodev.fixture import RepoCase, git, parallel
from retrodev import state
from tests.retrodev.fixture import retrodev_docs
from tests.retrodev.test_scaffold import ScaffoldCase
from retrodev import (
    checks,
)
from tests.retrodev.test_scaffold import ROOT
from retrodev import repo

load_tests = parallel


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


def line_with(out: str, start: str) -> str:
    return next((line for line in out.splitlines() if line.startswith(start)), "")


def line_with_RoundSix(out: str, start: str) -> str:
    return next((line for line in out.splitlines() if line.startswith(start)), "")


def line_with_RoundTen(text: str, start: str) -> str:
    return next((line for line in text.splitlines() if line.startswith(start)), "")


def line_with_RoundTwo(text: str, start: str) -> str:
    return next(line for line in text.splitlines() if line.lstrip().startswith(start))


class Docs(unittest.TestCase):
    def test_the_readme_and_reference_say_it(self):
        readme = (ROOT / "tools/retrodev/README.md").read_text()
        quick = readme.split("## Quick path", 1)[1].split("\n5. ", 1)[0]
        self.assertIn("an RPC about one game takes `--game`", quick)
        split = readme.split("### Split a long module", 1)[1].split("\n## ", 1)[0]
        self.assertIn("`from .<new> import X as X`", split)
        self.assertIn("`tests/retrodev` (trial tests read file text)", split)
        self.assertIn("400-line warning", split)
        self.assertLess(readme.index("### Rename or move a module"), readme.index("### Split a long module"))
        reference = (ROOT / "tools/retrodev/REFERENCE.md").read_text()
        check = reference.split("### `check [names", 1)[1].split("\n### ", 1)[0]
        self.assertIn("`check <names>` counts toward that gate too", check)
        sync = reference.split("### `sync`", 1)[1].split("\n### ", 1)[0]
        self.assertIn(
            "first check whether\ndev's version there already does what your lines did; if it does, add only a test",
            sync,
        )


class DocsRoundFourteen(RepoCase):
    def test_the_quick_path_has_a_worked_tool_example(self):
        readme = retrodev_docs("README.md")
        section = readme[readme.index("### Add a plugin tool") :]
        self.assertIn("python tools/retrodev new tool library probe --step", section)
        for edited in (
            "the handler module",
            "tests/backend/<feature>/test_tool_<name>.py",
            "docs/dev/CONTRACT.md:<line>",
        ):
            self.assertIn(edited, section)


class Readme(unittest.TestCase):
    def test_no_line_of_the_readme_or_the_reference_runs_past_600_characters(self):
        for name in ("README.md", "REFERENCE.md"):
            text = (ROOT / "tools/retrodev" / name).read_text()
            long = [(number, len(line)) for number, line in enumerate(text.splitlines(), 1) if len(line) > 600]
            self.assertEqual(long, [], name)
        self.assertLess(len((ROOT / "tools/retrodev/README.md").read_text()), 8000, "the README stays the entry")

    def test_the_readme_keeps_the_entry_and_the_reference_is_a_listed_document(self):
        readme = (ROOT / "tools/retrodev/README.md").read_text()
        self.assertIn("## Quick path", readme)
        self.assertIn("## The flow, from plan to merge", readme)
        self.assertIn("by default a `<checkout>-wt` folder next to the checkout", readme)
        self.assertIn("`python tools/retrodev config list` shows it", readme)
        self.assertIn("## Releases", readme)  # AGENTS.md and RELEASE-CHECKLIST.md point at it
        self.assertIn('"tools/retrodev/REFERENCE.md" = ', (ROOT / "tools/layout.toml").read_text())
        reference = (ROOT / "tools/retrodev/REFERENCE.md").read_text()
        for kind in ("feature", "rpc", "tool", "event", "listener", "page", "tab", "slot", "contribution"):
            self.assertIn(f"### `new {kind} ", reference, kind)  # one sub-section per kind


class QuickPath(unittest.TestCase):
    def test_the_readme_opens_with_a_numbered_quick_path(self):  # round eight: first, after the title paragraph
        text = (ROOT / "tools/retrodev/README.md").read_text()
        parts = text.split("\n\n")
        self.assertEqual(parts[2], "## Quick path", parts[:3])
        block = parts[3]
        self.assertTrue(all(line[:1].isdigit() for line in block.splitlines()), block)
        self.assertLessEqual(len(block.splitlines()), 10)
        self.assertIn("RETRODEV_AGENT", parts[4])
        for step in (
            "plan new",
            "plan approve",
            "start",
            "new ",
            "check.py fix",
            "check",
            "notes/pr/",
            "ship --dry-run",
        ):
            self.assertIn(step, block)


class RenameSection(unittest.TestCase):
    def test_the_readme_says_how_to_rename_a_module(self):
        section = retrodev_docs("README.md").split("### Rename or move a module")[1].split("\n## ")[0]
        for said in ("git grep -n <old>", "tests/retrodev", "tools/retrodev/", "docs/", "shadow", "check.py fix"):
            self.assertIn(said, section)
        self.assertLessEqual(len(section.strip().splitlines()), 7)


class Takeover(RepoCase):
    def pushed(self, branch: str) -> None:
        """A teammate's branch, pushed from their own clone; dev moves on after it."""
        mate = self.base / "mate"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(mate))
        git(mate, "switch", "-q", "-c", branch)
        self.commit(mate, "docs/mate.md", "# Theirs\n")
        git(mate, "push", "-q", "origin", branch)
        self.on_dev("docs/other.md", "# Other\n")

    def test_the_readme_takes_over_with_the_command(self):
        text = retrodev_docs("REFERENCE.md")
        section = text[text.index("**Taking over a teammate's branch**") :].split("\n\n")[0]
        self.assertIn("python tools/retrodev takeover", section)
        self.assertNotIn("<root>", section)


class Paths(RepoCase):
    def pushed(self) -> None:
        mate = self.base / "mate"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(mate))
        git(mate, "switch", "-q", "-c", "feat/mate")
        self.commit(mate, "backend/library/core.py", "VALUE = 2\n")
        git(mate, "push", "-q", "origin", "feat/mate")

    def test_the_readme_says_notes_is_in_the_main_checkout_and_to_recheck_what_changed(self):
        readme = retrodev_docs("README.md")
        self.assertIn("`notes/` is in the main checkout, shared by every worktree", readme)
        seven = line_with_RoundTen((ROOT / "tools/retrodev/README.md").read_text(), "7. ")
        self.assertIn("check What changed still matches the code; start copied it from the plan", seven)


class Tool(ScaffoldCase):
    def test_the_reference_says_how_tools_py_splits(self):
        text = retrodev_docs("REFERENCE.md")
        self.assertIn("when `tools.py` is over 400 lines", text)
        self.assertIn(
            "Splitting `tools.py` by hand works the same way: each module has its own `TOOLS`, `tools.py` aggregates "
            "them",
            text,
        )
        self.assertIn("tests patch names on the new module", text)


class ReadmeRoundTwenty(unittest.TestCase):
    def test_the_quick_path_names_the_no_plan_entry_and_the_split_recipe_where_to_patch(self):
        step = next(line for line in (ROOT / "tools/retrodev/README.md").read_text().splitlines() if line[:3] == "3. ")
        readme = retrodev_docs("README.md")
        self.assertIn("`docs/` and `chore/` may skip steps 1-2: `start <kind>/<topic> --no-plan`", step)
        self.assertIn('the moved code imports: `mock.patch.object(<new module>, "dep")`, not the old module', readme)


class ReadmeRoundTwentyOne(unittest.TestCase):
    def test_the_split_recipe_covers_old_re_exports_tool_order_and_the_exact_size_rule(self):
        text = (ROOT / "tools/retrodev/README.md").read_text()
        quick = text.split("## Quick path\n\n", 1)[1].split("\n\n", 1)[0].splitlines()
        self.assertEqual([row[:3] for row in quick], [f"{n}. " for n in range(1, 9)], "one numbered line per step")
        split = " ".join(text.split("### Split a long module", 1)[1].split("\n## ", 1)[0].split())
        self.assertIn("(so does an import it kept only for importers, once its last use moves out)", split)
        self.assertIn(
            "Moved tools keep their `TOOLS` positions (the registration snapshot pins the order): import them into "
            "the module that lists `TOOLS`, at the same places",
            split,
        )
        layout = (ROOT / "tools/layout.toml").read_text()  # the numbers the recipe states, from the one size rule
        sizes = dict(re.findall(r"^(warn|fail) = (\d+)$", layout, re.M))
        self.assertIn(
            f"under the {sizes['warn']}-line warning (above {sizes['warn']} warns, above {sizes['fail']} fails)", split
        )
        self.assertIn("`from .<new> import X as X`", retrodev_docs("README.md"))


class Flow(RepoCase):
    def passed(self, tree, name):
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        record = state.load_branch(self.main, name)
        record.update(passed_tree=repo.tree_digest(tree), passed_checks=sorted(checks.required(ctx)))
        state.save_branch(self.main, record)

    def feat(self, topic="goalie"):
        self.new_plan(topic)
        self.run_cli("plan", "approve", topic, "--words", "start")
        tree = self.worktree(f"feat/{topic}")
        record = state.load_branch(self.main, f"feat/{topic}")
        state.save_branch(self.main, {**record, "plan": topic})
        self.commit(tree, "docs/guide.md", f"# {topic}\n")
        self.passed(tree, f"feat/{topic}")
        return tree

    def test_the_budgets_are_measured_cold_runs_and_the_readme_agrees(self):
        ctx = config.Context.make(self.main, output.Out(stream=io.StringIO()))
        budgets = ctx.policy["checks"]["budgets"]  # one source: a retune moves the README's words with it
        readme = retrodev_docs()
        self.assertIn(
            f"unit {budgets['unit']} s, scaffold {budgets['scaffold']} s, "
            f"the fast checks together {budgets['fast_total']} s",
            readme,
        )
        self.assertIn("over its budget twice in a row", readme)
        self.assertNotIn("Over twice its budget", readme)

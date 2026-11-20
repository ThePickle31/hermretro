"""Friction the twenty-first round of fresh-agent trials found in retrodev: `new tool`'s game card advice passed the
str tool_project gives where a Path is taken and did not say the lockstep test counts backticked tool names in the
CONTRACT sentence; `new tab --from-page` left a README **Shows:** line explaining the old page-level Page; the
listener's docstring and first step ran the event's description into its payload; sync's "lines neither side had"
warning read as an error for a reworded prose conflict; the README's split recipe; and a CONTRACT-only edit reran
the real-engine run. Each test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_twenty_one_tooling
"""

import ast
import re
import unittest
from pathlib import Path

import retrodev

from tests.retrodev.fixture import GOOD_BODY, RepoCase, git, parallel, retrodev_docs, write
from tests.retrodev.test_scaffold import ScaffoldCase

load_tests = parallel
ROOT = Path(retrodev.__file__).resolve().parents[2]


class Real(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")


class NewTool(Real):
    def test_the_game_card_step_says_to_pass_a_path_and_the_contract_step_names_the_lockstep_count(self):
        self.real("backend/features.py", "backend/library/*.py", "backend/library/README.md")
        said = " ".join(self.new("tool", "library", "rdprobe_card", "--project")["next"])
        self.assertIn(
            "game_card.status(root, strict=True) for what is missing (its missing and problems); both take a Path "
            "and tool_project gives root as a str, so pass them Path(root) (from pathlib import Path)",
            said,
        )
        # What the advice rests on, read from the real files rather than assumed.
        card = (ROOT / "backend/library/game_card.py").read_text()
        self.assertIn("def public(root: Path) -> dict | None:", card)
        self.assertRegex(card, r"def status\(root: Path,")
        args = (ROOT / "backend/hermes/tool_args.py").read_text()
        self.assertIn("def tool_project(tool: str, args: dict, kwargs: dict) -> tuple[str | None, str | None]:", args)
        self.assertIn(
            "(another tool named there goes without backticks: tests/repo/test_lockstep.py counts every backticked "
            "chromatic_* name in that sentence as a listed tool)",
            said,
        )
        self.assertIn(
            r're.findall(r"`(chromatic_\w+)`", sentence.group(2))', (ROOT / "tests/repo/test_lockstep.py").read_text()
        )


class FromPageShows(ScaffoldCase):
    PAGE = "rdprobe-shows"

    def page_with(self, shows: str) -> str:
        """A probe page (never a live one: those change) whose README Shows paragraph reads ``shows``."""
        self.new("page", self.PAGE)
        rel = f"page/pages/{self.PAGE}/README.md"
        text = self.read(rel)
        write(self.tree, rel, re.sub(r"^\*\*Shows:\*\*[^\n]*", f"**Shows:** {shows}", text, count=1, flags=re.M))
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "The probe page")
        return rel

    def test_a_shows_line_that_explains_the_page_level_page_gets_a_step_with_the_tab_s_real_import(self):
        rel = self.page_with("the notes. The page's `Page` is `RdprobeShowsPage`; the descriptor imports it.")
        preview = self.new("tab", self.PAGE, "main", "--from-page", "--dry-run")
        self.assertEqual(git(self.tree, "status", "--porcelain"), "", "the dry run wrote nothing")
        out = self.new("tab", self.PAGE, "main", "--from-page")
        tab = self.read(f"page/pages/{self.PAGE}/main/index.js")
        source = f"#pages/{self.PAGE}/{self.PAGE}-page.js"
        imported = f"import {{ RdprobeShowsPage }} from '{source}'"
        self.assertIn(imported, tab, "the step quotes the import the tab really has")
        line = next(n for n, row in enumerate(self.read(rel).split("\n"), 1) if row.startswith("**Shows:**"))
        step = (
            f"{rel}:{line} (**Shows:**) still explains the page's own Page, which the descriptor no longer has: say "
            f"the main tab shows it now; its Page is RdprobeShowsPage from page/pages/{self.PAGE}/{self.PAGE}-page.js, "
            f"which page/pages/{self.PAGE}/main/index.js imports as {imported}"
        )
        self.assertIn(step, out["next"])
        self.assertIn(step, preview["next"], "the preview names the same step")

    def test_a_shows_line_that_does_not_explain_it_gets_no_such_step(self):
        self.page_with("the notes, newest first.")
        out = self.new("tab", self.PAGE, "main", "--from-page")
        self.assertFalse([step for step in out["next"] if "still explains the page's own Page" in step], out)
        self.assertIn(
            f"the page's own Page (#pages/{self.PAGE}/{self.PAGE}-page.js) is now the main tab, and the descriptor "
            "has no Page",
            out["next"],
        )


class Listener(Real):
    DOC = "chromatic_rdprobe_tool kept a note; note=<the note's text, str>, at=<when, float>"

    def test_the_docstring_and_first_step_keep_the_description_and_the_payload_apart_as_written(self):
        self.real("backend/history/*.py", "backend/history/README.md")
        self.new("event", "history", "rdprobe_noted")
        door = self.read("backend/history/__init__.py")
        door, count = re.subn(r'("history\.rdprobe_noted":\s*\(?\s*)"[^"]*"', rf'\1"{self.DOC}"', door)
        self.assertEqual(count, 1, door)
        write(self.tree, "backend/history/__init__.py", door)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "The probe event's entry")
        out = self.new("listener", "history", "history.rdprobe_noted")
        source = self.read("backend/history/listeners.py")
        func = next(
            node
            for node in ast.parse(source).body
            if isinstance(node, ast.FunctionDef) and node.name == "on_history_rdprobe_noted"
        )
        doc = ast.get_docstring(func) or ""
        flat = " ".join(doc.split())
        self.assertIn(
            "When history.rdprobe_noted happens, backend/history does this (a listener that raises is logged): "
            "say what this listener does.",
            flat,
        )
        self.assertIn("The event: chromatic_rdprobe_tool kept a note.", flat, "its case stays as written")
        self.assertIn("Its payload: note=<the note's text, str>, at=<when, float>.", flat)
        self.assertNotIn("(chromatic_rdprobe_tool kept a note;", flat)
        self.assertTrue(all(len(row) <= 120 for row in source.splitlines()), source)
        self.assertIn("    say what this listener does.\n", source, "the placeholder stays a line of its own")
        self.assertIn(
            'on_history_rdprobe_noted; the event: "chromatic_rdprobe_tool kept a note"; its payload: '
            "note=<the note's text, str>, at=<when, float>); to log, ",
            out["next"][0],
        )


class SyncProse(RepoCase):
    def test_a_reworded_prose_resolution_still_warns_and_says_it_needs_no_commit_of_its_own(self):
        doc = "docs/guide.md"
        self.on_dev(doc, "# Guide\n\nThe page shows games.\n", "Guide")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("docs/guide")
        self.commit(tree, doc, "# Guide\n\nThe page shows every game.\n")
        self.on_dev(doc, "# Guide\n\nThe page shows the games you made.\n")
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 1, out)
        write(tree, doc, "# Guide\n\nThe page shows every game you made.\n")  # both sides' words, reworded
        git(tree, "add", doc)
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 0, out)
        flat = " ".join(out.split())
        self.assertIn(
            "warning: the resolution adds 1 line(s) neither side had (docs/guide.md): new work belongs in its own "
            "commit after sync (a resolution over 20 lines needs a full review round at land); prose reworded to "
            "join both sides' text counts too: if that is all they are, they need no commit of their own, and land "
            "still counts them toward the 20",
            flat,
        )


class AcceptanceContract(RepoCase):
    """A branch that needs the real-engine run passed it, then changed only docs/dev/CONTRACT.md (round 21: the run
    reran). Nothing acceptance runs reads that file; every neighbour still takes the pass back, and the clean install
    still counts it (ship's scanner reads the docs)."""

    def checked(self, tree, *, cached: bool, code: int = 0) -> dict:
        self.clear_log()
        got, data = self.run_cli("check", cwd=tree, as_json=True)
        self.assertEqual(got, code, data)
        ran = [name for entry in self.check_log() for name in entry.get("names", [])]
        self.assertEqual("acceptance" not in ran, cached, ran)
        row = next(row for row in data["checks"] if row["name"] == "acceptance")
        self.assertEqual(row["cached"], cached, row)
        return data

    def shipped(self, tree) -> list[str]:
        body = write(self.base, "body.md", GOOD_BODY)
        _code, data = self.run_cli(
            "ship", "--title", "Say what the tool does", "--body", str(body), "--dry-run", cwd=tree, as_json=True
        )
        return [gate["name"] for gate in data["gates"] if not gate["ok"]]

    def test_a_contract_edit_keeps_the_acceptance_pass_and_the_tree_may_ship(self):
        tree = self.worktree("chore/tool")
        self.commit(tree, "backend/library/core.py", "VALUE = 2\n", "Change the core")
        self.assertTrue(self.checked(tree, cached=False)["tree_passed"])
        self.commit(tree, "docs/dev/CONTRACT.md", "# Contract\n\n`chromatic_x`: says what it does.\n", "Describe it")
        data = self.checked(tree, cached=True)
        self.assertTrue(data["tree_passed"], data)
        self.assertEqual(self.check_log()[0]["names"], ["unit", "scan"], "the fast checks that read it still run")
        self.assertEqual(self.shipped(tree), [], "the ship gate takes the tree whose pass reused acceptance")
        write(tree, "docs/dev/CONTRACT.md", "# Contract\n\nChanged.\n")  # uncommitted: the other gates still hold
        self.assertIn("committed and clean", self.shipped(tree))
        git(tree, "commit", "-q", "-am", "Change it again")
        self.fail_checks("scan")
        data = self.checked(tree, cached=True, code=1)
        self.assertFalse(data["tree_passed"], "a cached acceptance pass never outweighs a failure")
        self.assertIn("checks passed on this tree", self.shipped(tree))

    def test_only_that_exact_file_is_left_out(self):
        tree = self.worktree("chore/tool")
        self.commit(tree, "backend/library/core.py", "VALUE = 2\n", "Change the core")
        self.checked(tree, cached=False)
        for name in ("docs/dev/CONTRACT.md.orig", "docs/dev/ARCHITECTURE.md", "docs/guide.md", "docs/CONTRACT.md"):
            with self.subTest(name):
                self.commit(tree, name, f"# {name}\n", f"Change {name}")
                self.checked(tree, cached=False)

    def test_the_clean_install_still_reruns_after_a_contract_edit(self):
        tree = self.worktree("chore/glue")
        self.commit(tree, "backend/hermes/glue.py", "GLUE = 2\n", "Change the glue")  # adds the clean install
        self.checked(tree, cached=False)
        self.assertTrue([entry for entry in self.check_log() if "script" in entry], self.check_log())
        self.commit(tree, "docs/dev/CONTRACT.md", "# Contract\n", "Describe it")
        self.checked(tree, cached=True)
        self.assertTrue([entry for entry in self.check_log() if "script" in entry], "the install key keeps docs")


class Readme(unittest.TestCase):
    def test_the_split_recipe_covers_old_re_exports_tool_order_and_the_exact_size_rule(self):
        text = (ROOT / "tools/retrodev/README.md").read_text()
        self.assertLess(len(text), 8000, "the README stays the entry")
        quick = text.split("## Quick path\n\n", 1)[1].split("\n\n", 1)[0].splitlines()
        self.assertEqual([row[:3] for row in quick], [f"{n}. " for n in range(1, 9)], "one numbered line per step")
        split = " ".join(text.split("### Split a long module", 1)[1].split("\n## ", 1)[0].split())
        self.assertIn("(so does an import it kept only for importers, once its last use moves out)", split)
        self.assertIn(
            "Moved tools keep their `TOOLS` positions (the registration snapshot pins the order): import them into "
            "the module that lists `TOOLS`, at the same places",
            split,
        )
        self.assertIn("under the 400-line warning (above 400 warns, above 600 fails)", split)
        layout = (ROOT / "tools/layout.toml").read_text()  # the numbers the recipe states, from the one size rule
        self.assertEqual(re.findall(r"^(warn|fail) = (\d+)$", layout, re.M), [("warn", "400"), ("fail", "600")])
        self.assertIn("`from .<new> import X as X`", retrodev_docs("README.md"))


if __name__ == "__main__":
    unittest.main()

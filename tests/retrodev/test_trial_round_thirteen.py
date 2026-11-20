"""Friction the thirteenth round of fresh-agent trials found: `new`'s next steps said to describe a tab or an RPC in
the page's row of docs/dev/STUDIO-PAGES.md, whose Pages table keeps short cells and a `### <Page>` subsection per page
since #70; sync gave no hint for a block dev rewrote into a longer one (a table row into a subsection); the body's
'What changed' warning named files cited only as evidence (yet a change from a file still claims it); the README's Quick path started without RETRODEV_AGENT.
Each test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_thirteen
"""

import io
import re
from pathlib import Path

from retrodev import body_names, config, output, sync

from tests.repo import test_pages_table
from tests.retrodev.fixture import GOOD_BODY, RepoCase, git, parallel, retrodev_docs
from tests.retrodev.test_scaffold import ScaffoldCase

load_tests = parallel
ROOT = Path(__file__).resolve().parents[2]
SUBSECTION = "as a bullet in its `### <Page>` subsection under `## Pages` of docs/dev/STUDIO-PAGES.md"


def joined(out) -> str:
    return " ".join(out["next"])


def add_row_and_subsection(doc: str, label: str) -> str:
    """What `new page`'s step asks: a short row last in the Pages table, a `### <label>` subsection under Pages."""
    lines = doc.split("\n")
    start = next(i for i, line in enumerate(lines) if line.startswith("## Pages"))
    last_row = next(
        i for i in range(start + 1, len(lines)) if lines[i].startswith("|") and not lines[i + 1].startswith("|")
    )
    lines.insert(last_row + 1, f"| {label} | not designed yet | not designed yet |")
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("## "))
    lines[end:end] = [f"### {label}", "", "- not designed yet", ""]
    return "\n".join(lines)


def add_bullet(doc: str, label: str, bullet: str) -> str:
    """What `new tab`'s step asks: a bullet in the page's subsection (the row untouched)."""
    return doc.replace(f"\n### {label}\n\n", f"\n### {label}\n\n- {bullet}\n", 1)


class PagesSteps(ScaffoldCase):
    def test_new_page_tab_and_rpc_point_to_the_page_s_subsection_and_following_them_keeps_the_table_test(self):
        page = joined(self.new("page", "rdprobe-notes", "--label", "Notes"))
        self.assertIn("a row in its Pages table (cells of at most 160 characters) plus a new `### Notes`", page)
        self.assertIn("with 'not designed yet' in the design columns", page)
        tab = joined(self.new("tab", "home", "rdprobe-extra"))
        self.assertIn(SUBSECTION + " (the table row stays short)", tab)
        rpc = joined(self.new("rpc", "history", "rdprobe_shown"))
        self.assertIn(SUBSECTION + " (the table row stays short)", rpc)
        for steps in (page, tab, rpc):
            self.assertNotIn("row of docs/dev/STUDIO-PAGES.md", steps)
            self.assertNotIn("its row in docs/dev/STUDIO-PAGES.md", steps)
        doc = (ROOT / "docs/dev/STUDIO-PAGES.md").read_text(encoding="utf-8")
        grown = add_bullet(add_row_and_subsection(doc, "Notes"), "Home", "the rdprobe-extra tab shows a probe")
        self.assertIn("\n### Notes\n", grown)
        self.assertEqual(test_pages_table.table_problems(grown), [])

    def test_no_retrodev_text_still_says_the_page_s_row(self):
        folder = ROOT / "tools" / "retrodev"
        stale = [
            f"{path.relative_to(ROOT)}: {line.strip()}"
            for path in sorted(folder.rglob("*"))
            if path.is_file() and path.suffix in (".py", ".md", ".tmpl")
            for line in path.read_text(encoding="utf-8").splitlines()
            if re.search(r"(?:row of|its row in) `?docs/dev/STUDIO-PAGES\.md", line)
        ]
        self.assertEqual(stale, [])


ROWS = (
    "# Pages\n\n## Pages\n\n| Page | Approved design |\n|---|---|\n"
    "| Home | Hero band with the title, the last game played and the quick start buttons under it |\n\n"
    "## Next\n\nMore.\n"
)
MINE = ROWS.replace("buttons under it |", "buttons under it, and a news strip at the bottom |")
REWRITTEN = ROWS.replace(
    "| Home | Hero band with the title, the last game played and the quick start buttons under it |\n",
    "| Home | Hero + band |\n\n### Home\n\n- Hero band with the title and the last game played\n"
    "- Quick start buttons under the band\n- The band keeps one line on a narrow window\n",
)


class SyncRewrite(RepoCase):
    def test_a_row_dev_rewrote_into_a_subsection_says_take_dev_s_side_and_where_to_redo_it(self):
        name = "docs/dev/STUDIO-PAGES.md"
        self.on_dev(name, ROWS, "Pages")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("docs/news")
        self.commit(tree, name, MINE)
        self.on_dev(name, REWRITTEN, "The row becomes a subsection")
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 1, out)
        fix = out["error"]["fix"]
        self.assertRegex(
            fix,
            r"docs/dev/STUDIO-PAGES\.md:\d+-\d+: dev rewrote this block; take dev's side, then redo your change in "
            r"the `### Home` subsection at docs/dev/STUDIO-PAGES\.md:\d+ in its own commit after sync",
        )
        self.assertNotIn("dev moved this block", fix)
        git(tree, "merge", "--abort")

    def test_a_row_dev_rewrote_into_two_alike_subsections_names_no_place_but_the_diff(self):
        name = "docs/dev/STUDIO-PAGES.md"
        self.on_dev(name, ROWS, "Pages")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("docs/news")
        self.commit(tree, name, MINE)
        twins = "- Hero band with the title, the last game played\n- Quick start buttons under the band\n"
        split = ROWS.replace(
            "| Home | Hero band with the title, the last game played and the quick start buttons under it |\n",
            f"| Home | Hero + band |\n\n### Hero\n\n{twins}\n### Band\n\n{twins}",
        )
        self.on_dev(name, split, "The row becomes two subsections")
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 1, out)
        fix = out["error"]["fix"]
        self.assertIn(
            "dev rewrote this block (see git diff HEAD...origin/dev -- docs/dev/STUDIO-PAGES.md); take dev's side, "
            "then redo your change where it belongs now in its own commit after sync",
            fix,
        )
        self.assertNotRegex(fix, r"redo your change in docs/dev/STUDIO-PAGES\.md:\d+")
        git(tree, "merge", "--abort")

    def test_only_a_modified_copy_of_a_removed_line_in_a_much_longer_dev_side_counts(self):
        base = ["| Home | Hero band with the title and the buttons |", "x"]
        dev = ["| Home | Hero |", "", "### Home", "- Hero band", "- Buttons", "x"]
        theirs = "\n".join(dev[:5])
        mine = "| Home | Hero band with the title and the buttons, and news |"
        self.assertEqual(sync.rewritten_from(mine, theirs, base, dev), [mine])
        self.assertEqual(sync.rewritten_from("| Away | something else entirely here |", theirs, base, dev), [])
        self.assertEqual(sync.rewritten_from(mine, "| Home | Hero |", base, dev), [], "dev's side is not longer")

    def test_a_rewritten_row_points_to_its_subsection_never_to_the_shortened_row(self):
        base = ["| Home | Hero band with the title and the buttons |", "x"]
        dev = ["| Home | Hero |", "", "### Home", "- Hero band", "- Buttons", "x"]
        mine = ["| Home | Hero band with the title and the buttons, and news |"]
        self.assertEqual(sync.new_location("docs/p.md", mine, dev, base), "the `### Home` subsection at docs/p.md:3")

    def test_without_a_heading_named_by_the_row_the_most_alike_block_wins_and_never_a_row(self):
        base = ["| Start | Hero band with the title and the buttons |", "x"]
        dev = ["| Start | Hero band with the title |", "", "### Landing", "- Hero band with the title", "- The buttons",
               "", "### Other", "- Unrelated words entirely", "x"]  # fmt: skip
        mine = ["| Start | Hero band with the title and the buttons, and news |"]
        self.assertEqual(sync.new_location("docs/p.md", mine, dev, base), "the `### Landing` subsection at docs/p.md:3")

    def test_two_blocks_about_as_alike_or_two_named_headings_name_no_place(self):
        base = ["| Start | Hero band with the title and the buttons |", "x"]
        twins = ["- Hero band with the title", "- The buttons"]
        dev = ["| Start | Hero |", "", "### Left", *twins, "", "### Right", *twins, "x"]
        mine = ["| Start | Hero band with the title and the buttons, and news |"]
        self.assertEqual(sync.new_location("docs/p.md", mine, dev, base), sync.AMBIGUOUS)
        named = ["| Start | Hero |", "## A", "### Start", "- one", "## B", "### Start", "- two", "x"]
        self.assertEqual(sync.new_location("docs/p.md", mine, named, base), sync.AMBIGUOUS)


class BodyCitedPaths(RepoCase):
    def warning(self, what: str) -> str:
        if not hasattr(self, "tree"):
            self.tree = self.worktree("fix/core")
            self.commit(self.tree, "backend/library/core.py", "VALUE = 2\n")
        tree = self.tree
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        return body_names.warning(ctx, GOOD_BODY.replace("Things.", what)) or ""

    def test_paths_cited_as_evidence_or_under_engine_do_not_warn(self):
        said = self.warning(
            "- `backend/library/core.py` keeps the value, checked against `backend/hermes/glue.py` and verified in "
            "`tests/backend/library/test_core.py`.\n"
            "- The value comes from `backend/library/names.py` (source: `docs/dev/CONTRACT.md`).\n"
            "- Changed the value to match `engine/modretro-chromatic/tools.json`."
        )
        self.assertEqual(said, "")

    def test_paths_a_sentence_claims_a_change_to_still_warn_and_say_to_ignore_a_cited_one(self):
        said = self.warning(
            "- Added `backend/library/extra.py` for the value.\n"
            "- `backend/hermes/glue.py`: takes the new value.\n"
            "- Things around `backend/library/core.py`."
        )
        self.assertIn("names the file(s) `backend/library/extra.py`, `backend/hermes/glue.py`, which the", said)
        self.assertIn("ignore if the file is only cited", said)

    def test_a_change_from_an_untouched_file_still_warns_and_a_source_it_comes_from_does_not(self):
        for claim in (
            "- Removed the obsolete helper from `backend/hermes/glue.py`.",
            "- Moved the parser from `backend/hermes/glue.py` to `backend/library/core.py`.",
            "- Deleted the old copy from `backend/hermes/glue.py`.",
        ):
            with self.subTest(claim=claim):
                self.assertIn("names the file(s) `backend/hermes/glue.py`, which the", self.warning(claim))
        quiet = (
            "- Changed `backend/library/core.py`: the numbers come from `backend/hermes/glue.py`, taken from "
            "`backend/library/names.py`, read from `docs/dev/CONTRACT.md` and copied from `tools/layout.toml`."
        )
        self.assertEqual(self.warning(quiet), "")


class QuickPath(RepoCase):
    def test_step_three_starts_with_the_agent_named(self):
        readme = retrodev_docs("README.md")
        self.assertIn("3. `RETRODEV_AGENT='<agent, model>' python tools/retrodev start <kind>/<topic>`", readme)

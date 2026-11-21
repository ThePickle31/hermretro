"""The trial rounds' regressions for this area (RoundEightNew, RoundThirteen), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_new_page
"""

import re
from tests.retrodev.fixture import parallel
from tests.retrodev.test_scaffold import ROOT, ScaffoldCase
from tests.repo import test_pages_table

load_tests = parallel


def joined(out) -> str:
    return " ".join(out["next"])


SUBSECTION = "as a bullet in its `### <Page>` subsection under `## Pages` of docs/dev/STUDIO-PAGES.md"


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


class PageRoundEightNew(ScaffoldCase):
    def test_the_next_steps_name_every_place_that_lists_the_pages(self):
        steps = joined(self.new("page", "rdprobe-board"))
        self.assertIn("README.md 'What works today'", steps)
        self.assertIn("docs/dev/CONTRACT.md 'Studio pages (desktop) and their RPCs'", steps)
        self.assertIn("docs/dev/STUDIO-PAGES.md: a row in its Pages table", steps)
        self.assertIn("## What works today", (ROOT / "README.md").read_text())
        self.assertIn("## Studio pages", (ROOT / "docs/dev/CONTRACT.md").read_text())
        self.assertIn("## Pages", (ROOT / "docs/dev/STUDIO-PAGES.md").read_text())


class PagesStepsRoundThirteen(ScaffoldCase):
    def test_new_page_tab_and_rpc_point_to_the_page_s_subsection_and_following_them_keeps_the_table_test(self):
        page = joined(self.new("page", "rdprobe-notes", "--label", "Notes"))
        self.assertIn("a row in its Pages table (cells of at most 160 characters) plus a new `### Notes`", page)
        self.assertIn("with 'not designed yet' in the design columns", page)
        tab = joined(self.new("tab", "build", "rdprobe-extra"))
        self.assertIn(SUBSECTION + " (the table row stays short)", tab)
        rpc = joined(self.new("rpc", "history", "rdprobe_shown"))
        self.assertIn(SUBSECTION + " (the table row stays short)", rpc)
        for steps in (page, tab, rpc):
            self.assertNotIn("row of docs/dev/STUDIO-PAGES.md", steps)
            self.assertNotIn("its row in docs/dev/STUDIO-PAGES.md", steps)
        doc = (ROOT / "docs/dev/STUDIO-PAGES.md").read_text(encoding="utf-8")
        grown = add_bullet(add_row_and_subsection(doc, "Notes"), "Games", "the rdprobe-extra tab shows a probe")
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

"""docs/dev/STUDIO-PAGES.md's Pages table keeps short cells, each page's design in its own subsection.

Cells of over a thousand characters were hard to edit; a page's details go in its `### <Page>` subsection under
"## Pages", one bullet per area.
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DOC = ROOT / "docs/dev/STUDIO-PAGES.md"
MAX_CELL = 160


def section(text: str, heading: str) -> str:
    start = text.index(heading)
    following = re.search(r"^## ", text[start + len(heading) :], re.M)
    return text[start : start + len(heading) + following.start()] if following else text[start:]


def table_problems(text: str) -> list[str]:
    pages = section(text, "## Pages")
    rows = [line for line in pages.splitlines() if line.startswith("| ") and not line.startswith("| Page |")]
    problems = []
    for row in rows:
        cells = [cell.strip() for cell in row.strip().strip("|").split(" | ")]
        name = cells[0]
        problems += [
            f"{name}: a cell of {len(cell)} characters (at most {MAX_CELL})" for cell in cells if len(cell) > MAX_CELL
        ]
        if f"\n### {name}\n" not in pages:
            problems.append(f"{name}: no '### {name}' subsection under '## Pages'")
    return problems if rows else ["the Pages table has no rows"]


class PagesTable(unittest.TestCase):
    def test_the_pages_table_has_short_cells_and_a_subsection_per_page(self):
        self.assertEqual(
            table_problems(DOC.read_text(encoding="utf-8")),
            [],
            "FIX: move the page's design into its '### <Page>' subsection under '## Pages', one bullet per area",
        )

    def test_a_long_cell_or_a_missing_subsection_is_caught(self):
        doc = (
            "## Pages\n\n| Page | Approved design | Mockup |\n|---|---|---|\n| Home | "
            + "x" * 200
            + " | m |\n\n## Next\n"
        )
        self.assertEqual(
            table_problems(doc),
            ["Home: a cell of 200 characters (at most 160)", "Home: no '### Home' subsection under '## Pages'"],
        )


if __name__ == "__main__":
    unittest.main()

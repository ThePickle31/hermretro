"""Every ruff exception (``# noqa: <CODE>``) says why, so the next person knows whether it still holds.

The reason follows the codes after ' - ' or an em dash, on the same line:

    lock = open(path, "a+")  # noqa: SIM115 - a lock held until the process exits

A bare ``# noqa``, or codes with nothing after them (or a reason in brackets), fails. The vendored engine and the
pinned npm tools are not ours and are skipped.

Run alone: python -m unittest tests.repo.test_noqa
"""

import io
import re
import sys
import tokenize
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.repo.test_layout import files  # noqa: E402 - the repository root goes on sys.path first

SKIPPED = ("engine/", "tools/npm/")
NOQA = re.compile(r"#\s*noqa\b")
REASONED = re.compile(r"#\s*noqa:\s*[A-Z]+[0-9]+(?:\s*,\s*[A-Z]+[0-9]+)*\s+(?:-|\u2014)\s+\S")


def unreasoned(text: str, file: str) -> list[str]:
    """The comments in ``text`` (Python source) that carry a noqa without its reason; strings never count."""
    found = []
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.COMMENT and NOQA.search(token.string) and not REASONED.search(token.string):
            found.append(f"{file}:{token.start[0]}: {token.line.strip()}")
    return found


class Noqa(unittest.TestCase):
    def test_the_pattern(self):
        self.assertEqual(unreasoned("import x  # noqa: F401 - re-exported\n", "a.py"), [])
        self.assertEqual(unreasoned("s = '# noqa'  # a string is not a comment\n", "a.py"), [])
        self.assertEqual(unreasoned("import x  # noqa: E402, F401 \u2014 the root goes first\n", "a.py"), [])
        for bare in (
            "import x  # noqa",
            "import x  # noqa: F401",
            "import x  # noqa: F401  (brackets)",
            "import x  # noqa: F401 -",
            "import x  # noqa: F401 re-exported",
        ):
            self.assertEqual(len(unreasoned(bare + "\n", "a.py")), 1, bare)

    def test_every_noqa_has_a_reason(self):
        problems = []
        for name in files():
            if name.endswith(".py") and not name.startswith(SKIPPED):
                problems += unreasoned((ROOT / name).read_text(encoding="utf-8", errors="replace"), name)
        self.assertEqual(
            problems,
            [],
            "\nA lint exception without its reason cannot be judged later (does it still hold?):\n  "
            + "\n  ".join(problems)
            + "\nFIX: change the code so the rule passes, or write the reason after the codes: "
            "'# noqa: <CODE> - <reason>' (or an em dash), as docs/dev/TESTING.md shows",
        )


if __name__ == "__main__":
    unittest.main()

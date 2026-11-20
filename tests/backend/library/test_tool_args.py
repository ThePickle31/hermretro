"""backend/library/tool_args.py's docstring lists every error code a library tool answers with, and only those
(tool_project's own codes come from backend/hermes/tool_args.py, which it re-exports).

Run alone: python -m unittest tests.backend.library.test_tool_args
"""

import re
import unittest
from pathlib import Path

from backend.library import tool_args

LIBRARY = Path(__file__).resolve().parents[3] / "backend" / "library"
# A code is the second argument of tool_error (or its old name _present_error), or a "code": "..." value.
CODE = re.compile(
    r'"code": "([A-Z_]+)"|(?:tool_error|_present_error)\((?:[^()]|\([^()]*\))*?,\s*"([A-Z_]+)"\s*,?\s*\)', re.S
)


class ToolErrorCodes(unittest.TestCase):
    def test_the_docstring_lists_the_codes_in_use(self):
        used = set()
        for path in (LIBRARY / "tools.py", LIBRARY / "tool_args.py", LIBRARY.parent / "hermes" / "tool_args.py"):
            text = path.read_text(encoding="utf-8")
            used |= {a or b for a, b in CODE.findall(text)}
        listed = set(re.findall(r"^- ``([A-Z_]+)``:", tool_args.__doc__ or "", re.M))
        self.assertIn("NO_PROJECT", used, "the code pattern must still find the codes")
        self.assertEqual(
            listed,
            used,
            "FIX: list each code a library tool answers with in backend/library/tool_args.py's docstring "
            "(and drop codes no longer used)",
        )


if __name__ == "__main__":
    unittest.main()

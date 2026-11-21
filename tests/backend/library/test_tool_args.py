"""backend/library/tool_args.py's docstring lists every error code a library tool answers with, and only those
(tool_project's own codes come from backend/hermes/tool_args.py, which it re-exports).

The codes are read from tools.py and every *_tools.py sibling (the modules `retrodev new tool` writes past 400
lines; the same set tools/retrodev/scaffold_tool.py reads), plus both tool_args.py.

Run alone: python -m unittest tests.backend.library.test_tool_args
"""

import re
import tempfile
import unittest
from pathlib import Path

from backend.library import tool_args

LIBRARY = Path(__file__).resolve().parents[3] / "backend" / "library"
# A code is the second argument of tool_error, or a "code": "..." value.
CODE = re.compile(r'"code": "([A-Z_]+)"|tool_error\((?:[^()]|\([^()]*\))*?,\s*"([A-Z_]+)"\s*,?\s*\)', re.S)


def tool_modules(folder: Path) -> list[Path]:
    """tools.py, then each <name>_tools.py sibling in name order, then the two tool_args.py."""
    return [
        folder / "tools.py",
        *sorted(folder.glob("*_tools.py")),
        folder / "tool_args.py",
        folder.parent / "hermes" / "tool_args.py",
    ]


def used_codes(folder: Path) -> set[str]:
    used = set()
    for path in tool_modules(folder):
        if path.is_file():
            used |= {a or b for a, b in CODE.findall(path.read_text(encoding="utf-8"))}
    return used


class ToolErrorCodes(unittest.TestCase):
    def test_the_docstring_lists_the_codes_in_use(self):
        used = used_codes(LIBRARY)
        listed = set(re.findall(r"^- ``([A-Z_]+)``:", tool_args.__doc__ or "", re.M))
        self.assertIn("NO_PROJECT", used, "the code pattern must still find the codes")
        self.assertEqual(
            listed - used,
            set(),
            "listed in backend/library/tool_args.py's docstring but answered by no tool in backend/library/tools.py "
            "or a *_tools.py sibling\nFIX: drop those codes from the docstring (or restore the tool_error that "
            "answers with them)",
        )
        self.assertEqual(
            used - listed,
            set(),
            "answered by a library tool (backend/library/tools.py or a *_tools.py sibling) but missing from "
            "backend/library/tool_args.py's docstring\nFIX: add a `- ``CODE``: <when>` line for each to that docstring",
        )

    def test_a_sibling_tools_module_counts(self):
        """A tool moved to <x>_tools.py (as `retrodev new tool` does past 400 lines) keeps its codes in use."""
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "library"
            folder.mkdir()
            (folder / "tools.py").write_text('def a():\n    return tool_error("no", "NO_PROJECT")\n')
            (folder / "game_tools.py").write_text('def b():\n    return tool_error(f"bad {x}", "ONLY_IN_SIBLING")\n')
            (folder / "helpers.py").write_text('def c():\n    return tool_error("no", "NOT_A_TOOL_MODULE")\n')
            used = used_codes(folder)
        self.assertIn("ONLY_IN_SIBLING", used, "a *_tools.py sibling's codes must count as used")
        self.assertIn("NO_PROJECT", used)
        self.assertNotIn("NOT_A_TOOL_MODULE", used, "only tools.py and *_tools.py are tool modules")


if __name__ == "__main__":
    unittest.main()

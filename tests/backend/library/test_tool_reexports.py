"""backend/library/tools.py keeps re-exporting the shared tool helpers from tool_args.py, as the same objects, with a
reasoned ``# noqa: F401``, so ``python tools/check.py fix`` (ruff's unused-import fix) cannot drop them once a split
leaves tools.py itself not using one.

Run alone: python -m unittest tests.backend.library.test_tool_reexports
"""

import ast
import unittest
from pathlib import Path

from backend.library import tool_args, tools

SOURCE = Path(tools.__file__).read_text(encoding="utf-8")


class ToolReexports(unittest.TestCase):
    def test_the_shared_helpers_are_re_exported_explicitly(self):
        lines = SOURCE.splitlines()
        found = {}
        for node in ast.parse(SOURCE).body:
            if isinstance(node, ast.ImportFrom) and node.module == "tool_args" and node.level == 1:
                for alias in node.names:
                    found[alias.asname or alias.name] = lines[node.end_lineno - 1]
        self.assertEqual(sorted(found), ["_present_error", "_tool_project"])
        for name, line in found.items():
            self.assertIn("# noqa: F401 - re-exported", line, f"{name}: ruff's fix would remove an unused re-export")
            self.assertIs(getattr(tools, name), getattr(tool_args, name))


if __name__ == "__main__":
    unittest.main()

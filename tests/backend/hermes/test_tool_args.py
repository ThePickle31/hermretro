"""backend/hermes/tool_args.py: the tool helpers any feature may use (tool_error, tool_project).

Run alone: python -m unittest tests.backend.hermes.test_tool_args
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.hermes import tool_args
from backend.library import tool_args as library_tool_args
from tests.repo import test_boundaries

ROOT = Path(__file__).resolve().parents[3]


class ToolHelpers(unittest.TestCase):
    def test_the_library_re_exports_the_same_helpers(self):
        self.assertIs(library_tool_args.tool_error, tool_args.tool_error)
        self.assertIs(library_tool_args.tool_project, tool_args.tool_project)

    def test_answers(self):
        self.assertEqual(json.loads(tool_args.tool_error("no", "X")), {"ok": False, "error": "no", "code": "X"})
        with tempfile.TemporaryDirectory() as project:
            self.assertEqual(tool_args.tool_project("t", {"project": project}, {}), (project, None))
            root, error = tool_args.tool_project("t", {"project": str(Path(project) / "missing")}, {})
        self.assertIsNone(root)
        self.assertEqual(json.loads(error or "{}").get("code"), "PROJECT_NOT_FOUND")

    def test_a_feature_other_than_library_may_import_them(self):
        """history (any feature but the standard-library-only ones the broker imports) imports the Hermes layer."""
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp)
            shutil.copytree(ROOT / "backend", copy / "backend", ignore=shutil.ignore_patterns("__pycache__"))
            (copy / "backend" / "history" / "planted_tools.py").write_text(
                "from ..hermes import host\nfrom ..hermes.tool_args import tool_error, tool_project\n"
            )
            problems = [p for p in test_boundaries.check(copy) if "planted_tools.py" in p[1]]
        self.assertEqual(problems, [], "tests/repo/test_boundaries.py must allow backend.hermes.tool_args")


if __name__ == "__main__":
    unittest.main()

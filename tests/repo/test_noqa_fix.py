"""`python tools/check.py fix` gives a bare ``# noqa: E402`` its standard reason (tools/py/noqa_reasons.py).

Every E402 exception here means the same thing (the root goes on sys.path before the import), so the fix writes
'# noqa: E402 - the repository root goes on sys.path first' in .py and .py.tmpl files outside engine/ and
tools/npm/. Other bare codes need a person's reason and stay as they are (tests/repo/test_noqa.py names them).

Run alone: python -m unittest tests.repo.test_noqa_fix
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "py"))

import check  # noqa: E402 - tools/check.py is imported from its own folder
import noqa_reasons  # noqa: E402 - tools/py/noqa_reasons.py is imported from its own folder

FIXED = "# noqa: E402 - the repository root goes on sys.path first"
BARE = "import x  # noqa: E402\n"
OTHER = "import y  # noqa: F401\n"


class AddReason(unittest.TestCase):
    def test_a_bare_e402_gets_the_reason_and_nothing_else_changes(self):
        text = "import sys\n" + BARE + "import z  # noqa: E402 - a reason of its own\n" + OTHER
        fixed, count = noqa_reasons.add_reason(text)
        self.assertEqual(count, 1)
        self.assertEqual(
            fixed, f"import sys\nimport x  {FIXED}\nimport z  # noqa: E402 - a reason of its own\n" + OTHER
        )
        self.assertEqual(noqa_reasons.add_reason(fixed), (fixed, 0), "a second run changes nothing")

    def test_a_string_is_not_a_comment(self):
        text = 's = """\n# noqa: E402\n"""\n'
        self.assertEqual(noqa_reasons.add_reason(text), (text, 0))

    def test_crlf_and_spacing_are_kept(self):
        self.assertEqual(noqa_reasons.add_reason("import x  #noqa:E402  \r\n"), (f"import x  {FIXED}\r\n", 1))


class CheckFix(unittest.TestCase):
    def test_check_fix_adds_the_reason_where_it_belongs_and_reports_the_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {
                "tests/a.py": BARE + BARE,
                "tools/retrodev/templates/b.py.tmpl": "{{name}} = 1\n" + BARE,
                "engine/c.py": BARE,
                "tools/npm/d.py": BARE,
                "tests/e.py": OTHER,
                "notes.md": BARE,
            }
            for name, text in files.items():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text(text)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            out = []
            with (
                mock.patch.object(check, "ROOT", root),
                mock.patch.object(check, "ruff_missing", lambda: "ruff is not installed in .dev/py"),
                mock.patch("builtins.print", lambda *a, **_k: out.append(" ".join(map(str, a)))),
            ):
                code = check.fix(SimpleNamespace(strict=False))
            self.assertEqual(code, 1, "no ruff: the rest of the fix stops, the noqa reasons are still written")
            self.assertEqual((root / "tests/a.py").read_text(), f"import x  {FIXED}\n" * 2)
            self.assertEqual(
                (root / "tools/retrodev/templates/b.py.tmpl").read_text(), f"{{{{name}}}} = 1\nimport x  {FIXED}\n"
            )
            for name in ("engine/c.py", "tools/npm/d.py", "tests/e.py", "notes.md"):
                self.assertEqual((root / name).read_text(), files[name], name)
            self.assertIn("gave 3 bare '# noqa: E402' the standard reason", out[0])
            self.assertIn("tests/a.py", out[0])


if __name__ == "__main__":
    unittest.main()

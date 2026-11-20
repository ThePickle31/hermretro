"""Committed markdown has no backslash-escaped quote (\\" or \\') outside code.

Markdown shows a quote as it is, so `\\"` outside a code span or block renders the backslash too: it is what an edit
that wrote a string literal into a document leaves behind. The vendored engine's documents are its own.
"""

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

FENCE = re.compile(r"^\s*(```|~~~)")
CODE_SPAN = re.compile(r"(`+)(?:.+?)\1")
ESCAPED_QUOTE = re.compile(r"\\[\"']")
NOT_OURS = ("engine/",)


def stray_escapes(text: str) -> list[int]:
    """Line numbers (1-based) with a backslash-escaped quote outside code spans and fenced blocks."""
    found, fence = [], None
    for number, line in enumerate(text.splitlines(), 1):
        opened = FENCE.match(line)
        if opened:
            if fence is None:
                fence = opened.group(1)
            elif opened.group(1) == fence:
                fence = None
            continue
        if fence is None and ESCAPED_QUOTE.search(CODE_SPAN.sub("", line)):
            found.append(number)
    return found


def committed_markdown() -> list[str]:
    listed = subprocess.run(["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [name for name in listed.splitlines() if not name.startswith(NOT_OURS)]


class DocEscapes(unittest.TestCase):
    def test_no_committed_document_has_an_escaped_quote(self):
        problems = []
        for name in committed_markdown():
            path = ROOT / name
            if path.is_file():
                problems += [f"{name}:{line}" for line in stray_escapes(path.read_text(encoding="utf-8"))]
        self.assertEqual(
            problems, [], "FIX: write the quote without its backslash (markdown shows \\\" as a backslash and a quote)"
        )

    def test_the_rule_catches_an_escape_in_a_temp_doc(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "doc.md"
            doc.write_text(
                'Plain "quotes" are fine.\n'
                'A trial wrote \\"Reset text\\" here.\n'
                "Code `say(\\\"hi\\\")` is fine.\n"
                "```\nprint(\\'hi\\')\n```\n"
                "And it\\'s caught here.\n",
                encoding="utf-8",
            )
            self.assertEqual(stray_escapes(doc.read_text(encoding="utf-8")), [2, 7])


if __name__ == "__main__":
    unittest.main()

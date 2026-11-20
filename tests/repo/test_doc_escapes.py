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

from tests.repo.markdown import fenced_lines, without_code_spans  # noqa: E402 - the repository root goes on the path first

ESCAPED_QUOTE = re.compile(r"\\[\"']")
NOT_OURS = ("engine/",)


def stray_escapes(text: str) -> list[int]:
    """Line numbers (1-based) with a backslash-escaped quote outside code spans and fenced blocks."""
    lines = text.splitlines()
    return [
        number
        for number, (line, fenced) in enumerate(zip(lines, fenced_lines(text), strict=True), 1)
        if not fenced and ESCAPED_QUOTE.search(without_code_spans(line))
    ]


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

    def test_a_longer_fence_closes_only_on_a_matching_fence(self):
        text = (
            "````md\n"  # 1: a four-backtick block showing a three-backtick example
            "```py\n"
            "print(\\'inside\\')\n"
            "```\n"
            "still code \\'here\\'\n"  # 5: the shorter fence did not close the block
            "```` trailing\n"  # 6: text after a fence: not a closing fence
            "code \\'too\\'\n"
            "````\n"  # 8: closes
            'Prose \\"after\\" the block.\n'  # 9: flagged
        )
        self.assertEqual(stray_escapes(text), [9])

    def test_tilde_fences_follow_the_same_rule(self):
        text = "~~~~\n~~~\nprint(\\'hi\\')\n```\n~~~~~\nIt\\'s prose.\n"
        self.assertEqual(stray_escapes(text), [6])

    def test_an_indented_fence_of_four_spaces_is_not_a_fence(self):
        self.assertEqual(stray_escapes("```\nx = \\'a\\'\n    ```\ny = \\'b\\'\n```\nIt\\'s prose.\n"), [6])

    def test_code_spans_close_on_a_run_of_the_same_length(self):
        text = (
            'Double ``say(`\\"hi\\"`)`` is code.\n'  # a span of two holds single backticks
            'A run ``` \\"a\\" `` is no span.\n'  # three opens, nothing closes it: prose
        )
        self.assertEqual(stray_escapes(text), [2])


if __name__ == "__main__":
    unittest.main()

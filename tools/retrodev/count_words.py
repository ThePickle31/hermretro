"""How docs/dev/CONTRACT.md writes the plugin-owned tools' count: a word through twenty, digits past it.

The one policy for both sides: the `new tool` scaffold (scaffold_backend.py) writes the count with it, and
tests/repo/test_lockstep.py checks the count with it (loading this file by path). Stdlib only.
"""

from __future__ import annotations

WORDS = [
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
]
NUMBER_WORDS = dict(enumerate(WORDS, start=1))


def count_text(number: int) -> str:
    """The count as CONTRACT.md writes it: 'seven' for 7, '21' for 21."""
    return NUMBER_WORDS.get(number, str(number))


def count_value(text: str) -> int | None:
    """The number a written count stands for ('seven' or '7' -> 7); None when it is neither."""
    for number, word in NUMBER_WORDS.items():
        if word == text:
            return number
    return int(text) if text.isdigit() else None

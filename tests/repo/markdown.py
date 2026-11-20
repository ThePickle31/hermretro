"""Where code is in a markdown document, by CommonMark's rules, for the repository checks that read prose.

A fenced block opens on a line of three or more backticks or tildes (at most three spaces in) and closes only on a
fence of the same character, at least as long, with nothing but whitespace after it: a four-backtick block can show
a three-backtick example. An inline code span opened by N backticks closes on the next run of exactly N.
"""

import re

OPENING = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def _closes(line: str, fence: str) -> bool:
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3:
        return False
    run = len(stripped) - len(stripped.lstrip(fence[0]))
    return run >= len(fence) and not stripped[run:].strip()


def fenced_lines(text: str) -> list[bool]:
    """For each line of ``text`` (``str.splitlines``), whether it is a fence or inside a fenced block."""
    marks, fence = [], None
    for line in text.splitlines():
        if fence is not None:
            marks.append(True)
            if _closes(line, fence):
                fence = None
            continue
        opened = OPENING.match(line)
        if opened and not (opened.group(1)[0] == "`" and "`" in opened.group(2)):
            fence = opened.group(1)
        marks.append(fence is not None)
    return marks


def without_fences(text: str) -> str:
    """``text`` with every fenced block's lines (fences included) blanked, so line numbers stay the same."""
    lines = text.splitlines()
    return "\n".join("" if fenced else line for line, fenced in zip(lines, fenced_lines(text), strict=True))


def split_code_spans(line: str) -> list[tuple[str, bool]]:
    """``line`` cut into ``(piece, is_code)``; a code piece is a span's content without its backticks."""
    pieces: list[tuple[str, bool]] = []
    plain, index = [], 0
    while index < len(line):
        if line[index] != "`":
            plain.append(line[index])
            index += 1
            continue
        end = index
        while end < len(line) and line[end] == "`":
            end += 1
        width, close = end - index, None
        search = end
        while search < len(line):
            if line[search] != "`":
                search += 1
                continue
            run_end = search
            while run_end < len(line) and line[run_end] == "`":
                run_end += 1
            if run_end - search == width:
                close = search
                break
            search = run_end
        if close is None:
            plain.append(line[index:end])  # no closing run of the same length: literal backticks
            index = end
            continue
        if plain:
            pieces.append(("".join(plain), False))
            plain = []
        pieces.append((line[end:close], True))
        index = close + width
    if plain:
        pieces.append(("".join(plain), False))
    return pieces


def without_code_spans(line: str) -> str:
    """``line`` with its inline code spans removed."""
    return "".join(piece for piece, code in split_code_spans(line) if not code)

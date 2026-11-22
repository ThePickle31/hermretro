"""Where code is in a markdown document, by CommonMark's rules, for the repository checks that read prose.

A fenced block opens on a line of three or more backticks or tildes (at most three spaces in) and closes only on a
fence of the same character, at least as long, with nothing but whitespace after it: a four-backtick block can show
a three-backtick example. An inline code span opened by N backticks closes on the next run of exactly N, which may
be on a later line of the same paragraph; in prose a backtick after an odd run of backslashes is literal and opens
none, while inside a span a backslash is literal and escapes nothing.
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


def _spans(text: str) -> list[tuple[int, int, int]]:
    """Each code span in ``text`` as ``(start, end, width)``: ``text[start:end]`` is the span with its backticks."""
    spans: list[tuple[int, int, int]] = []
    index, prose_from = 0, 0
    while index < len(text):
        if text[index] != "`":
            index += 1
            continue
        slashes = index
        while slashes > prose_from and text[slashes - 1] == "\\":
            slashes -= 1
        if (index - slashes) % 2:
            index += 1  # an escaped backtick is literal; any backticks after it start their own run
            continue
        end = index
        while end < len(text) and text[end] == "`":
            end += 1
        width, close, search = end - index, None, end
        while search < len(text):
            if text[search] != "`":
                search += 1
                continue
            run_end = search
            while run_end < len(text) and text[run_end] == "`":
                run_end += 1
            if run_end - search == width:
                close = search
                break
            search = run_end
        if close is None:
            index = end  # no closing run of the same length: literal backticks
            continue
        spans.append((index, close + width, width))
        index = prose_from = close + width
    return spans


def _content(raw: str) -> str:
    """A span's content as rendered: line endings become spaces, and one space is dropped from each end when both ends
    have one and it is not all spaces."""
    raw = raw.replace("\n", " ")
    if len(raw) >= 2 and raw[0] == " " and raw[-1] == " " and raw.strip(" "):
        raw = raw[1:-1]
    return raw


def split_code_spans(text: str) -> list[tuple[str, bool]]:
    """``text`` (one line, or one paragraph's lines) cut into ``(piece, is_code)``; a code piece is a span's content
    as rendered, without its backticks."""
    pieces: list[tuple[str, bool]] = []
    at = 0
    for start, end, width in _spans(text):
        if start > at:
            pieces.append((text[at:start], False))
        pieces.append((_content(text[start + width : end - width]), True))
        at = end
    if at < len(text):
        pieces.append((text[at:], False))
    return pieces

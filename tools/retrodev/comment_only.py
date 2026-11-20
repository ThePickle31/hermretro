"""Whether a change to a source file touches only its comments, docstrings and blank lines (comments_only answers).

Python: the two sides' syntax trees with every docstring dropped (a comment is never in the tree). JavaScript
(.js, .mjs): the text with its // and /* */ comments cut, outside strings and template literals, then compared line by
line without blank lines or trailing spaces; each template literal's text stays byte-exact (compared on its own, never
normalised). Any other '/' in the code (a division or a regular expression literal, which only context tells apart)
makes the file unreadable here. Anything this cannot read for sure (a syntax error, such a '/', another kind of file,
a missing side) counts as a real change: the caller then does what it did before.
"""

from __future__ import annotations

import ast

JS_SUFFIXES = (".js", ".mjs")


def python_shape(text: str) -> str | None:
    """The module's syntax tree without docstrings, as text (None when it does not parse)."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) or not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            node.body = body[1:] or [ast.Pass()]
    return ast.dump(tree, include_attributes=False)


TEMPLATE = "\x00"  # stands in the code for one piece of template literal text, kept apart byte-exact


def js_without_comments(text: str, pieces: list[str] | None = None) -> str | None:
    """``text`` with its comments cut (None when a string, template or comment never closes, or when the code holds a
    '/' that opens no comment: a division or a regular expression, which only context tells apart). With ``pieces``, each
    template literal's text (from its ` or } to its closing ` or up to its ${) goes there verbatim, a TEMPLATE mark in its place."""
    out: list[str] = []
    keep = out if pieces is None else []
    braces: list[int] = []  # for each open template ${...}: the brace depth it closes at
    depth, i, n = 0, 0, len(text)
    in_template = False
    while i < n:
        c = text[i]
        if in_template:
            if c == "\\":
                keep.append(text[i : i + 2])
                i += 2
            elif c == "`" or text.startswith("${", i):
                keep.append("`" if c == "`" else "")
                if pieces is not None:
                    pieces.append("".join(keep))
                    keep.clear()
                if c != "`":
                    out.append("${")
                    braces.append(depth)
                    depth += 1
                in_template, i = False, i + 1 + (c != "`")
            else:
                keep.append(c)
                i += 1
            continue
        if text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end < 0 else end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                return None
            out.append(" " if "\n" not in text[i:end] else "\n" * text.count("\n", i, end))
            i = end + 2
        elif c in "'\"":
            end = i + 1
            while end < n and text[end] != c and text[end] != "\n":
                end += 2 if text[end] == "\\" else 1
            if end >= n or text[end] != c:
                return None
            out.append(text[i : end + 1])
            i = end + 1
        elif c == "`":
            _open_template(out, keep, pieces, c)
            in_template, i = True, i + 1
        elif c == "/":  # a division or a regular expression: telling them apart needs a parser, so unsure
            return None
        else:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if braces and depth == braces[-1]:
                    braces.pop()
                    _open_template(out, keep, pieces, c)
                    in_template, i = True, i + 1
                    continue
            out.append(c)
            i += 1
    return None if in_template else "".join(out)


def _open_template(out: list[str], keep: list[str], pieces: list[str] | None, c: str) -> None:
    """A piece of template text starts at ``c``: in the code itself, or (with pieces) a mark there and the text kept."""
    if pieces is not None:
        out.append(TEMPLATE)
    keep.append(c)


def js_shape(text: str) -> str | None:
    """The code without comments, blank lines and trailing spaces, then every template text piece byte-exact."""
    pieces: list[str] = []
    cut = js_without_comments(text, pieces)
    if cut is None:
        return None
    code = "\n".join(line.rstrip() for line in cut.splitlines() if line.strip())
    return code + TEMPLATE * 2 + TEMPLATE.join(pieces)


def comments_only(path: str, before: str | None, after: str | None) -> bool:
    """The two sides of ``path`` differ only in comments, docstrings or blank lines (False when unsure)."""
    if before is None or after is None:
        return False
    if path.endswith(".py"):
        shape = python_shape
    elif path.endswith(JS_SUFFIXES):
        shape = js_shape
    else:
        return False
    old, new = shape(before), shape(after)
    return old is not None and old == new

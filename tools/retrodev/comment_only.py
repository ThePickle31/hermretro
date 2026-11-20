"""Whether a change to a source file touches only its comments, docstrings and blank lines (comments_only answers).

Python: the two sides' syntax trees with every docstring dropped (a comment is never in the tree). JavaScript
(.js, .mjs): the text with its // and /* */ comments cut, outside strings, template literals and regular expression
literals, then compared line by line without blank lines or trailing spaces. Anything this cannot read for sure (a
syntax error, another kind of file, a missing side) counts as a real change: the caller then does what it did before.
"""

from __future__ import annotations

import ast

JS_SUFFIXES = (".js", ".mjs")
# A '/' after one of these (or at the start) opens a regular expression literal, not a division.
REGEX_BEFORE = set("(,=:[!&|?{};+-*%<>~^")
REGEX_WORDS = ("return", "typeof", "case", "do", "else", "in", "of", "void", "yield", "await", "delete", "throw")


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


def _regex_allowed(out: list[str]) -> bool:
    """A '/' here starts a regular expression literal: what came before is an operator, an opening or a keyword."""
    code = "".join(out[-40:]).rstrip()
    if not code or code[-1] in REGEX_BEFORE:
        return True
    return any(
        code.endswith(word) and not (code[: -len(word)][-1:].isalnum() or code[: -len(word)][-1:] in "_$")
        for word in REGEX_WORDS
    )


def js_without_comments(text: str) -> str | None:
    """``text`` with its comments cut (None when a string, template or comment never closes)."""
    out: list[str] = []
    braces: list[int] = []  # for each open template ${...}: the brace depth it closes at
    depth, i, n = 0, 0, len(text)
    in_template = False
    while i < n:
        c = text[i]
        if in_template:
            if c == "\\":
                out.append(text[i : i + 2])
                i += 2
            elif c == "`":
                out.append(c)
                in_template, i = False, i + 1
            elif text.startswith("${", i):
                out.append("${")
                braces.append(depth)
                depth += 1
                in_template, i = False, i + 2
            else:
                out.append(c)
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
            out.append(c)
            in_template, i = True, i + 1
        elif c == "/" and _regex_allowed(out):
            end, in_class = i + 1, False
            while end < n and text[end] != "\n" and (in_class or text[end] != "/"):
                if text[end] == "\\":
                    end += 1
                elif text[end] == "[":
                    in_class = True
                elif text[end] == "]":
                    in_class = False
                end += 1
            if end >= n or text[end] != "/":
                return None
            out.append(text[i : end + 1])
            i = end + 1
        else:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if braces and depth == braces[-1]:
                    braces.pop()
                    out.append(c)
                    in_template, i = True, i + 1
                    continue
            out.append(c)
            i += 1
    return None if in_template else "".join(out)


def js_shape(text: str) -> str | None:
    cut = js_without_comments(text)
    if cut is None:
        return None
    return "\n".join(line.rstrip() for line in cut.splitlines() if line.strip())


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

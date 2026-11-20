"""Probe pages whose index.js defines its own Page, for `new tab --from-page` (scaffold_move.py): the fast tests in
test_scaffold_move.py and the slow bundle run in test_scaffold_tree.py (moved_pages_bundle) share them.
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

from retrodev import scaffold_move

from tests.retrodev.tree_copy import git_ok, run

ROOT = Path(__file__).resolve().parents[2]
needs_acorn = unittest.skipUnless(
    shutil.which("node") and scaffold_move.acorn(ROOT), "needs node and the npm tools: npm ci --prefix tools/npm"
)
BLOCK = "/* Its own Page,\n * in detail\n */\n"  # review 2, 3: an ordinary block comment of several lines
JSDOC = "// stays in index.js (a blank line parts it from the Page)\n\n/**\n * Its own Page.\n */\n"
COMMA = "import { Small, } from '#shared/ui/text.js'\n\nexport const {NOTE} = Small\n"  # review 2, 2


def door(page_id: str, comment: str, imports: str = "", uses: str = "Lede") -> str:
    """index.js of a probe page that defines its Page (``comment`` above it), importing jsx and Lede."""
    name = "".join(part.title() for part in page_id.split("-"))
    const = page_id.upper().replace("-", "_")
    return (
        f"// {name}: a probe page.\nimport {{ jsx }} from '#sdk'\nimport {{ Lede }} from '#shared/ui/text.js'\n"
        f"{imports}\n{comment}function {name}() {{\n  return jsx('div', {{ children: jsx({uses}, {{ children: \"{name}\" }}) }})\n}}\n\n"
        f"export const {const}_PAGE = {{\n  id: '{page_id}',\n  label: '{name}',\n  Page: {name}\n}}\n"
    )


def snapshot(tree: Path) -> dict[str, bytes]:
    """Every file's bytes (.git aside): a refusal leaves the tree exactly so."""
    return {
        str(path.relative_to(tree)): path.read_bytes()
        for path in sorted(tree.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(tree).parts
    }


def moved_pages_bundle(case, retrodev: list[str]) -> None:
    """Three inline Pages on a copy of the real tree, one above a block comment, one above a JSDoc block (and a
    comment a blank line above it that stays), one moving into a file whose matching import ends in a comma: each
    moves whole and the copy passes lint and the bundle."""
    _, tree, env = case.make_tree()
    pages = {"rdblock": (BLOCK, None), "rddoc": (JSDOC, None), "rdcomma": ("", COMMA.replace("{NOTE}", "RDCOMMA_NOTE"))}
    for page_id, (comment, own) in pages.items():
        done = run([*retrodev, "new", "page", page_id, "--no-check", "--no-build"], tree, env)
        case.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        folder = tree / "page/pages" / page_id
        (folder / "index.js").write_text(door(page_id, comment))
        if own is None:
            (folder / f"{page_id}-page.js").unlink()
        else:
            (folder / f"{page_id}-page.js").write_text(own)
    for command in (["add", "-A"], ["commit", "-q", "-m", "Inline Pages"]):
        git_ok(case, tree, env, command)
    for page_id in pages:  # built once, after the last (rdcomma's page file is imported only once it moved)
        last = ["--no-build"] if page_id != "rdcomma" else []
        done = run([*retrodev, "new", "tab", page_id, "first", "--from-page", "--no-check", *last], tree, env)
        case.assertEqual(done.returncode, 0, done.stdout + done.stderr)
    moved = {page_id: (tree / f"page/pages/{page_id}/{page_id}-page.js").read_text() for page_id in pages}
    case.assertIn(BLOCK + "export function Rdblock()", moved["rdblock"])
    case.assertIn("/**\n * Its own Page.\n */\nexport function Rddoc()", moved["rddoc"])
    case.assertIn("// stays in index.js", (tree / "page/pages/rddoc/index.js").read_text())
    case.assertIn("import { Small, Lede } from '#shared/ui/text.js'", moved["rdcomma"])
    judged = run([sys.executable, "tools/check.py", "lint", "bundle"], tree, env)
    case.assertEqual(judged.returncode, 0, judged.stdout + judged.stderr)

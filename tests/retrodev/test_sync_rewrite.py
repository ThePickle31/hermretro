"""The trial rounds' regressions for this area (RoundEleven, RoundSeven, RoundSixteen), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_sync_rewrite
"""

from pathlib import Path
from tests.retrodev.fixture import RepoCase, git, parallel

load_tests = parallel

DOC = (
    '"""The library\'s helpers."""\n\n\ndef keep():\n    return 1\n\n\n'
    "def rename_the_game_folder(root, title):\n"
    '    """The folder takes the title, as the card says."""\n'
    "    return root.with_name(title.replace(' ', '-'))\n\n\n"
    "def tail():\n    return 3\n"
)

BLOCK = DOC[DOC.index("def rename_the_game_folder") : DOC.index("def tail")]

HOOKS = (
    '"""Hooks."""\n\nimport json\n\nfrom ..hermes import host\n\nlogger = host.logger\n\n\n'
    'def _result_payload(result):\n    """A tool result as the model saw it."""\n'
    "    if isinstance(result, str):\n        try:\n            result = json.loads(result)\n"
    "        except ValueError:\n            return None\n    return result if isinstance(result, dict) else None\n\n\n"
    "def build_succeeded(result) -> bool:\n    payload = _result_payload(result)\n    return bool(payload)\n"
)

BYTES = (
    "    if isinstance(result, (bytes, bytearray)):\n"
    '        result = bytes(result).decode("utf-8", "replace")\n    if isinstance(result, str):\n'
)

MOVED = HOOKS[: HOOKS.index("def _result_payload")] + HOOKS[HOOKS.index("def build_succeeded") :].replace(
    "_result_payload(result)", "host.tool_result_payload(result)"
)

RULE = ".rd-card-menu {\n  display: flex;\n  gap: 4px;\n  border-radius: 6px;\n}\n"

SOURCE = "page/pages/games/styles.css.js"

MOVED_TO = "page/shared/styles/base.css.js"


class SyncRoundEleven(RepoCase):
    def moved(self, elsewhere: bool) -> tuple[Path, dict]:
        self.on_dev("backend/library/names.py", DOC, "Names")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/names")
        self.commit(tree, "backend/library/names.py", DOC.replace("' ', '-'", "' ', '_'"))
        if elsewhere:
            self.on_dev("backend/library/folders.py", BLOCK, "The helper moves to folders.py")
        self.on_dev("backend/library/names.py", DOC.replace(BLOCK, ""), "Names loses the helper")
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 1, out)
        return tree, out

    def test_a_moved_block_names_the_file_it_went_to_and_the_steps(self):
        tree, out = self.moved(elsewhere=True)
        fix = out["error"]["message"]
        self.assertRegex(
            fix,
            r"backend/library/names\.py:\d+-\d+: dev moved this block to backend/library/folders\.py \(or deleted "
            r"it\); first check whether dev's version there already does what your lines did; if it does, add only a "
            r"test that pins it; delete the HEAD side of this hunk, git add, sync again, then add your lines in "
            r"backend/library/folders\.py in a new commit",
        )
        self.assertNotIn("-SThe", fix)
        self.assertIn("'-S\"\"\"The folder takes the title, as the card says.\"\"\"'", fix)  # its longest line
        git(tree, "merge", "--abort")


class SyncRoundSeven(RepoCase):
    def test_a_function_dev_deleted_and_the_branch_edited_gets_the_hint_in_every_conflict_style(self):
        self.on_dev("backend/history/hooks.py", HOOKS, "Hooks")
        git(self.main, "fetch", "-q", "origin")
        trees = {}
        for style in ("merge", "diff3", "zdiff3"):
            trees[style] = self.worktree(f"fix/bytes-{style}")
            self.commit(
                trees[style], "backend/history/hooks.py", HOOKS.replace("    if isinstance(result, str):\n", BYTES)
            )
        self.on_dev("backend/history/hooks.py", MOVED, "Move _result_payload to host")
        for style, tree in trees.items():
            git(self.main, "config", "merge.conflictStyle", style)
            code, out = self.run_cli("sync", cwd=tree, as_json=True)
            self.assertEqual(code, 1, (style, out))
            self.assertRegex(  # round eleven: the hunk's lines, and no other file has them
                out["error"]["message"],
                r"backend/history/hooks\.py:\d+-\d+: dev deleted this block \(no other file on origin/dev has its "
                r"lines; .*\); delete the HEAD side of this hunk, git add, sync again",
                style,
            )
            markers = (tree / "backend/history/hooks.py").read_text()
            self.assertEqual("|||||||" in markers, style != "merge", style)  # the style git really used
            git(tree, "merge", "--abort")


class SyncMoveHintRoundSixteen(RepoCase):
    def test_a_rule_moved_to_another_source_names_that_source_never_the_bundle(self):
        self.on_dev(SOURCE, "export const CSS = `\n" + RULE + "`\n", "A rule")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/menu")
        self.commit(tree, SOURCE, "export const CSS = `\n" + RULE.replace("4px", "6px") + "`\n")
        self.on_dev(MOVED_TO, "export const BASE = `\n" + RULE + "`\n", "The rule moves to the shared styles")
        self.on_dev("desktop/plugin.js", "// generated\nconst BASE = `\n" + RULE + "`\n", "Rebuilt")
        self.on_dev(SOURCE, "export const CSS = `\n`\n", "Its old place is empty")
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 1, out)
        message = out["error"]["message"]
        self.assertIn(f"dev moved this block to {MOVED_TO} (or deleted it)", message)
        self.assertIn(f"then add your lines in {MOVED_TO} in a new commit", message)
        self.assertNotIn("desktop/plugin.js (or deleted it)", message)
        self.assertNotIn("in desktop/plugin.js in a new commit", message)

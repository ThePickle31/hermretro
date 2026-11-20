"""Friction the sixteenth round of fresh-agent trials found: sync's per-hunk hint named the generated page bundle as
where a moved CSS rule went; sync's closing line said 'check, then ship again' on a branch with no plan and no pull
request; the body warning flagged a file the branch's own commits changed when a merge with dev dropped that edit;
a data-only edit of tests/page/games-fixture.mjs and a comment-only edit of a tests/repo test ran the nested
scaffold guard; `new slot` on a page that declares a slot already only said to mention it; `new tool`, `new rpc`
and `new contribution` lacked steps (tool_project against host.library_game_for, the game card, a real useQuery
caller and scenario.queries, a direct-import test for a contribution reading its page's atom). Each test failed
before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_sixteen
"""

import io
from pathlib import Path

from retrodev import body_names, comment_only, config, output, state

from tests.retrodev.fixture import GOOD_BODY, RepoCase, git, parallel, retrodev_docs, write
from tests.retrodev.test_scaffold import ScaffoldCase

load_tests = parallel
ROOT = Path(__file__).resolve().parents[2]

RULE = ".rd-card-menu {\n  display: flex;\n  gap: 4px;\n  border-radius: 6px;\n}\n"
SOURCE = "page/pages/games/styles.css.js"
MOVED_TO = "page/shared/styles/base.css.js"


def steps(out) -> list[str]:
    return [line.removeprefix("next: ") for line in out.splitlines() if line.startswith("next: ")]


class SyncMoveHint(RepoCase):
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


class SyncNextStep(RepoCase):
    def merged(self, branch: str, record: dict | None = None) -> str:
        tree = self.worktree(branch)
        if record:
            state.save_branch(self.main, state.load_branch(self.main, branch) | record)
        self.commit(tree, "backend/library/mine.py", "VALUE = 1\n")
        self.on_dev(f"backend/library/theirs_{branch.partition('/')[2]}.py", "VALUE = 2\n")
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 0, out)
        return steps(out)[-1]

    def test_a_branch_without_a_plan_gets_status_s_plan_step(self):
        said = self.merged("feat/taken", {"taken_over": True})
        self.assertTrue(said.startswith("python tools/retrodev plan new taken"), said)
        self.assertNotIn("ship again", said)

    def test_no_pull_request_says_ship_and_one_says_ship_again(self):
        self.assertEqual(self.merged("docs/tidy"), "python tools/retrodev check, then ship")
        said = self.merged("docs/shipped", {"pr": {"number": 7, "url": "u"}})
        self.assertEqual(said, "python tools/retrodev check, then ship again")


class BodyDroppedInMerge(RepoCase):
    def test_a_file_the_branch_s_own_commit_changed_is_quiet_after_a_merge_dropped_it(self):
        tree = self.worktree("fix/notes")
        self.commit(tree, "docs/dev/DEBUGGING.md", "# Debugging\n\nThe same words.\n")
        self.commit(tree, "tools/kept.py", "VALUE = 1\n")
        self.on_dev("docs/dev/DEBUGGING.md", "# Debugging\n\nThe same words.\n", "dev wrote it the same")
        git(tree, "fetch", "-q", "origin")
        git(tree, "merge", "-q", "--no-edit", "origin/dev")
        self.assertNotIn("docs/dev/DEBUGGING.md", git(tree, "diff", "--name-only", "origin/dev...HEAD"))
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        body = GOOD_BODY.replace("Things.", "- Changed `docs/dev/DEBUGGING.md` and `tools/kept.py`.")
        self.assertIsNone(body_names.warning(ctx, body))
        never = GOOD_BODY.replace("Things.", "- Changed `tools/never.py`.")
        self.assertIn("`tools/never.py`", body_names.warning(ctx, never) or "")

    def test_a_rename_dev_also_made_counts_its_old_path_too(self):
        self.on_dev("tools/old_name.py", "VALUE = 1\n", "The file")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/rename")
        git(tree, "mv", "tools/old_name.py", "tools/new_name.py")
        git(tree, "commit", "-q", "-m", "Rename")
        other = self.base / "other"
        git(other, "pull", "-q", "origin", "dev")
        git(other, "mv", "tools/old_name.py", "tools/new_name.py")
        git(other, "commit", "-q", "-m", "dev renames it the same")
        git(other, "push", "-q", "origin", "dev")
        git(tree, "fetch", "-q", "origin")
        git(tree, "merge", "-q", "--no-edit", "origin/dev")
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        body = GOOD_BODY.replace("Things.", "- Renamed `tools/old_name.py` to `tools/new_name.py`.")
        self.assertIsNone(body_names.warning(ctx, body))


class CommentOnly(RepoCase):
    def checked(self, name: str, before: str, after: str, branch: str) -> str:
        self.on_dev(name, before, "The file")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree(branch)
        self.commit(tree, name, after)
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 0, out)
        return out

    def test_a_comment_or_docstring_edit_of_a_repo_test_runs_no_nested_guard(self):
        before = '"""A test."""\n\nVALUE = 1  # one\n\n\ndef test():\n    """Checks."""\n    assert VALUE\n'
        after = '"""A test, reworded."""\n\n# A new comment.\nVALUE = 1  # still one\n\n\ndef test():\n    """Checks it."""\n\n    assert VALUE\n'
        out = self.checked("tests/repo/test_probe.py", before, after, "fix/comments")
        self.assertNotIn("run nested", out)

    def test_a_real_code_edit_still_runs_it_nested(self):
        out = self.checked("tests/repo/test_probe.py", "VALUE = 1  # one\n", "VALUE = 2  # one\n", "fix/code")
        self.assertIn("adding scaffold: changed tests/repo/test_probe.py; run nested", out)

    def test_a_harness_comment_edit_is_quiet_and_its_code_edit_is_not(self):
        before = "// The harness.\nexport const url = 'http://x/y' // where\n"
        out = self.checked("tests/page/harness.mjs", before, before.replace("where", "the page"), "fix/jsc")
        self.assertNotIn("run nested", out)
        out = self.checked("tests/page/shells.mjs", before, before.replace("x/y", "x/z"), "fix/jsx")
        self.assertIn("adding scaffold: changed tests/page/shells.mjs; run nested", out)

    def test_blank_lines_or_trailing_spaces_inside_a_template_are_code(self):
        before = "// The harness.\nexport const page = `a\n\nb`\n"
        out = self.checked("tests/page/harness.mjs", before, before.replace("a\n\nb", "a\nb"), "fix/tblank")
        self.assertIn("adding scaffold: changed tests/page/harness.mjs; run nested", out)
        out = self.checked("tests/page/shells.mjs", before, before.replace("a\n", "a  \n"), "fix/tspace")
        self.assertIn("adding scaffold: changed tests/page/shells.mjs; run nested", out)

    def test_the_games_fixture_is_data_and_never_adds_it(self):
        out = self.checked("tests/page/games-fixture.mjs", "export const A = 1\n", "export const A = 2\n", "fix/data")
        self.assertNotIn("run nested", out)

    def test_the_comparison(self):
        same = comment_only.comments_only
        self.assertTrue(same("a.py", "x = 1\n", "# c\nx = 1  # d\n\n"))
        self.assertTrue(same("a.py", 'def f():\n    """A."""\n    return 1\n', "def f():\n    return 1\n"))
        self.assertFalse(same("a.py", "x = 1\n", "x = 2\n"))
        self.assertFalse(same("a.py", "x = '# a'\n", "x = '# b'\n"))
        self.assertFalse(same("a.py", "x = 1\n", "x = (\n"))  # cannot parse: a real change
        self.assertTrue(same("a.mjs", "const a = 1\n", "// c\nconst a = 1 /* d */\n"))
        self.assertFalse(same("a.mjs", "const u = 'http://a'\n", "const u = 'http://b'\n"))
        self.assertFalse(same("a.mjs", "const t = `x ${a} // y`\n", "const t = `x ${a} // z`\n"))
        self.assertFalse(same("a.mjs", "const r = /a\\/\\/b/\n", "const r = /a\\/\\/c/\n"))
        self.assertTrue(same("a.mjs", "const t = `${f({ a: 1 })}`\n", "const t = `${f({ a: 1 })}` // c\n"))
        self.assertFalse(same("a.mjs", "const t = `${f({ a: 1 })}`\n", "const t = `${f({ a: 2 })}`\n"))
        self.assertFalse(same("a.json", "{}\n", "{ }\n"))  # another kind of file: a real change
        self.assertFalse(same("a.mjs", "const a = 1\n", "const a = 1 /* open\n"))
        template = "const t = `a\n\nb ${f(\n\n  x)}  \nc`\n"
        self.assertFalse(same("a.mjs", template, template.replace("a\n\nb", "a\nb")))
        self.assertFalse(same("a.mjs", template, template.replace("}  \nc", "}\nc")))
        regex = "const t = `a ${/x\\/y/.test(s)} b`\n"
        self.assertTrue(same("a.mjs", regex, regex + "// c\n"))
        self.assertFalse(same("a.mjs", regex, regex.replace("x\\/y", "x\\/z")))
        self.assertTrue(same("a.mjs", template, "// c\n\n" + template.replace("(\n\n  x)", "(\n  // d\n  x)")))


class RealFiles(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")


class SlotOnADeclaringPage(RealFiles):
    def test_new_slot_adds_its_sentence_to_the_existing_slots_line(self):
        self.real("page/pages/games/**/*.js", "page/pages/games/*.md", "page/pages/emulator/*.md")
        out = self.new("slot", "games", "cardBadge", "--doc", "A badge on each game card. Props: { ctx, game }")
        self.assertFalse([note for note in out.get("notes", []) if "under **Slots:**" in note], out)
        block = " ".join(self.read("page/pages/games/README.md").split("**Slots:**")[1].split("\n\n")[0].split())
        self.assertIn(
            "(return `item(...)`; starts empty). Also declares `games.cardBadge`: a badge on each game card. Props: "
            "`{ ctx, game }`. Contributes `InstallButton` to `emulator.barActions`",
            block,
        )
        slots = self.read("page/pages/games/README.md").split("**Slots:**")[1].split("\n\n")[0]
        self.assertTrue(all(len(line) <= 120 for line in slots.splitlines()), slots)
        self.assertIn("Also declares `<page>.<name>`: <doc>.", retrodev_docs("REFERENCE.md"))


class NewSteps(RealFiles):
    def test_new_tool_says_tool_project_first_and_the_game_card(self):
        self.real("backend/features.py", "backend/library/*.py", "backend/library/README.md")
        said = " ".join(self.new("tool", "library", "rdprobe_card", "--project")["next"])
        self.assertIn(
            "the chat's or given project: tool_project (as the stub does); use host.library_game_for only when the "
            "tool needs the game's library id or entry",
            said,
        )
        self.assertIn(
            "game_card.public(root) (None without a game.json); game_card.status(root, strict=True) for what is "
            "missing",
            said,
        )
        card = (ROOT / "backend/library/game_card.py").read_text()
        self.assertIn("def public(root: Path) -> dict | None:", card)
        self.assertIn("*, strict: bool = False", card)
        self.assertIn("def library_game_for(", (ROOT / "backend/hermes/host.py").read_text())

    def test_new_rpc_names_a_real_use_query_and_scenario_queries(self):
        said = " ".join(self.new("rpc", "history", "rdprobe_recent")["next"])
        self.assertIn("page/pages/setup/install/installer.js's useInstall", said)
        self.assertNotIn("games-page.js", said)
        self.assertIn("scenario.queries.some(q => q.key === 'rdprobe_recent')", said)
        self.assertIn("useQuery({", (ROOT / "page/pages/setup/install/installer.js").read_text())
        stub = (ROOT / "tests/page/sdk-stub.mjs").read_text()
        self.assertIn("const key = options.queryKey[1]", stub)
        self.assertIn("scenario.queries.push({ key,", stub)
        self.assertIn("takes `--module <name>_rpcs`", retrodev_docs("README.md"))

    def test_new_contribution_says_where_to_test_a_page_atom(self):
        self.real("page/pages/games/**/*.js", "page/pages/games/*.md")
        said = " ".join(self.new("contribution", "home", "games.cardMenu", "RdprobeItem")["next"])
        self.assertIn("test it in a direct-import test like tests/page/slots.test.mjs", said)
        self.assertIn("registerAliases() from tests/page/aliases.mjs", said)
        self.assertIn("export function registerAliases()", (ROOT / "tests/page/aliases.mjs").read_text())
        self.assertIn("registerAliases()", (ROOT / "tests/page/slots.test.mjs").read_text())

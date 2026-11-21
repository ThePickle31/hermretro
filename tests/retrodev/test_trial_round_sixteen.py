"""Friction the sixteenth round of fresh-agent trials found: sync's per-hunk hint named the generated page bundle as
where a moved CSS rule went; sync's closing line said 'check, then ship again' on a branch with no plan and no pull
request; the body warning flagged a file the branch's own commits changed when a merge with dev dropped that edit;
`new slot` on a page that declares a slot already only said to mention it; `new tool`, `new rpc`
and `new contribution` lacked steps (tool_project against host.library_game_for, the game card, a real useQuery
caller and scenario.queries, a direct-import test for a contribution reading its page's atom). Each test failed
before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_sixteen
"""

import io
import unittest
from pathlib import Path

from retrodev import body_names, config, output, scaffold_readme, state

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


class WrappedSlots(unittest.TestCase):
    def test_each_fills_sentence_follows_its_own_slot_when_wrapping_split_the_boundary(self):
        for gap in ("Also\ndeclares `games.cardBadge`", "Also declares\n`games.cardBadge`"):
            text = (
                "# Games\n\n**Slots:** declares `games.cardActions`: buttons on a card. "
                + gap
                + ": a badge on a card. Contributes `X` to `emulator.barActions`.\n\nMore.\n"
            )
            text = scaffold_readme.filled_by(text, "games.cardActions", "Setup", "Install")
            text = scaffold_readme.filled_by(text, "games.cardBadge", "Library", "Badge")
            flat = " ".join(text.split())
            self.assertIn(
                "buttons on a card. Setup fills it with `Install`. Also declares `games.cardBadge`", flat, gap
            )
            self.assertIn("a badge on a card. Library fills it with `Badge`. Contributes `X`", flat, gap)
            said = "declares `games.cardBadge`: a badge on a card"
            self.assertEqual(scaffold_readme.also_declares(text, said), text, gap)


class NewSteps(RealFiles):
    def test_new_tool_says_tool_project_first_and_the_game_card(self):
        self.real("backend/features.py", "backend/library/*.py", "backend/library/README.md")
        said = " ".join(self.new("tool", "library", "rdprobe_card", "--project")["next"])
        self.assertIn(
            "the selected game is this chat's project (or the `project` argument): tool_project, as the stub does; "
            "call host.library_game_for([root])",
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
        said = " ".join(self.new("contribution", "build", "games.cardMenu", "RdprobeItem")["next"])
        self.assertIn("test it in a direct-import test like tests/page/slots.test.mjs", said)
        self.assertIn("registerAliases() from tests/page/aliases.mjs", said)
        self.assertIn("export function registerAliases()", (ROOT / "tests/page/aliases.mjs").read_text())
        self.assertIn("registerAliases()", (ROOT / "tests/page/slots.test.mjs").read_text())

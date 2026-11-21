"""Friction the nineteenth round of fresh-agent trials found: a conflicted sync named the file dev moved the branch's
block to, but the sync that finished the merge printed only the ordinary next step, so the edit to redo there was
forgotten; `new tool --project` capped no length, unlike the library's tools; `new rpc` sent Build's page docs to a
`### Build` subsection that does not exist and its --game step did not name CONTRACT's game object; `new listener
--dry-run` before the event did not say its preview was generic, and its log hint fixed the level at INFO; `new tab`
did not point at the runnable tab test in STUDIO-PAGES.md. Each test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_nineteen
"""

import ast
import json
import re
from pathlib import Path

from retrodev import plan, scaffold_readme, state

from tests.retrodev.fixture import RepoCase, git, parallel, write
from tests.retrodev.test_scaffold import ScaffoldCase
from tests.retrodev.test_trial_round_eleven import BLOCK, DOC
from tests.retrodev.test_trial_round_seventeen import RealFiles

load_tests = parallel
NAMES, FOLDERS = "backend/library/names.py", "backend/library/folders.py"
ROOT = Path(__file__).resolve().parents[2]
PAGES = "docs/dev/STUDIO-PAGES.md"
# A pages doc of the real shape, made up: one page under ## Pages, one (Rdbuild) with a top section of its own.
PAGES_TEXT = (
    "# Pages\n\n## Pages (one control)\n\n### Home\n\n- hero\n\n## Rdbuild: one game\n\n### Binding\n\n### Page\n\n"
    "- chat\n\n## Adding to the page\n\n### A tab\n\nTesting a tab:\n\n```js\nawait runScenario(async () => {})\n```\n\n"
    "### An event\n"
)


class SyncFollowUp(RepoCase):
    def conflicted(self, elsewhere: bool):
        """A branch edits the helper in names.py while dev moves it to folders.py (or deletes it); the first sync
        stops on the conflict."""
        self.on_dev(NAMES, DOC, "Names")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/names")
        self.commit(tree, NAMES, DOC.replace("' ', '-'", "' ', '_'"))
        if elsewhere:
            self.on_dev(FOLDERS, BLOCK, "The helper moves to folders.py")
        self.on_dev(NAMES, DOC.replace(BLOCK, ""), "Names loses the helper")
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 1, out)
        return tree

    def resolve(self, tree):
        """Delete the HEAD side of the hunk (dev's file as it is) and stage it, as the first sync's hint says."""
        write(tree, NAMES, git(tree, "show", f"MERGE_HEAD:{NAMES}"))
        git(tree, "add", NAMES)

    def record(self):
        return state.root(self.main) / "sync" / "fix" / "names.json"

    def test_the_finishing_sync_repeats_where_the_block_went_before_the_next_step(self):
        tree = self.conflicted(elsewhere=True)
        self.assertTrue(self.record().is_file())
        self.resolve(tree)
        code, text = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 0, text)
        lines = text.splitlines()
        follow = next(i for i, line in enumerate(lines) if line.startswith("follow up after the merge"))
        advice = lines[follow + 1]
        self.assertRegex(
            advice,
            rf"^  {NAMES} \(conflict lines \d+-\d+\): dev moved that block to {FOLDERS} \(or deleted it\); check ",
        )
        self.assertIn("add only a test that pins it", advice)
        step = next(i for i, line in enumerate(lines) if line.startswith("next: "))
        self.assertGreater(step, follow + 1)
        self.assertNotIn(FOLDERS, lines[step])
        self.assertNotIn("warning: the resolution adds", text)
        self.assertEqual(len(git(tree, "rev-list", "--parents", "-1", "HEAD").split()), 3)  # the merge commit
        self.assertFalse(self.record().exists())

    def test_a_deleted_block_names_no_destination(self):
        tree = self.conflicted(elsewhere=False)
        self.resolve(tree)
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 0, out)
        self.assertEqual(len(out["followup"]), 2, out["followup"])
        self.assertRegex(out["followup"][1], rf"^  {NAMES} \(conflict lines \d+-\d+\): dev deleted that block")
        self.assertNotIn("moved that block", out["followup"][1])
        self.assertTrue(out["next"].startswith("next: "), out["next"])

    def test_advice_from_an_aborted_merge_is_not_repeated_for_another(self):
        tree = self.conflicted(elsewhere=True)
        git(tree, "merge", "--abort")
        self.on_dev("docs/other.md", "more\n", "Dev moves on")
        git(tree, "fetch", "-q", "origin")
        # a merge started by hand: a different MERGE_HEAD than the one the kept advice is about
        git(tree, "merge", "--no-edit", "origin/dev", check=False)
        self.assertTrue(git(tree, "diff", "--name-only", "--diff-filter=U"))
        self.assertTrue(self.record().is_file())
        self.resolve(tree)
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 0, out)
        self.assertEqual(len(out["followup"]), 1, out["followup"])
        self.assertIn(f"it conflicted in {NAMES}; if dev moved or rewrote", out["followup"][0])
        self.assertNotIn(FOLDERS, out["followup"][0])

    def test_a_malformed_advice_record_falls_back_and_cannot_stop_a_merge(self):
        tree = self.conflicted(elsewhere=True)
        record = json.loads(self.record().read_text(encoding="utf-8"))
        record["hunks"] = [{}]
        self.record().write_text(json.dumps(record), encoding="utf-8")
        self.resolve(tree)
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 0, out)
        assert isinstance(out, dict)
        self.assertIn(f"it conflicted in {NAMES}", out["followup"][0])
        self.assertNotIn(FOLDERS, "\n".join(out["followup"]))

    def test_an_unwritable_advice_record_cannot_stop_either_sync(self):
        self.record().mkdir(parents=True)  # a directory at the record path refuses both replacement and unlink
        tree = self.conflicted(elsewhere=True)
        self.resolve(tree)
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 0, out)
        assert isinstance(out, dict)
        self.assertIn(f"it conflicted in {NAMES}", out["followup"][0])
        self.assertNotIn(FOLDERS, "\n".join(out["followup"]))

    def test_no_follow_up_after_a_clean_merge_or_a_plain_conflict(self):
        self.on_dev(NAMES, DOC, "Names")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/names")
        self.commit(tree, NAMES, DOC.replace("return 1", "return 10"))
        self.on_dev("docs/other.md", "more\n", "Unrelated")
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual((code, out.get("followup", [])), (0, []), out)
        self.on_dev(NAMES, DOC.replace("return 1", "return 11"), "Both sides edit one line")
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual((code, out.get("hunks")), (1, []), out)
        self.resolve(tree)
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual((code, out["followup"]), (0, []), out)
        self.assertNotIn("new_lines", out)


class ProjectTool(RealFiles):
    def test_the_project_argument_has_the_library_tools_length_cap(self):
        self.real("backend/library/*.py", "backend/library/README.md")
        self.new("tool", "library", "rdprobe_proj", "--project")
        home = next(
            path for path in (self.tree / "backend/library").glob("*.py") if "RDPROBE_PROJ_TOOL" in path.read_text()
        )
        schema = next(
            node.value
            for node in ast.parse(home.read_text()).body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "RDPROBE_PROJ_TOOL" for target in node.targets)
        )
        project = ast.literal_eval(schema)["parameters"]["properties"]["project"]
        # the cap the library's own project tools give the same argument
        library = (ROOT / "backend/library/tools.py").read_text()
        caps = set(re.findall(r'"project": \{\s*"type": "string",\s*"maxLength": (\d+)', library))
        self.assertEqual((project["type"], project.get("maxLength")), ("string", 4096))
        self.assertIn(str(project["maxLength"]), caps)

    def test_the_plan_template_says_the_registry_changes_under_what_changes(self):
        what = plan.TEMPLATE.split("## What changes")[1].split("\n## ")[0]
        self.assertIn("generated", what)
        self.assertIn("tests/repo/registration.json", what)


class RpcPageDocs(ScaffoldCase):
    def page_step(self, *argv) -> str:
        steps = self.new("rpc", "history", *argv)["next"]
        return next(step for step in steps if step.startswith("if a page shows it"))

    def test_a_page_with_a_section_of_its_own_is_named_with_its_real_heading(self):
        self.commit(self.tree, PAGES, PAGES_TEXT, "A pages doc")
        step = self.page_step("rdprobe_ping")
        self.assertIn("as a bullet in its `### <Page>` subsection under `## Pages` of docs/dev/STUDIO-PAGES.md", step)
        self.assertIn("; Rdbuild's is its `### Page` subsection under `## Rdbuild: one game`", step)
        self.assertNotIn("Home's", step)

    def test_every_heading_named_for_the_real_doc_is_in_it(self):
        doc = (ROOT / PAGES).read_text()
        for top in re.findall(r"under `## ([^`]+)`", scaffold_readme.own_sections(doc)):
            self.assertIn(f"\n## {top}\n", doc)
            self.assertIn("### Page", doc.split(f"\n## {top}\n")[1].split("\n## ")[0])

    def test_a_game_rpc_points_at_contract_s_game_object_and_its_card(self):
        steps = " ".join(self.new("rpc", "history", "rdprobe_rom", "--game")["next"])
        self.assertIn("docs/dev/CONTRACT.md 'The game object' lists each field, the game card's (`card`", steps)
        self.assertIn("\n## The game object\n", self.read("docs/dev/CONTRACT.md"))
        self.commit(self.tree, "docs/dev/CONTRACT.md", "# Contract\n", "No game object")
        steps = " ".join(self.new("rpc", "history", "rdprobe_web", "--game")["next"])
        self.assertNotIn("The game object", steps)
        self.assertIn("before adding a per-game query (its row in docs/dev/CONTRACT.md", steps)


class ListenerPreview(RealFiles):
    def test_a_preview_before_the_event_says_it_is_generic(self):
        self.real("backend/assets/*.py", "backend/assets/README.md")
        out = self.new("listener", "assets", "history.rdprobe_later", "--dry-run", as_json=False)
        self.assertIn("in a generic form (**_payload for the payload, no CONTRACT 'Heard by' row)", out)
        self.assertIn("once the event exists, --dry-run again shows the exact ones", out)

    def test_the_log_hint_takes_the_listener_s_own_level(self):
        said = " ".join(self.new("listener", "history", "history.build_kept")["next"])
        self.assertNotIn('logger, "INFO")', said)
        self.assertIn('"<LEVEL>"):`, the level the listener logs at ("INFO" for host.logger.info', said)


class TabExample(ScaffoldCase):
    def test_new_tab_points_at_the_runnable_example_when_the_doc_has_it(self):
        self.commit(self.tree, PAGES, PAGES_TEXT, "A pages doc")
        said = " ".join(self.new("tab", "prompts", "extra", "--dry-run")["next"])
        self.assertIn("a runnable example to start from: docs/dev/STUDIO-PAGES.md 'A tab' (Testing a tab)", said)
        self.commit(self.tree, PAGES, PAGES_TEXT.replace("```js", "```text"), "No example")
        said = " ".join(self.new("tab", "prompts", "extra", "--dry-run")["next"])
        self.assertNotIn("a runnable example", said)

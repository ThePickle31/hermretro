"""Friction the fourth round of fresh-agent trials found in check (scaffold after a lint failure, a bundle whose
banner alone changed), ship and status (a dry run's next step stays a dry run; nothing in progress), `new` (the
agent-half Declares cell, tab --from-page, the listener signature, the rpc and library tool next steps) and the
test pool (discovery can be walked); each test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_four
"""

import shutil
import unittest
from pathlib import Path

import retrodev
from retrodev import checks_triggers

from tests.retrodev import test_trial_round_two as two
from tests.retrodev.fixture import GOOD_BODY, RepoCase, git, parallel, write
from tests.retrodev.test_scaffold import ScaffoldCase
from tests.retrodev.test_trial_round_two import TITLE, line_with

load_tests = parallel
ROOT = Path(retrodev.__file__).resolve().parents[2]
HASH = "a" * 64


def bundle(sources: str, body: str, text: str = "export const a = 1\n") -> str:
    """A generated file opening with tools/bundle/bundle.mjs's banner."""
    return (
        f"/**\n * hermretro: a generated file.\n * build: esbuild 0.28.2\n * sources: sha256 {sources}\n"
        f" * body: sha256 {body}\n */\n{text}"
    )


class Check(RepoCase):
    def test_scaffold_does_not_run_when_lint_fails_in_the_same_run(self):
        tree = self.worktree("chore/lint")
        self.fail_checks("lint")
        code, out = self.run_cli("check", "lint", "scaffold", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertEqual([entry["names"] for entry in self.check_log()], [["lint"]], "scaffold never started")
        self.assertIn("skipped  scaffold", out)
        self.fail_checks()
        self.clear_log()
        self.run_cli("check", "lint", "scaffold", cwd=tree)
        self.assertEqual([entry["names"] for entry in self.check_log()], [["lint"], ["scaffold"]])

    def frame_shim(self, sources: str, body: str, text: str = "export const a = 1\n") -> Path:
        self.on_dev("player/frame-shim.js", bundle(HASH, HASH))
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("chore/shim")
        self.commit(tree, "player/frame-shim.js", bundle(sources, body, text))
        return tree

    def test_a_frame_shim_whose_body_hash_is_unchanged_adds_no_acceptance(self):
        tree = self.frame_shim("b" * 64, HASH)  # only sources: moved (a page/shared edit outside the frame)
        _code, out = self.run_cli("check", cwd=tree)
        self.assertNotIn("adding acceptance", out)

    def test_a_frame_shim_whose_body_changed_still_adds_acceptance(self):
        tree = self.frame_shim("b" * 64, "c" * 64, "export const a = 2\n")
        _code, out = self.run_cli("check", cwd=tree)
        self.assertIn("adding acceptance: changed player/frame-shim.js", out)

    def test_the_body_hash_is_read_from_the_banner_only(self):
        self.assertEqual(checks_triggers.body_hash(bundle(HASH, "c" * 64)), "c" * 64)
        self.assertIsNone(checks_triggers.body_hash("export const a = 1\n * body: sha256 " + HASH))
        self.assertIsNone(checks_triggers.body_hash(None))


class Ship(two.Flow):  # its helpers (two.Flow's own tests run in test_trial_round_two)
    def test_a_dry_run_s_body_fix_and_status_keep_dry_run(self):
        tree = self.feat()
        body = write(self.main, "notes/pr/goalie.md", GOOD_BODY.replace("Because.", ""))
        code, out = self.run_cli("ship", "--title", TITLE, "--body", str(body), "--dry-run", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertTrue(line_with(out, "FIX: fill in").endswith(" --dry-run"), line_with(out, "FIX: fill in"))
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn(" --dry-run (fill in every section", line_with(out, "next:"))
        body.write_text(GOOD_BODY)
        self.run_cli("ship", "--title", TITLE, "--body", str(body), "--dry-run", cwd=tree)
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn(" --dry-run (ship --dry-run passed at ", line_with(out, "next:"))
        self.assertIn("without --dry-run the same command pushes", line_with(out, "next:"))

    def test_after_a_real_ship_status_names_a_real_ship(self):
        tree = self.feat()
        body = write(self.main, "notes/pr/goalie.md", GOOD_BODY.replace("Because.", ""))
        self.run_cli("ship", "--title", TITLE, "--body", str(body), "--dry-run", cwd=tree)
        code, out = self.run_cli("ship", "--title", TITLE, "--body", str(body), cwd=tree)  # the body gate stops it
        self.assertEqual(code, 1, out)
        self.assertFalse(line_with(out, "FIX: fill in").endswith("--dry-run"))
        _code, out = self.run_cli("status", cwd=tree)
        self.assertNotIn("--dry-run", line_with(out, "next:"))

    def test_status_with_nothing_in_progress_names_both_ways_to_start(self):
        _code, out = self.run_cli("status")
        self.assertIn("next: python tools/retrodev plan new <topic> (docs/chore: start <kind>/<topic> --no-plan)", out)


def agent_row(text: str, feature: str) -> str:
    rows = text.split("## The agent half", 1)[1].splitlines()
    return next(line for line in rows if line.startswith(f"| `backend/{feature}/` |"))


class New(ScaffoldCase):
    def row(self, feature: str) -> str:
        return agent_row(self.read("docs/dev/ARCHITECTURE.md"), feature)

    def test_rpc_tool_and_event_name_themselves_in_the_agent_half_row(self):
        self.new("feature", "rdprobe")
        self.new("rpc", "rdprobe", "rdprobe_ping")
        self.assertEqual(self.row("rdprobe"), "| `backend/rdprobe/` | RPC `rdprobe_ping` | nothing; no events |")
        self.new("rpc", "rdprobe", "rdprobe_pong")
        self.new("tool", "rdprobe", "rdprobe_go")
        self.new("event", "rdprobe", "moved", "--payload", "game")
        self.assertEqual(
            self.row("rdprobe"),
            "| `backend/rdprobe/` | RPCs `rdprobe_ping`, `rdprobe_pong`; tool `chromatic_rdprobe_go` | "
            "nothing; `rdprobe.moved` |",
        )

    def test_an_existing_row_gets_the_tool_after_its_rpcs_and_the_event_after_its_events(self):
        before = self.row("history")
        self.new("tool", "history", "rdprobe_hist")
        self.new("event", "history", "rdprobe_pruned", "--payload", "game")
        after = self.row("history")
        declares, events = after.strip("| ").split(" | ")[1:3]
        self.assertIn("; tool `chromatic_rdprobe_hist`", declares)
        self.assertTrue(declares.startswith(before.split(" | ")[1].split("; ")[0]), after)  # its RPCs stay first
        self.assertTrue(events.endswith(", `history.rdprobe_pruned`"), events)

    def test_tab_from_page_turns_the_page_s_page_into_its_first_tab(self):
        self.new("page", "rdprobe-notes")
        self.new("tab", "rdprobe-notes", "first", "--from-page")
        tab = self.read("page/pages/rdprobe-notes/first/index.js")
        self.assertIn("import { RdprobeNotesPage } from '#pages/rdprobe-notes/rdprobe-notes-page.js'", tab)
        self.assertIn("  Page: RdprobeNotesPage\n", tab)
        self.assertNotIn("from '../", tab)
        self.assertIn("as #pages/rdprobe-notes/<file>.js (../ is refused)", tab)
        door = self.read("page/pages/rdprobe-notes/index.js")
        self.assertNotIn("Page: ", door)
        self.assertNotIn("rdprobe-notes-page.js", door)
        self.assertIn("  tabs: [\n    RDPROBE_NOTES_FIRST_TAB\n  ]", door)
        out = self.new("tab", "rdprobe-notes", "again", "--from-page", code=1)  # it has tabs now
        self.assertIn("has tabs already", out["error"]["message"])
        out = self.new("tab", "home", "rdprobe-moved", "--from-page", code=1)  # Home is defined in index.js
        self.assertIn("defines Home itself", out["error"]["message"])

    def test_a_tab_template_says_how_a_tab_imports_its_page_s_files(self):
        self.new("tab", "home", "rdprobe-extra")
        tab = self.read("page/pages/home/rdprobe-extra/index.js")
        self.assertIn("// A tab imports its page's files as #pages/home/<file>.js (../ is refused).", tab)

    def test_a_first_tab_beside_the_page_s_own_page_skips_the_page_check_with_a_note(self):
        code, out = self.run_cli("new", "tab", "home", "rdprobe-extra", cwd=self.tree)
        self.assertEqual(code, 0, out)
        self.assertIn("note: the page check is skipped now", out)
        ran = [name for entry in self.check_log() for name in entry["names"]]
        self.assertIn("bundle", ran)
        self.assertNotIn("page", ran)
        self.clear_log()
        self.run_cli("new", "tab", "home", "rdprobe-more", cwd=self.tree)  # it has a tab: its page check runs
        self.assertIn("page", [name for entry in self.check_log() for name in entry["names"]])

    def test_the_listener_takes_underscored_payload(self):
        shutil.copyfile(ROOT / "backend/library/__init__.py", self.tree / "backend/library/__init__.py")
        self.new("feature", "rdprobe_ears")
        self.new("listener", "rdprobe_ears", "library.build_reported")
        listeners = self.read("backend/rdprobe_ears/listeners.py")
        self.assertIn("def on_library_build_reported(**_payload) -> None:", listeners)

    def test_rpc_next_steps_name_shell_via_profile(self):
        steps = " ".join(self.new("rpc", "history", "rdprobe_recent")["next"])
        self.assertIn("use shell.viaProfile for the queryKey's third part", steps)

    def test_a_library_project_tool_s_next_steps_name_project_files_and_the_title(self):
        for name in ("__init__.py", "tool_args.py"):
            write(self.tree, f"backend/library/{name}", (ROOT / f"backend/library/{name}").read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "tool_args")
        steps = self.new("tool", "library", "rdprobe_open")["next"]
        self.assertIn(
            'project files: backend/library/README.md "Project files"; title: games.project_title(root)', steps
        )


class Pool(unittest.TestCase):
    def test_walking_the_discovered_suite_reaches_every_test_id(self):
        def flat(suite):
            for item in suite:
                if isinstance(item, unittest.TestSuite):
                    yield from flat(item)
                else:
                    yield item

        found = unittest.TestLoader().discover(str(ROOT / "tests"), top_level_dir=str(ROOT))  # as check.py unit
        ids = [test.id() for test in flat(found)]
        self.assertIn(f"{__name__}.Pool.test_walking_the_discovered_suite_reaches_every_test_id", ids)
        self.assertIn("tests.retrodev.test_trial_round_four.Check.test_the_body_hash_is_read_from_the_banner_only", ids)


class Readme(unittest.TestCase):
    def test_taking_over_a_branch_already_checked_out_skips_the_worktree(self):
        text = (ROOT / "tools/retrodev/README.md").read_text()
        part = text[text.index("**Taking over a teammate's branch**") :].split("\n\n", 1)[0]
        self.assertIn("When the branch is checked out already", part)
        self.assertIn("skip the worktree: run `plan new`, `plan approve`, `sync`, `check` and `ship` there", part)


if __name__ == "__main__":
    unittest.main()

"""plan new / show / approve, start's gates and the worktree it makes, and config precedence.

Run alone: python -m unittest tests.retrodev.test_plan_start
"""

import unittest

from retrodev import state

from tests.retrodev.fixture import RepoCase, git, parallel, write
import io
import re
from pathlib import Path
import retrodev
from retrodev import checks, config, output, repo
from tests.retrodev.fixture import GOOD_BODY
from retrodev import plan
from tests.retrodev.fixture import FILLED_PLAN
from retrodev import status
from tests.retrodev.fixture import retrodev_docs
from tests.retrodev.test_scaffold import ScaffoldCase

load_tests = parallel


class Plans(RepoCase):
    def test_new_writes_the_template_once_and_approve_records_the_words(self):
        code, out = self.run_cli("plan", "new", "speedy")
        self.assertEqual(code, 0, out)
        path = self.main / "notes" / "plans" / "speedy.md"
        self.assertIn("## How the owner and users use it", path.read_text())
        path.write_text("# Plan: speedy\nmine\n")
        code, out = self.run_cli("plan", "new", "speedy")
        self.assertIn("kept", out)
        self.assertEqual(path.read_text(), "# Plan: speedy\nmine\n")

        code, data = self.run_cli("plan", "approve", "speedy", "--words", "  ", as_json=True)
        self.assertEqual((code, data["status"]), (3, "needs the owner"))
        self.assertIn("exact words", data["error"]["message"])
        code, data = self.run_cli("plan", "approve", "speedy", "--words", "start, looks good", as_json=True)
        self.assertEqual(code, 0)
        self.assertEqual(data["approved"]["words"], "start, looks good")
        self.assertEqual(state.load_plan(self.main, "speedy")["approved"]["words"], "start, looks good")

        path.write_text("# Plan: speedy\nchanged after approval\n")
        code, data = self.run_cli("plan", "show", "speedy", as_json=True)
        self.assertTrue(data["changed_since_approval"])
        self.assertIn("changed after approval", data["text"])

    def test_bad_topics_are_refused(self):
        code, out = self.run_cli("plan", "new", "Bad Topic")
        self.assertEqual(code, 1)
        self.assertIn("FIX: use lowercase letters", out)


class Start(RepoCase):
    def test_a_feature_needs_an_approved_plan(self):
        code, out = self.run_cli("start", "feat/speedy", "--no-setup")
        self.assertEqual(code, 3, out)
        self.assertIn("there is no plan 'speedy'", out)
        self.assertTrue(out.rstrip().splitlines()[-1].startswith("FIX: "))
        code, out = self.run_cli("start", "feat/speedy", "--no-plan", "--no-setup")
        self.assertEqual(code, 3, out)
        self.assertIn("--no-plan is only for small docs and chore changes", out)
        self.assertFalse((self.base / "hermretro-wt").exists())

    def test_start_makes_the_worktree_at_the_computed_path_from_origin_dev(self):
        self.new_plan("speedy")
        self.run_cli("plan", "approve", "speedy", "--words", "start")
        self.on_dev("docs/news.md", "# News\n")  # origin/dev moved since the last fetch
        code, data = self.run_cli("start", "feat/speedy", as_json=True)
        self.assertEqual(code, 0, data)
        path = self.base / "hermretro-wt" / "speedy"
        self.assertEqual(data["path"], str(path))
        self.assertEqual(data["setup"][0]["detail"], "set up")
        self.assertTrue((path / "docs" / "news.md").is_file(), "started from the freshly fetched origin/dev")
        self.assertEqual(git(path, "branch", "--show-current").strip(), "feat/speedy")
        self.assertEqual(git(path, "config", "--get-regexp", "^branch\\.feat/speedy\\.", check=False), "")
        record = state.load_branch(self.main, "feat/speedy")
        self.assertEqual((record["topic"], record["plan"], record["worktree"]), ("speedy", "speedy", str(path)))
        code, out = self.run_cli("start", "feat/speedy", "--no-setup")
        self.assertEqual(code, 1)
        self.assertIn("already exists", out)

    def test_one_plan_covers_several_branches(self):
        self.new_plan("bigplan")
        code, out = self.run_cli("start", "feat/part-one", "--plan", "bigplan", "--no-setup")
        self.assertEqual(code, 3, out)
        self.assertIn("'bigplan' is not approved", out)
        self.run_cli("plan", "approve", "bigplan", "--words", "start")
        code, data = self.run_cli("start", "feat/part-one", "--plan", "bigplan", "--no-setup", as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual(state.load_branch(self.main, "feat/part-one")["plan"], "bigplan")
        code, data = self.run_cli("status", cwd=self.base / "hermretro-wt" / "part-one", as_json=True)
        self.assertEqual((data["plan"], data["plan_approved"]), ("bigplan", True), data)
        code, data = self.run_cli("plan", "show", cwd=self.base / "hermretro-wt" / "part-one", as_json=True)
        self.assertEqual((code, data.get("topic")), (0, "bigplan"), data)

    def test_a_branch_made_by_hand_links_to_its_plan(self):
        self.new_plan("bigplan")
        self.run_cli("plan", "approve", "bigplan", "--words", "start")
        path = self.base / "by-hand"
        git(self.main, "worktree", "add", "-q", "-b", "feat/by-hand", str(path), "dev")
        code, out = self.run_cli("plan", "link", "bigplan", cwd=path)
        self.assertEqual(code, 0, out)
        self.assertIn("works under the plan bigplan (approved)", out)
        code, data = self.run_cli("status", cwd=path, as_json=True)
        self.assertEqual((data["plan"], data["plan_approved"]), ("bigplan", True), data)
        code, data = self.run_cli("plan", "show", cwd=path, as_json=True)
        self.assertEqual((code, data.get("topic")), (0, "bigplan"), data)
        code, out = self.run_cli("plan", "link", "bigplan")  # the main checkout is on dev
        self.assertEqual(code, 1, out)
        self.assertIn("is not a work branch", out)

    def test_start_refuses_while_the_main_checkout_is_dirty_or_off_dev(self):
        write(self.main, "docs/draft.md", "owner's work\n")
        code, out = self.run_cli("start", "docs/tidy", "--no-plan", "--no-setup")
        self.assertEqual(code, 3, out)
        self.assertIn("main checkout clean", out)
        (self.main / "docs" / "draft.md").unlink()
        git(self.main, "switch", "-q", "-c", "elsewhere")
        code, out = self.run_cli("start", "docs/tidy", "--no-plan", "--no-setup")
        self.assertEqual(code, 3, out)
        self.assertIn("is on 'elsewhere', not 'dev'", out)


class Config(RepoCase):
    def test_local_settings_win_over_the_policy_and_reset_to_it(self):
        code, data = self.run_cli("config", "get", "worktree_root", as_json=True)
        self.assertEqual((data["value"], data["source"]), ("", "policy"))
        self.run_cli("config", "set", "worktree_root", "trees")
        code, data = self.run_cli("config", "get", "worktree_root", as_json=True)
        self.assertEqual((data["value"], data["source"]), ("trees", "local"))
        self.assertTrue((self.main / ".git" / "retrodev" / "config.toml").is_file())
        self.assertEqual(self.run_cli("start", "docs/tidy", "--no-plan", "--no-setup")[0], 0)
        self.assertFalse((self.base / "hermretro-wt").exists())
        self.assertTrue((self.base / "trees" / "tidy").is_dir(), "a relative root sits beside the main checkout")
        self.run_cli("config", "set", "worktree_root", 'odd "quoted" \\ value')
        self.assertEqual(
            self.run_cli("config", "get", "worktree_root", as_json=True)[1]["value"], 'odd "quoted" \\ value'
        )
        self.run_cli("config", "set", "worktree_root", "")
        self.assertEqual(self.run_cli("config", "get", "worktree_root", as_json=True)[1]["source"], "policy")

    def test_unknown_keys_are_refused(self):
        code, out = self.run_cli("config", "set", "wrokt", "x")
        self.assertEqual(code, 1)
        self.assertIn(
            "FIX: use one of: base, github_account, mac_host, mac_repo, remote, review_model, review_profile, review_provider, review_reasoning, worktree_root",
            out,
        )


ROOT = Path(retrodev.__file__).resolve().parents[2]


def line_with(text: str, start: str) -> str:
    return next(line for line in text.splitlines() if line.lstrip().startswith(start))


README = """# {Label}

**Shows:** the page.

**Tabs:** none.

**Slots:** declares none, contributes none.

**Tests:** `tests/page/page-{page}.test.mjs`.

## Adding a tab here

Make a folder `page/pages/{page}/<tab>/`{taken} with an `index.js` exporting `{{ id, label, Page }}`.
"""

LONG = "Show how many builds each game of the library has had, newest first, on the Home page's shelf and in Game"


def titled(topic: str, title: str) -> str:
    return FILLED_PLAN.format(topic=topic).replace("\n\n## Goal", f"\n\nTitle: {title}\n\n## Goal")


def line_with_RoundEight(out: str, start: str) -> str:
    return next((line for line in out.splitlines() if line.startswith(start)), "")


def line_with_RoundSeven(out: str, start: str) -> str:
    return next((line for line in out.splitlines() if line.startswith(start)), "")


def line_with_RoundSix(out: str, start: str) -> str:
    return next((line for line in out.splitlines() if line.startswith(start)), "")


def line_with_RoundTen(text: str, start: str) -> str:
    return next((line for line in text.splitlines() if line.startswith(start)), "")


def line_with_RoundThree(text: str, start: str) -> str:
    return next(line for line in text.splitlines() if line.lstrip().startswith(start))


class FlowFixes(RepoCase):
    def passed(self, tree, name):
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        record = state.load_branch(self.main, name)
        record.update(passed_tree=repo.tree_digest(tree), passed_checks=sorted(checks.required(ctx)))
        state.save_branch(self.main, record)

    def ready(self, name="docs/tidy"):
        tree = self.worktree(name)
        self.commit(tree, "docs/guide.md", "# Guide, better\n", "Improve the guide")
        self.passed(tree, name)
        return tree, str(write(self.base, "body.md", GOOD_BODY))

    def test_plan_approve_refuses_a_plan_that_is_still_the_template(self):
        code, out = self.run_cli("plan", "new", "empty")
        self.assertIn("edit it in place", out)
        code, out = self.run_cli("plan", "approve", "empty", "--words", "start")
        self.assertEqual(code, 1, out)
        self.assertIn("'## Goal'", out)
        self.assertTrue(line_with(out, "FIX:").startswith(f"FIX: fill in {self.main}/notes/plans/empty.md first"), out)
        self.assertIsNone(state.load_plan(self.main, "empty").get("approved"))
        self.new_plan("empty")  # written: now it may be approved
        self.assertEqual(self.run_cli("plan", "approve", "empty", "--words", "start")[0], 0)

    def test_plan_approve_points_a_branch_made_by_hand_at_check(self):
        path = self.base / "hermretro-wt" / "handy"
        git(self.main, "worktree", "add", "-q", "-b", "fix/handy", str(path), "origin/dev")
        self.new_plan("handy")
        code, out = self.run_cli("plan", "approve", "handy", "--words", "start")
        self.assertEqual(code, 0, out)
        self.assertIn(f"next: fix/handy already works under it: cd {path} && python tools/retrodev check", out)

    def test_config_list_shows_where_the_worktrees_go(self):
        code, out = self.run_cli("config", "list")
        root = self.base / "hermretro-wt"
        self.assertIn(f"worktree_root = ''  (policy; resolves to {root})", out)


class TitleAndBodyRoundEight(RepoCase):
    def test_the_plan_template_asks_for_a_title_and_present_tense(self):
        self.run_cli("plan", "new", "titled")
        text = (self.main / "notes/plans/titled.md").read_text()
        self.assertIn("Title: <!-- One plain sentence", text)
        self.assertIn("in the present tense ('X does Y')", text)
        self.assertEqual(plan.unfilled(FILLED_PLAN.format(topic="t")), [])


class StartNamesEmptySectionsRoundEighteen(RepoCase):
    def test_start_prints_the_sections_left_empty_and_copies_the_plan_s_risk(self):
        self.new_plan("risky")
        self.run_cli("plan", "approve", "risky", "--words", "start")
        code, out = self.run_cli("start", "feat/risky", "--no-setup")
        self.assertEqual(code, 0, out)
        self.assertIn("(still empty: How verified, Risk and rollback)", out)
        from retrodev import plan

        path = self.new_plan("careful")
        text = path.read_text().replace(
            "## Not in scope", "## Risk and rollback\nRevert the commit.\n\n## Not in scope"
        )
        path.write_text(text)
        self.run_cli("plan", "approve", "careful", "--words", "start")
        code, out = self.run_cli("start", "feat/careful", "--no-setup")
        self.assertEqual(code, 0, out)
        self.assertIn("(still empty: How verified)", out)
        body = (self.main / "notes" / "pr" / "careful.md").read_text()
        self.assertRegex(
            body,
            r"## Risk and rollback\n(?:<!--.*?-->\n)*Revert the commit\.",
        )
        self.assertIn("## Risk and rollback\n<!--", plan.TEMPLATE)
        self.run_cli("plan", "new", "bare")
        code, out = self.run_cli("plan", "approve", "bare", "--words", "start", as_json=True)
        self.assertEqual(code, 1, out)
        self.assertIn("'## Risk and rollback'", out["error"]["message"])


class StartNoPlanRoundEleven(RepoCase):
    def test_start_no_plan_writes_the_template_body_and_names_its_path(self):
        code, out = self.run_cli("start", "docs/tidy", "--no-plan", "--no-setup")
        self.assertEqual(code, 0, out)
        body = self.main / "notes" / "pr" / "tidy.md"
        self.assertTrue(body.is_file(), out)
        text = body.read_text()
        self.assertIn("Made by an agent (", text)
        self.assertIn("<!-- no plan: say why -->", text)
        self.assertIn("## How verified", text)
        step = next(line for line in out.splitlines() if line.startswith("next: "))
        self.assertIn(f"fill in {body} as you go", step)
        self.assertIn("with `--no-plan` too: the template with the `Made by` line", retrodev_docs("REFERENCE.md"))
        self.assertIn("with `--no-plan`, the template", retrodev_docs("README.md"))


class DocsRoundFourteen(RepoCase):
    def test_the_plan_template_says_where_a_page_s_tests_are_named(self):
        tested = plan.TEMPLATE[plan.TEMPLATE.index("## How it is tested") :].split("##")[1]
        self.assertIn("each page README's Tests: line names the test file that covers it", " ".join(tested.split()))


class TitleRoundNine(RepoCase):
    def test_the_template_says_the_limit_and_where_files_go_points_to_dry_run(self):
        self.assertIn("Title: <!-- One plain sentence, at most 100 characters, no trailing period", plan.TEMPLATE)
        where = plan.TEMPLATE.split("## Where files go")[1].split("##")[0]
        self.assertIn("--dry-run", where)

    def test_plan_approve_runs_the_title_gate_on_the_plan_s_title_line(self):
        path = self.main / "notes/plans/longer.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(titled("longer", LONG))
        code, out = self.run_cli("plan", "approve", "longer", "--words", "start")
        self.assertEqual(code, 1, out)
        self.assertIn("the plan's title: the title is 105 characters; the limit is 100", out)
        self.assertIn("shorten it to 100 characters or fewer (yours is 105)", out)
        path.write_text(titled("longer", "Show every build."))
        code, out = self.run_cli("plan", "approve", "longer", "--words", "start")
        self.assertEqual(code, 1, out)
        self.assertIn("drop the trailing period", out)
        path.write_text(titled("longer", "Show every build"))
        code, out = self.run_cli("plan", "approve", "longer", "--words", "start")
        self.assertEqual(code, 0, out)


class ProjectToolRoundNineteen(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def test_the_plan_template_says_the_registry_changes_under_what_changes(self):
        what = plan.TEMPLATE.split("## What changes")[1].split("\n## ")[0]
        self.assertIn("generated", what)
        self.assertIn("tests/repo/registration.json", what)


class PlanApproveRoundSeven(RepoCase):
    def test_two_linked_worktrees_both_behind_dev_each_get_their_next_step(self):  # review 3, 0
        trees = [self.worktree(name) for name in ("feat/pair", "fix/pair-two")]
        record = state.load_branch(self.main, "fix/pair-two")
        state.save_branch(self.main, {**record, "plan": "pair"})  # as plan link records it
        self.on_dev("docs/other.md", "# Other\n")
        git(self.main, "fetch", "-q", "origin")
        self.new_plan("pair")
        code, out = self.run_cli("plan", "approve", "pair", "--words", "start")
        self.assertEqual(code, 0, out)
        for branch, tree in zip(("feat/pair", "fix/pair-two"), trees, strict=True):
            self.assertIn(
                f"next: {branch} already works under it: cd {tree} && python tools/retrodev sync (HEAD lacks 1 "
                "commit(s) of origin/dev), then python tools/retrodev check",
                out,
            )


class BodyRoundSix(RepoCase):
    def started(self, topic: str = "goalie") -> Path:
        self.new_plan(topic)
        self.run_cli("plan", "approve", topic, "--words", "start")
        code, out = self.run_cli("start", f"feat/{topic}")
        self.assertEqual(code, 0, out)
        return self.base / "hermretro-wt" / topic

    def test_start_writes_the_body_from_the_plan_and_never_over_an_existing_one(self):
        self.started()
        body = (self.main / "notes" / "pr" / "goalie.md").read_text()
        self.assertIn("## Why\nMake goalie work.\n", body)
        self.assertIn("## What changed\nThe code of goalie.\n", body)
        self.assertIn("## Not done\nNothing else.\n", body)
        self.assertIn(
            "Made by an agent (Hermes) for the owner.", body
        )  # no GitHub remote (flipped in rounds seven, ten)
        write(self.main, "notes/pr/keeper.md", "## Why\nMine.\n")
        self.started("keeper")
        self.assertEqual((self.main / "notes" / "pr" / "keeper.md").read_text(), "## Why\nMine.\n")

    def test_plan_approve_inside_its_branch_writes_the_body_too(self):
        tree = self.worktree("feat/keeper")
        self.new_plan("keeper")
        code, out = self.run_cli("plan", "approve", "keeper", "--words", "start", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertIn("## What changed\nThe code of keeper.\n", (self.main / "notes/pr/keeper.md").read_text())
        self.worktree("feat/other")
        self.new_plan("unrelated")
        self.run_cli("plan", "approve", "unrelated", "--words", "start", cwd=self.base / "hermretro-wt" / "other")
        self.assertFalse((self.main / "notes/pr/other.md").exists(), "a plan the branch does not work under")

    def test_the_docs_and_status_say_start_writes_the_body_and_ship_only_when_it_is_missing(self):
        # Review round 2: the quick flow still said the first ship writes the body and stops.
        readme = (ROOT / "tools/retrodev/README.md").read_text()
        build = line_with_RoundSix(readme, "| 4 build |")
        self.assertIn("`start`, or `plan approve` inside the linked branch, writes it", build)
        self.assertIn("`ship` writes it only when it is missing", build)
        self.assertNotIn("the first one writes the body", readme)
        self.assertNotIn("first ship writes the body", readme)

        step = status.next_step({"needs_plan": False, "checks_passed": True, "dirty": False, "topic": "t"})
        self.assertNotIn("first ship writes", step)
        self.assertIn("no body yet: ship writes notes/pr/t.md from the template when it is missing", step)


class PathsRoundTen(RepoCase):
    def pushed(self) -> None:
        mate = self.base / "mate"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(mate))
        git(mate, "switch", "-q", "-c", "feat/mate")
        self.commit(mate, "backend/library/core.py", "VALUE = 2\n")
        git(mate, "push", "-q", "origin", "feat/mate")

    def test_start_names_the_body_by_its_path_and_where_notes_live(self):
        self.new_plan("goalie")
        self.run_cli("plan", "approve", "goalie", "--words", "start")
        code, out = self.run_cli("start", "feat/goalie", "--no-setup")
        self.assertEqual(code, 0, out)
        body = self.main / "notes" / "pr" / "goalie.md"
        step = line_with_RoundTen(out, "next: ")
        self.assertIn(f"fill in {body} as you go: notes/ is in the main checkout, shared by every worktree", step)


class ApproveRoundTen(RepoCase):
    def test_plan_approve_rewrites_the_status_line_with_the_day_and_the_words(self):
        path = self.main / "notes/plans/stat.md"
        text = FILLED_PLAN.format(topic="stat").replace(
            "\n\n## Goal", "\n\nStatus: draft for the owner's approval.\n\n## Goal"
        )
        text += "\n## Notes\nStatus: a line in a section stays.\n"
        write(self.main, "notes/plans/stat.md", text)
        code, out = self.run_cli("plan", "approve", "stat", "--words", 'go  ahead\nwith it')
        self.assertEqual(code, 0, out)
        after = path.read_text()
        day = re.search(r'^Status: approved (\d{4}-\d{2}-\d{2}): "go ahead with it"$', after, re.M)
        self.assertIsNotNone(day, after)
        self.assertNotIn("draft for the owner's approval", after)
        self.assertIn("Status: a line in a section stays.", after)
        data: dict = self.run_cli("plan", "show", "stat", as_json=True)[1]
        self.assertFalse(data["changed_since_approval"], "the rewrite is part of what was approved")
        self.assertEqual(data["approved"]["at"][:10], day and day.group(1))
        self.assertIn("Status: draft for the owner's approval.", plan.TEMPLATE)


class ApproveRoundThree(RepoCase):
    def test_plan_approve_names_every_kind_and_what_chore_is_for(self):
        self.new_plan("alone")
        _code, out = self.run_cli("plan", "approve", "alone", "--words", "start")
        line = line_with_RoundThree(out, "next:")
        self.assertIn("start <kind>/alone", line)
        for kind in ("feat", "fix", "docs", "chore"):
            self.assertIn(kind, line)
        self.assertIn("chore (refactors that change no behaviour)", line)
        self.assertNotIn("start feat/alone", line)


if __name__ == "__main__":
    unittest.main()

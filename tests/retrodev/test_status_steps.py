"""The trial rounds' regressions for this area (Fixes, RoundFive, RoundFour, RoundThree, RoundTwo), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_status_steps
"""

import io
import shlex
from retrodev import checks, config, output, repo, state
from tests.retrodev.fixture import GOOD_BODY, RepoCase, git, parallel, write

load_tests = parallel


def line_with(text: str, start: str) -> str:
    return next(line for line in text.splitlines() if line.lstrip().startswith(start))


TITLE = "Make the goalie work"


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

    def test_a_missing_plan_says_none_written_and_plan_new(self):
        tree = self.worktree("feat/ghost")
        code, out = self.run_cli("status", cwd=tree)
        self.assertIn("plan:   ghost (none written)", out)
        self.assertIn("next: python tools/retrodev plan new ghost", out)


class Status(RepoCase):
    def test_behind_dev_without_a_plan_syncs_first_and_says_so_up_front(self):
        tree = self.worktree("feat/goalie")
        self.on_dev("docs/other.md", "# Other\n")
        git(tree, "fetch", "-q", "origin")
        _code, out = self.run_cli("status", cwd=tree)
        lines = out.splitlines()
        self.assertTrue(
            lines[1].startswith("  plan:   goalie (none written): a feat branch ships only under"), lines[1]
        )
        self.assertIn("python tools/retrodev plan new goalie", lines[1])
        self.assertIn('python tools/retrodev plan approve goalie --words "<the owner\'s exact words>"', lines[1])
        step = next(line for line in lines if line.startswith("next: "))
        self.assertTrue(step.startswith("next: python tools/retrodev sync (HEAD lacks 1 commit(s)"), step)
        self.assertIn("then python tools/retrodev plan new goalie", step)


class Ship(RepoCase):
    def passed(self, tree, name):
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        record = state.load_branch(self.main, name)
        record.update(passed_tree=repo.tree_digest(tree), passed_checks=sorted(checks.required(ctx)))
        state.save_branch(self.main, record)

    def feat(self, topic="goalie"):
        self.new_plan(topic)
        self.run_cli("plan", "approve", topic, "--words", "start")
        tree = self.worktree(f"feat/{topic}")
        record = state.load_branch(self.main, f"feat/{topic}")
        state.save_branch(self.main, {**record, "plan": topic})
        self.commit(tree, "docs/guide.md", f"# {topic}\n")
        self.passed(tree, f"feat/{topic}")
        return tree

    def test_status_with_nothing_in_progress_names_both_ways_to_start(self):
        _code, out = self.run_cli("status")
        self.assertIn("next: python tools/retrodev plan new <topic> (docs/chore: start <kind>/<topic> --no-plan)", out)


class StatusRoundThree(RepoCase):
    def passed(self, tree, name):
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        record = state.load_branch(self.main, name)
        record.update(passed_tree=repo.tree_digest(tree), passed_checks=sorted(checks.required(ctx)))
        state.save_branch(self.main, record)

    def feat(self, topic="goalie"):
        self.new_plan(topic)
        self.run_cli("plan", "approve", topic, "--words", "start")
        tree = self.worktree(f"feat/{topic}")
        record = state.load_branch(self.main, f"feat/{topic}")
        state.save_branch(self.main, {**record, "plan": topic})
        self.commit(tree, "docs/guide.md", f"# {topic}\n")
        self.passed(tree, f"feat/{topic}")
        return tree

    def test_a_filled_body_drops_the_fill_in_clause_and_a_passing_dry_run_is_named(self):
        tree = self.feat()
        body = write(self.main, "notes/pr/goalie.md", GOOD_BODY)
        self.run_cli("ship", "--title", TITLE, "--body", str(body), "--dry-run", "--json", cwd=tree)
        _code, out = self.run_cli("status", cwd=tree)
        self.assertNotIn("fill in every section", line_with(out, "next:"), out)
        self.assertIn("ship --dry-run passed at ", line_with(out, "next:"), out)
        write(tree, "docs/guide.md", "# changed\n")  # another tree: that dry run no longer speaks for it
        git(tree, "commit", "-qam", "More")
        self.passed(tree, "feat/goalie")
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn("(the body passes ship's body gate)", line_with(out, "next:"), out)

    def test_a_body_emptied_after_a_passing_dry_run_says_fill_it_in(self):
        tree = self.feat()
        body = write(self.main, "notes/pr/goalie.md", GOOD_BODY)
        self.run_cli("ship", "--title", TITLE, "--body", str(body), "--dry-run", cwd=tree)
        body.write_text(GOOD_BODY.replace("Because.", ""))  # the tree is the same; only the body changed
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn("(fill in every section of the body first)", line_with(out, "next:"), out)
        self.assertNotIn("dry-run passed", out)
        body.write_text(GOOD_BODY.replace("Things.", "Other things."))  # filled in, but not the body that passed
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn("(the body passes ship's body gate)", line_with(out, "next:"), out)

    def test_behind_origin_dev_names_sync_in_a_worktree_and_in_the_main_checkout(self):
        tree = self.worktree("docs/tidy")
        self.on_dev("docs/other.md", "# Other\n")
        git(self.main, "fetch", "-q", "origin")  # the cached ref moves; status itself never fetches
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn("behind origin/dev: 1 commits (python tools/retrodev sync)", out)
        self.assertTrue(line_with(out, "next:").startswith("next: python tools/retrodev sync"), out)
        _code, out = self.run_cli("status", cwd=self.main)
        self.assertIn("behind origin/dev: 1 commits (python tools/retrodev sync)", out)
        self.assertIn("next: python tools/retrodev sync", out)
        write(tree, "docs/guide.md", "# dirty\n")
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn("git commit", line_with(out, "next:"))
        self.assertIn("then python tools/retrodev sync", line_with(out, "next:"))

    def test_docs_and_chore_without_a_plan_need_none(self):
        for name in ("docs/tidy", "chore/sweep"):
            tree = self.worktree(name)
            _code, out = self.run_cli("status", cwd=tree)
            self.assertIn("plan:   none needed (docs/chore)", out)
            self.assertNotIn("plan new", out)
            self.assertNotIn("none written", out)


class Flow(RepoCase):
    def passed(self, tree, name):
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        record = state.load_branch(self.main, name)
        record.update(passed_tree=repo.tree_digest(tree), passed_checks=sorted(checks.required(ctx)))
        state.save_branch(self.main, record)

    def feat(self, topic="goalie"):
        self.new_plan(topic)
        self.run_cli("plan", "approve", topic, "--words", "start")
        tree = self.worktree(f"feat/{topic}")
        record = state.load_branch(self.main, f"feat/{topic}")
        state.save_branch(self.main, {**record, "plan": topic})
        self.commit(tree, "docs/guide.md", f"# {topic}\n")
        self.passed(tree, f"feat/{topic}")
        return tree

    def test_status_names_the_ship_with_its_body_and_how_far_dev_moved_on(self):
        tree = self.feat()
        self.run_cli("ship", "--title", TITLE, "--dry-run", cwd=tree)  # writes the body, records the title
        path = self.main / "notes" / "pr" / "goalie.md"
        _code, out = self.run_cli("status", cwd=tree)
        words = shlex.split(line_with(out, "next:").removeprefix("next: ").split(" (")[0])
        # after a dry run, still a dry run (it once named the real ship: test_trial_round_four)
        self.assertEqual(
            words, ["python", "tools/retrodev", "ship", "--title", TITLE, "--body", str(path), "--dry-run"]
        )
        self.assertNotIn("behind", out)
        self.on_dev("docs/other.md", "# Other\n")
        self.on_dev("docs/more.md", "# More\n")
        git(tree, "fetch", "-q", "origin")
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn("behind origin/dev: 2 commits (python tools/retrodev sync)", out)

    def test_status_falls_back_to_the_plan_s_title(self):
        tree = self.feat("keeper")
        plan = self.main / "notes" / "plans" / "keeper.md"
        plan.write_text(plan.read_text().replace("# Plan: keeper", "# Plan: Keep the keeper in goal"))
        write(self.main, "notes/pr/keeper.md", "## Why\n")
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn("--title 'Keep the keeper in goal' --body", line_with(out, "next:"))

    def test_status_keeps_a_custom_body_after_a_dry_run_before_any_pull_request(self):
        tree = self.feat()
        write(self.main, "notes/pr/goalie.md", "## Why\n")  # an unrelated default body must not win
        body = write(self.base, "custom.md", "## Why\nBecause.\n")
        self.run_cli("ship", "--title", TITLE, "--body", str(body), "--dry-run", cwd=tree)
        _code, out = self.run_cli("status", cwd=tree)
        words = shlex.split(line_with(out, "next:").removeprefix("next: ").split(" (")[0])
        self.assertEqual(
            words, ["python", "tools/retrodev", "ship", "--title", TITLE, "--body", str(body), "--dry-run"]
        )

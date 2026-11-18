"""check's caching and automatic extras, and ship's gates, push and pull request.

Run alone: python -m unittest tests.retrodev.test_check_ship
"""

import io
import json
import os
import unittest

from retrodev import checks, repo, state

from tests.retrodev.fixture import GOOD_BODY, RepoCase, git, parallel, write

load_tests = parallel
FAST = ["unit", "bundle", "lint", "page", "scan"]
DEPS = "/nonexistent-deps"  # set for every test (fixture.shared_env): acceptance must drop it


class Check(RepoCase):
    def test_a_pass_is_cached_and_a_change_reruns_only_the_checks_that_read_it(self):
        tree = self.worktree()
        code, data = self.run_cli("check", cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual(self.check_log(), [{"names": FAST, "tmpdir": os.environ.get("TMPDIR"), "deps": DEPS}])
        self.assertTrue(data["tree_passed"])
        self.assertEqual(
            sorted(data),
            sorted(
                ["branch", "checks", "code", "command", "fast_wall", "ok", "status", "tree", "tree_passed", "warnings"]
            ),
        )
        self.clear_log()
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count("ok (cached)"), 5, out)
        self.assertEqual(self.check_log(), [], "nothing reran")
        write(tree, "docs/guide.md", "# Guide, edited\n")
        self.run_cli("check", cwd=tree)
        self.assertEqual(self.check_log()[0]["names"], ["unit", "scan"], "a doc is read only by unit and scan")
        self.clear_log()
        write(tree, "page/a.js", "export const a = 2\n")
        self.run_cli("check", cwd=tree)
        self.assertEqual(self.check_log()[0]["names"], FAST)
        self.clear_log()
        self.run_cli("check", "--again", "lint", cwd=tree)
        self.assertEqual(self.check_log()[0]["names"], ["lint"])

    def test_a_failure_is_not_cached_and_ends_with_fix(self):
        tree = self.worktree()
        self.fail_checks("lint")
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 1)
        self.assertIn("FIX: fix lint", out)
        self.assertTrue(out.rstrip().splitlines()[-1].startswith("FIX: "))
        self.assertNotIn("passed_tree", state.load_branch(self.main, "docs/tidy"))
        self.clear_log()
        self.fail_checks()
        self.run_cli("check", cwd=tree)
        self.assertEqual(self.check_log()[0]["names"], ["lint"], "only the failed check runs again")
        self.assertIn("passed_tree", state.load_branch(self.main, "docs/tidy"))

    def test_backend_changes_add_acceptance_and_the_clean_install(self):
        tree = self.worktree("chore/move")
        git(tree, "mv", "backend/hermes/glue.py", "backend/hermes/seam.py")
        git(tree, "commit", "-q", "-m", "Move the glue")
        code, data = self.run_cli("check", cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)
        log = self.check_log()
        self.assertEqual(log[0]["names"], FAST)
        self.assertEqual(log[1]["names"], ["acceptance"])
        self.assertEqual(log[1]["tmpdir"], checks.short_tmp())
        self.assertIsNone(log[1]["deps"], "acceptance uses the toolchain setup put in place")
        self.assertEqual(log[2:], [{"script": []}, {"script": ["--update-from"]}])
        self.assertEqual([row["name"] for row in data["checks"]], FAST + ["acceptance", "clean_install", "update"])

    def test_budgets_warn_but_never_fail(self):
        tree = self.worktree()
        from retrodev import config, output

        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        rows = [{"name": "lint", "seconds": 4.5, "cached": False}, {"name": "unit", "seconds": 7.0, "cached": False}]
        warnings = checks.budget_warnings(ctx, rows, 31.0, True)
        self.assertEqual(len(warnings), 2)
        self.assertIn("lint took 4.5 s, over twice its 2 s budget", warnings[0])
        self.assertIn("fast checks took 31.0 s", warnings[1])

    def test_watch_sees_a_change(self):
        tree = self.worktree()
        from retrodev import config, output

        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        before = checks.snapshot(ctx)
        write(tree, "docs/new.md", "# New\n")
        self.assertEqual(checks.changed_since(before, checks.snapshot(ctx)), ["docs/new.md"])
        self.assertEqual(checks.watch(ctx, [], rounds=1), 0)


class Ship(RepoCase):
    def passed(self, tree, name):
        """Record a passing check of this tree, as `check` does (Check tests the real thing)."""
        record = state.load_branch(self.main, name)
        record["passed_tree"] = repo.tree_digest(tree)
        state.save_branch(self.main, record)

    def ready(self, name="docs/tidy"):
        tree = self.worktree(name)
        self.commit(tree, "docs/guide.md", "# Guide, better\n", "Improve the guide")
        self.passed(tree, name)
        body = write(self.base, "body.md", GOOD_BODY)
        return tree, str(body)

    def test_every_gate_is_reported_at_once(self):
        tree = self.worktree()
        write(tree, "docs/guide.md", "# Uncommitted\n")
        body = write(self.base, "body.md", "## Why\nBecause.\n")
        code, data = self.run_cli("ship", "--title", "Fix it.", "--body", str(body), cwd=tree, as_json=True)
        self.assertEqual(code, 1)
        failed = [gate["name"] for gate in data["gates"] if not gate["ok"]]
        self.assertEqual(failed, ["title", "body", "committed and clean", "checks passed on this tree", "has commits"])
        self.assertEqual(self.gh.calls, [])

    def test_a_tree_that_did_not_pass_check_is_refused(self):
        tree, body = self.ready()
        self.commit(tree, "docs/guide.md", "# Changed after the check\n")
        code, out = self.run_cli("ship", "--title", "Improve the guide", "--body", body, cwd=tree)
        self.assertEqual(code, 1)
        self.assertTrue(out.rstrip().endswith("FIX: python tools/retrodev check"), out)

    def test_ship_pushes_and_opens_a_draft_with_area_labels(self):
        tree, body = self.ready("chore/both")
        self.commit(tree, "backend/library/core.py", "VALUE = 2\n")
        self.passed(tree, "chore/both")
        code, data = self.run_cli("ship", "--title", "Tidy", "--body", body, "--dry-run", cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["push"], ["git", "push", "-u", "origin", "chore/both"])
        self.assertIsNone(git(self.origin, "rev-parse", "-q", "--verify", "chore/both", check=False).strip() or None)
        self.gh.answers[("pr", "create")] = (0, "https://github.com/o/r/pull/12\n", "")
        code, data = self.run_cli("ship", "--title", "Tidy", "--body", body, cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)
        head = git(tree, "rev-parse", "HEAD").strip()
        self.assertEqual(git(self.origin, "rev-parse", "chore/both").strip(), head)
        create = self.gh.called("pr", "create")[0]
        self.assertEqual(create[2:6], ["--draft", "--base", "dev", "--head"])
        self.assertEqual([create[i + 1] for i, word in enumerate(create) if word == "--label"], ["backend"])
        record = state.load_branch(self.main, "chore/both")
        self.assertEqual((record["pr"]["number"], record["pushed"]), (12, head))

        self.gh.answers[("pr", "list")] = (0, json.dumps([{"number": 12, "url": "u"}]), "")
        self.gh.answers[("pr", "edit")] = (0, "", "")
        code, data = self.run_cli("ship", "--title", "Tidy", "--body", body, cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual(self.gh.called("pr", "edit")[0][:3], ["pr", "edit", "12"])
        self.assertEqual(len(self.gh.called("pr", "create")), 1)

    def test_a_remote_that_moved_is_never_overwritten(self):
        tree, body = self.ready()
        git(tree, "push", "-q", "origin", "docs/tidy")
        other = self.base / "other"
        git(self.base, "clone", "-q", "-b", "docs/tidy", str(self.origin), str(other))
        self.commit(other, "docs/theirs.md", "# Theirs\n")
        git(other, "push", "-q", "origin", "docs/tidy")
        code, out = self.run_cli("ship", "--title", "Improve the guide", "--body", body, cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("FIX: python tools/retrodev sync", out)

    def test_dev_itself_is_never_shipped(self):
        body = write(self.base, "body.md", GOOD_BODY)
        code, out = self.run_cli("ship", "--title", "Tidy", "--body", str(body))
        self.assertEqual(code, 1)
        self.assertIn("'dev' takes changes only through pull requests", out)


if __name__ == "__main__":
    unittest.main()

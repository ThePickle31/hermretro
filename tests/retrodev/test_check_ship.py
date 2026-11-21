"""check's caching and ship's gates, push and pull request.

Run alone: python -m unittest tests.retrodev.test_check_ship
"""

import io
import json
import os
import subprocess
import sys
import threading
import unittest
from pathlib import Path

import retrodev
from retrodev import checks, repo, state, watch

from tests.retrodev.fixture import GOOD_BODY, RepoCase, git, parallel, write

load_tests = parallel
FAST = ["unit", "bundle", "lint", "page", "scan"]
FAST_LINE = 'fast = ["unit", "bundle", "lint", "page", "scan"]'  # policy.toml's line
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
                # next: the body to fill in (missing here), then ship (round eight: also before the body exists)
                [
                    *["branch", "checks", "code", "command", "fast_wall", "next", "ok", "status", "tree"],
                    *["tree_passed", "unpassed", "warnings"],
                ]
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

    def test_a_failed_rerun_takes_back_the_tree_s_pass(self):
        tree = self.worktree()
        self.assertEqual(self.run_cli("check", cwd=tree)[0], 0)
        self.assertIn("passed_tree", state.load_branch(self.main, "docs/tidy"))
        self.fail_checks("lint")
        code, out = self.run_cli("check", "--again", "lint", cwd=tree)
        self.assertEqual(code, 1, out)
        record = state.load_branch(self.main, "docs/tidy")
        self.assertNotIn("passed_tree", record, "a tree that just failed a check may not ship")
        self.assertNotIn("passed_at", record)

    def test_a_check_reruns_when_its_tools_or_their_pins_change(self):
        tree = self.worktree()
        self.assertEqual(self.run_cli("check", cwd=tree)[0], 0)
        self.clear_log()
        write(tree, "tools/npm/package-lock.json", '{"jsdom": "30.0.0"}\n')  # new pins of the page tests' tools
        self.run_cli("check", cwd=tree)
        self.assertEqual(self.check_log()[0]["names"], FAST, "page, bundle and lint run with the npm tools")
        for runner in ("tools/check.py", "tools/retrodev/policy.toml"):
            self.clear_log()
            write(tree, runner, (tree / runner).read_text() + "\n# changed\n")
            self.run_cli("check", cwd=tree)
            self.assertEqual(self.check_log()[0]["names"], FAST, f"every check is run by or decided in {runner}")

    def test_the_install_checks_run_only_on_a_committed_tree_and_install_its_head(self):
        tree = self.worktree("chore/glue")
        write(tree, "backend/hermes/glue.py", "GLUE = 2\n")  # not committed: the install would miss it
        code, out = self.run_cli("check", "clean_install", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertNotIn("script", "".join(json.dumps(entry) for entry in self.check_log()))
        self.assertIn("FIX: commit first: the clean install installs the committed tree", out)
        self.assertTrue(out.rstrip().endswith("then python tools/retrodev check clean_install"), out)
        self.assertEqual(self.check_log(), [], "refused before any check ran")
        self.assertNotIn("passed_tree", state.load_branch(self.main, "chore/glue"))
        git(tree, "commit", "-q", "-am", "Change the glue")
        self.clear_log()
        code, out = self.run_cli("check", "clean_install", cwd=tree)
        self.assertEqual(code, 0, out)
        installs = [entry for entry in self.check_log() if "script" in entry]
        self.assertEqual(installs, [{"script": [], "head": git(tree, "rev-parse", "HEAD").strip()}])
        self.assertEqual(state.load_branch(self.main, "chore/glue")["checks"]["clean_install"]["state"], "ok")

    def test_the_digest_sees_modes_and_symlinks(self):
        tree = self.worktree()
        self.commit(tree, "docs/link.md", "guide.md")
        before = repo.tree_digest(tree)
        os.chmod(tree / "docs" / "guide.md", 0o755)
        self.assertNotEqual(repo.tree_digest(tree), before, "an executable bit is part of the tree")
        os.chmod(tree / "docs" / "guide.md", 0o644)
        self.assertEqual(repo.tree_digest(tree), before)
        (tree / "docs" / "link.md").unlink()
        os.symlink("guide.md", tree / "docs" / "link.md")  # the same bytes as the file it replaced
        self.assertNotEqual(repo.tree_digest(tree), before, "a symlink is not the file it replaced")

    def test_budgets_warn_only_when_a_check_is_over_twice_in_a_row(self):
        # Flipped: one slow run once warned (on every cold run of every trial); now only the second in a row does.
        tree = self.worktree()
        from retrodev import config, output

        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        budgets = ctx.policy["checks"]["budgets"]
        unit_budget, total_budget = float(budgets["unit"]), float(budgets["fast_total"])
        rows = [
            {"name": "lint", "state": "ok", "seconds": 3.0, "cached": False},
            {"name": "unit", "state": "ok", "seconds": unit_budget - 5.0, "cached": False},
        ]
        self.assertEqual(
            checks.budget_warnings(ctx, rows, total_budget - 5.0, True, {}), [], "a cold unit run is in budget"
        )
        rows[1]["seconds"] = unit_budget + 5.0
        self.assertEqual(
            checks.budget_warnings(ctx, rows, total_budget + 10.0, True, {}), [], "one slow run says nothing"
        )
        last = checks.durations(rows, total_budget + 10.0, {})
        self.assertEqual((last["unit"], last["fast_total"]), (unit_budget + 5.0, total_budget + 10.0))
        warnings = checks.budget_warnings(ctx, rows, total_budget + 10.0, True, last)
        self.assertEqual(len(warnings), 2, warnings)
        self.assertIn(
            f"unit took {unit_budget + 5.0:.1f} s, over its {unit_budget:g} s budget twice in a row: slower than usual",
            warnings[0],
        )
        self.assertIn("machines and load differ", warnings[0])
        self.assertIn(
            f"fast checks took {total_budget + 10.0:.1f} s together, over their {total_budget:g} s budget twice in a row",
            warnings[1],
        )
        # Back in budget after a slow run: quiet (a gate looking only at the previous run would warn).
        recovered = [{**rows[0]}, {**rows[1], "seconds": unit_budget - 5.0}]
        self.assertEqual(checks.budget_warnings(ctx, recovered, total_budget - 5.0, True, last), [])
        cached = [{"name": "unit", "state": "ok", "seconds": 0.0, "cached": True}]
        self.assertEqual(checks.durations(cached, None, last), last, "a cached row keeps the last run's time")

    def test_watch_sees_a_change(self):
        tree = self.worktree()
        from retrodev import config, output

        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        before = watch.snapshot(ctx)
        write(tree, "docs/new.md", "# New\n")
        self.assertEqual(watch.changed_since(before, watch.snapshot(ctx)), [":clean", "docs/new.md"])
        self.assertEqual(watch.watch(ctx, [], rounds=1), 0)

    def test_watch_wakes_on_a_commit_that_edits_no_file(self):
        tree = self.worktree("chore/glue")
        from retrodev import config, output

        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        write(tree, "backend/hermes/glue.py", "GLUE = 2\n")  # uncommitted: the asked install waits for a commit
        waits = []

        def sleep(seconds):
            waits.append(seconds)
            if len(waits) == 1:
                self.assertNotIn("script", json.dumps(self.check_log()), "no install of an uncommitted tree")
                git(tree, "commit", "-q", "-am", "Change the glue")  # no file is touched
            elif len(waits) > 5:
                raise AssertionError("the watcher never woke after the commit")

        self.assertEqual(watch.watch(ctx, ["clean_install"], rounds=2, sleep=sleep), 0)
        installs = [entry for entry in self.check_log() if "script" in entry]
        self.assertEqual(installs[0], {"script": [], "head": git(tree, "rev-parse", "HEAD").strip()})

    def test_watch_reloads_the_policy_and_runs_a_check_it_now_requires(self):
        tree = self.worktree()
        self.commit(tree, "docs/guide.md", "# Guide, better\n")
        from retrodev import config, output

        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        waits = []

        def sleep(seconds):
            waits.append(seconds)
            if len(waits) == 1:  # while watching, the policy starts requiring the clean install of every tree
                self.assertIn("passed_tree", state.load_branch(self.main, "docs/tidy"))
                policy = tree / "tools/retrodev/policy.toml"
                text = policy.read_text().replace(FAST_LINE, FAST_LINE[:-1] + ', "clean_install"]')
                self.commit(tree, "tools/retrodev/policy.toml", text, "Docs need the clean install")
            elif len(waits) > 5:
                raise AssertionError("the watcher never woke after the policy change")

        self.assertEqual(watch.watch(ctx, [], rounds=2, sleep=sleep), 0)
        installs = [entry for entry in self.check_log() if "script" in entry]
        self.assertEqual(installs, [{"script": [], "head": git(tree, "rev-parse", "HEAD").strip()}])
        record = state.load_branch(self.main, "docs/tidy")
        self.assertEqual(record["passed_tree"], repo.tree_digest(tree))
        self.assertIn("clean_install", record.get("passed_checks", []))

    def test_watch_again_reruns_cached_checks_on_its_first_run(self):
        tree = self.worktree()
        self.assertEqual(self.run_cli("check", cwd=tree)[0], 0)
        self.clear_log()
        tools = str(Path(retrodev.__file__).resolve().parents[1])
        env = dict(os.environ, PYTHONPATH=tools)
        command = [sys.executable, "-m", "retrodev", "check", "--watch", "--again"]
        with subprocess.Popen(command, cwd=tree, env=env, text=True, stdout=subprocess.PIPE) as process:
            seen = []
            timer = threading.Timer(60, process.kill)
            timer.start()
            try:
                for line in process.stdout:
                    seen.append(line)
                    if "watching for changes" in line:
                        break
            finally:
                timer.cancel()
                process.terminate()
        self.assertIn("watching for changes", "".join(seen), "".join(seen))
        self.assertEqual([entry["names"] for entry in self.check_log()], [FAST], "--again reran the cached passes")


class Ship(RepoCase):
    def passed(self, tree, name):
        """Record a passing check of this tree, as `check` does (Check tests the real thing)."""
        from retrodev import config, output

        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        record = state.load_branch(self.main, name)
        record.update(passed_tree=repo.tree_digest(tree), passed_checks=sorted(checks.required(ctx)))
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
        labelled = [create[i + 1] for i, word in enumerate(create) if word == "--label"]
        self.assertEqual(labelled, ["backend", "documentation"], "docs/ is documentation now (it had no label)")
        record = state.load_branch(self.main, "chore/both")
        self.assertEqual((record["pr"]["number"], record["pushed"]), (12, head))

        self.gh.answers[("pr", "list")] = (0, json.dumps([{"number": 12, "url": "u", "baseRefName": "dev"}]), "")
        self.gh.answers[("pr", "edit")] = (0, "", "")
        code, data = self.run_cli("ship", "--title", "Tidy", "--body", body, cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual(self.gh.called("pr", "edit")[0][:3], ["pr", "edit", "12"])
        self.assertEqual(len(self.gh.called("pr", "create")), 1)
        review = json.loads((state.root(self.main) / "reviews" / "12.json").read_text())
        self.assertEqual(review["shipped"]["head"], head, "the first ship's time stays (stats: ship to merge)")

    def test_a_remote_that_moved_is_never_overwritten(self):
        tree, body = self.ready()
        git(tree, "push", "-q", "origin", "docs/tidy")
        other = self.base / "other"
        git(self.base, "clone", "-q", "-b", "docs/tidy", str(self.origin), str(other))
        self.commit(other, "docs/theirs.md", "# Theirs\n")
        git(other, "push", "-q", "origin", "docs/tidy")
        code, out = self.run_cli("ship", "--title", "Improve the guide", "--body", body, cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("FIX: git fetch origin && git merge origin/docs/tidy, then python tools/retrodev check", out)
        git(tree, "fetch", "-q", "origin")  # following the FIX makes the gate pass
        git(tree, "merge", "-q", "origin/docs/tidy")
        self.assertEqual(self.run_cli("check", cwd=tree)[0], 0)
        self.gh.answers[("pr", "create")] = (0, "https://github.com/o/r/pull/3\n", "")
        code, out = self.run_cli("ship", "--title", "Improve the guide", "--body", body, cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertEqual(git(self.origin, "rev-parse", "docs/tidy"), git(tree, "rev-parse", "HEAD"))

    def test_ship_needs_an_approved_plan_unless_docs_or_chore(self):
        body = str(write(self.base, "body.md", GOOD_BODY))
        path = self.base / "by-hand"
        git(self.main, "worktree", "add", "-q", "-b", "feat/by-hand", str(path), "origin/dev")
        self.commit(path, "docs/guide.md", "# By hand\n")
        self.passed(path, "feat/by-hand")  # a record without a plan, as check leaves on a hand-made branch

        def plan_gate():
            code, data = self.run_cli("ship", "--title", "T", "--body", body, "--dry-run", cwd=path, as_json=True)
            return code, next(gate for gate in data["gates"] if gate["name"] == "plan approved")

        code, gate = plan_gate()
        self.assertEqual((code, gate["ok"]), (3, False))
        self.assertIn("there is no plan 'by-hand'", gate["message"])
        self.new_plan("bigplan")
        self.run_cli("plan", "link", "bigplan", cwd=path)
        code, gate = plan_gate()
        self.assertEqual((code, gate["ok"]), (3, False))
        self.assertIn("'bigplan' is not approved", gate["message"])
        self.run_cli("plan", "approve", "bigplan", "--words", "start")
        code, gate = plan_gate()
        self.assertEqual((code, gate["ok"]), (0, True))

        tree = self.worktree("fix/noplan")  # recorded with no plan: only docs and chore may do that
        self.commit(tree, "docs/guide.md", "# Fix\n")
        self.passed(tree, "fix/noplan")
        code, data = self.run_cli("ship", "--title", "T", "--body", body, "--dry-run", cwd=tree, as_json=True)
        self.assertEqual(code, 3, data)
        self.assertEqual([gate["name"] for gate in data["gates"] if not gate["ok"]], ["plan approved"])

    def test_a_pass_recorded_before_the_policy_required_more_is_refused(self):
        tree, body = self.ready()
        policy = tree / "tools/retrodev/policy.toml"
        text = policy.read_text().replace(FAST_LINE, FAST_LINE[:-1] + ', "clean_install"]')
        self.commit(tree, "tools/retrodev/policy.toml", text, "Every tree needs the clean install")
        record = state.load_branch(self.main, "docs/tidy")  # as a watcher holding the old policy recorded it
        record.update(passed_tree=repo.tree_digest(tree), passed_checks=FAST)
        state.save_branch(self.main, record)
        code, data = self.run_cli("ship", "--title", "Tidy", "--body", body, "--dry-run", cwd=tree, as_json=True)
        self.assertEqual(code, 1, data)
        gate = next(gate for gate in data["gates"] if gate["name"] == "checks passed on this tree")
        self.assertFalse(gate["ok"])
        self.assertIn("clean_install", gate["message"])
        self.assertEqual(self.run_cli("check", cwd=tree)[0], 0)  # following the FIX makes the gate pass
        code, data = self.run_cli("ship", "--title", "Tidy", "--body", body, "--dry-run", cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)

    def test_an_open_pull_request_into_another_base_is_refused(self):
        tree, body = self.ready()
        answer = [{"number": 12, "url": "u", "baseRefName": "main"}]
        self.gh.answers[("pr", "list")] = (0, json.dumps(answer), "")
        self.gh.answers[("pr", "edit")] = (0, "", "")
        code, out = self.run_cli("ship", "--title", "Improve the guide", "--body", body, cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("into main", out)
        self.assertTrue(out.rstrip().endswith("FIX: gh pr edit 12 --base dev, then python tools/retrodev ship"), out)
        self.assertEqual(self.gh.called("pr", "edit"), [], "ship never retargets or edits it itself")
        self.assertEqual(git(self.origin, "branch", "--list", "docs/tidy"), "", "nothing was pushed")
        self.assertIn("baseRefName", self.gh.called("pr", "list")[0][-1])
        _code, out = self.run_cli("ship", "--title", "Improve the guide", "--body", body, "--dry-run", cwd=tree)
        self.assertTrue(out.rstrip().endswith("then python tools/retrodev ship --dry-run"), out)  # still a dry run
        answer[0]["baseRefName"] = "dev"  # what following the FIX does
        self.gh.answers[("pr", "list")] = (0, json.dumps(answer), "")
        code, out = self.run_cli("ship", "--title", "Improve the guide", "--body", body, cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.gh.called("pr", "edit")[0][:3], ["pr", "edit", "12"])

    def test_dev_itself_is_never_shipped(self):
        body = write(self.base, "body.md", GOOD_BODY)
        code, out = self.run_cli("ship", "--title", "Tidy", "--body", str(body))
        self.assertEqual(code, 1)
        self.assertIn("'dev' takes changes only through pull requests", out)


if __name__ == "__main__":
    unittest.main()

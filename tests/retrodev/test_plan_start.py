"""plan new / show / approve, start's gates and the worktree it makes, and config precedence.

Run alone: python -m unittest tests.retrodev.test_plan_start
"""

import unittest

from retrodev import state

from tests.retrodev.fixture import RepoCase, git, parallel, write

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
        self.run_cli("plan", "new", "speedy")
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
        self.run_cli("plan", "new", "bigplan")
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
        self.run_cli("plan", "new", "bigplan")
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
        self.assertIn("FIX: use one of: base, github_account, remote, worktree_root", out)


if __name__ == "__main__":
    unittest.main()

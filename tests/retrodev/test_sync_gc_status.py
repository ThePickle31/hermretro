"""sync's conflict handling, gc's care with unfinished worktrees, status, report and doctor.

Run alone: python -m unittest tests.retrodev.test_sync_gc_status
"""

import json
import unittest

from retrodev import repo, state, sync

from tests.retrodev.fixture import PYTHON, RepoCase, git, parallel, write

load_tests = parallel

BUILT = "desktop/plugin.js"


class Sync(RepoCase):
    def build(self, cwd):
        self.assertEqual(repo.run([PYTHON, "tools/gen.py"], cwd)[0], 0)

    def test_a_conflict_only_in_generated_files_is_rebuilt_and_finished(self):
        tree = self.worktree()
        write(tree, "page/b.js", "export const b = 2\n")
        self.build(tree)
        self.commit(tree, "page/b.js", "export const b = 2\n", "Add b")
        other = self.base / "other"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(other))
        write(other, "page/c.js", "export const c = 3\n")
        self.build(other)
        self.commit(other, "page/c.js", "export const c = 3\n", "Add c")
        git(other, "push", "-q", "origin", "dev")
        code, data = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["resolved"], [BUILT])
        self.assertEqual(
            (tree / BUILT).read_text(), "// built\nexport const a = 1\nexport const b = 2\nexport const c = 3\n"
        )
        self.assertEqual(git(tree, "status", "--porcelain"), "")
        self.assertEqual(len(git(tree, "rev-list", "--parents", "-n", "1", "HEAD").split()), 3, "a merge commit")

    def test_a_real_conflict_stops_with_the_files(self):
        tree = self.worktree()
        self.commit(tree, "page/a.js", "export const a = 'mine'\n")
        self.on_dev("page/a.js", "export const a = 'theirs'\n")
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("conflicts in files only a person can merge: page/a.js", out)
        self.assertIn("FIX: edit each file", out)
        self.assertIn("UU page/a.js", git(tree, "status", "--porcelain"), "the merge stays open to resolve")

    def test_a_clean_merge_rebuilds_stale_generated_files(self):
        tree = self.worktree()
        self.commit(tree, "docs/guide.md", "# Mine\n")
        self.on_dev("page/a.js", "export const a = 5\n")  # dev forgot to rebuild
        code, data = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["regenerated"], [BUILT])
        self.assertEqual(git(tree, "log", "-1", "--format=%s").strip(), sync.REGENERATED)
        self.assertEqual(self.run_cli("sync", cwd=tree, as_json=True)[1]["merged"], False)


class GC(RepoCase):
    def committed(self, name):
        tree = self.worktree(name)
        self.commit(tree, f"docs/{name.split('/')[1]}.md", "# Done\n")
        return tree

    def test_only_finished_clean_worktrees_go(self):
        merged = self.committed("docs/merged")
        dirty = self.committed("docs/dirty")
        fresh = self.worktree("docs/fresh")
        squashed = self.committed("docs/squashed")
        git(self.main, "push", "-q", "origin", "docs/merged", "docs/dirty", "docs/squashed")
        record = state.load_branch(self.main, "docs/squashed")
        record["pr"] = {"number": 5}
        state.save_branch(self.main, record)
        self.gh.answers[("pr", "view", "5")] = (0, "MERGED\n", "")
        other = self.base / "other"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(other))
        git(other, "merge", "-q", "origin/docs/merged", "origin/docs/dirty")
        git(other, "push", "-q", "origin", "dev")
        write(dirty, "docs/wip.md", "not committed\n")
        cache = write(self.main, "adapter/__pycache__/old.cpython-311.pyc", "x")
        write(self.main, "backend/library/__pycache__/core.cpython-311.pyc", "x")
        git(self.main, "fetch", "-q", "origin")
        before = git(self.main, "worktree", "list")

        code, data = self.run_cli("gc", "--dry-run", as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual(sorted(row["branch"] for row in data["removed"]), ["docs/merged", "docs/squashed"])
        self.assertEqual(data["folders"], [str(self.main / "adapter")])
        self.assertEqual(git(self.main, "worktree", "list"), before, "a dry run changes nothing")
        self.assertTrue(cache.is_file())

        code, data = self.run_cli("gc", as_json=True)
        self.assertEqual(code, 0, data)
        kept = {row["branch"]: row["why"] for row in data["kept"]}
        self.assertIn("uncommitted", kept["docs/dirty"])
        self.assertEqual(kept["docs/fresh"], "never pushed")
        self.assertFalse(merged.exists() or squashed.exists())
        self.assertTrue(dirty.is_dir() and fresh.is_dir())
        self.assertEqual(git(self.main, "branch", "--list", "docs/merged"), "")
        self.assertFalse(state.branch_path(self.main, "docs/merged").exists())
        self.assertFalse((self.main / "adapter").exists())
        self.assertTrue((self.main / "backend" / "library" / "__pycache__").is_dir())


class StatusReportDoctor(RepoCase):
    def test_status_on_a_branch_and_in_the_main_checkout(self):
        tree = self.worktree("chore/look")
        code, data = self.run_cli("status", cwd=tree, as_json=True)
        self.assertEqual(data["next"], "next: python tools/retrodev check")
        self.commit(tree, "docs/guide.md", "# Better\n")
        self.run_cli("check", cwd=tree)
        code, out = self.run_cli("status", cwd=tree)
        self.assertIn("checks: passed on this tree", out)
        self.assertIn("next: python tools/retrodev ship --title", out)
        code, data = self.run_cli("status", as_json=True)
        self.assertEqual([row["branch"] for row in data["branches"]], ["chore/look"])
        self.assertIn("retrodev ship", data["branches"][0]["next"])

    def test_report_groups_files_and_says_what_to_restart(self):
        tree = self.worktree("chore/both")
        self.commit(tree, "backend/library/core.py", "VALUE = 3\n")
        self.commit(tree, BUILT, "// built\nchanged\n")
        record = state.load_branch(self.main, "chore/both")
        record["pr"] = {"number": 9, "url": "https://github.com/o/r/pull/9"}
        state.save_branch(self.main, record)
        jobs = [{"name": "All checks pass", "state": "SUCCESS", "bucket": "pass", "link": "l"}]
        self.gh.answers[("pr", "checks", "9")] = (0, json.dumps(jobs), "")
        code, data = self.run_cli("report", cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["files"], {"backend/library/": ["backend/library/core.py"], "desktop/": [BUILT]})
        self.assertEqual(sorted(data["restart"]), ["app", "gateway"])
        self.assertEqual(data["ci"]["summary"], "passing")
        self.assertEqual(len(data["commits"]), 2)
        self.assertEqual(data["review_rounds"], [])
        code, out = self.run_cli("report", cwd=tree)
        self.assertIn("restarts the Hermes gateway", out)
        self.assertIn("reloads Hermes Desktop", out)

    def test_doctor_names_the_account_it_sees(self):
        self.run_cli("config", "set", "github_account", "someone")
        code, data = self.run_cli("doctor", as_json=True)
        self.assertEqual(code, 1)
        account = next(item for item in data["items"] if item["name"] == "gh account")
        self.assertIn("logged in as you", account["detail"])
        self.assertIn("gh auth switch --user someone", account["fix"])
        self.assertTrue(data["error"]["fix"])


if __name__ == "__main__":
    unittest.main()

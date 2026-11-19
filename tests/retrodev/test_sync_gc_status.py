"""sync's conflict handling, gc's care with unfinished worktrees, status, report and doctor.

Run alone: python -m unittest tests.retrodev.test_sync_gc_status
"""

import json
import shutil
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
        self.assertIn("FIX: resolve each listed source file", out)
        self.assertIn("UU page/a.js", git(tree, "status", "--porcelain"), "the merge stays open to resolve")

    def test_after_a_source_conflict_sync_again_rebuilds_and_finishes_the_merge(self):
        tree = self.worktree()
        write(tree, "page/a.js", "export const a = 'mine'\n")
        self.build(tree)
        self.commit(tree, "page/a.js", "export const a = 'mine'\n", "Mine")
        other = self.base / "other"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(other))
        write(other, "page/a.js", "export const a = 'theirs'\n")
        self.build(other)
        self.commit(other, "page/a.js", "export const a = 'theirs'\n", "Theirs")
        git(other, "push", "-q", "origin", "dev")
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn(
            "only a person can merge: page/a.js (and generated ones retrodev rebuilds: desktop/plugin.js)", out
        )
        fix = out.rstrip().splitlines()[-1]
        self.assertIn("git add", fix)
        self.assertIn("python tools/retrodev sync", fix)
        self.assertNotIn("git commit", fix, "sync finishes the merge itself")
        write(tree, "page/a.js", "export const a = 'both'\n")  # following the FIX: the source only
        git(tree, "add", "page/a.js")
        code, data = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual((tree / BUILT).read_text(), "// built\nexport const a = 'both'\n")
        self.assertEqual(git(tree, "status", "--porcelain"), "")
        self.assertEqual(len(git(tree, "rev-list", "--parents", "-n", "1", "HEAD").split()), 3, "a merge commit")
        self.assertEqual(git(tree, "show", f"HEAD:{BUILT}"), "// built\nexport const a = 'both'\n")
        self.assertTrue(repo.is_ancestor(tree, git(tree, "rev-parse", "origin/dev").strip(), "HEAD"))

    def test_status_during_an_open_sync_merge_points_back_to_sync_never_to_a_commit(self):
        tree = self.worktree()
        write(tree, "page/a.js", "export const a = 'mine'\n")
        self.build(tree)
        self.commit(tree, "page/a.js", "export const a = 'mine'\n", "Mine")
        other = self.base / "other"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(other))
        write(other, "page/a.js", "export const a = 'theirs'\n")
        self.build(other)
        self.commit(other, "page/a.js", "export const a = 'theirs'\n", "Theirs")
        git(other, "push", "-q", "origin", "dev")
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("edit the hunks", out.rstrip().splitlines()[-1], "sync's own FIX says how to resolve")
        # before resolving: the worktree's own status and the main checkout's row both name the hunks, then sync
        _code, data = self.run_cli("status", cwd=tree, as_json=True)
        _code, rows = self.run_cli("status", cwd=self.main, as_json=True)
        for step in (data["next"], rows["branches"][0]["next"]):
            self.assertIn("resolve the conflict hunks in page/a.js", step)
            self.assertIn("--ours/--theirs", step)
            self.assertIn("then python tools/retrodev sync", step)
            self.assertNotIn("git commit", step, "a manual commit would keep conflict markers and skip the rebuild")
        self.assertEqual(data["merge_unresolved"], ["page/a.js"], "the generated file is sync's to rebuild")
        # after resolving and adding the source: sync finishes it
        write(tree, "page/a.js", "export const a = 'both'\n")
        git(tree, "add", "page/a.js")
        _code, data = self.run_cli("status", cwd=tree, as_json=True)
        self.assertTrue(data["next"].startswith("next: python tools/retrodev sync ("), data["next"])
        self.assertNotIn("git commit", data["next"])
        self.assertEqual(self.run_cli("sync", cwd=tree)[0], 0)
        self.assertEqual(git(tree, "show", f"HEAD:{BUILT}"), "// built\nexport const a = 'both'\n")
        _code, data = self.run_cli("status", cwd=tree, as_json=True)
        self.assertFalse(data["merging"])
        self.assertEqual(data["next"], "next: python tools/retrodev check")

    def test_sync_again_with_a_source_still_unresolved_stops(self):
        tree = self.worktree()
        self.commit(tree, "page/a.js", "export const a = 'mine'\n")
        self.on_dev("page/a.js", "export const a = 'theirs'\n")
        self.assertEqual(self.run_cli("sync", cwd=tree)[0], 1)
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("still unresolved: page/a.js", out)
        self.assertIn("UU page/a.js", git(tree, "status", "--porcelain"), "the merge stays open")

    def test_a_clean_merge_rebuilds_stale_generated_files(self):
        tree = self.worktree()
        self.commit(tree, "docs/guide.md", "# Mine\n")
        self.on_dev("page/a.js", "export const a = 5\n")  # dev forgot to rebuild
        code, data = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["regenerated"], [BUILT])
        self.assertEqual(git(tree, "log", "-1", "--format=%s").strip(), sync.REGENERATED)
        self.assertEqual(self.run_cli("sync", cwd=tree, as_json=True)[1]["merged"], False)

    def test_the_rebuilt_line_names_the_command_as_a_person_types_it(self):
        tree = self.worktree()
        self.commit(tree, "docs/guide.md", "# Mine\n")
        self.on_dev("page/a.js", "export const a = 6\n")
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 0, out)
        rebuilt = [line for line in out.splitlines() if "rebuilt:" in line]
        self.assertEqual([line.strip() for line in rebuilt], ["rebuilt: python tools/gen.py"], out)
        self.assertNotIn("{", rebuilt[0])


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

    def test_bytecode_cleanup_never_touches_anything_else(self):
        outside = write(self.base, "outside/data.txt", "precious\n").parent
        keep = {
            "hidden": "hidden/.history/important",
            "notes": "notes-pkg/notes/plan.md",
            "deep": "deep/sub/node_modules/x/index.js",
            "dotfile": "dotfile/.keep",
        }
        for name, path in keep.items():
            write(self.main, f"{name}/__pycache__/old.pyc" if name != "notes" else "notes-pkg/x.pyc", "x")
            write(self.main, path, "data\n")
        write(self.main, "linked/__pycache__/old.pyc", "x")
        (self.main / "linked" / "data").symlink_to(outside, target_is_directory=True)
        write(self.main, "linkfile/__pycache__/old.pyc", "x")
        (self.main / "linkfile" / "mod.pyc").symlink_to(outside / "data.txt")
        write(self.main, "gone/__pycache__/old.pyc", "x")
        (self.main / "gone" / "empty" / "deeper").mkdir(parents=True)
        code, data = self.run_cli("gc", as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["folders"], [str(self.main / "gone")])
        for path in keep.values():
            self.assertTrue((self.main / path).is_file(), path)
        self.assertTrue((self.main / "linked" / "__pycache__").is_dir() and (outside / "data.txt").is_file())
        self.assertTrue((self.main / "linkfile" / "mod.pyc").is_symlink())

    def test_a_missing_worktree_folder_never_costs_its_branch(self):
        lost = self.committed("docs/lost")  # unpushed work: the branch is its only copy
        done = self.committed("docs/done")
        git(self.main, "push", "-q", "origin", "docs/done")
        git(self.main, "push", "-q", "origin", "docs/done:dev")  # merged
        for path in (lost, done):
            shutil.rmtree(path)
        code, data = self.run_cli("gc", as_json=True)
        self.assertEqual(code, 0, data)
        kept = {row["branch"]: row["why"] for row in data["kept"]}
        self.assertIn("never pushed", kept["docs/lost"])
        self.assertEqual([row["branch"] for row in data["removed"]], ["docs/done"])
        self.assertNotEqual(git(self.main, "branch", "--list", "docs/lost"), "", "the branch stays")
        self.assertTrue(state.branch_path(self.main, "docs/lost").is_file(), "and so does its record")
        self.assertNotIn(str(lost), git(self.main, "worktree", "list"), "the stale worktree entry is pruned")
        self.assertEqual(git(self.main, "branch", "--list", "docs/done"), "")

    def test_a_finished_worktree_holding_ignored_data_is_kept(self):
        notes = self.committed("docs/notes")
        caches = self.committed("docs/caches")
        git(self.main, "push", "-q", "origin", "docs/notes", "docs/caches")
        other = self.base / "other"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(other))
        git(other, "merge", "-q", "origin/docs/notes", "origin/docs/caches")  # both merged, both clean
        git(other, "push", "-q", "origin", "dev")
        write(notes, "notes/x.md", "the owner's notes\n")  # ignored: git status calls this tree clean
        write(caches, "node_modules/x/index.js", "cache\n")
        write(caches, "backend/library/__pycache__/core.cpython-311.pyc", "x")
        code, data = self.run_cli("gc", as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual([row["branch"] for row in data["removed"]], ["docs/caches"])
        kept = {row["branch"]: row for row in data["kept"]}
        self.assertIn("notes/", kept["docs/notes"]["why"])
        self.assertIn("move them out", kept["docs/notes"]["fix"])
        self.assertTrue((notes / "notes" / "x.md").is_file())
        self.assertNotEqual(git(self.main, "branch", "--list", "docs/notes"), "", "the branch stays too")
        self.assertFalse(caches.exists())
        code, out = self.run_cli("gc")
        self.assertIn("FIX: move them out", out)

    def test_a_branch_whose_worktree_was_pruned_goes_once_it_is_merged(self):
        later = self.committed("docs/later")
        git(self.main, "push", "-q", "origin", "docs/later")
        shutil.rmtree(later)
        code, data = self.run_cli("gc", as_json=True)
        self.assertEqual(code, 0, data)
        self.assertIn("still open", {row["branch"]: row["why"] for row in data["kept"]}["docs/later"])
        self.assertNotIn(str(later), git(self.main, "worktree", "list"))
        git(self.main, "push", "-q", "origin", "docs/later:dev")  # merged later
        code, data = self.run_cli("gc", as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual([row["branch"] for row in data["removed"]], ["docs/later"])
        self.assertEqual(data["forgotten"], [], "a record removed with its branch is not forgotten twice")
        self.assertEqual(git(self.main, "branch", "--list", "docs/later"), "")
        self.assertFalse(state.branch_path(self.main, "docs/later").exists())


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

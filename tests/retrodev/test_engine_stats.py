"""`engine update` (owner-gated, a checklist that never changes engine/) and `stats` (read-only numbers).

Both run in the test repository: its engine/ is a stand-in made here, never the real one.
Run alone: python -m unittest tests.retrodev.test_engine_stats
"""

import hashlib
import json
import shutil
from pathlib import Path

import retrodev
from retrodev import state

from tests.retrodev.fixture import RepoCase, git, parallel, write

load_tests = parallel

ROOT = Path(retrodev.__file__).resolve().parents[2]
WORDS = "please update the engine to 9.9.9"
TOOLS = '{"tools": []}\n'


def report(passed=True, sha=None, engine="9.9.9", pinned_engine="9.9.9") -> dict:
    """A reconciliation report in the shape tools/engine/reconcile_schemas.py writes (engine/pins/<v>/)."""
    return {
        "pinned_file": "engine/pins/9.9.9/tools.json",
        "pinned_file_sha256": sha or hashlib.sha256(TOOLS.encode()).hexdigest(),
        "live_server_info": {"name": "modretro-chromatic", "version": engine},
        "pinned_server_info": {"name": "modretro-chromatic", "version": pinned_engine},
        "passed": passed,
    }


class EngineUpdate(RepoCase):
    def tree(self, branch="chore/engine-9.9.9"):
        tree = self.worktree(branch)
        shutil.copyfile(ROOT / "docs/dev/ENGINE-UPDATE.md", tree / "docs/ENGINE-UPDATE.md")
        (tree / "docs/dev").mkdir(exist_ok=True)
        (tree / "docs/ENGINE-UPDATE.md").rename(tree / "docs/dev/ENGINE-UPDATE.md")
        write(tree, "backend/system/paths.py", 'ENGINE_VERSION = "1.0.0"\n')
        write(tree, "engine/modretro-chromatic/package.json", '{"version": "1.0.0"}\n')
        git(tree, "add", "-A")
        git(tree, "commit", "-q", "-m", "Engine 1.0.0")
        return tree

    def records(self):
        return sorted((state.root(self.main) / "engine").glob("*.json"))

    def test_without_the_owners_words_it_needs_the_owner_even_for_a_dry_run(self):
        tree = self.tree()
        for extra in ([], ["--dry-run"], ["--owner-words", "  "]):
            code, out = self.run_cli("engine", "update", "9.9.9", *extra, cwd=tree)
            self.assertEqual(code, 3, out)
            self.assertIn("needs the owner", out)
            self.assertIn("FIX: ask the owner", out)
        self.assertEqual(self.records(), [])

    def test_a_dry_run_prints_every_step_and_records_nothing(self):
        tree = self.tree("feat/other")
        code, data = self.run_cli(
            "engine", "update", "9.9.9", "--owner-words", WORDS, "--dry-run", cwd=tree, as_json=True
        )
        self.assertEqual(code, 0, data)
        self.assertEqual([step["number"] for step in data["steps"]], list(range(1, 9)))
        self.assertEqual(data["steps"][0]["state"], "todo")
        self.assertIn(
            "python tools/engine/manifest.py write engine/pins/9.9.9/manifest.json", data["steps"][2]["commands"]
        )
        self.assertEqual(self.records(), [])
        self.assertEqual(git(tree, "status", "--porcelain"), "")

    def test_it_runs_only_on_the_engine_branch(self):
        tree = self.tree("feat/other")
        code, out = self.run_cli("engine", "update", "9.9.9", "--owner-words", WORDS, cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("FIX: python tools/retrodev start chore/engine-9.9.9 --no-plan", out)

    def test_it_records_the_words_and_names_the_first_step_left(self):
        tree = self.tree()
        write(tree, "engine/modretro-chromatic/package.json", '{"version": "9.9.9"}\n')
        for name in ("dist/server.js", "dist/device-capture/linux-helper.js"):
            write(tree, f"engine/modretro-chromatic/{name}", "spawn(ffmpeg, ['-i', '/dev/fd/6'])\n")
        code, data = self.run_cli("engine", "update", "9.9.9", "--owner-words", WORDS, cwd=tree, as_json=True)
        self.assertEqual(code, 2, data)
        self.assertEqual([step["state"] for step in data["steps"][:3]], ["done", "done", "todo"])
        self.assertEqual(data["next"], "step 3")
        record = json.loads(self.records()[0].read_text())
        self.assertEqual((record["version"], record["words"]), ("9.9.9", WORDS))
        before = git(tree, "status", "--porcelain")
        self.run_cli("engine", "update", "9.9.9", "--owner-words", WORDS, cwd=tree)
        self.assertEqual(git(tree, "status", "--porcelain"), before, "it changes nothing in the tree itself")

    def test_manual_steps_wait_until_acknowledged_by_number(self):
        tree = self.tree()
        write(tree, "engine/modretro-chromatic/package.json", '{"version": "9.9.9"}\n')
        for name in ("dist/server.js", "dist/device-capture/linux-helper.js"):
            write(tree, f"engine/modretro-chromatic/{name}", "spawn(ffmpeg, ['-i', '/dev/fd/6'])\n")
        write(tree, "engine/pins/9.9.9/manifest.json", '{"local_patches": []}\n')
        write(tree, "engine/pins/9.9.9/tools.json", TOOLS)
        write(tree, "engine/pins/9.9.9/schema-reconcile.json", json.dumps(report()))
        write(tree, "tools/engine/manifest.py", "")  # stand-ins of the read-only helpers: they pass
        for name in ("tests/__init__.py", "tests/repo/__init__.py"):
            write(tree, name, "")
        write(
            tree,
            "tests/repo/test_lockstep.py",
            "import unittest\n\n\nclass T(unittest.TestCase):\n    def test(self):\n        pass\n",
        )
        write(tree, "backend/system/paths.py", 'ENGINE_VERSION = "9.9.9"\n')
        update = ("engine", "update", "9.9.9", "--owner-words", WORDS)
        code, data = self.run_cli(*update, cwd=tree, as_json=True)
        self.assertEqual(code, 2, data)  # every tree step is done; steps 6 and 8 are by hand
        self.assertEqual([step["state"] for step in data["steps"] if step["number"] not in (6, 8)], ["done"] * 6)
        manual = [step["number"] for step in data["steps"] if step["state"] == "manual"]
        self.assertEqual(manual, [6, 8])
        self.assertEqual(data["outstanding"], [6, 8])
        code, out = self.run_cli(*update, "--done", "6", cwd=tree)
        self.assertEqual(code, 2, out)
        self.assertIn("--done 8", out)
        code, data = self.run_cli(*update, "--done", "5", cwd=tree, as_json=True)
        self.assertEqual(code, 1, data)  # the tree judges step 5: it cannot be waved through
        code, data = self.run_cli(*update, "--done", "8", cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)
        record = json.loads(self.records()[0].read_text())
        self.assertEqual(sorted(record["done"]), ["6", "8"])
        self.assertEqual(record["done"]["6"]["by"], "the agent")
        self.assertTrue(record["done"]["6"]["at"])

    def test_the_contract_step_needs_a_passing_current_reconciliation(self):
        tree = self.tree("feat/other")
        reconcile = "python tools/engine/reconcile_schemas.py engine/pins/9.9.9/tools.json engine/pins/9.9.9/schema-reconcile.json"
        cases = {
            "missing": None,
            "malformed": "{not json",
            "not an object": "[]",
            "failed": json.dumps(report(passed=False)),
            "no verdict": json.dumps({key: value for key, value in report().items() if key != "passed"}),
            "stale": json.dumps(report(sha=hashlib.sha256(b"an older tools.json").hexdigest())),
            "other engine": json.dumps(report(engine="9.9.8")),
            "other pinned engine": json.dumps(report(pinned_engine="9.9.8")),
            "current": json.dumps(report()),
        }
        write(tree, "engine/pins/9.9.9/tools.json", TOOLS)
        path = tree / "engine/pins/9.9.9/schema-reconcile.json"
        for case, text in cases.items():
            with self.subTest(case):
                path.unlink(missing_ok=True)
                if text is not None:
                    path.write_text(text)
                code, data = self.run_cli(
                    "engine", "update", "9.9.9", "--owner-words", WORDS, "--dry-run", cwd=tree, as_json=True
                )
                self.assertEqual(code, 0, data)
                step = next(step for step in data["steps"] if "tool contracts" in step["title"].lower())
                self.assertEqual(step["state"], "done" if case == "current" else "todo", step)
                self.assertEqual(step["commands"], [reconcile])
        path.write_text(json.dumps(report(passed=False)))
        code, out = self.run_cli("engine", "update", "9.9.9", "--owner-words", WORDS, "--dry-run", cwd=tree)
        self.assertIn("did not pass", out)
        self.assertIn(reconcile, out)

    def test_a_version_must_look_like_one(self):
        code, out = self.run_cli("engine", "update", "latest", "--owner-words", WORDS, cwd=self.tree())
        self.assertEqual(code, 1, out)


class Stats(RepoCase):
    def test_it_counts_rounds_findings_times_checks_and_friction(self):
        reviews = state.root(self.main) / "reviews"
        reviews.mkdir(parents=True)
        finding = {"severity": "low", "file": "a", "line": 1, "problem": "p", "fix": "f"}
        landed = {
            "pr": 7,
            "rounds": [
                {"round": 1, "result": {"findings": [finding, finding]}, "answers": {"0": "x", "1": "y"}},
                {"round": 2, "result": {"findings": []}},
                {"round": 3, "void": True, "result": {"findings": [finding]}},
            ],
            "shipped": {"at": "2026-11-17T10:00:00-0800"},
            "approval": {"at": "2026-11-17T11:00:00-0800"},
            "merged": {"at": "2026-11-17T12:30:00-0800", "subject": "Thing (#7)"},
        }
        (reviews / "7.json").write_text(json.dumps(landed))
        (reviews / "8.json").write_text(json.dumps({"pr": 8, "rounds": []}))
        record = {
            "branch": "feat/x",
            "checks": {"unit": {"state": "ok", "seconds": 8.0}, "lint": {"state": "FAILED", "seconds": 1.0}},
            "last_run": {"fast_wall": 11.0},
        }
        state.save_branch(self.main, record)
        write(
            self.main,
            "notes/friction.md",
            "| When | What | Cost | Fix |\n|---|---|---|---|\n| a | b | c | d (open) |\n| e | f | g | h (done) |\n",
        )
        self.on_dev("docs/x.md", "x\n", "Thing (#7)")
        git(self.main, "fetch", "-q", "origin")
        code, data = self.run_cli("stats", as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["landed_with_retrodev"], 1)
        self.assertEqual(data["merged_into_base"], 1)
        self.assertEqual(data["open_or_unmerged_records"], [8])
        pr = data["pull_requests"][0]
        self.assertEqual((pr["rounds"], pr["findings"], pr["answered"]), (2, [2, 0], 2))
        self.assertEqual((pr["ship_to_merge_hours"], pr["approval_to_merge_hours"]), (2.5, 1.5))
        self.assertEqual(data["checks"]["per_check"], {"unit": {"runs": 1, "mean_seconds": 8.0}})
        self.assertEqual(data["checks"]["fast_wall_mean_seconds"], 11.0)
        self.assertEqual((data["friction"]["rows"], data["friction"]["open"]), (2, 1))
        code, text = self.run_cli("stats")
        self.assertIn("#7: 2 rounds, findings per round: 2, 0, answered 2; ship->merge 2.5 h", text)

    def test_skipped_reviews_print_the_recorded_reason_and_never_the_owner(self):
        reviews = state.root(self.main) / "reviews"
        reviews.mkdir(parents=True)
        landed = {
            "pr": 9,
            "rounds": [],
            "skipped": {"reason": "land --no-review"},
            "merged": {"at": "2026-11-17T12:30:00-0800", "subject": "Thing (#9)"},
        }
        (reviews / "9.json").write_text(json.dumps(landed))
        code, text = self.run_cli("stats")
        self.assertEqual(code, 0, text)
        self.assertIn("#9: 0 rounds, findings per round: none, answered 0; reviews skipped: land --no-review", text)
        self.assertNotIn("owner", text)

    def test_a_legacy_skip_reason_is_shown_neutrally_and_others_as_written(self):
        reviews = state.root(self.main) / "reviews"
        reviews.mkdir(parents=True)
        for pr, reason in ((10, "land --no-review (the owner's call)"), (11, "reviewer down (the owner's call)")):
            landed = {
                "pr": pr,
                "rounds": [],
                "skipped": {"reason": reason},
                "merged": {"at": "2026-11-17T12:30:00-0800", "subject": f"Thing (#{pr})"},
            }
            (reviews / f"{pr}.json").write_text(json.dumps(landed))
        code, text = self.run_cli("stats")
        self.assertEqual(code, 0, text)
        lines = [line.strip() for line in text.splitlines()]
        self.assertIn("#10: 0 rounds, findings per round: none, answered 0; reviews skipped: land --no-review", lines)
        self.assertIn(
            "#11: 0 rounds, findings per round: none, answered 0; reviews skipped: reviewer down (the owner's call)",
            text,
        )
        stored = json.loads((reviews / "10.json").read_text())
        self.assertEqual(stored["skipped"]["reason"], "land --no-review (the owner's call)")

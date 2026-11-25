"""tools/dev/bench_compare.py: `bench compare` finds the earlier finished run that made exactly the same games, sets
each shared game's measures side by side, exits 1 only when a game got clearly worse (its thresholds) and 2 when one
could not be judged, reading the profile's state.db and logs without writing anything in the profile."""

import io
import json
import sys
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from tests.dev.test_bench import PROMPT, CliFixture

TOP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOP / "tools" / "dev"))

import bench  # noqa: E402 - tools/dev, put on the path just above
import bench_compare  # noqa: E402

GOOD = bench.Report(
    session="local-before",
    wall=1200.0,
    cost=10.0,
    model_calls=100,
    tool_calls=200,
    builds=2,
    compactions=1,
    ended="yes",
)


def report(**changed) -> bench.Report:
    return bench.Report(**{**GOOD.__dict__, "session": "local-after", **changed})


class JudgedTest(unittest.TestCase):
    """A measure got clearly worse when it rose by its floor and by more than its share; the ending counts alone."""

    def test_the_same_or_better_is_not_worse(self):
        self.assertEqual(bench_compare.judged(GOOD, GOOD), [])
        self.assertEqual(bench_compare.judged(GOOD, report(wall=600.0, cost=4.0, tool_calls=90)), [])

    def test_a_rise_must_pass_both_its_floor_and_its_share(self):
        judged = bench_compare.judged
        self.assertEqual(judged(GOOD, report(wall=1490.0)), [])  # +4m50s: under the 5-minute floor
        self.assertEqual(judged(GOOD, report(wall=1500.0)), [])  # +5m, but only 25% of 20m
        self.assertEqual(judged(GOOD, report(wall=1501.0)), ["wall time"])  # +5m01s: both
        big = report(wall=12000.0)
        self.assertEqual(judged(big, report(wall=14000.0)), [])  # +33m but +17%
        self.assertEqual(judged(GOOD, report(cost=12.5, model_calls=125, tool_calls=250)), [])  # each 25%: not more
        self.assertEqual(judged(GOOD, report(cost=12.6, model_calls=126)), ["cost (estimated)", "model calls"])

    def test_a_cost_rise_of_exactly_the_floor_is_one(self):
        cheap = report(cost=7.2)
        self.assertEqual(bench_compare.judged(cheap, report(cost=9.19)), [])
        self.assertEqual(bench_compare.judged(cheap, report(cost=9.2)), ["cost (estimated)"])  # 9.2 - 7.2 < 2.0
        self.assertEqual(
            bench_compare.described("cost (estimated)", cheap, report(cost=9.2)), "cost (estimated) +$2.00 (+28%)"
        )

    def test_from_none_any_rise_past_the_floor_is_worse(self):
        worse = report(source_commands=3, source_reads=2, duplicate_drops=5, errors=Counter({"BUILD_FAILED": 3}))
        self.assertEqual(bench_compare.judged(GOOD, worse), ["duplicate drops", "source commands", "tool errors"])

    def test_unknown_drops_are_not_judged(self):
        self.assertEqual(bench_compare.judged(report(duplicate_drops=None), report(duplicate_drops=40)), [])
        drops = bench_compare.MEASURES[8]
        self.assertEqual(bench_compare.change(drops, None, 40), "")

    def test_measures_shown_only_are_never_worse(self):
        self.assertEqual(bench_compare.judged(GOOD, report(steps=500, builds=20, restores=30)), [])

    def test_no_longer_ending_normally_is_worse_alone(self):
        stopped = report(wall=9000.0, ended="no (startup_orphan_reap, no final answer)")
        self.assertEqual(bench_compare.judged(GOOD, stopped), ["ended normally"])
        self.assertEqual(
            bench_compare.described("ended normally", GOOD, stopped),
            "ended normally yes -> no (startup_orphan_reap, no final answer)",
        )

    def test_measures_are_not_judged_against_a_chat_that_did_not_end_normally(self):
        stopped = report(wall=60.0, ended="no (startup_orphan_reap, no final answer)")
        self.assertEqual(bench_compare.judged(stopped, GOOD), [])
        self.assertEqual(bench_compare.judged(stopped, report(ended="no (still open)")), [])

    def test_changes_are_signed_with_their_share(self):
        wall = bench_compare.MEASURES[0]
        self.assertEqual(bench_compare.change(wall, 1200.0, 1500.0), "+5m00s (+25%)")
        self.assertEqual(bench_compare.change(wall, 1200.0, 600.0), "-10m00s (-50%)")
        self.assertEqual(bench_compare.change(wall, 0.0, 90.0), "+1m30s")
        self.assertEqual(bench_compare.change(wall, 90.0, 90.0), "")


class PreviousRunTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.runs = Path(temp.name).resolve()

    def run_folder(self, name: str, games: list[str] | None, started: float, ended: float | None = 1.0) -> Path:
        folder = self.runs / name
        folder.mkdir()
        if games is not None:
            made = {game: {"prompt": game, "log": f"{game}.log", "ended": ended} for game in games}
            (folder / "run.json").write_text(json.dumps({"started": started, "games": made}), encoding="utf-8")
        return folder

    def test_the_newest_earlier_finished_run_with_exactly_its_games(self):
        self.run_folder("20261125-010000", ["2-bolt", "3-starling"], started=100)  # older
        # Named out of order: the recorded start decides which is newer.
        wanted = self.run_folder("20261125-000000", ["3-starling", "2-bolt"], started=300)
        self.run_folder("20261125-040000", ["1-lantern", "2-bolt", "3-starling"], started=400)  # more games
        self.run_folder("20261125-050000", ["2-bolt"], started=500)  # fewer
        self.run_folder("20261125-060000", None, started=600)  # no run.json
        self.run_folder("20261125-070000", ["2-bolt", "3-starling"], started=700, ended=None)  # not finished
        run = self.run_folder("20261125-094708", ["2-bolt", "3-starling"], started=900)
        self.run_folder("20261126-000000", ["2-bolt", "3-starling"], started=1000)  # later
        self.assertEqual(bench_compare.previous_run(run), wanted)

    def test_no_earlier_run_with_exactly_the_games(self):
        self.run_folder("20261125-040000", ["1-lantern", "2-bolt", "3-starling"], started=400)
        run = self.run_folder("20261125-094708", ["2-bolt", "3-starling"], started=900)
        message = "no finished run before 20261125-094708 .* made exactly 2-bolt, 3-starling: name one with --against"
        with self.assertRaisesRegex(bench.BenchError, message):
            bench_compare.previous_run(run)


class CompareCommandTest(CliFixture):
    """`python tools/dev bench compare` against a profile home of its own: two runs of the same games."""

    def setUp(self):
        super().setUp()
        self.clock = 0.0
        self.before = self.make_run("20261125-023312", {"2-bolt": 600.0, "3-starling": 300.0})

    def make_run(self, name: str, walls: dict[str, float], ended: str = "cli_close", **recorded) -> Path:
        folder = self.home.parent / "runs" / name
        folder.mkdir(parents=True)
        record = {"started": self.clock, "profile": "hermretro", "home": str(self.home), "commit": f"{name[-6:]}abcdef"}
        games = {}
        for game, wall in walls.items():
            session = f"local-{name}-{game}"
            started = self.clock
            self.session(session, started=started, ended=started + wall, reason=ended, calls=10, cost=1.0)
            self.message("user", session=session, content=PROMPT)
            self.message("assistant", session=session, content="Done.", finish_reason="stop")
            games[game] = {"prompt": PROMPT, "log": f"{game}.log", "session": session, "ended": started + wall}
            self.clock += 10000
        (folder / "run.json").write_text(json.dumps({**record, "games": games, **recorded}), encoding="utf-8")
        return folder

    def edit_record(self, folder: Path, game: str, **changed) -> None:
        record = json.loads((folder / "run.json").read_text(encoding="utf-8"))
        record["games"][game].update(changed)
        (folder / "run.json").write_text(json.dumps(record), encoding="utf-8")

    def compare(self, *argv) -> tuple[int, str, str]:
        output, error = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            code = self.cli.main(["bench", "compare", *argv])
        return code, output.getvalue(), error.getvalue()

    def test_no_game_worse_exits_zero(self):
        after = self.make_run("20261125-094708", {"2-bolt": 300.0, "3-starling": 300.0})
        self.tool(
            "chromatic_rom_build", {"isError": True, "code": "BUILD_FAILED"}, session="local-20261125-094708-2-bolt"
        )
        code, output, _ = self.compare("--run", str(after))
        self.assertEqual(code, 0)
        lines = output.splitlines()
        self.assertEqual(lines[:2], ["run      20261125-094708 (094708a)", "against  20261125-023312 (023312a)"])
        self.assertIn("2-bolt               20261125-023312  20261125-094708  change", lines)
        self.assertIn("wall time            10m00s           5m00s            -5m00s (-50%)", lines)
        self.assertIn("ended normally       yes              yes", lines)
        self.assertIn("sessions: local-20261125-023312-2-bolt -> local-20261125-094708-2-bolt", lines)
        self.assertIn("errors: BUILD_FAILED 0 -> 1", lines)
        self.assertEqual(lines[-1], "clearly worse: none")

    def test_nothing_in_the_profile_is_written(self):
        """A live writer keeps state.db's `-wal` and `-shm`; a closed one leaves none. Either way the profile's folder
        is byte for byte the same after the comparison, and what only the log holds is read."""
        self.db.execute("PRAGMA journal_mode=wal")
        after = self.make_run("20261125-094708", {"2-bolt": 300.0, "3-starling": 300.0})
        for writer in ("open", "closed"):
            with self.subTest(writer=writer):
                if writer == "closed":
                    self.db.close()
                sidecars = {path.name for path in self.home.iterdir()} - {"state.db", "logs"}
                self.assertEqual(sidecars, {"state.db-wal", "state.db-shm"} if writer == "open" else set())
                before = {path: path.read_bytes() for path in self.home.rglob("*") if path.is_file()}
                code, output, _ = self.compare("--run", str(after))
                self.assertEqual(code, 0)
                self.assertIn("wall time            10m00s           5m00s", output)
                self.assertEqual({path: path.read_bytes() for path in self.home.rglob("*") if path.is_file()}, before)

    def test_a_game_clearly_worse_exits_non_zero(self):
        after = self.make_run("20261125-094708", {"2-bolt": 1200.0, "3-starling": 300.0})
        code, output, _ = self.compare("--run", str(after), "--against", str(self.before))
        self.assertEqual(code, 1)
        self.assertIn("wall time            10m00s           20m00s           +10m00s (+100%)  worse", output)
        self.assertTrue(output.endswith("clearly worse:\n  2-bolt: wall time +10m00s (+100%)\n"))

    def test_a_game_that_stopped_ending_normally(self):
        after = self.make_run("20261125-094708", {"2-bolt": 60.0, "3-starling": 60.0}, ended="startup_orphan_reap")
        code, output, _ = self.compare("--run", str(after))
        self.assertEqual(code, 1)
        self.assertIn("measures not judged: a chat did not end normally", output)
        self.assertIn("  2-bolt: ended normally yes -> no (startup_orphan_reap)", output)

    def test_a_named_run_of_other_games_says_the_workload_differs(self):
        after = self.make_run("20261125-094708", {"2-bolt": 300.0, "1-lantern": 300.0})
        code, output, _ = self.compare("--run", str(after), "--against", str(self.before))
        self.assertEqual(code, 0)
        self.assertIn(
            "workload differs, so contention does too: only in run: 1-lantern; only in against: 3-starling", output
        )

    def test_games_either_run_cannot_speak_for_are_not_judged(self):
        """A missing session in the candidate is not a worse ending, nor in the baseline a pass: exit 2."""
        studio = self.home.parent / "hermes" / "profiles" / "hermretro"  # the CLI's way to the fixture's home
        db = studio / "state.db"
        for case in ("run session", "against session", "unfinished", "other home", "other profile"):
            with self.subTest(case=case):
                against = self.make_run(f"{case}-against", {"2-bolt": 300.0})
                after = self.make_run(f"{case}-run", {"2-bolt": 3000.0})  # 50 minutes against 5: worse, if judged
                if case == "run session":
                    self.edit_record(after, "2-bolt", session="local-gone")
                    reason = f"run: no such session in {db}"
                elif case == "against session":
                    self.edit_record(against, "2-bolt", session=None)
                    self.db.execute("DELETE FROM messages WHERE session_id = ?", (f"local-{against.name}-2-bolt",))
                    self.db.commit()
                    reason = f"against: no session in {db}"
                elif case == "unfinished":
                    self.edit_record(after, "2-bolt", ended=None)
                    reason = "run: its chat had not exited"
                elif case == "other home":
                    record = json.loads((after / "run.json").read_text(encoding="utf-8"))
                    (after / "run.json").write_text(json.dumps({**record, "home": "/elsewhere"}), encoding="utf-8")
                    reason = f"run: made in /elsewhere, not {studio}"
                else:  # a run recorded before runs named their home
                    record = json.loads((after / "run.json").read_text(encoding="utf-8"))
                    del record["home"]
                    (after / "run.json").write_text(json.dumps({**record, "profile": "work"}), encoding="utf-8")
                    reason = "run: made in the work profile, not hermretro"
                code, output, _ = self.compare("--run", str(after), "--against", str(against))
                self.assertEqual(code, 2)
                self.assertIn(f"not judged: {reason}", output)
                self.assertTrue(output.endswith("clearly worse: none\nnot judged: 2-bolt\n"))

    def test_runs_that_cannot_be_compared(self):
        after = self.make_run("20261125-094708", {"5-tidepool": 300.0})
        for argv, message in (
            (["--run", str(after)], "no finished run before 20261125-094708"),
            (["--run", str(after), "--against", str(self.before)], "made no game in common"),
            (["--run", str(self.before), "--against", str(self.before)], "compared with itself"),
            (["bolt", "--run", str(after)], "bench compare takes no games"),
        ):
            with self.subTest(argv=argv):
                code, output, error = self.compare(*argv)
                self.assertEqual((code, output), (1, ""))
                self.assertIn(message, error)

    def test_against_is_only_for_compare(self):
        error = io.StringIO()
        with redirect_stderr(error):
            self.assertEqual(self.cli.main(["bench", "report", "--against", str(self.before)]), 1)
        self.assertIn("--against is for bench compare", error.getvalue())


class SnapshotTest(CliFixture):
    def test_a_database_that_changes_while_it_is_copied_is_refused(self):
        with (
            mock.patch.object(bench, "stamp", side_effect=range(100)),  # a new size or time at every look
            self.assertRaisesRegex(bench.BenchError, "changed each time it was copied"),
            bench.snapshot(self.home / "state.db"),
        ):
            pass


if __name__ == "__main__":
    unittest.main()

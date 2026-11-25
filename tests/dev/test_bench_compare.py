"""tools/dev/bench_compare.py: `bench compare` finds the earlier run that made the same games, sets each shared game's
measures side by side, and exits non-zero only when a game got clearly worse (its thresholds), reading the profile's
state.db and logs without writing them."""

import io
import json
import sys
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

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

    def test_from_none_any_rise_past_the_floor_is_worse(self):
        worse = report(source_commands=3, source_reads=2, duplicate_drops=5, errors=Counter({"BUILD_FAILED": 3}))
        self.assertEqual(bench_compare.judged(GOOD, worse), ["duplicate drops", "source commands", "tool errors"])

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
        stopped = report(wall=60.0, ended="no session")
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

    def run_folder(self, name: str, games: list[str] | None) -> Path:
        folder = self.runs / name
        folder.mkdir()
        if games is not None:
            record = {"games": {game: {"prompt": game, "log": f"{game}.log"} for game in games}}
            (folder / "run.json").write_text(json.dumps(record), encoding="utf-8")
        return folder

    def test_the_newest_earlier_run_that_made_every_game(self):
        wanted = self.run_folder("20261125-040000", ["1-lantern", "2-bolt", "3-starling", "4-burrow"])
        self.run_folder("20261125-050000", ["2-bolt"])  # misses Starling
        self.run_folder("20261125-060000", None)  # no run.json
        self.run_folder("20261125-070000", [])  # a record without games
        run = self.run_folder("20261125-094708", ["2-bolt", "3-starling"])
        self.run_folder("20261126-000000", ["2-bolt", "3-starling"])  # later
        self.assertEqual(bench_compare.previous_run(run), wanted)

    def test_no_earlier_run_with_the_games(self):
        self.run_folder("20261125-050000", ["2-bolt"])
        run = self.run_folder("20261125-094708", ["2-bolt", "3-starling"])
        with self.assertRaisesRegex(bench.BenchError, "no run before 20261125-094708 .* made 2-bolt, 3-starling"):
            bench_compare.previous_run(run)


class CompareCommandTest(CliFixture):
    """`python tools/dev bench compare` against a profile home of its own: two runs of the same games."""

    def setUp(self):
        super().setUp()
        self.clock = 0.0
        self.before = self.make_run("20261125-023312", {"2-bolt": 600.0, "3-starling": 300.0, "1-lantern": 300.0})

    def make_run(self, name: str, walls: dict[str, float], ended: str = "cli_close") -> Path:
        folder = self.home.parent / "runs" / name
        folder.mkdir(parents=True)
        games = {}
        for game, wall in walls.items():
            session = f"local-{name}-{game}"
            started = self.clock
            self.session(session, started=started, ended=started + wall, reason=ended, calls=10, cost=1.0)
            self.message("user", session=session, content=PROMPT)
            self.message("assistant", session=session, content="Done.", finish_reason="stop")
            games[game] = {"prompt": PROMPT, "log": f"{game}.log", "session": session}
            self.clock += 10000
        record = {"started": 0, "commit": f"{name[-6:]}abcdef0123", "games": games}
        (folder / "run.json").write_text(json.dumps(record), encoding="utf-8")
        return folder

    def compare(self, *argv) -> tuple[int, str, str]:
        output, error = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            code = self.cli.main(["bench", "compare", *argv])
        return code, output.getvalue(), error.getvalue()

    def test_no_game_worse_exits_zero(self):
        after = self.make_run("20261125-094708", {"2-bolt": 300.0, "3-starling": 300.0})
        db = (self.home / "state.db").read_bytes()
        code, output, _ = self.compare("--run", str(after))
        self.assertEqual(code, 0)
        self.assertEqual((self.home / "state.db").read_bytes(), db)  # only read
        lines = output.splitlines()
        self.assertEqual(lines[:3], [
            "run      20261125-094708 (094708a)",
            "against  20261125-023312 (023312a)",
            "only in against: 1-lantern",
        ])  # fmt: skip
        self.assertIn("2-bolt               20261125-023312  20261125-094708  change", lines)
        self.assertIn("wall time            10m00s           5m00s            -5m00s (-50%)", lines)
        self.assertIn("ended normally       yes              yes", lines)
        self.assertEqual(lines[-1], "clearly worse: none")

    def test_a_game_clearly_worse_exits_non_zero(self):
        after = self.make_run("20261125-094708", {"2-bolt": 1200.0, "3-starling": 300.0})
        code, output, _ = self.compare("--run", str(after), "--against", str(self.before))
        self.assertEqual(code, 1)
        self.assertIn("wall time            10m00s           20m00s           +10m00s (+100%)  worse", output)
        self.assertTrue(output.endswith("clearly worse:\n  2-bolt: wall time +10m00s (+100%)\n"))

    def test_a_game_that_stopped_ending_normally(self):
        after = self.make_run("20261125-094708", {"2-bolt": 60.0}, ended="startup_orphan_reap")
        code, output, _ = self.compare("--run", str(after))
        self.assertEqual(code, 1)
        self.assertIn("measures not judged: a chat did not end normally", output)
        self.assertIn("  2-bolt: ended normally yes -> no (startup_orphan_reap)", output)

    def test_runs_that_cannot_be_compared(self):
        after = self.make_run("20261125-094708", {"5-tidepool": 300.0})
        for argv, message in (
            (["--run", str(after)], "no run before 20261125-094708"),
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


if __name__ == "__main__":
    unittest.main()

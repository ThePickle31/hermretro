"""tools/dev/bench.py `run`: it starts the games only when the studio profile loads this checkout and the local
gateway runs that code, reloading it when it does not, then every game at once with the right command, recording each one's session. The
gateway and `hermes` are stand-ins here; nothing reaches a real Hermes."""

import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

TOP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOP / "tools" / "dev"))

import bench  # noqa: E402 - tools/dev, put on the path just above

_spec = importlib.util.spec_from_file_location("dev_cli", TOP / "tools" / "dev" / "__main__.py")
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)


class CurrentGatewayTest(unittest.TestCase):
    """`run` starts only when the studio profile loads this checkout and the gateway runs its code as it is now:
    reloaded when it does not."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.checkout = self.root / "checkout"
        self.checkout.mkdir()
        plugins = self.root / "profiles" / "hermretro" / "plugins"
        plugins.mkdir(parents=True)
        self.link = plugins / "hermretro"
        self.link.symlink_to(self.checkout)
        clean = {key: value for key, value in os.environ.items() if key != bench.REMOTE_GATEWAY}
        self.enterContext(mock.patch.dict(os.environ, clean, clear=True))

    def check(self, answers, reload_result=0):
        reloads = []

        def reload():
            reloads.append(1)
            return reload_result

        with (
            mock.patch.object(bench.hermes, "stale_plugin", side_effect=answers) as stale,
            redirect_stdout(io.StringIO()) as output,
        ):
            try:
                bench.current_gateway(self.root, "hermretro", self.checkout, reload)
            finally:
                self.output = output.getvalue()
        for asked in stale.call_args_list:
            self.assertEqual(asked.args, ("hermretro", self.checkout))
        return len(reloads)

    def test_a_current_gateway_is_left_alone(self):
        self.assertEqual(self.check([None]), 0)

    def test_a_stale_gateway_is_reloaded_and_asked_again(self):
        self.assertEqual(self.check(["/x changed since it loaded", None]), 1)
        self.assertIn("older hermretro code (/x changed since it loaded): reloading", self.output)

    def test_still_stale_after_the_reload_refuses(self):
        with self.assertRaisesRegex(bench.BenchError, "still runs older hermretro code .* restart Hermes"):
            self.check(["old", "old"])

    def test_a_failed_reload_refuses(self):
        with self.assertRaisesRegex(bench.BenchError, "reload failed"):
            self.check(["old"], reload_result=1)

    def test_no_gateway_refuses(self):
        error = bench.hermes.GatewayError("the gateway did not answer plugin.hermretro.status: no gateway")
        with self.assertRaisesRegex(bench.BenchError, "no gateway: the games need a running gateway"):
            self.check(error)

    def test_a_profile_on_another_checkout_refuses_before_asking(self):
        other = self.root / "other"
        other.mkdir()
        self.link.unlink()
        self.link.symlink_to(other)
        with self.assertRaisesRegex(bench.BenchError, f"loads {other}, not {self.checkout}: python tools/dev live"):
            self.check(AssertionError("the gateway is not asked"))
        self.link.unlink()
        with self.assertRaisesRegex(bench.BenchError, "loads no checkout, not .*python tools/dev live"):
            self.check(AssertionError("the gateway is not asked"))

    def test_a_remote_gateway_refuses_before_asking(self):
        with mock.patch.dict(os.environ, {bench.REMOTE_GATEWAY: "wss://elsewhere.example/gateway"}):
            with self.assertRaisesRegex(bench.BenchError, f"{bench.REMOTE_GATEWAY} sends the chats .*: unset it"):
                self.check(AssertionError("the gateway is not asked"))

    def cli(self, *arguments):
        error = io.StringIO()
        with (
            mock.patch.object(cli.shutil, "which", return_value="/bin/tool"),
            mock.patch.object(cli.hermes, "hermes_root", return_value=self.root),
            mock.patch.object(cli, "TOP", self.checkout),
            mock.patch.object(cli.bench.hermes, "stale_plugin", return_value="old") as stale,
            mock.patch.object(cli, "reload_profiles", return_value=0) as reload,
            mock.patch.object(cli.bench, "run") as run,
            redirect_stdout(io.StringIO()),
            redirect_stderr(error),
        ):
            self.assertEqual(cli.main(["bench", "run", *arguments]), 1)
        run.assert_not_called()
        return stale, reload, error.getvalue()

    def test_run_starts_no_game_on_a_gateway_it_cannot_bring_current(self):
        stale, reload, error = self.cli()
        reload.assert_called_once_with(self.root, ["hermretro"])  # every profile that loads hermretro
        self.assertEqual(stale.call_count, 2)
        self.assertIn("still runs older hermretro code (old): restart Hermes", error)

    def test_an_unknown_game_ends_it_before_the_gateway_is_asked(self):
        stale, reload, error = self.cli("no-such-game")
        stale.assert_not_called()
        reload.assert_not_called()
        self.assertIn("no game matches no-such-game", error)


class RunTest(unittest.TestCase):
    """`run` with a stand-in `hermes` on PATH that prints its arguments and a session id, as a quiet chat does."""

    def setUp(self):
        folder = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        self.folder = folder
        bin_ = folder / "bin"
        bin_.mkdir()
        hermes = bin_ / "hermes"
        # Each stand-in waits (up to 10 s) until both have started, so they finish only when run side by side.
        hermes.write_text(
            '#!/bin/sh\necho "$@"\npwd\nprompt="$5"\nname=$(basename "$prompt" .txt)\n'
            'touch "$BENCH_STARTED/$name"\ni=0\n'
            'while [ "$(ls "$BENCH_STARTED" | wc -l)" -lt 2 ] && [ $i -lt 100 ]; do sleep 0.1; i=$((i + 1)); done\n'
            'if [ "$(ls "$BENCH_STARTED" | wc -l)" -lt 2 ]; then echo alone; exit 4; fi\n'
            'if [ "$name" = "2-fails" ]; then echo boom >&2; exit 3; fi\n'
            'echo "Done."\necho\necho "session_id: local-$name"\n',
            encoding="utf-8",
        )
        started = folder / "started"
        started.mkdir()
        hermes.chmod(0o755)
        patcher = mock.patch.dict(
            os.environ, {"PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}", "BENCH_STARTED": str(started)}
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.prompts = []
        for name in ("1-works", "2-fails"):
            prompt = folder / f"{name}.txt"
            prompt.write_text(f"Make {name}.\n", encoding="utf-8")
            self.prompts.append(prompt)

    def test_runs_every_game_at_once_and_records_each_session(self):
        with mock.patch("sys.stdout"):
            folder = bench.run(self.prompts, "hermretro", self.folder / "home", self.folder / "runs", None)
        record = json.loads((folder / "run.json").read_text(encoding="utf-8"))
        works, fails = record["games"]["1-works"], record["games"]["2-fails"]
        self.assertEqual((works["exit"], works["session"]), (0, "local-1-works"))
        self.assertEqual((fails["exit"], fails["session"]), (3, None))
        self.assertEqual(works["prompt"], "Make 1-works.\n")
        self.assertEqual(record["home"], str((self.folder / "home").resolve()))
        self.assertLessEqual(works["started"], works["ended"])
        log = (folder / "1-works.log").read_text(encoding="utf-8").splitlines()
        prompt = self.prompts[0]
        self.assertEqual(log[0], f"-p hermretro chat --query-file {prompt} --oneshot -Q --reasoning high")
        self.assertEqual(Path(log[1]).resolve(), folder)  # each chat starts in the run folder
        self.assertIn("boom", (folder / "2-fails.log").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

"""The page's status poll and a first run: cheap to poll, honest about Node and updates, folders that exist."""

import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.broker import client  # noqa: E402 - the repository root goes on sys.path first
from backend.broker import engine  # noqa: E402 - the repository root goes on sys.path first
from backend.broker import lane  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.system import host as host_os  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first
from backend.setup import provision  # noqa: E402 - the repository root goes on sys.path first
from backend.setup import studio_profile  # noqa: E402 - the repository root goes on sys.path first
from backend.setup import studio_providers  # noqa: E402 - the repository root goes on sys.path first
from backend.library import rpcs as library_rpcs  # noqa: E402 - the repository root goes on sys.path first
from backend.setup import rpcs as setup_rpcs  # noqa: E402 - the repository root goes on sys.path first
from tests.support import throwaway_deps, throwaway_profile  # noqa: E402 - the repository root goes on sys.path first

CTX = mock.Mock(get_config=lambda key, default=None: default)
PROXY = {
    "HTTPS_PROXY": "http://proxy.example:3128",
    "no_proxy": "localhost",
    "NODE_EXTRA_CA_CERTS": "/etc/company-ca.pem",
    "SSL_CERT_FILE": "/etc/company-ca.pem",
}


class Home(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name).resolve()
        clean = {k: v for k, v in os.environ.items() if not k.startswith("HERMRETRO_")}
        # A Hermes home of its own too: status's provider sync finds the profiles through Hermes, which would read
        # (and write) an inherited HERMES_HOME's studio profile.
        hermes_home = str(self.base / "hermes")
        for patch in (
            mock.patch.dict(
                os.environ, {**clean, "HERMRETRO_HOME": str(self.base / "hr"), "HERMES_HOME": hermes_home}, clear=True
            ),
            throwaway_profile(self.base),
            throwaway_deps(self.base / "hr"),
            mock.patch.object(hermes_host, "try_connect", lambda _dir: (None, None)),
            # The profile report asks Hermes itself; these tests run without Hermes installed.
            mock.patch.object(studio_profile, "describe", return_value={}),
        ):
            self.enterContext(patch)
        self.sync = self.enterContext(mock.patch.object(studio_providers, "sync_soon"))


class NodeIsAskedOnce(unittest.TestCase):
    def test_two_polls_start_node_once(self):
        provision._platform_of.cache_clear()
        node = {"found": True, "path": sys.executable, "version": "24.0.0", "required": "22", "ok": True}
        answer = subprocess.CompletedProcess([], 0, stdout="linux x64\n", stderr="")
        with (
            mock.patch.object(paths, "find_node", return_value=node),
            mock.patch.object(provision.subprocess, "run", return_value=answer) as run,
        ):
            first, second = provision._node_platform(), provision._node_platform()
        self.assertEqual(first, ("linux", "x64"))
        self.assertEqual(second, first)
        self.assertEqual(run.call_count, 1)
        provision._platform_of.cache_clear()


class NodeArchitecture(unittest.TestCase):
    def report(self, machine, node):
        with (
            mock.patch.object(
                host_os,
                "describe",
                return_value={"system": "darwin", "machine": machine, "rosetta": False, "supported": True},
            ),
            mock.patch.object(provision, "_node_platform", return_value=node),
        ):
            return setup_rpcs._platform_report()

    def test_an_intel_node_on_apple_silicon_is_reported_and_not_qualified(self):
        report = self.report("arm64", ("darwin", "x64"))
        self.assertEqual(report["node_arch"], "x64")
        self.assertFalse(report["qualified"])

    def test_a_matching_or_unknown_node_is_fine(self):
        self.assertTrue(self.report("arm64", ("darwin", "arm64"))["qualified"])
        self.assertTrue(self.report("x64", None)["qualified"])

    def test_apple_silicon_homebrew_is_tried_before_usr_local(self):
        tried = []

        def version(candidate):
            tried.append(candidate)
            return None

        paths._failed_probes.clear()  # every candidate is probed: none is cooling down from an earlier failure
        self.addCleanup(paths._failed_probes.clear)
        with (
            mock.patch.dict(os.environ, {"PATH": ""}),
            mock.patch.object(paths, "_node_stamp", return_value=(0,)),
            mock.patch.object(paths, "_node_version", side_effect=version),
        ):
            paths.find_node()
        self.assertLess(tried.index("/opt/homebrew/bin/node"), tried.index("/usr/local/bin/node"))


class ProxySettingsReachDownloads(unittest.TestCase):
    def test_the_broker_gets_them(self):
        with (
            mock.patch.dict(os.environ, PROXY),
            mock.patch.object(client.subprocess, "Popen") as popen,
            mock.patch.object(client, "own_scope", return_value=[]),
            tempfile.TemporaryDirectory() as run,
        ):
            client.spawn_broker(Path(run), "/usr/bin/node")
        env = popen.call_args.kwargs["env"]
        self.assertEqual({k: env.get(k) for k in PROXY}, PROXY)

    def test_the_engine_gets_them(self):
        # The environment Popen actually receives from the broker's launch, not a helper's return value:
        # checking sanitized_environment() alone stays green if new_engine stops passing its result.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "engine"
            (root / "scripts").mkdir(parents=True)
            (root / "scripts" / "start-mcp.mjs").write_text("", encoding="utf-8")
            # Popen is faked, but the broker still checks that its executable exists.
            broker = mock.Mock(node=sys.executable)
            with (
                mock.patch.dict(os.environ, {**PROXY, "HERMES_GATEWAY_TOKEN": "secret"}),
                mock.patch.object(
                    paths, "select_engine", return_value={"root": root, "prepared": False, "check": {"verified": True}}
                ),
                mock.patch.object(paths, "setup_root", return_value=Path(folder) / "toolchain"),
                mock.patch.object(engine.subprocess, "Popen") as popen,
                mock.patch.object(engine.EngineProcess, "request", return_value={}),
                mock.patch.object(engine.EngineProcess, "notify"),
            ):
                popen.return_value.stdin = io.StringIO()
                popen.return_value.stdout = io.StringIO("")
                popen.return_value.stderr = io.StringIO("")
                lane.LaneMixin.new_engine(broker, "test-client")
        env = popen.call_args.kwargs["env"]
        self.assertEqual({k: env.get(k) for k in PROXY}, PROXY)
        self.assertNotIn("HERMES_GATEWAY_TOKEN", env)
        self.assertEqual(env["CHROMATIC_DEVICE_SKINS"], str(paths.SKINS_DIR), "the engine's device art")

    def test_setup_scripts_get_them(self):
        node = {"found": True, "path": "/usr/bin/node", "version": "24.0.0", "required": "22", "ok": True}
        done = subprocess.CompletedProcess([], 0, stdout="{}", stderr="")
        with (
            mock.patch.dict(os.environ, PROXY),
            mock.patch.object(paths, "find_node", return_value=node),
            mock.patch.object(provision.subprocess, "run", return_value=done) as run,
        ):
            provision._node("process.stdout.write('{}')", cwd=Path("/"))
        env = run.call_args.kwargs["env"]
        self.assertEqual({k: env.get(k) for k in PROXY}, PROXY)


class FreshInstall(Home):
    def test_the_games_folder_exists_once_the_page_asks_for_it(self):
        games = self.base / "hr" / "games"
        self.assertFalse(games.exists())
        answer = library_rpcs.rpc_games(CTX)({})
        self.assertTrue(answer["ok"], answer)
        self.assertEqual(Path(answer["gamesDir"]), games)
        self.assertTrue(games.is_dir())


class UpdatedOnDisk(Home):
    def test_status_says_when_hermes_must_restart(self):
        status = setup_rpcs.rpc_status(CTX)
        self.assertFalse(status({})["restart_needed"])
        self.assertEqual(status({})["plugin"]["root"], str(paths.PLUGIN_ROOT))  # with it, where the code came from
        with mock.patch.object(paths, "code_fingerprint", return_value="changed-on-disk"):
            self.assertTrue(status({})["restart_needed"])
        # Loaded across an engine change: the fingerprint it recorded is the new engine's, its identity the old one.
        with mock.patch.object(paths, "ENGINE_IDENTITY", "2.0.0-loadedbefore0"):
            self.assertTrue(status({})["restart_needed"])

    def test_status_says_which_feature_flags_are_on(self):
        self.assertEqual(setup_rpcs.rpc_status(CTX)({})["flags"], [])
        with mock.patch.dict(os.environ, {"HERMRETRO_FLAGS": "level_editor"}):
            self.assertEqual(setup_rpcs.rpc_status(CTX)({})["flags"], ["level_editor"])

    def test_a_status_that_only_reads_syncs_no_providers(self):
        status = setup_rpcs.rpc_status(CTX)
        looked = status({"sync": False})
        self.assertEqual((looked["plugin"]["root"], looked["restart_needed"]), (str(paths.PLUGIN_ROOT), False))
        self.sync.assert_not_called()
        status({})
        self.sync.assert_called_once_with(self.base / "profile")  # the page's look brings the providers up to date


class ReadOnlyStatus(Home):
    def test_silent_hello_leaves_the_broker_state_unknown(self):
        error = client.BrokerUnavailable("Broker did not answer hello before its deadline")
        with mock.patch.object(hermes_host, "try_connect", return_value=(None, error)):
            status = setup_rpcs.rpc_status(CTX)({})
            activity = setup_rpcs.rpc_activity(CTX)({})
        self.assertTrue(status["ok"])
        self.assertIsNone(status["broker"]["running"])
        self.assertIsNone(status["project"])
        self.assertFalse(activity["ok"])

    def test_lane_status_timeout_preserves_the_rest_of_the_report(self):
        connected = mock.MagicMock()
        connected.request.side_effect = client.BrokerUnavailable("Broker did not answer lane_status")
        with mock.patch.object(hermes_host, "try_connect", return_value=(connected, None)):
            status = setup_rpcs.rpc_status(CTX)({"chat": "chat-a"})
        self.assertTrue(status["ok"])
        self.assertTrue(status["broker"]["running"])
        self.assertIsNone(status["project"])


if __name__ == "__main__":
    unittest.main()

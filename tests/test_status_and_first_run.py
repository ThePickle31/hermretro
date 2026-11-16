"""The page's status poll and a first run: cheap to poll, honest about Node and updates, folders that exist."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from adapter import client, engine, hermes_host, host_os, paths, provision, studio_profile  # noqa: E402
from support import throwaway_deps, throwaway_profile  # noqa: E402

CTX = mock.Mock(get_config=lambda key, default=None: default)
PROXY = {"HTTPS_PROXY": "http://proxy.example:3128", "no_proxy": "localhost",
         "NODE_EXTRA_CA_CERTS": "/etc/company-ca.pem", "SSL_CERT_FILE": "/etc/company-ca.pem"}


class Home(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name).resolve()
        clean = {k: v for k, v in os.environ.items() if not k.startswith("HERMRETRO_")}
        for patch in (mock.patch.dict(os.environ, {**clean, "HERMRETRO_HOME": str(self.base / "hr")}, clear=True),
                      throwaway_profile(self.base), throwaway_deps(self.base / "hr"),
                      mock.patch.object(hermes_host, "try_connect", lambda _dir: (None, None)),
                      # The profile report asks Hermes itself; these tests run without Hermes installed.
                      mock.patch.object(studio_profile, "describe", return_value={})):
            self.enterContext(patch)


class NodeIsAskedOnce(unittest.TestCase):
    def test_two_polls_start_node_once(self):
        provision._platform_of.cache_clear()
        node = {"found": True, "path": sys.executable, "version": "24.0.0", "required": "22", "ok": True}
        answer = subprocess.CompletedProcess([], 0, stdout="linux x64\n", stderr="")
        with mock.patch.object(paths, "find_node", return_value=node), \
                mock.patch.object(provision.subprocess, "run", return_value=answer) as run:
            first, second = provision._node_platform(), provision._node_platform()
        self.assertEqual(first, ("linux", "x64"))
        self.assertEqual(second, first)
        self.assertEqual(run.call_count, 1)
        provision._platform_of.cache_clear()


class NodeArchitecture(unittest.TestCase):
    def report(self, machine, node):
        with mock.patch.object(host_os, "describe", return_value={"system": "darwin", "machine": machine,
                                                                  "rosetta": False, "supported": True}), \
                mock.patch.object(provision, "_node_platform", return_value=node):
            return hermes_host._platform_report()

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

        paths.find_node.cache_clear()
        try:
            with mock.patch.dict(os.environ, {"PATH": ""}), \
                    mock.patch.object(paths.os.path, "isfile", return_value=True), \
                    mock.patch.object(paths.os, "access", return_value=True), \
                    mock.patch.object(paths, "_node_version", side_effect=version):
                paths.find_node()
        finally:
            paths.find_node.cache_clear()
        self.assertLess(tried.index("/opt/homebrew/bin/node"), tried.index("/usr/local/bin/node"))


class ProxySettingsReachDownloads(unittest.TestCase):
    def test_the_broker_gets_them(self):
        with mock.patch.dict(os.environ, PROXY), mock.patch.object(client.subprocess, "Popen") as popen, \
                mock.patch.object(client, "own_scope", return_value=[]), tempfile.TemporaryDirectory() as run:
            client.spawn_broker(Path(run), "/usr/bin/node")
        env = popen.call_args.kwargs["env"]
        self.assertEqual({k: env.get(k) for k in PROXY}, PROXY)

    def test_the_engine_gets_them(self):
        for key in PROXY:
            self.assertIn(key, engine._PASSTHROUGH)

    def test_setup_scripts_get_them(self):
        node = {"found": True, "path": "/usr/bin/node", "version": "24.0.0", "required": "22", "ok": True}
        done = subprocess.CompletedProcess([], 0, stdout="{}", stderr="")
        with mock.patch.dict(os.environ, PROXY), mock.patch.object(paths, "find_node", return_value=node), \
                mock.patch.object(provision.subprocess, "run", return_value=done) as run:
            provision._node("process.stdout.write('{}')", cwd=Path("/"))
        env = run.call_args.kwargs["env"]
        self.assertEqual({k: env.get(k) for k in PROXY}, PROXY)


class FreshInstall(Home):
    def test_the_games_folder_exists_once_the_page_asks_for_it(self):
        games = self.base / "hr" / "games"
        self.assertFalse(games.exists())
        answer = hermes_host.rpc_games(CTX)({})
        self.assertTrue(answer["ok"], answer)
        self.assertEqual(Path(answer["gamesDir"]), games)
        self.assertTrue(games.is_dir())


class UpdatedOnDisk(Home):
    def test_status_says_when_hermes_must_restart(self):
        status = hermes_host.rpc_status(CTX)
        self.assertFalse(status({})["restart_needed"])
        with mock.patch.object(paths, "code_fingerprint", return_value="changed-on-disk"):
            self.assertTrue(status({})["restart_needed"])


if __name__ == "__main__":
    unittest.main()

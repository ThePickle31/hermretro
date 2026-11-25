"""tools/dev/local_hermes.py: the profile links `live` moves, Hermes Desktop's copy of the page, the gateway's
control socket `reload` talks to (a stand-in gateway here), and the plugin RPC `bench run` asks which code the gateway
runs."""

import importlib.util
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

TOP = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("local_hermes", TOP / "tools" / "dev" / "local_hermes.py")
local_hermes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(local_hermes)


class FakeGateway:
    """A control socket that answers one request with ``answer`` and keeps the request it read."""

    def __init__(self, path: Path, answer: dict):
        self.request = None
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(str(path))
        self.listener.listen(1)
        self.thread = threading.Thread(target=self.serve, args=(answer,), daemon=True)
        self.thread.start()

    def serve(self, answer):
        connection, _ = self.listener.accept()
        with connection:
            data = b""
            while b"\n" not in data:
                data += connection.recv(65536)
            self.request = json.loads(data)
            connection.sendall(json.dumps(answer).encode() + b"\n")

    def close(self):
        self.thread.join(5)
        self.listener.close()


class HermesHomeTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.root = self.base / "hermes"
        self.main, self.worktree = self.base / "main", self.base / "worktree"
        for checkout in (self.main, self.worktree):
            (checkout / "desktop").mkdir(parents=True)
            (checkout / "desktop" / "plugin.js").write_text(f"// {checkout.name}\n")
        for profile in ("hermretro", "maker", "other"):
            (self.root / "profiles" / profile / "plugins").mkdir(parents=True)
        (self.root / "profiles" / "hermretro" / "plugins" / "hermretro").symlink_to(self.main)
        (self.root / "profiles" / "maker" / "plugins" / "hermretro").mkdir()  # an installed copy

    def test_links_are_only_the_symlinked_profiles(self):
        self.assertEqual(list(local_hermes.plugin_links(self.root)), ["hermretro"])
        self.assertEqual(local_hermes.loading_profiles(self.root), ["hermretro", "maker"])
        self.assertEqual(local_hermes.live_checkout(self.root), self.main)

    def test_point_moves_the_link_once(self):
        link = self.root / "profiles" / "hermretro" / "plugins" / "hermretro"
        self.assertTrue(local_hermes.point(link, self.worktree))
        self.assertEqual(local_hermes.live_checkout(self.root), self.worktree)
        self.assertFalse(local_hermes.point(link, self.worktree))
        self.assertEqual(sorted(path.name for path in link.parent.iterdir()), ["hermretro"])

    def test_is_checkout_wants_hermretro_with_its_entry_point_and_page(self):
        self.assertFalse(local_hermes.is_checkout(self.main))
        (self.main / "__init__.py").write_text("")
        (self.main / "plugin.yaml").write_text("name: other-plugin\n")
        self.assertFalse(local_hermes.is_checkout(self.main))
        (self.main / "plugin.yaml").write_text("name: hermretro\nversion: 0.0.1\n")
        self.assertTrue(local_hermes.is_checkout(self.main))

    def desktop_copy(self, marker: dict | None) -> Path:
        copy = self.root / "desktop-plugins" / "hermretro" / "plugin.js"
        copy.parent.mkdir(parents=True)
        copy.write_text("// main\n")
        if marker is not None:
            (copy.parent / ".hermes-package.json").write_text(json.dumps(marker))
        return copy

    def test_refresh_desktop_copies_only_a_changed_bundle_into_desktops_linked_copy(self):
        self.assertFalse(local_hermes.refresh_desktop(self.root, self.worktree), "no Desktop copy to refresh")
        copy = self.desktop_copy({"package": "hermretro", "source": str(self.main / "desktop"), "linked": True})
        self.assertTrue(local_hermes.refresh_desktop(self.root, self.worktree))
        self.assertEqual(copy.read_text(), "// worktree\n")
        self.assertFalse(local_hermes.refresh_desktop(self.root, self.worktree))
        self.assertEqual(sorted(path.name for path in copy.parent.iterdir()), [".hermes-package.json", "plugin.js"])

    def test_refresh_desktop_leaves_a_page_desktop_did_not_link_alone(self):
        for marker in (None, {"package": "hermretro", "linked": False}, {"package": "other", "linked": True}):
            with self.subTest(marker=marker):
                copy = self.desktop_copy(marker)
                self.assertFalse(local_hermes.refresh_desktop(self.root, self.worktree))
                self.assertEqual(copy.read_text(), "// main\n")
                shutil.rmtree(copy.parent)

    def test_refresh_desktop_never_writes_through_a_linked_folder(self):
        (self.root / "desktop-plugins").mkdir(parents=True)
        (self.main / "desktop" / ".hermes-package.json").write_text(
            json.dumps({"package": "hermretro", "linked": True})
        )
        (self.root / "desktop-plugins" / "hermretro").symlink_to(self.main / "desktop")
        self.assertFalse(local_hermes.refresh_desktop(self.root, self.worktree))
        self.assertEqual((self.main / "desktop" / "plugin.js").read_text(), "// main\n")


class ReloadTest(HermesHomeTest):
    def setUp(self):
        super().setUp()
        # A socket path must fit in about 100 bytes: the gateway's own socket lives in a short folder of its own.
        self.sockets = Path(tempfile.mkdtemp(prefix="hrd-", dir="/tmp"))
        self.addCleanup(shutil.rmtree, self.sockets, ignore_errors=True)
        self.root.mkdir(exist_ok=True)

    def gateway(self, answer: dict) -> FakeGateway:
        path = self.sockets / "control.sock"
        (self.root / "gateway.sock.path").write_text(str(path))
        fake = FakeGateway(path, answer)
        self.addCleanup(fake.close)
        return fake

    def test_reload_asks_the_gateway_to_reload_the_profiles_home(self):
        fake = self.gateway({"ok": True, "result": {"reloaded": True, "plugins": ["hermretro"], "activations": []}})
        result = local_hermes.reload(self.root, "hermretro")
        self.assertEqual(result["plugins"], ["hermretro"])
        fake.close()
        home = str(self.root / "profiles" / "hermretro")
        self.assertEqual(fake.request, {"verb": "reload-plugins", "id": 1, "protocol": 1, "params": {"home": home}})

    def test_a_refused_or_failed_reload_is_an_error(self):
        self.gateway({"ok": False, "error": "unknown verb: 'reload-plugins'"})
        with self.assertRaisesRegex(local_hermes.GatewayError, "unknown verb"):
            local_hermes.reload(self.root, "hermretro")

    def test_a_reload_the_gateway_did_not_do_is_an_error(self):
        self.gateway({"ok": True, "result": {"reloaded": False, "error": "home is not served by this gateway"}})
        with self.assertRaisesRegex(local_hermes.GatewayError, "not served"):
            local_hermes.reload(self.root, "hermretro")

    def test_no_gateway_and_no_profile_are_errors(self):
        with self.assertRaisesRegex(local_hermes.GatewayError, "no gateway is running"):
            local_hermes.reload(self.root, "hermretro")
        with self.assertRaisesRegex(local_hermes.GatewayError, "no profile"):
            local_hermes.reload(self.root, "missing")


class RootTest(unittest.TestCase):
    """The Hermes root the development loop and the benchmark use (the chats write there): Hermes's rule."""

    def test_hermes_home(self):
        native = Path.home() / ".hermes"
        for configured, root in (
            ("", native),
            (str(native / "profiles" / "hermretro"), native),
            ("/srv/hermes", Path("/srv/hermes")),
            ("/srv/hermes/profiles/hermretro", Path("/srv/hermes")),
        ):
            with mock.patch.dict(os.environ, {"HERMES_HOME": configured}):
                self.assertEqual(local_hermes.hermes_root(), root, configured)


class StalePluginTest(unittest.TestCase):
    """What the plugin's status says about the code the gateway runs, against the checkout `bench run` runs."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.checkout = Path(temp.name).resolve() / "checkout"
        self.checkout.mkdir()

    def stale(self, status):
        with mock.patch.object(local_hermes, "plugin_rpc", return_value=status) as rpc:
            found = local_hermes.stale_plugin("hermretro", self.checkout)
        rpc.assert_called_once_with("hermretro", "status", {"sync": False})  # a status that only reads
        return found

    def test_the_loaded_folder_and_its_files(self):
        self.assertIsNone(self.stale({"plugin": {"root": str(self.checkout)}, "restart_needed": False}))
        changed = self.stale({"plugin": {"root": str(self.checkout)}, "restart_needed": True})
        self.assertEqual(changed, f"{self.checkout} changed since it loaded")
        elsewhere = self.stale({"plugin": {"root": "/old/checkout"}, "restart_needed": False})
        self.assertEqual(elsewhere, f"it loaded /old/checkout, not {self.checkout}")
        self.assertIn("predates", self.stale({"plugin": {"version": "1.0.0"}, "restart_needed": False}))


class PluginRpcTest(unittest.TestCase):
    """The RPC goes through tools/debug/gateway_rpc.mjs, whose last line is the answer."""

    def answer(self, stdout, stderr=""):
        done = subprocess.CompletedProcess([], 0, stdout, stderr)
        with mock.patch.object(local_hermes.subprocess, "run", return_value=done) as run:
            result = local_hermes.plugin_rpc("hermretro", "status")
        command = run.call_args.args[0]
        self.assertEqual(command[0], "node")
        self.assertEqual(command[2:], ["hermretro", "plugin.hermretro.status", "{}"])
        self.assertEqual(run.call_args.kwargs["env"]["GATEWAY_RPC_FULL"], "1")
        return result

    def test_the_result(self):
        line = json.dumps({"profile": "hermretro", "result": {"ok": True, "restart_needed": False}})
        self.assertEqual(self.answer(f"noise\n{line}\n"), {"ok": True, "restart_needed": False})

    def test_no_gateway_or_a_failed_call(self):
        for stdout, said in (
            (json.dumps({"profile": "hermretro", "error": "no gateway: not running"}), "no gateway: not running"),
            (json.dumps({"result": {"ok": False, "error": "boom"}}), "boom"),
            ("", "no answer"),
        ):
            with self.assertRaisesRegex(local_hermes.GatewayError, said):
                self.answer(stdout)


if __name__ == "__main__":
    unittest.main()

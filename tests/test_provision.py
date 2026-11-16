"""Offline checks of the device-CLI installer's refusals. No network, no vendor binary."""
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from adapter import paths, provision  # noqa: E402
from support import throwaway_deps  # noqa: E402


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class ProvisionTests(unittest.TestCase):
    def test_dependencies_live_in_the_hermretro_home_never_the_plugin_folder(self):
        # Plugin updates and removal replace the plugin folder (and refuse one holding a 2 GB toolchain).
        if os.environ.get("HERMRETRO_DEPS_ROOT") or os.environ.get("GB_STUDIO_SETUP_ROOT"):
            self.skipTest("location overridden by the environment")
        cache = paths.hermretro_home().resolve() / ".cache"
        self.assertEqual(paths.DEPS_ROOT, cache)
        self.assertEqual(paths.setup_root(), cache / "toolchain")
        self.assertEqual(paths.PREPARED_ENGINE, cache / f"engine-{paths.ENGINE_VERSION}")
        for folder in (paths.DEPS_ROOT, paths.setup_root(), paths.PREPARED_ENGINE):
            self.assertFalse(folder.is_relative_to(paths.PLUGIN_ROOT), folder)

    def test_install_needs_recorded_agreement_to_vendor_terms(self):
        called = []
        with self.assertRaises(provision.ProvisionError) as caught:
            provision.install_device_cli(False, opener=lambda *a, **k: called.append(a))
        self.assertEqual(caught.exception.code, "TERMS_NOT_ACCEPTED")
        self.assertEqual(called, [], "nothing may be downloaded without agreement")

    def test_pins_point_at_modretro_on_the_npm_registry(self):
        for target in provision._RUST_TARGETS:
            pins = provision._pins(target)
            self.assertTrue(pins["package"]["url"].startswith("https://registry.npmjs.org/@modretro/chromatic-cli-"))
            self.assertEqual(len(pins["executable"]["sha256"]), 64)
            self.assertTrue(pins["executable"]["path"].startswith(target + "/bin/chromatic-cli"))

    def test_a_download_that_does_not_match_its_pin_installs_nothing(self):
        host = provision.host_target()
        if host["target"] is None:
            self.skipTest(host["reason"])
        size = provision._pins(host["target"])["package"]["bytes"]
        with tempfile.TemporaryDirectory() as scratch, throwaway_deps(Path(scratch)):
            before = paths.PREPARED_ENGINE.exists(), provision.read_receipt()
            with self.assertRaises(provision.ProvisionError) as caught:
                provision.install_device_cli(True, opener=lambda *a, **k: _Response(b"\0" * size))
            self.assertEqual(caught.exception.code, "CHECKSUM_MISMATCH")
            self.assertEqual(before, (paths.PREPARED_ENGINE.exists(), provision.read_receipt()))
            self.assertEqual(list(paths.DEPS_ROOT.glob("engine.staging-*")), [])

    def test_cache_reuse_never_touches_an_existing_toolchain_or_a_foreign_folder(self):
        if os.environ.get("GB_STUDIO_SETUP_ROOT"):
            self.skipTest("location overridden by the environment")
        with tempfile.TemporaryDirectory() as scratch, throwaway_deps(Path(scratch) / "hr"):
            foreign = Path(scratch) / "not-a-setup-root"
            (foreign / "downloads").mkdir(parents=True)
            answer = provision.seed_toolchain_cache(foreign)
            self.assertFalse(answer["seeded"])
            self.assertEqual(sorted(p.name for p in foreign.iterdir()), ["downloads"])
            self.assertEqual(list(paths.DEPS_ROOT.glob("toolchain.seeding-*")), [])

    @unittest.skipIf(os.name == "nt", "POSIX launcher script")
    def test_node_is_found_in_hermes_own_tools_without_path(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as scratch:
            node = Path(scratch) / ".hermes" / "tools" / "node-99.1.2-linux-x64" / "bin" / "node"
            node.parent.mkdir(parents=True)
            node.write_text("#!/bin/sh\necho v99.1.2\n")
            node.chmod(0o755)
            environment = {"HOME": scratch, "PATH": "", "GB_STUDIO_SETUP_ROOT": str(Path(scratch) / "setup")}
            paths.find_node.cache_clear()
            try:
                with mock.patch.dict(os.environ, environment), mock.patch.dict(os.environ, {"HERMRETRO_NODE": ""}):
                    found = paths.find_node()
            finally:
                paths.find_node.cache_clear()
            self.assertEqual((found["path"], found["version"], found["ok"]), (str(node), "99.1.2", True))


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        from adapter import hermes_host

        class Ctx:
            def get_config(self, key, default=None):
                return default  # hardware off: the install must be gated regardless
        self.hook = hermes_host.make_pre_tool_call(Ctx())

    def test_installing_the_vendor_cli_always_asks_the_person(self):
        if provision.host_target()["target"] is None:
            self.skipTest("no vendor CLI for this host")
        answer = self.hook(tool_name="chromatic_studio_device_cli",
                           args={"action": "install", "acceptVendorTerms": True})
        self.assertEqual(answer["action"], "approve")
        self.assertIn("registry.npmjs.org/@modretro/", answer["message"])
        self.assertIn(provision.VENDOR_TERMS_URL, answer["message"])
        self.assertTrue(answer["rule_key"].startswith("hermretro:device-cli-install:"))

    def test_status_and_other_tools_are_not_interrupted(self):
        self.assertIsNone(self.hook(tool_name="chromatic_studio_device_cli", args={"action": "status"}))
        self.assertIsNone(self.hook(tool_name="chromatic_rom_build", args={}))


if __name__ == "__main__":
    unittest.main()

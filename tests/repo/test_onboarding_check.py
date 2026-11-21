"""The clean install's onboarding judgements (tools/ci/onboarding_check.py): what counts as a finished studio profile
after the page's calls on a real gateway, and which gateway it may stop. The real gateway run is the clean install
itself (python tools/ci/clean_install_check.py); these pin the decisions on recorded answers."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "ci"))

import onboarding_check  # noqa: E402 - tools/ci goes on sys.path first

TOOLS = len(onboarding_check.declared_tools())


def answers(**changes) -> dict:
    found = {
        "before": {"profile": {"is_studio": False, "studio": {"exists": False}}},
        "created": {"ok": True},
        "finished": {"ok": True, "plugin": "linked"},
        "after": {"profile": {"studio": {"exists": True, "installed": True, "ours": True}}},
        "toolsets": [{"name": "chromatic", "enabled": True, "tool_count": TOOLS}],
    }
    found.update(changes)
    return found


class Judge(unittest.TestCase):
    def setUp(self):
        held = tempfile.TemporaryDirectory()
        self.addCleanup(held.cleanup)
        self.root = Path(held.name).resolve() / "hermes-home"
        self.install = self.root / "plugins" / "hermretro"
        self.install.mkdir(parents=True)
        self.studio = self.root / "profiles" / "hermretro"
        (self.studio / "plugins").mkdir(parents=True)
        (self.studio / "workspace").mkdir()
        (self.studio / "SOUL.md").write_text("soul")
        os.symlink(self.install, self.studio / "plugins" / "hermretro", target_is_directory=True)

    def judge(self, found):
        found.setdefault("created", {}).setdefault("path", str(self.studio))
        with redirect_stdout(StringIO()):
            return onboarding_check.judge(found, self.root)

    def test_a_finished_profile_linking_the_one_install_passes(self):
        self.assertEqual(self.judge(answers()), [])

    def test_each_unfinished_answer_is_a_problem_with_a_fix(self):
        cases = {
            "studio before": answers(before={"profile": {"studio": {"exists": True}}}),
            "create refused": answers(created={"ok": False}),
            "copied": answers(finished={"ok": True, "plugin": "own copy"}),
            "not installed": answers(after={"profile": {"studio": {"exists": True, "installed": False, "ours": True}}}),
            "no tools": answers(toolsets=[{"name": "chromatic", "enabled": False, "tool_count": TOOLS}]),
            "missing toolset": answers(toolsets=[]),
            "wrong count": answers(toolsets=[{"name": "chromatic", "enabled": True, "tool_count": TOOLS - 1}]),
        }
        for name, found in cases.items():
            with self.subTest(name):
                problems = self.judge(found)
                self.assertEqual(len(problems), 1, problems)
                self.assertIn("FIX:", problems[0])

    def test_a_second_install_instead_of_the_link_is_a_problem(self):
        link = self.studio / "plugins" / "hermretro"
        link.unlink()
        link.mkdir()
        (link / "plugin.yaml").write_text("name: hermretro\n")
        problems = self.judge(answers())
        self.assertEqual(len(problems), 1)
        self.assertIn("is not a link to the one install", problems[0])

    def test_a_profile_created_somewhere_else_is_a_problem(self):
        problems = self.judge(answers(created={"ok": True, "path": str(self.root / "profiles" / "other")}))
        self.assertEqual(len(problems), 1)

    def test_a_hermes_without_profiles_describe_is_judged_on_the_rest(self):
        found = answers(describe_error="GatewayRPCError: unknown method")
        found["toolsets"] = None
        self.assertEqual(self.judge(found), [])

    def test_the_declared_tools_are_plugin_yamls_list(self):
        self.assertGreater(TOOLS, 0)
        self.assertTrue(all(name.startswith("chromatic_") for name in onboarding_check.declared_tools()))


class StopGateway(unittest.TestCase):
    def setUp(self):
        held = tempfile.TemporaryDirectory()
        self.addCleanup(held.cleanup)
        self.root = Path(held.name).resolve()
        self.child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        self.addCleanup(self.child.wait)
        self.addCleanup(self.child.kill)

    def record(self, home):
        (self.root / "gateway.pid").write_text(json.dumps({"pid": self.child.pid, "hermes_home": str(home)}))

    def test_the_gateway_of_this_home_is_stopped(self):
        self.record(self.root)
        # The child is ours, so it stays a zombie until reaped: _alive must count that as gone.
        self.assertEqual(onboarding_check.stop_gateway(self.root), "stopped")
        self.assertIsNotNone(self.child.wait(timeout=5))

    def test_a_record_naming_another_home_or_none_is_left_alone(self):
        self.record(self.root / "elsewhere")
        self.assertTrue(onboarding_check.stop_gateway(self.root).startswith("left alone"))
        (self.root / "gateway.pid").unlink()
        self.assertEqual(onboarding_check.stop_gateway(self.root), "not recorded")
        self.assertIsNone(self.child.poll())


class HermesOnPath(unittest.TestCase):
    def test_the_hermes_under_test_comes_first_on_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(onboarding_check.hermes_on_path(Path(tmp), None), {})
            env = onboarding_check.hermes_on_path(Path(tmp), "/opt/hermes python/bin/python")
            launcher = Path(tmp) / "bin" / "hermes"
            self.assertTrue(env["PATH"].startswith(str(launcher.parent) + os.pathsep))
            self.assertIn("'/opt/hermes python/bin/python' -I -m hermes_cli.main", launcher.read_text())
            self.assertTrue(os.access(launcher, os.X_OK))


if __name__ == "__main__":
    unittest.main()

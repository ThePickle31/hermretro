"""The clean install's onboarding (tools/ci/onboarding_check.py): what counts as a finished studio profile after the
page's calls on a real gateway, which answers stop it before it creates anything, which gateway errors may be
skipped, where `--inside` may run, how the gateway child is stopped, and what environment the throwaway Hermes gets.
The real gateway run is the clean install itself (python tools/ci/clean_install_check.py); these pin the decisions
on recorded answers and on a scripted stand-in for Hermes's gateway client."""

import asyncio
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "ci"))

import clean_install_check  # noqa: E402 - tools/ci goes on sys.path first
import onboarding_check  # noqa: E402 - the repository root goes on sys.path first

TOOLS = len(onboarding_check.declared_tools())
BEFORE = {
    "ok": True,
    "profile": {"is_studio": False, "studio": {"exists": False, "installed": False}, "create": {"name": "hermretro"}},
}


def answers(root: Path, **changes) -> dict:
    studio = root / "profiles" / "hermretro"
    found = {
        "before": BEFORE,
        "created": {"ok": True, "path": str(studio)},
        "finished": {"ok": True, "plugin": "linked"},
        "after": {"profile": {"studio": {"exists": True, "installed": True, "ours": True}}},
        "profiles": {"profiles": [{"name": "default", "path": str(root)}, {"name": "hermretro", "path": str(studio)}]},
        "toolsets": [{"name": "chromatic", "enabled": True, "tool_count": TOOLS}],
        "studio_endpoint": str(studio),
        "studio_status": {"ok": True, "profile": {"is_studio": True, "name": "hermretro"}},
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
        with redirect_stdout(StringIO()):
            return onboarding_check.judge(found, self.root)

    def test_a_finished_profile_linking_the_one_install_passes(self):
        self.assertEqual(self.judge(answers(self.root)), [])

    def test_each_unfinished_answer_is_one_problem_with_a_fix(self):
        studio = {"exists": True, "installed": False, "ours": True}
        cases = {
            "studio before": {"before": {**BEFORE, "profile": {**BEFORE["profile"], "studio": {"exists": True}}}},
            "create refused": {"created": {"ok": False}},
            "created elsewhere": {"created": {"ok": True, "path": str(self.root / "profiles" / "other")}},
            "copied": {"finished": {"ok": True, "plugin": "own copy"}},
            "not installed": {"after": {"profile": {"studio": studio}}},
            "no tools": {"toolsets": [{"name": "chromatic", "enabled": False, "tool_count": TOOLS}]},
            "missing toolset": {"toolsets": []},
            "wrong count": {"toolsets": [{"name": "chromatic", "enabled": True, "tool_count": TOOLS - 1}]},
            "describe without toolsets": {"toolsets": None},
            "not listed": {"profiles": {"profiles": [{"name": "default", "path": str(self.root)}]}},
            "listed elsewhere": {"profiles": {"profiles": [{"name": "hermretro", "path": str(self.root)}]}},
            "default route": {"studio_endpoint": str(self.root)},
            "no route": {"studio_endpoint": None},
            "route not studio": {"studio_status": {"ok": True, "profile": {"is_studio": False, "name": "hermretro"}}},
            "route refused": {"studio_status": {"ok": False, "error": "not loaded"}},
        }
        for name, change in cases.items():
            with self.subTest(name):
                problems = self.judge(answers(self.root, **change))
                self.assertEqual(len(problems), 1, problems)
                self.assertIn("FIX:", problems[0])

    def test_a_missing_describe_answer_fails_and_only_method_not_found_is_skipped(self):
        found = answers(self.root)
        del found["toolsets"]
        self.assertEqual(len(self.judge(found)), 1)
        self.assertEqual(self.judge({**found, "describe_unavailable": "unknown_method (-32601)"}), [])

    def test_a_second_install_instead_of_the_link_is_a_problem(self):
        link = self.studio / "plugins" / "hermretro"
        link.unlink()
        link.mkdir()
        (link / "plugin.yaml").write_text("name: hermretro\n")
        problems = self.judge(answers(self.root))
        self.assertEqual(len(problems), 1)
        self.assertIn("is not a link to the one install", problems[0])

    def test_the_declared_tools_are_plugin_yamls_list(self):
        self.assertGreater(TOOLS, 0)
        self.assertTrue(all(name.startswith("chromatic_") for name in onboarding_check.declared_tools()))


class InitialStatus(unittest.TestCase):
    def test_only_a_status_that_offers_setup_passes(self):
        self.assertIsNone(onboarding_check.initial_refusal(BEFORE))
        profile = BEFORE["profile"]
        refused = {
            "not ok": {**BEFORE, "ok": None},
            "studio": {**BEFORE, "profile": {**profile, "is_studio": True}},
            "is_studio unknown": {**BEFORE, "profile": {k: v for k, v in profile.items() if k != "is_studio"}},
            "installed without exists": {
                **BEFORE,
                "profile": {**profile, "studio": {"exists": False, "installed": True}},
            },
            "exists unknown": {**BEFORE, "profile": {**profile, "studio": {"installed": False}}},
            "no create params": {**BEFORE, "profile": {k: v for k, v in profile.items() if k != "create"}},
            "not a dict": None,
        }
        for name, status in refused.items():
            with self.subTest(name):
                self.assertIn("FIX:", onboarding_check.initial_refusal(status) or "")


class GatewayRPCError(Exception):  # the shape of hermes_cli.gateway_client.GatewayRPCError
    def __init__(self, reason, code=None, data=None):
        super().__init__(reason)
        self.code, self.data = code, data or {}


class PageCalls(unittest.TestCase):
    """_page_calls against a scripted gateway: what it calls, with which deadline, and what stops it."""

    def run_calls(self, phase="default", **script):
        calls = []
        replies = {
            "plugin.hermretro.status": BEFORE,
            "profiles.create": {"ok": True},
            "plugin.hermretro.studio_profile": {"ok": True, "plugin": "linked"},
            "profiles.list": {"profiles": []},
            "profiles.describe": {"toolsets": []},
            **script,
        }

        class Client:
            async def rpc(self, method, *, _timeout=None, **params):
                calls.append((method, _timeout))
                reply = replies[method]
                if isinstance(reply, BaseException):
                    raise reply
                return reply

        class Connection:
            async def __aenter__(self):
                return Client()

            async def __aexit__(self, *exc):
                return False

        endpoint = types.SimpleNamespace(profile_id="/throwaway/studio", control_home="/throwaway")
        discovered = types.SimpleNamespace(state="ready", endpoint=endpoint, reason_code=None)
        client_module = types.ModuleType("hermes_cli.gateway_client")
        client_module.GatewayRPCError = GatewayRPCError
        client_module.connect_gateway = lambda found=None: Connection()
        runtime_module = types.ModuleType("hermes_cli.gateway_runtime")
        runtime_module.discover_gateway_endpoint = lambda home: discovered
        modules = {
            "hermes_cli": types.ModuleType("hermes_cli"),
            "hermes_cli.gateway_client": client_module,
            "hermes_cli.gateway_runtime": runtime_module,
        }
        with mock.patch.dict(sys.modules, modules), mock.patch.dict(os.environ, {"HERMES_HOME": "/throwaway"}):
            try:
                return asyncio.run(onboarding_check._page_calls(phase)), calls
            except SystemExit as stop:
                return {"fatal": str(stop)}, calls

    def test_the_page_order_with_desktops_finish_deadline(self):
        found, calls = self.run_calls()
        self.assertNotIn("fatal", found)
        self.assertEqual(
            [method for method, _ in calls],
            ["plugin.hermretro.status", "profiles.create", "plugin.hermretro.studio_profile", "plugin.hermretro.status"]
            + ["profiles.list", "profiles.describe"],
        )
        self.assertEqual(dict(calls)["plugin.hermretro.studio_profile"], 240)

    def test_desktops_deadline_is_the_pages(self):
        source = (ROOT / "page" / "pages" / "setup" / "install" / "installer.js").read_text(encoding="utf-8")
        deadline = re.search(r"callBackend\(RPC_STUDIO_PROFILE, \{\}, (\d+)_000\)", source)
        self.assertIsNotNone(deadline, "installer.js no longer calls studio_profile with a deadline")
        self.assertEqual(int(deadline.group(1)), onboarding_check.FINISH_TIMEOUT)

    def test_a_status_that_does_not_offer_setup_creates_nothing(self):
        installed = {**BEFORE, "profile": {**BEFORE["profile"], "studio": {"exists": False, "installed": True}}}
        found, calls = self.run_calls(**{"plugin.hermretro.status": installed})
        self.assertIn("offers setup only", found["fatal"])
        self.assertEqual([method for method, _ in calls], ["plugin.hermretro.status"])

    def test_only_method_not_found_skips_profiles_describe(self):
        for error in (GatewayRPCError("request_failed", -32601), GatewayRPCError("unknown_method")):
            found, _ = self.run_calls(**{"profiles.describe": error})
            self.assertIn("describe_unavailable", found)
            self.assertNotIn("fatal", found)
        for error in (GatewayRPCError("internal_error", -32603), GatewayRPCError("permission_denied", 4003)):
            found, _ = self.run_calls(**{"profiles.describe": error})
            self.assertIn("profiles.describe failed", found["fatal"])
        with self.assertRaises(TimeoutError):  # inside() records it as fatal
            self.run_calls(**{"profiles.describe": TimeoutError("no answer")})

    def test_the_studio_phase_asks_the_studio_route_only(self):
        studio = {"ok": True, "profile": {"is_studio": True, "name": "hermretro"}}
        found, calls = self.run_calls("studio", **{"plugin.hermretro.status": studio})
        self.assertEqual(calls, [("plugin.hermretro.status", 120)])
        self.assertEqual(found["studio_endpoint"], "/throwaway/studio")
        self.assertEqual(found["studio_status"], studio)


class InsideRefusal(unittest.TestCase):
    def setUp(self):
        parent = clean_install_check.work_parent(os.environ, Path.home() / ".hermes")  # where the real run goes
        self.base = Path(tempfile.mkdtemp(prefix=clean_install_check.PREFIX, dir=parent)).resolve()
        self.addCleanup(shutil.rmtree, self.base)
        (self.base / "home").mkdir()
        (self.base / "hermes-home" / "profiles" / "hermretro").mkdir(parents=True)

    def env(self, home=None, hermes_home=None):
        return {"HOME": str(home or self.base / "home"), "HERMES_HOME": str(hermes_home or self.base / "hermes-home")}

    def test_only_the_throwaway_layout_is_accepted(self):
        out = self.base / "onboarding-default.json"
        self.assertIsNone(onboarding_check.inside_refusal("default", str(out), self.env()))
        studio_env = self.env(hermes_home=self.base / "hermes-home" / "profiles" / "hermretro")
        self.assertIsNone(
            onboarding_check.inside_refusal("studio", str(self.base / "onboarding-studio.json"), studio_env)
        )
        with tempfile.TemporaryDirectory() as other:
            refused = {
                "real HOME": ("default", out, self.env(home=Path.home())),
                "real HERMES_HOME": ("default", out, self.env(hermes_home=Path.home() / ".hermes")),
                "no HERMES_HOME": ("default", out, {"HOME": str(self.base / "home")}),
                "other phase's home": ("studio", self.base / "onboarding-studio.json", self.env()),
                "unknown phase": ("other", self.base / "onboarding-other.json", self.env()),
                "not throwaway": ("default", Path(other) / "onboarding-default.json", self.env()),
            }
            for name, (phase, target, env) in refused.items():
                with self.subTest(name):
                    self.assertIsNotNone(onboarding_check.inside_refusal(phase, str(target), env))

    def test_a_direct_run_is_refused_before_any_gateway_contact(self):
        out = Path(tempfile.gettempdir()) / "onboarding-default.json"
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(Path.home()), "HERMES_HOME": str(self.base)}
        script = ROOT / "tools" / "ci" / "onboarding_check.py"
        done = subprocess.run(
            [sys.executable, "-I", str(script), "--inside", "default", str(out)],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn("refusing", done.stderr)
        self.assertFalse(out.exists())


class OwnGateway(unittest.TestCase):
    def setUp(self):
        held = tempfile.TemporaryDirectory()
        self.addCleanup(held.cleanup)
        self.tmp = Path(held.name).resolve()
        self.env = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.tmp)}

    def gateway(self, code: str, grace: float = 20):
        return onboarding_check.own_gateway([sys.executable, "-c", code], self.tmp, self.env, self.tmp / "g.log", grace)

    def test_the_child_is_stopped_and_reaped_and_a_pid_file_is_never_read(self):
        bystander = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        self.addCleanup(bystander.wait)
        self.addCleanup(bystander.kill)
        (self.tmp / "gateway.pid").write_text(f'{{"pid": {bystander.pid}, "hermes_home": "{self.tmp}"}}')
        code = "import os, sys, time; print(sys.argv[1:], os.environ['HERMES_HOME'], flush=True); time.sleep(60)"
        with self.gateway(code) as state:
            time.sleep(0.5)
        self.assertEqual(state, {"exited_early": None, "stopped": "stopped"})
        self.assertIn(f"['gateway', 'run'] {self.tmp}", (self.tmp / "g.log").read_text())
        self.assertIsNone(bystander.poll())

    def test_a_child_ignoring_sigterm_is_killed(self):
        code = "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('up', flush=True); time.sleep(60)"
        with self.gateway(code, grace=0.5) as state:
            deadline = time.monotonic() + 10
            while "up" not in (self.tmp / "g.log").read_text() and time.monotonic() < deadline:
                time.sleep(0.05)
        self.assertEqual(state["stopped"], "killed after 0.5 s")


class Environment(unittest.TestCase):
    def test_only_process_basics_and_throwaway_paths_reach_hermes(self):
        outside = {
            "PATH": "/usr/bin",
            "LANG": "C.UTF-8",
            "OPENAI_API_KEY": "sk-secret",
            "ANTHROPIC_API_KEY": "secret",
            "AWS_SECRET_ACCESS_KEY": "secret",
            "GITHUB_TOKEN": "secret",
            "SSH_AUTH_SOCK": "/run/agent",
            "HERMES_HOME": "/real/.hermes",
            "HERMRETRO_HOME": "/real/hermretro",
            "INVOCATION_ID": "unit",
            "PYTHONPATH": "/elsewhere",
            "TMPDIR": "/real/tmp",
        }
        with mock.patch.dict(os.environ, outside, clear=True):
            env = clean_install_check.environment(Path("/t"), Path("/t/hermes-home"), {"HERMRETRO_HOME": "/t/hr"})
        self.assertEqual(
            env,
            {
                "PATH": "/usr/bin",
                "LANG": "C.UTF-8",
                "HOME": "/t/home",
                "HERMES_HOME": "/t/hermes-home",
                "TMPDIR": "/t",
                "HERMRETRO_HOME": "/t/hr",
            },
        )


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

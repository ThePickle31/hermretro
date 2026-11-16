"""The plugin's tools, skills, hooks and prompt exist only in the hermretro profile; the page's RPCs answer
in every profile the plugin is on (the profile it was installed into sets the studio profile up)."""
import importlib.util
import os
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
DECLARED_TOOLS = re.findall(r"^  - (chromatic_\w+)$", (ROOT / "plugin.yaml").read_text(encoding="utf-8"), re.M)


def load_plugin():
    spec = importlib.util.spec_from_file_location("hermretro_registration", ROOT / "__init__.py",
                                                  submodule_search_locations=[str(ROOT)])
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Recorder:
    def __init__(self, profile):
        self.profile_name = profile
        self.calls = {"tool": [], "skill": [], "rpc": [], "hook": [], "section": []}

    def register_tool(self, name, **_kwargs):
        self.calls["tool"].append(name)

    def register_skill(self, name, _path):
        self.calls["skill"].append(name)

    def register_rpc(self, name, _handler):
        self.calls["rpc"].append(name)

    def register_hook(self, name, _handler):
        self.calls["hook"].append(name)

    def register_system_prompt_section(self, name, *_args, **_kwargs):
        self.calls["section"].append(name)


class Registration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()

    def register(self, profile, env=None):
        ctx = Recorder(profile)
        clean = {k: v for k, v in os.environ.items() if k != "HERMRETRO_EVERY_PROFILE"}
        with mock.patch.dict(os.environ, {**clean, **(env or {})}, clear=True):
            self.plugin.register(ctx)
        return ctx.calls

    def test_the_studio_profile_gets_everything(self):
        calls = self.register("hermretro")
        self.assertEqual(len(calls["tool"]), len(DECLARED_TOOLS))
        self.assertIn("chromatic_present_game", calls["tool"])
        self.assertEqual(len(calls["skill"]), len([p for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").is_file()]))
        self.assertEqual(sorted(calls["hook"]), sorted(["pre_tool_call", "subagent_start", "subagent_stop",
                                                        "pre_llm_call", "post_llm_call", "post_tool_call"]))
        self.assertEqual(calls["section"], ["hermretro.guide"])
        self.assertIn("status", calls["rpc"])

    def test_any_other_profile_gets_the_page_rpcs_and_nothing_an_agent_sees(self):
        studio = self.register("hermretro")
        for profile in ("default", "work", "custom", None):
            calls = self.register(profile)
            self.assertEqual(calls["rpc"], studio["rpc"], profile)
            self.assertEqual((calls["tool"], calls["skill"], calls["hook"], calls["section"]), ([], [], [], []), profile)

    def test_plugin_development_can_opt_every_profile_in(self):
        calls = self.register("hermretro-development", {"HERMRETRO_EVERY_PROFILE": "1"})
        self.assertEqual(len(calls["tool"]), len(DECLARED_TOOLS))


if __name__ == "__main__":
    unittest.main()

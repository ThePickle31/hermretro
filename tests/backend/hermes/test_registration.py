"""The plugin's tools, skills, hooks and prompt exist only in the hermretro profile; the page's RPCs answer
in every profile the plugin is on (the profile it was installed into sets the studio profile up)."""
import importlib.util
import os
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
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
    """A fake plugin ctx: ``calls`` by kind, and ``order``, every register_* call in order (for the snapshot in
    tests/repo/test_registration_snapshot.py)."""
    def __init__(self, profile):
        self.profile_name = profile
        self.calls = {"tool": [], "skill": [], "rpc": [], "hook": [], "section": []}
        self.order = []

    def get_config(self, _key, default=None):
        return default

    def _note(self, kind, name, *detail):
        self.calls[kind].append(name)
        self.order.append([kind, name, *detail])

    def register_tool(self, name, toolset=None, emoji=None, handler=None, **_kwargs):
        self._note("tool", name, toolset, emoji, callable(handler))

    def register_skill(self, name, path):
        self._note("skill", name, Path(path).relative_to(ROOT).as_posix())

    def register_rpc(self, name, handler):
        self._note("rpc", name, callable(handler))

    def register_hook(self, name, handler):
        self._note("hook", name, callable(handler))

    def register_system_prompt_section(self, name, _text, **options):
        self._note("section", name, options)


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
        calls = self.register("studio-dev", {"HERMRETRO_EVERY_PROFILE": "1"})
        self.assertEqual(len(calls["tool"]), len(DECLARED_TOOLS))


if __name__ == "__main__":
    unittest.main()

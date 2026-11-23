"""The plugin's tools, skills, hooks and prompt exist only in the hermretro profile; the page's RPCs answer
in every profile the plugin is on (the profile it was installed into sets the studio profile up)."""

import hashlib
import importlib.util
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
DECLARED_TOOLS = re.findall(r"^  - (chromatic_\w+)$", (ROOT / "plugin.yaml").read_text(encoding="utf-8"), re.M)


def load_plugin():
    spec = importlib.util.spec_from_file_location(
        "hermretro_registration", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)]
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Recorder:
    """A fake plugin ctx: ``calls``, the names registered by kind, and ``given``, what each call handed Hermes."""

    def __init__(self, profile):
        self.profile_name = profile
        self.calls = {"tool": [], "skill": [], "rpc": [], "hook": [], "section": []}
        self.given = {kind: [] for kind in self.calls}

    def get_config(self, _key, default=None):
        return default

    def _note(self, kind, name, detail):
        self.calls[kind].append(name)
        self.given[kind].append((name, detail))

    def register_tool(self, name, toolset=None, emoji=None, handler=None, **_kwargs):
        self._note("tool", name, handler)

    def register_skill(self, name, path):
        self._note("skill", name, Path(path))

    def register_rpc(self, name, handler):
        self._note("rpc", name, handler)

    def register_hook(self, name, handler):
        self._note("hook", name, handler)

    def register_system_prompt_section(self, name, text, **options):
        self._note("section", name, (text, options))


class Registration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()

    def setUp(self):
        # The loaded copy's own host module: tests.support's isolated_home patches the repository's, not this one.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.profile_home = Path(tmp.name)
        data = self.profile_home / "plugin-data" / "hermretro"
        patch = mock.patch.object(self.plugin.hermes_host, "_data_dir", lambda: data)
        patch.start()
        self.addCleanup(patch.stop)

    def recorded(self, profile, env=None):
        ctx = Recorder(profile)
        clean = {k: v for k, v in os.environ.items() if k != "HERMRETRO_EVERY_PROFILE"}
        with mock.patch.dict(os.environ, {**clean, **(env or {})}, clear=True):
            self.plugin.register(ctx)
        return ctx

    def register(self, profile, env=None):
        return self.recorded(profile, env).calls

    def test_the_studio_profile_gets_everything(self):
        calls = self.register("hermretro")
        self.assertEqual(len(calls["tool"]), len(DECLARED_TOOLS))
        self.assertIn("chromatic_present_game", calls["tool"])
        self.assertEqual(
            len(calls["skill"]), len([p for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").is_file()])
        )
        # Collection (one name, every callback chained in order) is tested by tests/backend/hermes/test_declare.py.
        self.assertEqual(calls["section"], ["hermretro.guide"])
        self.assertIn("status", calls["rpc"])

    def test_what_hermes_runs_is_usable(self):
        """Hermes stores each handler and calls it later, resolves skill_view by the registered name, runs every hook
        entry it was given, and drops a prompt section longer than its max_chars: each must hold at registration."""
        given = self.recorded("hermretro").given
        for kind in ("tool", "rpc", "hook"):
            broken = [name for name, handler in given[kind] if not callable(handler)]
            self.assertEqual(broken, [], f"{kind}s registered without a callable handler")
        hooks = [name for name, _ in given["hook"]]
        self.assertEqual(sorted(hooks), sorted(set(hooks)), "a hook registered twice runs twice")
        shipped = {
            path.name: path / "SKILL.md" for path in (ROOT / "skills").iterdir() if (path / "SKILL.md").is_file()
        }
        self.assertEqual(dict(given["skill"]), shipped, "each skill under its folder's name, pointing at its SKILL.md")
        for name, (text, options) in given["section"]:
            self.assertLessEqual(len(text), options["max_chars"], f"{name}: Hermes skips a section over max_chars")
            named = set(re.findall(r"hermretro:([\w-]+)", text))
            self.assertTrue(named, f"{name} names the skills to load")
            self.assertLessEqual(named, set(shipped), f"{name} names skills that are not registered")

    def test_any_other_profile_gets_the_page_rpcs_and_nothing_an_agent_sees(self):
        studio = self.register("hermretro")
        for profile in ("default", "work", "custom", None):
            calls = self.register(profile)
            self.assertEqual(calls["rpc"], studio["rpc"], profile)
            self.assertEqual(
                (calls["tool"], calls["skill"], calls["hook"], calls["section"]), ([], [], [], []), profile
            )

    def test_the_studio_profile_gets_this_releases_soul_in_place_of_an_older_one(self):
        soul = self.profile_home / "SOUL.md"
        older = b"the SOUL an earlier release shipped"
        studio = self.plugin.studio_profile
        with mock.patch.object(studio, "OLDER_SOULS", frozenset({hashlib.sha256(older).hexdigest()})):
            soul.write_bytes(older)
            self.register("default")
            self.assertEqual(soul.read_bytes(), older, "only the hermretro profile's own SOUL")
            self.register("hermretro")
            self.assertEqual(soul.read_bytes(), studio.SOUL_FILE.read_bytes())
            soul.write_text("edited by the user")
            self.register("hermretro")
            self.assertEqual(soul.read_text(), "edited by the user")

    def test_registration_goes_on_when_hermes_storage_cannot_be_asked(self):
        def no_storage():
            raise ImportError("no plugins.plugin_storage")

        with mock.patch.object(self.plugin.hermes_host, "_data_dir", no_storage):
            calls = self.register("hermretro")
        self.assertEqual(len(calls["tool"]), len(DECLARED_TOOLS))

    def test_plugin_development_can_opt_every_profile_in(self):
        calls = self.register("studio-dev", {"HERMRETRO_EVERY_PROFILE": "1"})
        self.assertEqual(len(calls["tool"]), len(DECLARED_TOOLS))


if __name__ == "__main__":
    unittest.main()

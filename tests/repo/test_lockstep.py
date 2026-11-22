"""Names that must agree between the backend, the page and the manifest. A failure says which to edit.

Backend features declare what they add in their own folder (backend/hermes/declare.py); registration, counts and
order follow from those declarations. What is left to keep in step by hand:

Adding a plugin tool (2 places + the page): the feature folder (a schema, a handler and its Tool(...) entry, with
step words, in backend/<feature>/tools.py) and plugin.yaml's provides_tools. The page's copy of the step words in
page/pages/build/transcript/step-words.js must match the Tool's step_words (or HIDDEN_STEPS for None).
Adding an RPC (1 place): @rpc("name") in backend/<feature>/rpcs.py; then node tools/bundle/bundle.mjs regenerates
the page's name list page/app/rpc-names.js (RPC_<NAME>, through page/app/rpc.js; checked current here and by the
bundle check).
Adding a hook: @hook(...) in backend/<feature>/hooks.py; a hook name no feature used before also goes under
provides_hooks in plugin.yaml.
Tool and skill counts elsewhere in the tests are derived, not typed.
"""

import codecs
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.features import FEATURES  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import contracts, declare  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first
from tests.backend.hermes.test_registration import Recorder, load_plugin  # noqa: E402 - the repository root goes on sys.path first

# Hermes's own tools that the Build page names in its step list (not plugin tools).
HERMES_TOOLS_WITH_WORDS = {
    "browser_exec",
    "clarify",
    "delegate_task",
    "desktop_preview",
    "execute_code",
    "image_generate",
    "memory",
    "patch",
    "read_file",
    "search_files",
    "session_search",
    "skill_manage",
    "skill_view",
    "skills_list",
    "terminal",
    "todo",
    "tool_call",
    "tool_describe",
    "tool_search",
    "vision_analyze",
    "web_extract",
    "web_search",
    "write_file",
}


def collect():
    return declare.collect("backend", FEATURES)


def set_literal(source: str, name: str) -> set[str]:
    match = re.search(rf"{name} = new Set\(\[([^\]]*)\]\)", source)
    assert match, f"{name} not found in step-words.js"
    return set(re.findall(r"'(\w+)'", match.group(1)))


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def manifest_list(manifest: str, key: str) -> list[str]:
    """Every item of a top-level list in plugin.yaml, which writes each as `  - name`: an item in any other form
    fails here instead of being skipped by a pattern that only matches the usual one."""
    found = re.search(rf"^{key}:\n", manifest, re.M)
    if not found:
        raise AssertionError(f"plugin.yaml has no {key} list")
    items = []
    for line in manifest[found.end() :].splitlines():
        if line and not line.startswith(" "):
            break  # the next top-level key
        if line.strip():
            if not re.fullmatch(r"  - \w+", line):
                raise AssertionError(f"plugin.yaml {key}: {line.strip()!r} is not a plain `  - name` item")
            items.append(line[4:])
    return items


class LockStep(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ctx = Recorder("hermretro")
        load_plugin().register(ctx)
        cls.calls = ctx.calls
        cls.tools = set(ctx.calls["tool"])
        cls.rpcs = set(ctx.calls["rpc"])

    def test_the_page_rpc_names_are_generated_from_the_backend_and_current(self):
        spec = importlib.util.spec_from_file_location("rpc_names", ROOT / "tools" / "bundle" / "rpc_names.py")
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        declared = generator.declared()
        self.assertEqual(
            {name for name, _file in declared},
            self.rpcs,
            "@rpc names read from backend/*/rpcs.py differ from what the plugin registers (an @rpc outside rpcs.py?)",
        )
        self.assertEqual(
            read("page/app/rpc-names.js"),
            generator.render(declared),
            "page/app/rpc-names.js is stale\nFIX: " + generator.FIX,
        )

    def test_the_manifest_declares_exactly_the_tools_and_hooks_registered(self):
        manifest = read("plugin.yaml")
        # Every entry, whatever its form: an unregistered one in the list must fail as much as a missing one.
        listed = manifest_list(manifest, "provides_tools")
        self.assertEqual(set(listed), self.tools, "plugin.yaml provides_tools")
        engine = [schema["name"] for schema in contracts.hermes_schemas()]
        # plugin-owned tools first, then the engine's in pinned order: the registration order Hermes sees.
        self.assertEqual(listed[-len(engine) :], engine, "plugin.yaml's tail is not the engine's pinned order")
        self.assertEqual(len(set(listed)), len(listed), "plugin.yaml names a tool twice")
        self.assertEqual(
            set(manifest_list(manifest, "provides_hooks")), set(self.calls["hook"]), "plugin.yaml provides_hooks"
        )

    def test_a_manifest_entry_in_another_form_is_refused_not_skipped(self):
        for entry in ("- unregistered-tool", '- "unregistered_tool"', "-  spaced", "- name # a note"):
            with self.subTest(entry=entry), self.assertRaises(AssertionError) as caught:
                manifest_list(f"provides_tools:\n  - chromatic_a\n  {entry}\nnext: 1\n", "provides_tools")
            self.assertIn(entry, str(caught.exception))
        self.assertEqual(manifest_list("provides_tools:\n  - a\n\n  - b\nnext:\n  - c\n", "provides_tools"), ["a", "b"])

    def test_every_tool_has_step_words_and_every_step_word_names_a_real_tool(self):
        source = read("page/pages/build/transcript/step-words.js")
        table = source[source.index("const STEP_WORDS = {") :]
        words = set(re.findall(r"^  (\w+): ", table[: table.index("\n}\n")], re.M))
        hidden, build = set_literal(source, "HIDDEN_STEPS"), set_literal(source, "BUILD_STEPS")
        short = {name.removeprefix("chromatic_") for name in self.tools}
        self.assertEqual(short - words - hidden, set(), "tools the Build page has no words for (step-words.js)")
        self.assertEqual(
            (words | hidden | build) - short - HERMES_TOOLS_WITH_WORDS,
            set(),
            "step-words.js names tools that do not exist (renamed?)",
        )
        self.assertEqual(
            HERMES_TOOLS_WITH_WORDS - words - hidden - build, set(), "stale entries in HERMES_TOOLS_WITH_WORDS"
        )

    def test_plugin_tools_declare_the_step_words_the_page_shows(self):
        source = read("page/pages/build/transcript/step-words.js")
        table = source[source.index("const STEP_WORDS = {") :]
        entries = dict(
            re.findall(r"^  (\w+): \[('(?:[^'\\]|\\.)*', '(?:[^'\\]|\\.)*')\],?$", table[: table.index("\n}\n")], re.M)
        )
        hidden = set_literal(source, "HIDDEN_STEPS")
        wrong = []
        for tool in collect().tools:
            if tool.make is not None:
                continue  # the engine's tools: their words live on the page only
            short = tool.name.removeprefix("chromatic_")
            if tool.step_words is None:
                if short not in hidden:
                    wrong.append(f"{tool.name}: step_words=None, so HIDDEN_STEPS must list {short!r}")
                continue
            page = [
                codecs.decode(text, "unicode_escape")
                for text in re.findall(r"'((?:[^'\\]|\\.)*)'", entries.get(short, ""))
            ]
            if page != list(tool.step_words):
                wrong.append(f"{tool.name}: declared {list(tool.step_words)}, step-words.js has {page or 'nothing'}")
        self.assertEqual(
            wrong,
            [],
            "\nA plugin tool's step words are declared with its Tool(...) in "
            "backend/<feature>/tools.py; the page's copy must say the same\nFIX: make "
            "page/pages/build/transcript/step-words.js match the declaration",
        )

    def test_every_tool_name_the_page_uses_exists(self):
        used = set()
        for path in (ROOT / "page").rglob("*.js"):
            used |= set(re.findall(r"chromatic_[a-z_]+", path.read_text(encoding="utf-8")))
        self.assertEqual(used - self.tools, set())

    def test_hermes_is_reached_only_through_hermes_api(self):
        hermes_modules = r"(hermes_cli|hermes_constants|hermes_state|plugins|tools|agent|gateway)\b"
        outside = []
        for source in [*(ROOT / "backend").rglob("*.py"), ROOT / "__init__.py"]:
            if source == ROOT / "backend" / "hermes" / "api.py":
                continue
            for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
                if re.match(rf"\s*(from|import) {hermes_modules}", line):
                    outside.append(f"{source.relative_to(ROOT)}:{number}")
        self.assertEqual(outside, [], "import Hermes only in backend/hermes/api.py (and list the name in USED)")

    def test_the_engine_version_agrees_everywhere(self):
        version = paths.ENGINE_VERSION
        self.assertEqual(json.loads(read("engine/modretro-chromatic/package.json"))["version"], version)
        pins = ROOT / "engine" / "pins"
        self.assertEqual(
            [p.name for p in pins.iterdir() if p.is_dir()], [version], "one pins folder, the engine's version"
        )
        self.assertEqual(
            sorted(p.name for p in (pins / version).iterdir()), ["manifest.json", "schema-reconcile.json", "tools.json"]
        )
        self.assertEqual(json.loads(read(f"engine/pins/{version}/manifest.json"))["package_version"], version)
        self.assertEqual(json.loads(paths.PINNED_TOOLS.read_text())["initialize"]["serverInfo"]["version"], version)
        for skill in sorted(
            re.sub(r"^(modretro-)?chromatic-", "", path.name)
            for path in (ROOT / "engine" / "modretro-chromatic" / "skills").iterdir()
            if path.is_dir()
        ):  # every skill adapted from the engine's, read from the engine's own folders
            self.assertRegex(read(f"skills/{skill}/SKILL.md"), rf"(?m)^version: {re.escape(version)}$", skill)
        notices = read("THIRD_PARTY_NOTICES.md")
        self.assertIn(f"## ModRetro Chromatic Plugin engine {version}", notices)
        mentioned = {
            a or b
            for a, b in re.findall(
                r"engine/pins/([0-9]+\.[0-9]+\.[0-9]+)/|ModRetro's ([0-9]+\.[0-9]+\.[0-9]+)", notices
            )
        }
        self.assertEqual(mentioned, {version}, "engine versions named in THIRD_PARTY_NOTICES.md")


if __name__ == "__main__":
    unittest.main()

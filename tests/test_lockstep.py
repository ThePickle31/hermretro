"""Names that must change together across backend, page, manifest and docs. A failure says which list to edit.

Adding a plugin tool: register it in __init__.py, list it under provides_tools in plugin.yaml, give it step words
in page/pages/build/transcript/step-words.js (or hide it there), and describe it in docs/dev/CONTRACT.md (with the
counts there). Tool and skill counts elsewhere in the tests are derived, not typed.
Adding an RPC: register it in __init__.py, name it in page/app/rpc.js and in the README's RPC list, and
give it a heading or table row in docs/dev/CONTRACT.md or docs/dev/STUDIO-PAGES.md.
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.system import paths  # noqa: E402
from test_registration import Recorder, load_plugin  # noqa: E402

# Registered for older desktop halves and the broker's own use; today's page does not call it.
RPCS_THE_PAGE_DOES_NOT_CALL = {"activity"}
# Hermes's own tools that the Build page names in its step list (not plugin tools).
HERMES_TOOLS_WITH_WORDS = {"browser_exec", "clarify", "delegate_task", "desktop_preview", "execute_code",
                           "image_generate", "memory", "patch", "read_file", "search_files", "session_search",
                           "skill_manage", "skill_view", "skills_list", "terminal", "todo", "tool_call", "tool_describe",
                           "tool_search", "vision_analyze", "web_extract", "web_search", "write_file"}
RPC_HEADING = re.compile(r"^(?:### `(\w+)`|\| `(\w+)` \|)", re.M)


def plugin_owned_tools(registered: set[str]) -> set[str]:
    engine = {f"chromatic_{tool['name']}" for tool in json.loads(paths.PINNED_TOOLS.read_text())["tools"]}
    return registered - engine


def set_literal(source: str, name: str) -> set[str]:
    match = re.search(rf"{name} = new Set\(\[([^\]]*)\]\)", source)
    assert match, f"{name} not found in step-words.js"
    return set(re.findall(r"'(\w+)'", match.group(1)))


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


class LockStep(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ctx = Recorder("hermretro")
        load_plugin().register(ctx)
        cls.calls = ctx.calls
        cls.tools = set(ctx.calls["tool"])
        cls.rpcs = set(ctx.calls["rpc"])

    def test_rpc_names_agree_between_backend_page_readme_and_docs(self):
        page = set(re.findall(r"`plugin\.\$\{ID\}\.(\w+)`", read("page/app/rpc.js")))
        self.assertEqual(page - self.rpcs, set(), "page/app/rpc.js names RPCs the backend does not register")
        self.assertEqual(self.rpcs - page - RPCS_THE_PAGE_DOES_NOT_CALL, set(),
                         "registered RPCs missing from page/app/rpc.js")
        readme = read("README.md")
        start = readme.index("RPCs (`status`")
        end = re.compile(r";\s+see").search(readme, start)
        assert end, "README RPC list must end with '; see …'"
        listed = set(re.findall(r"`(\w+)`", readme[start:end.start()]))
        self.assertEqual(listed, self.rpcs, "the README's RPC list")
        docs = read("docs/dev/CONTRACT.md") + read("docs/dev/STUDIO-PAGES.md")
        documented = {a or b for a, b in RPC_HEADING.findall(docs)}
        self.assertEqual(self.rpcs - documented, set(), "RPCs without a heading or table row in CONTRACT.md or STUDIO-PAGES.md")
        self.assertEqual(documented - self.rpcs, set(), "CONTRACT.md / STUDIO-PAGES.md describe RPCs that no longer exist")

    def test_the_manifest_declares_exactly_the_tools_and_hooks_registered(self):
        manifest = read("plugin.yaml")
        declared = set(re.findall(r"^  - (chromatic_\w+)$", manifest, re.M))
        self.assertEqual(declared, self.tools, "plugin.yaml provides_tools")
        hooks = manifest.split("provides_hooks:")[1].split("provides_tools:")[0]
        self.assertEqual(set(re.findall(r"^  - (\w+)$", hooks, re.M)), set(self.calls["hook"]), "plugin.yaml provides_hooks")

    def test_the_contract_states_the_real_tool_counts(self):
        engine = len(json.loads(paths.PINNED_TOOLS.read_text())["tools"])
        contract = flat(read("docs/dev/CONTRACT.md"))
        owned = plugin_owned_tools(self.tools)
        words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
        self.assertIn(f"{engine} tools, plus {words.get(len(owned), len(owned))}", contract)
        self.assertEqual({name for name in owned if f"`{name}`" not in contract}, set(), "plugin-owned tools CONTRACT omits")
        self.assertIn(f"{len(self.tools)} in total", contract)
        self.assertIn(f"the {len(self.tools)} tools, {len(self.calls['skill'])} skills, {len(self.calls['hook'])} hooks",
                      contract)

    def test_every_tool_has_step_words_and_every_step_word_names_a_real_tool(self):
        source = read("page/pages/build/transcript/step-words.js")
        table = source[source.index("const STEP_WORDS = {"):]
        words = set(re.findall(r"^  (\w+): ", table[:table.index("\n}\n")], re.M))
        hidden, build = set_literal(source, "HIDDEN_STEPS"), set_literal(source, "BUILD_STEPS")
        short = {name.removeprefix("chromatic_") for name in self.tools}
        self.assertEqual(short - words - hidden, set(), "tools the Build page has no words for (step-words.js)")
        self.assertEqual((words | hidden | build) - short - HERMES_TOOLS_WITH_WORDS, set(),
                         "step-words.js names tools that do not exist (renamed?)")
        self.assertEqual(HERMES_TOOLS_WITH_WORDS - words - hidden - build, set(), "stale entries in HERMES_TOOLS_WITH_WORDS")

    def test_every_tool_name_the_page_uses_exists(self):
        used = set()
        for path in (ROOT / "page").rglob("*.js"):
            used |= set(re.findall(r"chromatic_[a-z_]+", path.read_text(encoding="utf-8")))
        self.assertEqual(used - self.tools, set())

    def test_every_environment_variable_the_backend_reads_is_documented(self):
        read_in_code = set()
        for source in [*(ROOT / "backend").rglob("*.py"), ROOT / "__init__.py"]:
            read_in_code |= set(re.findall(r"\b(HERMRETRO_[A-Z_]+)\b", source.read_text(encoding="utf-8")))
        table = set(re.findall(r"^\| `(HERMRETRO_[A-Z_]+)` \|", read("docs/dev/DEBUGGING.md"), re.M))
        self.assertEqual(read_in_code - table, set(), "HERMRETRO_* variables missing from DEBUGGING.md's table")
        self.assertEqual(table - read_in_code, set(), "DEBUGGING.md documents variables nothing reads")

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
        self.assertEqual([p.name for p in pins.iterdir() if p.is_dir()], [version], "one pins folder, the engine's version")
        self.assertEqual(sorted(p.name for p in (pins / version).iterdir()), ["manifest.json", "schema-reconcile.json", "tools.json"])
        self.assertEqual(json.loads(read(f"engine/pins/{version}/manifest.json"))["package_version"], version)
        self.assertEqual(json.loads(paths.PINNED_TOOLS.read_text())["initialize"]["serverInfo"]["version"], version)
        for skill in ("authoring", "deployment", "pixel-art", "rom-debugging", "setup"):   # adapted from the engine's
            self.assertRegex(read(f"skills/{skill}/SKILL.md"), rf"(?m)^version: {re.escape(version)}$", skill)
        notices = read("THIRD_PARTY_NOTICES.md")
        self.assertIn(f"## ModRetro Chromatic Plugin engine {version}", notices)
        mentioned = {a or b for a, b in re.findall(
            r"engine/pins/([0-9]+\.[0-9]+\.[0-9]+)/|ModRetro's ([0-9]+\.[0-9]+\.[0-9]+)", notices)}
        self.assertEqual(mentioned, {version}, "engine versions named in THIRD_PARTY_NOTICES.md")


if __name__ == "__main__":
    unittest.main()

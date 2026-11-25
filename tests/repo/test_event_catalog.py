"""tools/engine/event_catalog.py: the engine's event catalog is generated from GB Studio's own event definitions, the
committed one is complete, and every recipe in the authoring skill's event cookbook fits it. Whether the catalog
matches the toolchain's GB Studio, and whether the recipes build, is checked by the acceptance run (C1, C3), which has
the toolchain."""

import importlib.util
import json
import re
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "authoring" / "references"
sys.path.insert(0, str(ROOT / "tools" / "engine"))
_spec = importlib.util.spec_from_file_location("event_catalog", ROOT / "tools" / "engine" / "event_catalog.py")
event_catalog = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(event_catalog)

STRINGS = {
    "EVENT_PICK": "Pick Something",
    "EVENT_PICK_DESC": "Pick one of several things. Then do more.",
    "EVENT_OLD_PICK": "Old Pick",
    "EVENT_GROUP_MISC": "Miscellaneous",
    "FIELD_ITEMS": "How many items.",
    "FIELD_LOGO": "Text glitches in Logo scenes.",
}
# Shaped like GB Studio's own definitions: l10n labels, a group, repeated keys under different conditions, a
# collapsible section whose condition applies to its fields, a units field, a branch and a scene-type warning.
PICK = """
const l10n = require("../helpers/l10n").default;
const id = "EVENT_PICK";
const groups = ["EVENT_GROUP_MISC"];
const fields = [
  { label: l10n("FIELD_LOGO"), labelVariant: "warning", conditions: [{ sceneType: ["logo"] }] },
  { key: "__section", type: "tabs", defaultValue: "main" },
  { key: "variable", type: "variable", defaultValue: "LAST_VARIABLE" },
  { type: "group", fields: [
    { key: "items", type: "number", min: 2, max: 3, defaultValue: 2, description: l10n("FIELD_ITEMS") },
    { key: "x", type: "value", defaultValue: { type: "number", value: 0 }, unitsField: "units",
      unitsDefault: "tiles", unitsAllowed: ["tiles", "pixels"] },
  ] },
  { key: "option3", type: "textarea", defaultValue: "", conditions: [{ key: "items", gt: 2 }] },
  { key: "option3", type: "textarea", defaultValue: "", conditions: [{ key: "items", eq: 2 }, { key: "last", ne: true }] },
  { key: "__collapseExtra", type: "collapsable", conditions: [{ key: "items", gt: 2 }], fields: [
    { key: "extra", type: "checkbox", defaultValue: true },
  ] },
  { key: "true", type: "events" },
  { key: "layout", type: "select", defaultValue: "menu", options: [["menu", "Menu"], ["dialogue", "Dialogue"]] },
];
module.exports = { id, description: l10n("EVENT_PICK_DESC"), groups, fields, compile: () => {} };
"""
OLD_PICK = """
const id = "EVENT_OLD_PICK";
module.exports = { id, groups: [], fields: [], compile: () => {}, deprecated: true };
"""


def gb_studio(folder: Path, events: dict[str, str]) -> Path:
    (folder / "package.json").write_text('{"name": "gb-studio", "version": "9.9.9"}')
    (folder / "src" / "lang").mkdir(parents=True)
    (folder / "src" / "lang" / "en.json").write_text(json.dumps(STRINGS))
    (folder / "src" / "lib" / "events").mkdir(parents=True)
    for name, source in events.items():
        (folder / "src" / "lib" / "events" / name).write_text(source)
    return folder


class GeneratorTests(unittest.TestCase):
    def generate(self, events: dict[str, str], replacements: dict | None = None) -> dict:
        with tempfile.TemporaryDirectory() as folder, replacement_table(replacements or {}):
            return json.loads(event_catalog.generate(gb_studio(Path(folder), events)))

    def test_an_event_lists_its_args_branches_warnings_and_the_editors_example(self):
        catalog = self.generate({"eventPick.js": PICK})
        self.assertEqual(catalog["gbStudioVersion"], "9.9.9")
        pick = catalog["events"]["EVENT_PICK"]
        self.assertEqual(pick["name"], "Pick Something")
        self.assertEqual(pick["groups"], ["Miscellaneous"])
        self.assertEqual(pick["warnings"], [{"sceneTypes": ["LOGO"], "message": "Text glitches in Logo scenes."}])
        fields = {field["key"]: field for field in pick["fields"]}
        self.assertEqual(list(fields), ["variable", "items", "x", "units", "option3", "extra", "layout"])
        self.assertEqual(fields["variable"]["default"], "<variable>")
        self.assertEqual(
            fields["items"],
            {"key": "items", "type": "number", "default": 2, "min": 2, "max": 3, "description": "How many items."},
        )
        self.assertEqual(fields["units"]["options"], ["tiles", "pixels"])
        self.assertEqual(
            fields["option3"]["whenAny"],
            [[{"key": "items", "gt": 2}], [{"key": "items", "eq": 2}, {"key": "last", "ne": True}]],
        )
        self.assertEqual(fields["extra"]["when"], [{"key": "items", "gt": 2}])
        self.assertEqual(fields["layout"]["options"], ["menu", "dialogue"])
        self.assertEqual(pick["branches"], ["true"])
        self.assertEqual(
            pick["example"],
            {
                "command": "EVENT_PICK",
                "args": {
                    "variable": "<variable>",
                    "items": 2,
                    "x": {"type": "number", "value": 0},
                    "units": "tiles",
                    "option3": "",
                    "layout": "menu",
                },
                "children": {"true": []},
            },
        )

    def test_a_deprecated_event_names_its_replacement(self):
        catalog = self.generate({"eventPick.js": PICK, "eventOldPick.js": OLD_PICK}, {"EVENT_OLD_PICK": "EVENT_PICK"})
        self.assertEqual(catalog["events"]["EVENT_OLD_PICK"]["deprecated"], True)
        self.assertEqual(catalog["events"]["EVENT_OLD_PICK"]["replacement"], "EVENT_PICK")

    def test_a_newly_deprecated_event_stops_the_generator(self):
        with self.assertRaisesRegex(RuntimeError, "EVENT_OLD_PICK is deprecated: add it to REPLACEMENTS"):
            self.generate({"eventPick.js": PICK, "eventOldPick.js": OLD_PICK})

    def test_a_replacement_must_be_a_current_event(self):
        with self.assertRaisesRegex(RuntimeError, "EVENT_OLD_PICK's replacement EVENT_GONE is not a current"):
            self.generate({"eventPick.js": PICK, "eventOldPick.js": OLD_PICK}, {"EVENT_OLD_PICK": "EVENT_GONE"})

    def test_a_definition_needing_another_module_is_named(self):
        source = 'const x = require("../helpers/other"); module.exports = { id: "EVENT_X", fields: [] };'
        with self.assertRaisesRegex(RuntimeError, "eventX.js requires ../helpers/other"):
            self.generate({"eventX.js": source})


@contextmanager
def replacement_table(table: dict):
    """Run a copy of the generator whose REPLACEMENTS table is the test's own (the real one names GB Studio's events)."""
    source = event_catalog.GENERATOR.read_text()
    start = source.index("export const REPLACEMENTS = {")
    end = source.index("};", start) + 2
    saved = event_catalog.GENERATOR
    with tempfile.TemporaryDirectory() as folder:
        copy = Path(folder) / "event_catalog.mjs"
        copy.write_text(source[:start] + f"export const REPLACEMENTS = {json.dumps(table)};" + source[end:])
        event_catalog.GENERATOR = copy
        try:
            yield
        finally:
            event_catalog.GENERATOR = saved


class CommittedCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(event_catalog.CATALOG.read_text())
        self.events = self.catalog["events"]

    def test_every_event_has_args_and_an_example_of_itself(self):
        self.assertGreater(len(self.events), 100)
        for command, entry in self.events.items():
            with self.subTest(command=command):
                self.assertRegex(command, r"^EVENT_[A-Z0-9_]+$")
                self.assertTrue(entry["name"])
                self.assertEqual(entry["example"]["command"], command)
                keys = {field["key"] for field in entry["fields"]}
                self.assertLessEqual(set(entry["example"]["args"]), keys)
                self.assertEqual(set(entry["example"].get("children", {})) - set(entry.get("branches", [])), set())
                self.assertNotIn("LAST_", json.dumps(entry))

    def test_deprecated_events_name_a_current_replacement(self):
        deprecated = {command: entry for command, entry in self.events.items() if entry.get("deprecated")}
        self.assertIn("EVENT_IF_VALUE", deprecated)
        for command, entry in deprecated.items():
            with self.subTest(command=command):
                if "replacement" in entry:
                    self.assertFalse(self.events[entry["replacement"]].get("deprecated"))

    def test_script_values_are_typed_in_examples(self):
        self.assertEqual(
            self.events["EVENT_ACTOR_SET_DIRECTION"]["example"]["args"]["direction"],
            {"type": "direction", "value": "up"},
        )
        self.assertEqual(self.events["EVENT_SWITCH_SCENE"]["example"]["args"]["x"], {"type": "number", "value": 0})

    def test_text_events_warn_about_logo_scenes(self):
        warned = sorted(
            command
            for command, entry in self.events.items()
            if any("LOGO" in warning.get("sceneTypes", []) for warning in entry.get("warnings", []))
        )
        self.assertEqual(warned, ["EVENT_CHOICE", "EVENT_MENU", "EVENT_TEXT", "EVENT_TEXT_DRAW"])


class CookbookTests(unittest.TestCase):
    """Each recipe is a JSON list of current events whose args, values and branches are the ones GB Studio declares."""

    def setUp(self):
        self.events = json.loads(event_catalog.CATALOG.read_text())["events"]

    def check_event(self, event: dict, where: str):
        command = event.get("command")
        self.assertIn(command, self.events, where)
        entry = self.events[command]
        self.assertFalse(entry.get("deprecated"), f"{where}: {command} is deprecated")
        self.assertNotIn("id", event, f"{where}: recipes leave ids to the engine")
        fields = {field["key"]: field for field in entry["fields"]}
        for key, value in event.get("args", {}).items():
            self.assertIn(key, list(fields), f"{where}: {command} has no arg {key}")
            field = fields[key]
            if field["type"] in ("value", "constvalue"):
                self.assertIsInstance(value, dict, f"{where}: {command}.{key} must be a typed ScriptValue")
                self.assertIn("type", value, f"{where}: {command}.{key}")
            if "options" in field:
                for option in value if isinstance(value, list) else [value]:
                    self.assertIn(option, field["options"], f"{where}: {command}.{key}")
        for branch, children in event.get("children", {}).items():
            self.assertIn(branch, entry.get("branches", []), f"{where}: {command} has no branch {branch}")
            for index, child in enumerate(children):
                self.check_event(child, f"{where} > {command}.{branch}[{index}]")

    def test_every_recipe_is_current_events_with_their_declared_args(self):
        text = (SKILL / "event-cookbook.md").read_text()
        recipes = re.findall(r"```json\n(.*?)```", text, re.S)
        self.assertGreaterEqual(len(recipes), 10)
        for number, recipe in enumerate(recipes, 1):
            events = json.loads(recipe)
            self.assertIsInstance(events, list)
            for index, event in enumerate(events):
                self.check_event(event, f"recipe {number}[{index}]")

    def test_the_pages_name_only_real_events(self):
        for page in ("event-cookbook.md", "gb-studio-behaviours.md", "project-authoring.md"):
            for command in set(re.findall(r"\bEVENT_[A-Z0-9_]*[A-Z0-9]", (SKILL / page).read_text())):
                with self.subTest(page=page, command=command):
                    self.assertIn(command, self.events)


if __name__ == "__main__":
    unittest.main()

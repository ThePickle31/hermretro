"""tools/engine/event_catalog.py: the engine's event catalog is generated from GB Studio's own event definitions and
the hand-written guidance in event_guidance.mjs, and the generator stops on anything it cannot describe truthfully.
The committed catalog and the cookbook are checked in test_event_catalog_committed.py; whether the catalog matches
the toolchain's GB Studio is checked by the acceptance run (C1), which has the toolchain."""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
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
# collapsible section whose condition applies to its fields, a units field, branches and a scene-type warning.
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
  { key: "false", type: "events", conditions: [{ key: "__collapseElse", ne: true }, { key: "__disableElse", ne: true }] },
  { key: "layout", type: "select", defaultValue: "menu", options: [["menu", "Menu"], ["dialogue", "Dialogue"]] },
];
const compile = (input, helpers) => {
  const { pickThings } = helpers;
  pickThings(input.true, input.__disableElse ? [] : input.false);
};
module.exports = { id, description: l10n("EVENT_PICK_DESC"), groups, fields, compile };
"""
OLD_PICK = """
const id = "EVENT_OLD_PICK";
module.exports = { id, groups: [], fields: [], compile: () => {}, deprecated: true };
"""
BUILDER = "class ScriptBuilder {\n  pickThings = () => {};\n  // weaponAttack was removed\n}\n"


def definition(event_id: str, fields: str, compile_body: str = "") -> str:
    return (
        f'const id = "{event_id}";\nconst fields = {fields};\n'
        f"module.exports = {{ id, groups: [], fields, compile: (input, helpers) => {{ {compile_body} }} }};\n"
    )


def gb_studio(folder: Path, events: dict[str, str]) -> Path:
    (folder / "package.json").write_text('{"name": "gb-studio", "version": "9.9.9"}')
    (folder / "src" / "lang").mkdir(parents=True)
    (folder / "src" / "lang" / "en.json").write_text(json.dumps(STRINGS))
    (folder / "src" / "lib" / "compiler" / "scriptBuilder").mkdir(parents=True)
    (folder / "src" / "lib" / "compiler" / "scriptBuilder" / "scriptBuilder.ts").write_text(BUILDER)
    (folder / "src" / "lib" / "events").mkdir(parents=True)
    for name, source in events.items():
        (folder / "src" / "lib" / "events" / name).write_text(source)
    return folder


@contextmanager
def generator(guidance: dict | None = None, through_symlink: bool = False):
    """A copy of the generator with the test's own guidance tables (the real ones name GB Studio's events), reached
    through a symlinked folder when asked (macOS's /var and /tmp are symlinks)."""
    tables = {"DEPRECATIONS": {}, "UNAVAILABLE": [], "EXAMPLES": {}, "EDITOR_DEFAULTS": {}, **(guidance or {})}
    saved = event_catalog.GENERATOR
    with tempfile.TemporaryDirectory() as folder:
        real = Path(folder) / "real"
        real.mkdir()
        (real / "event_catalog.mjs").write_text(saved.read_text())
        (real / "event_guidance.mjs").write_text(
            "".join(f"export const {name} = {json.dumps(value)};\n" for name, value in tables.items())
        )
        reached = real
        if through_symlink:
            reached = Path(folder) / "link"
            os.symlink(real, reached)
        event_catalog.GENERATOR = reached / "event_catalog.mjs"
        try:
            yield
        finally:
            event_catalog.GENERATOR = saved


class GeneratorTests(unittest.TestCase):
    def generate(self, events: dict[str, str], guidance: dict | None = None, through_symlink: bool = False) -> dict:
        with tempfile.TemporaryDirectory() as folder, generator(guidance, through_symlink):
            return json.loads(event_catalog.generate(gb_studio(Path(folder), events)))

    def test_an_event_lists_its_args_branches_warnings_and_the_editors_example(self):
        catalog = self.generate({"eventPick.js": PICK})
        self.assertEqual(catalog["gbStudioVersion"], "9.9.9")
        pick = catalog["events"]["EVENT_PICK"]
        self.assertEqual(pick["name"], "Pick Something")
        self.assertEqual(pick["groups"], ["Miscellaneous"])
        self.assertEqual(pick["warnings"], [{"sceneTypes": ["LOGO"], "message": "Text glitches in Logo scenes."}])
        fields = {field["key"]: field for field in pick["fields"]}
        self.assertEqual(
            list(fields), ["variable", "items", "x", "units", "option3", "extra", "layout", "__disableElse"]
        )
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
        self.assertEqual(
            pick["branches"], [{"key": "true"}, {"key": "false", "when": [{"key": "__disableElse", "ne": True}]}]
        )
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
                "children": {"true": [], "false": []},
            },
        )

    def test_disable_else_is_kept_only_where_the_compiler_reads_it(self):
        fields = '[{ key: "true", type: "events" }, { key: "false", type: "events", conditions: [{ key: "__disableElse", ne: true }] }]'
        printed = self.generate({"eventPrint.js": definition("EVENT_PRINT", fields)})["events"]["EVENT_PRINT"]
        self.assertEqual(printed["branches"], [{"key": "true"}, {"key": "false"}])
        self.assertNotIn("__disableElse", [field["key"] for field in printed["fields"]])

    def test_or_and_place_conditions_become_alternatives(self):
        fields = """[{ key: "actorId", type: "actor", defaultValue: "$self$" }, { type: "group", conditions: [
          { sceneType: ["platform"] },
          { or: [[{ key: "actorId", eq: "$self$" }, { entityTypeNot: ["actor"] }], [{ key: "actorId", eq: "player" }]] },
        ], fields: [{ label: "Player speed is an engine field.", labelVariant: "warning" }] },
        { key: "position", type: "select", options: [["top", "Top"]], conditions: [{ parallaxEnabled: false }] }]"""
        speed = self.generate({"eventSpeed.js": definition("EVENT_SPEED", fields)})["events"]["EVENT_SPEED"]
        self.assertEqual(
            speed["warnings"],
            [
                {
                    "sceneTypes": ["PLATFORM"],
                    "whenAny": [
                        [{"key": "actorId", "eq": "$self$"}, {"entityTypeNot": ["actor"]}],
                        [{"key": "actorId", "eq": "player"}],
                    ],
                    "message": "Player speed is an engine field.",
                }
            ],
        )
        self.assertEqual(speed["fields"][1]["when"], [{"parallaxEnabled": False}])

    def test_a_condition_the_catalog_does_not_know_stops_it_naming_the_field(self):
        fields = '[{ key: "speed", type: "number", conditions: [{ key: "mode", startsWith: "fast" }] }]'
        with self.assertRaisesRegex(RuntimeError, "EVENT_FAST field speed: condition .* the catalog does not know"):
            self.generate({"eventFast.js": definition("EVENT_FAST", fields)})

    def test_cardinality_and_collision_groups(self):
        fields = """[
          { key: "channels", type: "togglebuttons", options: [[0, "Duty 1"], [1, "Duty 2"]], allowMultiple: true },
          { key: "collisionGroup", type: "collisionMask", includePlayer: false, defaultValue: "3" },
          { key: "collisionMask", type: "collisionMask", includePlayer: true, defaultValue: ["1"] }]"""
        fired = self.generate({"eventFire.js": definition("EVENT_FIRE", fields)})["events"]["EVENT_FIRE"]
        channels, group, mask = fired["fields"]
        self.assertEqual((channels["options"], channels["multiple"]), ([0, 1], True))
        self.assertEqual((group["options"], group.get("multiple")), (["1", "2", "3"], None))
        self.assertEqual((mask["options"], mask["multiple"]), (["player", "1", "2", "3"], True))

    def test_a_union_field_defaults_to_its_default_types_value(self):
        fields = """[{ key: "amount", type: "union", types: ["number", "variable"], defaultType: "number",
          defaultValue: { number: 4, variable: "LAST_VARIABLE" } }]"""
        add = self.generate({"eventAdd.js": definition("EVENT_ADD", fields)})["events"]["EVENT_ADD"]
        self.assertEqual(add["fields"][0]["types"], ["number", "variable"])
        self.assertEqual(add["example"]["args"], {"amount": {"type": "number", "value": 4}})
        broken = '[{ key: "amount", type: "union", types: ["number"], defaultValue: { number: 4 } }]'
        with self.assertRaisesRegex(RuntimeError, "EVENT_ADD field amount: union field amount has no defaultType"):
            self.generate({"eventAdd.js": definition("EVENT_ADD", broken)})

    def test_an_event_whose_compiler_helper_is_gone_must_be_listed_and_is_marked(self):
        attack = definition("EVENT_ATTACK", "[]", "const { weaponAttack } = helpers; weaponAttack();")
        with self.assertRaisesRegex(RuntimeError, "EVENT_ATTACK compiles with weaponAttack, which .* lacks"):
            self.generate({"eventAttack.js": attack})
        entry = self.generate({"eventAttack.js": attack}, {"UNAVAILABLE": ["EVENT_ATTACK"]})["events"]["EVENT_ATTACK"]
        self.assertIn("no weaponAttack", entry["unavailable"])
        with self.assertRaisesRegex(RuntimeError, "UNAVAILABLE names EVENT_PICK, whose helpers"):
            self.generate({"eventPick.js": PICK}, {"UNAVAILABLE": ["EVENT_PICK"]})

    def test_a_hand_written_example_replaces_the_default_and_must_fit(self):
        loop = {"command": "EVENT_PICK", "args": {"items": 3}, "children": {"true": []}}
        guidance = {"EXAMPLES": {"EVENT_PICK": {"requires": "A thing to pick.", "example": loop}}}
        pick = self.generate({"eventPick.js": PICK}, guidance)["events"]["EVENT_PICK"]
        self.assertEqual((pick["example"], pick["requires"]), (loop, "A thing to pick."))
        wrong = {"EXAMPLES": {"EVENT_PICK": {"example": {"command": "EVENT_PICK", "args": {"colour": 1}}}}}
        with self.assertRaisesRegex(RuntimeError, "EVENT_PICK's example gives EVENT_PICK an arg colour"):
            self.generate({"eventPick.js": PICK}, wrong)

    def test_an_editor_default_replaces_the_definitions_default(self):
        fields = '[{ key: "data", type: "dataTable", defaultValue: [{ variable: "0", values: [] }] }]'
        shape = {"variables": ["0"], "rows": []}
        table = self.generate(
            {"eventTable.js": definition("EVENT_TABLE", fields)}, {"EDITOR_DEFAULTS": {"dataTable": shape}}
        )
        self.assertEqual(table["events"]["EVENT_TABLE"]["example"]["args"], {"data": shape})

    def test_a_deprecated_event_names_its_replacement_and_conversion(self):
        old = {"EVENT_OLD_PICK": {"replacement": "EVENT_PICK", "migration": "Pick instead."}}
        catalog = self.generate({"eventPick.js": PICK, "eventOldPick.js": OLD_PICK}, {"DEPRECATIONS": old})
        entry = catalog["events"]["EVENT_OLD_PICK"]
        self.assertEqual(
            (entry["deprecated"], entry["replacement"], entry["migration"]), (True, "EVENT_PICK", "Pick instead.")
        )

    def test_a_newly_deprecated_event_stops_the_generator(self):
        with self.assertRaisesRegex(RuntimeError, "EVENT_OLD_PICK is deprecated: add it to DEPRECATIONS"):
            self.generate({"eventPick.js": PICK, "eventOldPick.js": OLD_PICK})

    def test_a_replacement_must_be_a_current_event(self):
        old = {"EVENT_OLD_PICK": {"replacement": "EVENT_GONE", "migration": "Gone."}}
        with self.assertRaisesRegex(RuntimeError, "EVENT_OLD_PICK's replacement EVENT_GONE is not a current"):
            self.generate({"eventPick.js": PICK, "eventOldPick.js": OLD_PICK}, {"DEPRECATIONS": old})

    def test_a_definition_needing_another_module_is_named(self):
        source = 'const x = require("../helpers/other"); module.exports = { id: "EVENT_X", fields: [] };'
        with self.assertRaisesRegex(RuntimeError, "eventX.js requires ../helpers/other"):
            self.generate({"eventX.js": source})

    def test_the_generator_runs_through_a_symlinked_folder(self):
        catalog = self.generate({"eventPick.js": PICK}, through_symlink=True)
        self.assertIn("EVENT_PICK", catalog["events"])


if __name__ == "__main__":
    unittest.main()

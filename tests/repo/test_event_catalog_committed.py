"""The committed event catalog (engine/modretro-chromatic/dist/gb-studio-events.json) is complete and its examples
work, and every recipe in the authoring skill's event cookbook fits it. Whether the recipes build is checked by the
acceptance run (C3), which has the toolchain."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "authoring" / "references"
CATALOG = ROOT / "engine" / "modretro-chromatic" / "dist" / "gb-studio-events.json"
CALL_BINDING = re.compile(r"^\$(?:actor|variable)\[[^\]]+\]\$$")


def example_events(entry: dict) -> list[dict]:
    """An entry's example as a list: one event, or the events it works with."""
    return entry["example"] if isinstance(entry["example"], list) else [entry["example"]]


def nested(events: list[dict]):
    for event in events:
        yield event
        for children in event.get("children", {}).values():
            yield from nested(children)


class CommittedCatalogTests(unittest.TestCase):
    def setUp(self):
        self.events = json.loads(CATALOG.read_text())["events"]

    def fields(self, command: str) -> dict:
        return {field["key"]: field for field in self.events[command]["fields"]}

    def test_every_event_has_args_and_an_example_using_only_what_gb_studio_declares(self):
        self.assertGreater(len(self.events), 100)
        for command, entry in self.events.items():
            with self.subTest(command=command):
                self.assertRegex(command, r"^EVENT_[A-Z0-9_]+$")
                self.assertTrue(entry["name"])
                self.assertIn(command, [event["command"] for event in example_events(entry)])
                for event in nested(example_events(entry)):
                    keys = set(self.fields(event["command"]))
                    binding = {key for key in event["args"] if CALL_BINDING.match(key)}
                    self.assertLessEqual(set(event["args"]) - binding, keys, event["command"])
                    branches = {branch["key"] for branch in self.events[event["command"]].get("branches", [])}
                    self.assertLessEqual(set(event.get("children", {})), branches, event["command"])
                self.assertNotIn("LAST_", json.dumps(entry))

    def test_deprecated_events_name_a_current_replacement_and_a_conversion(self):
        deprecated = {command: entry for command, entry in self.events.items() if entry.get("deprecated")}
        self.assertIn("EVENT_IF_VALUE", deprecated)
        for command, entry in deprecated.items():
            with self.subTest(command=command):
                self.assertTrue(entry["migration"])
                if "replacement" in entry:
                    self.assertFalse(self.events[entry["replacement"]].get("deprecated"))
        self.assertIn('"type":"gt"', deprecated["EVENT_IF_TRUE"]["migration"])
        self.assertIn('"type":"lte"', deprecated["EVENT_IF_FALSE"]["migration"])
        self.assertIn("collideWith []", deprecated["EVENT_ACTOR_MOVE_TO_VALUE"]["migration"])
        self.assertIn("initialOffset", deprecated["EVENT_WEAPON_ATTACK"]["migration"])

    def test_an_attack_the_compiler_cannot_build_says_so(self):
        self.assertIn("weaponAttack", self.events["EVENT_WEAPON_ATTACK"]["unavailable"])
        self.assertEqual(
            [command for command, entry in self.events.items() if entry.get("unavailable")], ["EVENT_WEAPON_ATTACK"]
        )

    def test_examples_that_need_more_than_defaults(self):
        table = self.events["EVENT_DATA_TABLE"]["example"]["args"]["data"]
        self.assertEqual(set(table), {"variables", "rows"})
        self.assertEqual(len(table["rows"][0]["values"]), len(table["variables"]))
        labels = example_events(self.events["EVENT_GOTO_LABEL"])
        self.assertEqual([event["args"]["label"] for event in labels if "label" in event["args"]], ["skip", "skip"])
        call = self.events["EVENT_CALL_CUSTOM_EVENT"]
        self.assertIn("customEventId", call["example"]["args"])
        self.assertIn("project_inventory", call["requires"])

    def test_loop_examples_wait_in_their_body(self):
        for command in ("EVENT_LOOP", "EVENT_LOOP_WHILE"):
            with self.subTest(command=command):
                body = self.events[command]["example"]["children"]["true"]
                self.assertIn("EVENT_WAIT", [event["command"] for event in body])
        body = self.events["EVENT_LOOP_WHILE"]["example"]["children"]["true"]
        self.assertIn("EVENT_INC_VALUE", [event["command"] for event in body])

    def test_cardinality_and_collision_groups(self):
        self.assertTrue(self.fields("EVENT_MUTE_CHANNEL")["channels"]["multiple"])
        projectile = self.fields("EVENT_LAUNCH_PROJECTILE")
        self.assertNotIn("multiple", projectile["collisionGroup"])
        self.assertNotIn("player", projectile["collisionGroup"]["options"])
        self.assertTrue(projectile["collisionMask"]["multiple"])
        self.assertIn("player", projectile["collisionMask"]["options"])

    def test_conditions_the_compiler_reads_are_kept(self):
        branches = {branch["key"]: branch for branch in self.events["EVENT_SWITCH"]["branches"]}
        self.assertEqual(branches["true3"]["when"], [{"key": "choices", "gt": 3}])
        self.assertEqual(branches["false"]["when"], [{"key": "__disableElse", "ne": True}])
        self.assertIn("__disableElse", self.fields("EVENT_IF"))
        speed = self.events["EVENT_ACTOR_SET_MOVEMENT_SPEED"]["warnings"][0]
        self.assertIn([{"key": "actorId", "eq": "player"}], speed["whenAny"])

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
        self.events = json.loads(CATALOG.read_text())["events"]

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
            if field.get("multiple") and field["type"] != "textarea":
                self.assertIsInstance(value, list, f"{where}: {command}.{key} takes a list")
            if "options" in field:
                for option in value if isinstance(value, list) else [value]:
                    self.assertIn(option, field["options"], f"{where}: {command}.{key}")
        branches = [branch["key"] for branch in entry.get("branches", [])]
        for branch, children in event.get("children", {}).items():
            self.assertIn(branch, branches, f"{where}: {command} has no branch {branch}")
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

    def test_a_sound_sequence_waits_before_the_next_sound(self):
        text = (SKILL / "event-cookbook.md").read_text()
        section = text.split("## Sound effects", 1)[1].split("\n## ", 1)[0]
        sounds = json.loads(re.search(r"```json\n(.*?)```", section, re.S).group(1))
        self.assertTrue(all(sound["args"]["wait"] for sound in sounds[:-1]))

    def test_lives_are_set_before_play_not_in_the_hazards_scene(self):
        text = (SKILL / "event-cookbook.md").read_text()
        menu = text.split("## Menu that stores a choice", 1)[1].split("\n## ", 1)[0]
        start = json.loads(re.search(r"```json\n(.*?)```", menu, re.S).group(1))[1]["children"]["true0"]
        self.assertIn(
            {"command": "EVENT_SET_VALUE", "args": {"variable": "1", "value": {"type": "number", "value": 3}}}, start
        )

    def test_the_pages_name_only_real_events(self):
        for page in ("event-cookbook.md", "gb-studio-behaviours.md", "project-authoring.md"):
            for command in set(re.findall(r"\bEVENT_[A-Z0-9_]*[A-Z0-9]", (SKILL / page).read_text())):
                with self.subTest(page=page, command=command):
                    self.assertIn(command, self.events)


if __name__ == "__main__":
    unittest.main()

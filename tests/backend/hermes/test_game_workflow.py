"""One way to make a game, said the same everywhere the agent reads it: the prompt section, the Build page's
context, the studio SOUL, a build's next step and the game card's schema.

Run alone: python -m unittest tests.backend.hermes.test_game_workflow
"""

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import results  # noqa: E402 - the repository root goes on sys.path first
from backend.library import game_card  # noqa: E402 - the repository root goes on sys.path first
from backend.library import hooks as library_hooks  # noqa: E402 - the repository root goes on sys.path first
from backend.library import tools as library_tools  # noqa: E402 - the repository root goes on sys.path first
from backend.setup import studio_profile  # noqa: E402 - the repository root goes on sys.path first

# The steps in their order, as each source names them.
ORDER = (
    "hermretro:game-planning",
    "chromatic_rom_build",
    "chromatic_emulator_",
    "chromatic_game_info",
    "chromatic_present_game",
    "chromatic_build_report",
)


def in_order(test, text):
    places = [text.index(step) for step in ORDER]
    test.assertEqual(places, sorted(places), f"the steps are out of order in: {text}")


class OneWorkflow(unittest.TestCase):
    def test_the_steps_are_in_order_wherever_they_are_said(self):
        in_order(self, hermes_host.GAME_STEPS)
        in_order(self, studio_profile.SOUL_FILE.read_text())

    def test_the_prompt_section_carries_the_steps_and_the_rules_within_its_limit(self):
        section = hermes_host.SYSTEM_PROMPT_SECTION
        self.assertLessEqual(len(section), 2000)
        self.assertIn(hermes_host.GAME_STEPS, section)
        self.assertIn(hermes_host.GAME_RULES, section)

    def test_the_rules_keep_the_game_in_the_tools(self):
        for text in (hermes_host.GAME_RULES, studio_profile.SOUL_FILE.read_text()):
            self.assertIn(".gbsres", text)
            self.assertIn("build/", text)
            self.assertIn("other programs", text)
            self.assertIn("skills unless the user asks", text)

    def context(self, kind, entry, first=True):
        registry = mock.Mock()
        registry.binding_for.return_value = (kind, entry)
        with (
            mock.patch.object(hermes_host, "_registry", return_value=registry),
            mock.patch.object(hermes_host, "_profile_identity", return_value="p"),
        ):
            return library_hooks.build_context(session_id="s", is_first_turn=first)["context"]

    def test_a_planned_new_game_waits_for_the_users_approval(self):
        context = self.context("pending", {"name": "Robin", "plan": True})
        self.assertIn("wait for the user to approve the brief before building anything", context)
        self.assertIn(hermes_host.GAME_STEPS, context)

    def test_a_quick_new_game_still_playtests_before_presenting(self):
        context = self.context("pending", {"name": "Robin", "plan": False})
        self.assertIn(hermes_host.GAME_STEPS, context)
        self.assertIn(hermes_host.GAME_RULES, context)

    def test_a_games_own_chat_hears_the_rules(self):
        self.assertIn(hermes_host.GAME_RULES, self.context("game", {"title": "Robin", "projectRoot": "/g/robin"}))

    def test_a_build_says_to_playtest_and_fill_the_card_before_presenting(self):
        built = {
            "ok": True,
            "result": {"content": [], "structuredContent": {"success": True}},
            "player": {"ready": True},
        }
        step = json.loads(results.encode(built, "chromatic_rom_build", None, False))["nextStep"]
        self.assertLess(step.index("chromatic_emulator_"), step.index("chromatic_game_info"))
        self.assertLess(step.index("chromatic_game_info"), step.index("chromatic_present_game"))


class CardRulesUpFront(unittest.TestCase):
    """What the card needs is in the schema the agent reads, not only in the refusal it would get."""

    def setUp(self):
        self.schema = library_tools.GAME_INFO_TOOL["parameters"]["properties"]

    def test_the_lengths_and_genre_count_are_the_enforced_ones(self):
        for field in ("title", "tagline", "description"):
            low, high = game_card.LIMITS[field]
            self.assertEqual((self.schema[field]["minLength"], self.schema[field]["maxLength"]), (low, high))
        self.assertEqual(
            (self.schema["genres"]["minItems"], self.schema["genres"]["maxItems"]), (1, game_card.MAX_GENRES)
        )

    def test_the_cover_field_states_every_cover_rule(self):
        rules = self.schema["cover"]["description"]
        for needed in (
            f"{game_card.COVER_WIDTH}x{game_card.COVER_HEIGHT}",
            "opaque",
            f"{game_card.MIN_COVER_COLOURS} to {game_card.MAX_COVER_COLOURS}",
            "not interlaced",
            f"{game_card.MAX_COVER_BYTES // 1024} KB",
            "unchanged copy of an image under assets/",
            "never Image",
        ):
            self.assertIn(needed, rules)
        self.assertIn("placeholder words", library_tools.GAME_INFO_TOOL["description"])


class StudioSoul(unittest.TestCase):
    def test_profiles_with_the_last_shipped_soul_get_this_one(self):
        self.assertIn("0d723cea8a6bb62e7819d0a371a802a4481895b1c9de751f8e32ff859ce01218", studio_profile.OLDER_SOULS)


if __name__ == "__main__":
    unittest.main()

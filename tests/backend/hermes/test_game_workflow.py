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
        self.assertIn("wait for the user to approve the brief before authoring anything", context)
        self.assertIn(hermes_host.GAME_STEPS, context)

    def test_a_quick_new_game_still_playtests_before_presenting(self):
        context = self.context("pending", {"name": "Robin", "plan": False})
        self.assertIn(hermes_host.GAME_STEPS, context)
        self.assertIn(hermes_host.GAME_RULES, context)

    def test_a_quick_new_game_agrees_a_list_and_builds_all_of_it(self):
        first = self.context("pending", {"name": "Robin", "plan": False})
        self.assertLess(first.index("a few quick questions"), first.index("a short list of what you will make"))
        self.assertIn("create nothing until they approve it", first)
        self.assertIn("docs/game/FIRST-BUILD.md and build all of it in one go", first)
        later = self.context("pending", {"name": "Robin", "plan": False}, first=False)
        self.assertIn("Until the user approves the list of what you will make, create nothing", later)
        self.assertIn(library_hooks.BUILD_THE_LIST, later)

    def test_a_planned_game_builds_its_whole_brief(self):
        for first in (True, False):
            self.assertIn(library_hooks.BUILD_THE_BRIEF, self.context("pending", {"plan": True}, first=first))

    def test_a_build_is_a_checkpoint_until_everything_agreed_is_in(self):
        self.assertIn("a build is a checkpoint, not a hand-off", hermes_host.GAME_STEPS)
        self.assertIn("A build is a checkpoint for you, not a hand-off", studio_profile.SOUL_FILE.read_text())
        built = {
            "ok": True,
            "result": {"content": [], "structuredContent": {"success": True}},
            "player": {"ready": True},
        }
        step = json.loads(results.encode(built, "chromatic_rom_build", None, False))["nextStep"]
        self.assertLess(step.index("keep authoring until everything agreed"), step.index("chromatic_emulator_"))

    def test_a_games_own_chat_hears_the_steps_and_the_rules(self):
        context = self.context("game", {"title": "Robin", "projectRoot": "/g/robin"})
        self.assertIn(hermes_host.GAME_STEPS, context)
        self.assertIn(hermes_host.GAME_RULES, context)

    def test_a_planned_game_keeps_waiting_for_approval_on_later_turns(self):
        context = self.context("pending", {"name": "Robin", "plan": True}, first=False)
        self.assertIn("Author nothing until the user has approved the game brief", context)
        self.assertNotIn("Author nothing", self.context("pending", {"name": "Robin"}, first=False))

    def test_drawing_art_and_importing_it_stays_allowed(self):
        self.assertIn("draw art as PNG files and bring it in with chromatic_asset_import", hermes_host.GAME_RULES)

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
        self.assertEqual(self.schema["genres"]["maxItems"], game_card.MAX_GENRES)
        self.assertNotIn("minItems", self.schema["genres"], "an empty list clears the genres in a partial update")

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
        self.assertIn("fc761b6efa1d664e24b9e444be7732b7a42a4b6e985f9b43a48984e25d494749", studio_profile.OLDER_SOULS)


if __name__ == "__main__":
    unittest.main()

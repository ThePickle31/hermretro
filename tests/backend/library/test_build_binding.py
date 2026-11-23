"""Game conversation bindings, their Build RPC and per-turn context."""

import json
import os
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.library import games  # noqa: E402 - the repository root goes on sys.path first
from backend.library import hooks as library_hooks  # noqa: E402 - the repository root goes on sys.path first
from backend.library import rpcs as library_rpcs  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home, make_project  # noqa: E402 - the repository root goes on sys.path first

PROFILE = "/profiles/studio"


class Binding(unittest.TestCase):
    def setUp(self):
        self.base = isolated_home(self).base
        self.registry = games.Registry(self.base / "lib")
        self.root = make_project(self.base, "Frog Post")
        self.game = self.registry.upsert(str(self.root))["id"]

    def test_a_game_gets_one_conversation_and_keeps_it(self):
        self.registry.bind(self.game, "st-1", PROFILE)
        kind, entry = self.registry.binding_for(PROFILE, ["st-1"])
        self.assertEqual((kind, entry["id"]), ("game", self.game))
        with self.assertRaises(games.BindingError) as refused:
            self.registry.bind(self.game, "st-2", PROFILE)
        self.assertEqual(refused.exception.code, "HAS_CONVERSATION")
        self.registry.bind(self.game, "st-2", PROFILE, replace="st-1")  # the old one was deleted
        self.assertEqual(self.registry.binding_for(PROFILE, ["st-1"]), (None, None))
        self.assertEqual(self.registry.binding_for(PROFILE, ["st-2"])[0], "game")

    def test_a_conversation_belongs_to_one_game(self):
        other = self.registry.upsert(str(make_project(self.base, "Comet Drift")))["id"]
        self.registry.bind(self.game, "st-1", PROFILE)
        with self.assertRaises(games.BindingError) as refused:
            self.registry.bind(other, "st-1", PROFILE)
        self.assertEqual(refused.exception.code, "BOUND")

    def test_bindings_are_per_profile(self):
        self.registry.bind(self.game, "st-1", PROFILE)
        self.assertEqual(self.registry.binding_for("/profiles/other", ["st-1"]), (None, None))

    def test_new_game_keeps_the_configured_number_of_pending_conversations(self):
        with mock.patch.object(games, "MAX_PENDING", 1):
            self.registry.build_start("st-first", PROFILE)
            self.registry.build_start("st-second", PROFILE)
        self.assertEqual([entry["storedId"] for entry in self.registry.pending(PROFILE)], ["st-second"])

    def test_a_new_game_conversation_claims_the_first_project_it_makes(self):
        self.registry.build_start("st-new", PROFILE, "Lamplight")
        self.assertEqual(self.registry.pending(PROFILE)[0]["name"], "Lamplight")
        made = make_project(self.base, "Lamplight")
        entry = self.registry.observe(
            "project_create",
            {"select": True},
            {"projectRoot": str(made)},
            False,
            lane_root=None,
            conversation_id="st-new",
            profile=PROFILE,
        )
        self.assertEqual(entry["session"]["storedId"], "st-new")
        self.assertEqual(self.registry.pending(PROFILE), [])
        self.assertEqual(self.registry.library()[0]["session"]["storedId"], "st-new")

    def test_plan_first_keeps_the_explicit_approval_gate_after_the_project_claims_the_chat(self):
        self.registry.build_start("st-plan", PROFILE, "Lamplight", plan=True)
        self.registry.note_alias(PROFILE, "st-plan", "st-live")
        with (
            mock.patch.object(hermes_host, "_registry", return_value=self.registry),
            mock.patch.object(hermes_host, "_profile_identity", return_value=PROFILE),
        ):
            pending = library_hooks.build_context(session_id="st-plan", is_first_turn=True)["context"]
            self.assertIn("wait for the user to approve the brief before authoring or building", pending)
            self.registry.observe(
                "project_create_blank",
                {"select": True},
                {"projectRoot": str(self.root)},
                False,
                lane_root=None,
                conversation_id="st-plan",
                sessions_seen=["st-live"],
                profile=PROFILE,
            )
            self.assertEqual(self.registry.pending(PROFILE), [])
            before_brief = library_hooks.build_context(session_id="st-plan")["context"]
            self.assertIn("If the brief is missing or still awaiting approval", before_brief)
            brief = self.root / "docs" / "game" / "GAME-BRIEF.md"
            brief.parent.mkdir(parents=True, exist_ok=True)
            brief.write_text("- Status: proposed\n")
            bound = library_hooks.build_context(session_id="st-plan")["context"]
            self.assertIn("wait for the user's explicit approval", bound)
            self.assertIn("Record that approval in the brief before starting the build", bound)
            self.assertNotIn("create the project", bound)
            self.assertEqual(library_hooks.build_context(session_id="st-live")["context"], bound)
            self.registry.upsert(str(self.root), build={"ok": True})
            self.assertEqual(library_hooks.build_context(session_id="st-plan")["context"], bound)
            self.registry.unbind(self.game, "st-plan", PROFILE)
            self.registry.bind(self.game, "st-reopened", PROFILE)
            self.assertEqual(library_hooks.build_context(session_id="st-reopened")["context"], bound)
            self.registry.present(str(self.root))
            delivered = library_hooks.build_context(session_id="st-reopened")["context"]
            self.assertIn("make the requested changes", delivered)
            self.assertNotIn("brief", delivered)

    def test_edit_does_not_treat_an_imported_games_notes_as_a_new_game_brief(self):
        entry = self.registry.bind(self.game, "st-edit", PROFILE)
        self.assertIs(entry["session"]["edit"], True)
        brief = self.root / "docs" / "game" / "GAME-BRIEF.md"
        brief.parent.mkdir(parents=True)
        brief.write_text("- Status: proposed")
        later = entry["session"]["createdAt"] + 1
        os.utime(brief, (later, later))
        with (
            mock.patch.object(hermes_host, "_registry", return_value=self.registry),
            mock.patch.object(hermes_host, "_profile_identity", return_value=PROFILE),
        ):
            context = library_hooks.build_context(session_id="st-edit")["context"]
        self.assertIn("make the requested changes", context)
        self.assertNotIn("brief", context)

    def test_a_game_that_already_has_a_conversation_is_never_claimed(self):
        self.registry.bind(self.game, "st-1", PROFILE)
        self.registry.build_start("st-new", PROFILE)
        self.assertIsNone(self.registry.claim_pending(self.game, PROFILE, ["st-new"]))
        self.assertEqual(self.registry.binding_for(PROFILE, ["st-new"])[0], "pending")

    def test_a_rotated_session_id_still_finds_the_game(self):
        self.registry.bind(self.game, "st-1", PROFILE)
        self.registry.note_alias(PROFILE, "st-1", "st-1-rotated")
        self.assertEqual(self.registry.binding_for(PROFILE, ["st-1-rotated"])[0], "game")

    def test_selecting_an_existing_game_does_not_claim_it(self):
        self.registry.build_start("st-new", PROFILE)
        self.registry.observe(
            "project_select",
            {},
            {"projectRoot": str(self.root)},
            False,
            lane_root=None,
            conversation_id="st-new",
            profile=PROFILE,
        )
        self.assertIsNone(self.registry.get(self.game).get("session"))
        self.assertEqual(self.registry.binding_for(PROFILE, ["st-new"])[0], "pending")

    def test_another_profiles_conversation_is_never_replaced(self):
        self.registry.bind(self.game, "st-1", "/profiles/other")
        old = (self.registry.get(self.game) or {})["session"]
        for stored in ("st-2", "st-1"):
            with self.subTest(stored=stored), self.assertRaises(games.BindingError) as refused:
                self.registry.bind(self.game, stored, PROFILE, replace="st-1")
            self.assertEqual(refused.exception.code, "OTHER_PROFILE")
        self.assertEqual((self.registry.get(self.game) or {})["session"], old)

    def test_a_replacement_names_the_conversation_it_replaces(self):
        self.registry.bind(self.game, "st-1", PROFILE)
        self.registry.bind(self.game, "st-2", PROFILE, replace="st-1")  # the first page wins
        with self.assertRaises(games.BindingError) as stale:  # a second page that also saw st-1 missing
            self.registry.bind(self.game, "st-3", PROFILE, replace="st-1")
        self.assertEqual(stale.exception.code, "STALE")
        self.registry.note_alias(PROFILE, "st-2", "st-2-rotated")
        winner = (self.registry.get(self.game) or {})["session"]
        self.assertEqual(winner["storedId"], "st-2")
        self.registry.bind(self.game, "st-2", PROFILE, replace="st-1")  # the winner retrying is a no-op
        self.assertEqual((self.registry.get(self.game) or {})["session"], winner)

    def test_a_replacement_of_a_binding_that_was_removed_is_refused(self):
        self.registry.bind(self.game, "st-1", PROFILE)
        self.registry.unbind(self.game, "st-1", PROFILE)
        with self.assertRaises(games.BindingError) as stale:
            self.registry.bind(self.game, "st-2", PROFILE, replace="st-1")
        self.assertEqual(stale.exception.code, "STALE")
        self.assertIsNone(self.registry.get(self.game).get("session"))
        self.registry.bind(self.game, "st-2", PROFILE)  # a free game binds without replace
        self.assertEqual(self.registry.get(self.game)["session"]["storedId"], "st-2")

    def test_replace_must_be_a_stored_session_id(self):
        self.registry.bind(self.game, "st-1", PROFILE)
        for bad in (True, False, "", 1, "x" * 257):
            with self.subTest(replace=bad), self.assertRaises(games.BindingError) as refused:
                self.registry.bind(self.game, "st-2", PROFILE, replace=bad)
            self.assertEqual(refused.exception.code, "INVALID")
        self.assertEqual(self.registry.get(self.game)["session"]["storedId"], "st-1")

    def test_racing_replacements_leave_exactly_one_winner(self):
        self.registry.bind(self.game, "st-1", PROFILE)
        outcomes, start = [], threading.Barrier(4)

        def replace(stored):
            start.wait()
            try:
                self.registry.bind(self.game, stored, PROFILE, replace="st-1")
                outcomes.append(("ok", stored))
            except games.BindingError as error:
                outcomes.append((error.code, stored))

        threads = [threading.Thread(target=replace, args=(f"st-new-{n}",)) for n in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        winners = [stored for code, stored in outcomes if code == "ok"]
        self.assertEqual(len(winners), 1, outcomes)
        self.assertEqual(sorted(code for code, _ in outcomes), ["STALE", "STALE", "STALE", "ok"])
        self.assertEqual(self.registry.get(self.game)["session"]["storedId"], winners[0])

    def test_a_pending_conversation_keeps_its_place_after_compression(self):
        self.registry.build_start("st-new", PROFILE)
        self.registry.note_alias(PROFILE, "st-new", "st-new-rotated")
        self.assertEqual(self.registry.binding_for(PROFILE, ["st-new-rotated"])[0], "pending")

    def test_stop_editing_frees_the_game_and_only_its_own_conversation(self):
        self.registry.bind(self.game, "st-1", PROFILE)
        self.assertFalse(self.registry.unbind(self.game, "st-old", PROFILE))  # a stale page
        self.assertEqual(self.registry.get(self.game)["session"]["storedId"], "st-1")
        self.assertTrue(self.registry.unbind(self.game, "st-1", PROFILE))
        self.assertIsNone(self.registry.get(self.game).get("session"))
        self.assertEqual(self.registry.binding_for(PROFILE, ["st-1"]), (None, None))
        self.assertFalse(self.registry.unbind(self.game, "st-1", PROFILE))  # already free
        self.registry.bind(self.game, "st-2", PROFILE)  # editable again, no replace
        self.assertEqual(self.registry.get(self.game)["session"]["storedId"], "st-2")

    def test_stop_editing_never_touches_another_profiles_conversation(self):
        self.registry.bind(self.game, "st-1", "/profiles/other")
        with self.assertRaises(games.BindingError) as refused:
            self.registry.unbind(self.game, "st-1", PROFILE)
        self.assertEqual(refused.exception.code, "OTHER_PROFILE")

    def test_unknown_top_level_keys_survive_a_write(self):
        path = self.registry.path
        data = json.loads(path.read_text())
        data["futureThing"] = {"keep": True}
        path.write_text(json.dumps(data))
        self.registry.bind(self.game, "st-1", PROFILE)
        self.assertEqual(json.loads(path.read_text())["futureThing"], {"keep": True})

    def test_other_writes_keep_the_binding_and_pending(self):
        self.registry.bind(self.game, "st-1", PROFILE)
        self.registry.build_start("st-new", PROFILE)
        self.registry.upsert(str(self.root), chat={"conversationId": "x", "sessionId": "x"})
        self.registry.present(str(self.root), note="hi")
        self.assertEqual(self.registry.get(self.game)["session"]["storedId"], "st-1")
        self.assertEqual(len(self.registry.pending()), 1)


class RpcAndContext(unittest.TestCase):
    def setUp(self):
        self.base = isolated_home(self).base  # the library, the plugin data folder and the profile home
        patch = mock.patch.object(hermes_host, "try_connect", lambda _dir: (None, None))
        patch.start()
        self.addCleanup(patch.stop)
        self.rpc = library_rpcs.rpc_build(mock.Mock())
        self.frog = make_project(self.base, "Frog Post")
        hermes_host._registry().upsert(str(self.frog))
        self.game = games.game_id(self.frog)

    def test_start_bind_and_the_games_list(self):
        self.assertTrue(self.rpc({"action": "start", "stored": "st-new", "name": "Lamplight"})["ok"])
        answer = self.rpc({"action": "bind", "game": self.game, "stored": "st-frog"})
        self.assertEqual((answer["ok"], answer["session"]["storedId"]), (True, "st-frog"))
        again = self.rpc({"action": "bind", "game": self.game, "stored": "st-other"})
        self.assertEqual((again["ok"], again["code"]), (False, "HAS_CONVERSATION"))
        legacy = self.rpc({"action": "bind", "game": self.game, "stored": "st-other", "replace": True})
        self.assertEqual((legacy["ok"], legacy["code"]), (False, "INVALID"))
        stale = self.rpc({"action": "bind", "game": self.game, "stored": "st-other", "replace": "st-gone"})
        self.assertEqual((stale["ok"], stale["code"]), (False, "STALE"))
        swapped = self.rpc({"action": "bind", "game": self.game, "stored": "st-other", "replace": "st-frog"})
        self.assertEqual((swapped["ok"], swapped["session"]["storedId"]), (True, "st-other"))
        late = self.rpc({"action": "bind", "game": self.game, "stored": "st-third", "replace": "st-frog"})
        self.assertEqual((late["ok"], late["code"]), (False, "STALE"))
        back = self.rpc({"action": "bind", "game": self.game, "stored": "st-frog", "replace": "st-other"})
        self.assertEqual((back["ok"], back["session"]["storedId"]), (True, "st-frog"))
        listed = library_rpcs.rpc_games(mock.Mock(get_config=lambda key, default=None: default))({})
        self.assertEqual(listed["games"][0]["session"]["storedId"], "st-frog")
        self.assertIs(listed["games"][0]["session"]["thisProfile"], True)
        self.assertNotIn("profile", listed["games"][0]["session"])
        self.assertIsNone(listed["games"][0]["session"]["exists"])  # no session database in this test
        self.assertEqual([item["storedId"] for item in listed["pending"]], ["st-new"])
        self.assertTrue(self.rpc({"action": "cancel", "stored": "st-new"})["cancelled"])
        self.assertTrue(self.rpc({"action": "unbind", "game": self.game, "stored": "st-frog"})["unbound"])
        self.assertIsNone(library_hooks.build_context(session_id="st-frog"))
        self.assertEqual(self.rpc({"action": "unbind", "game": "nope", "stored": "st-frog"})["code"], "INVALID")
        self.assertFalse(self.rpc({"action": "nope"})["ok"])

    def test_each_turn_of_a_games_conversation_is_told_its_game(self):
        self.rpc({"action": "bind", "game": self.game, "stored": "st-frog"})
        context = library_hooks.build_context(session_id="st-frog")["context"]
        self.assertIn("Frog Post", context)
        self.assertIn(str(self.frog), context)
        self.rpc({"action": "start", "stored": "st-new", "name": "Lamplight"})
        context = library_hooks.build_context(session_id="st-new", is_first_turn=True)["context"]
        self.assertIn("chromatic_project_create", context)
        self.assertIn('called "Lamplight"', context)
        self.assertIn("chromatic_present_game", context)
        self.assertNotIn("their message is the idea", library_hooks.build_context(session_id="st-new")["context"])
        self.rpc({"action": "start", "stored": "st-plan", "plan": True})
        self.assertIn(
            "hermretro:game-planning", library_hooks.build_context(session_id="st-plan", is_first_turn=True)["context"]
        )
        self.assertIsNone(library_hooks.build_context(session_id="plain-chat"))
        self.assertIsNone(library_hooks.build_context())


if __name__ == "__main__":
    unittest.main()

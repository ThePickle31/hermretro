"""Build: one game, one conversation. The registry binding, the broker's guards and auto-select, the
desktop RPC and the per-turn context hook."""

import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.library import games  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from tests.backend.broker.bare import bare_broker  # noqa: E402 - the repository root goes on sys.path first
from backend.broker.broker import Denied, Lane  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home, make_project  # noqa: E402 - the repository root goes on sys.path first
from backend.assets import rpcs as assets_rpcs  # noqa: E402 - the repository root goes on sys.path first
from backend.library import hooks as library_hooks  # noqa: E402 - the repository root goes on sys.path first
from backend.library import rpcs as library_rpcs  # noqa: E402 - the repository root goes on sys.path first

PROFILE = "/profiles/studio"


class Binding(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.registry = games.Registry(self.base / "lib")
        self.root = make_project(self.base, "Frog Post")
        self.game = self.registry.upsert(str(self.root))["id"]

    def tearDown(self):
        self.tmp.cleanup()

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
        import json

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


def guard_broker(registry):
    return bare_broker(games=registry)


class Guards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.registry = games.Registry(self.base / "lib")
        self.frog = make_project(self.base, "Frog Post")
        self.comet = make_project(self.base, "Comet Drift")
        self.registry.upsert(str(self.frog))
        self.registry.upsert(str(self.comet))
        self.registry.bind(games.game_id(self.frog), "st-frog", PROFILE)
        self.broker = guard_broker(self.registry)

    def tearDown(self):
        self.tmp.cleanup()

    def guard(self, conversation, tool, arguments, continue_here=False):
        lane = Lane((PROFILE, conversation))
        self.broker.guard_selection(lane.owner, lane, tool, arguments, continue_here)

    def denied(self, *args, **kwargs):
        with self.assertRaises(Denied) as refused:
            self.guard(*args, **kwargs)
        return refused.exception

    def test_a_games_conversation_may_open_its_own_game(self):
        self.guard("st-frog", "project_select", {"projectPath": str(self.frog / "frog-post.gbsproj")})
        self.guard("st-frog", "project_select", {"projectPath": str(self.frog)})

    def test_a_games_conversation_cannot_open_or_make_another_project(self):
        refused = self.denied("st-frog", "project_select", {"projectPath": str(self.comet)})
        self.assertEqual(refused.code, "ONE_GAME_PER_CONVERSATION")
        self.assertIn("New Game", str(refused))
        refused = self.denied("st-frog", "project_create", {"name": "X", "destinationPath": str(self.base / "x")})
        self.assertEqual(refused.code, "ONE_GAME_PER_CONVERSATION")
        self.assertIn("create another project", str(refused))
        # continueInThisChat never lifts the hard block
        self.denied("st-frog", "project_select", {"projectPath": str(self.comet)}, continue_here=True)

    def test_another_chat_is_warned_and_may_continue_once_the_user_confirms(self):
        refused = self.denied("plain-chat", "project_select", {"projectPath": str(self.frog)})
        self.assertEqual(refused.code, "GAME_HAS_CONVERSATION")
        self.assertIn("continueInThisChat", str(refused))
        self.guard("plain-chat", "project_select", {"projectPath": str(self.frog)}, continue_here=True)
        self.assertEqual(self.broker.events[-1]["event"], "continued_outside_game_conversation")

    def test_a_chat_in_another_profile_is_warned_too(self):
        lane = Lane(("/profiles/other", "plain-chat"))
        with self.assertRaises(Denied) as refused:
            self.broker.guard_selection(lane.owner, lane, "project_select", {"projectPath": str(self.frog)}, False)
        self.assertEqual(refused.exception.code, "GAME_HAS_CONVERSATION")

    def test_a_conversation_whose_game_folder_is_gone_is_told_so(self):
        import shutil

        shutil.rmtree(self.frog)
        refused = self.denied("st-frog", "project_select", {"projectPath": str(self.comet)})
        self.assertEqual(refused.code, "GAME_FOLDER_MISSING")

    def test_games_without_a_conversation_and_new_projects_are_open_to_any_chat(self):
        self.guard("plain-chat", "project_select", {"projectPath": str(self.comet)})
        self.guard("plain-chat", "project_create", {"name": "Y", "destinationPath": str(self.base / "y")})

    def test_a_new_game_conversation_makes_a_project_but_opens_no_existing_game(self):
        self.registry.build_start("st-new", PROFILE)
        self.guard("st-new", "project_create", {"name": "Z", "destinationPath": str(self.base / "z")})
        # Even a game without a conversation: it would stay selected once the new project claims this chat.
        refused = self.denied("st-new", "project_select", {"projectPath": str(self.comet)})
        self.assertEqual(refused.code, "NEW_GAME_ONLY")
        self.assertIn("chromatic_project_create", str(refused))
        refused = self.denied("st-new", "project_select", {"projectPath": str(self.frog)}, continue_here=True)
        self.assertEqual(refused.code, "GAME_HAS_CONVERSATION")


class EngineStub:
    def __init__(self, root):
        self.root, self.calls = root, []

    def call_tool(self, tool, arguments, timeout=None):
        self.calls.append((tool, arguments))
        if tool == "session_status":
            return {"structuredContent": {"projectRoot": str(self.root), "projectPath": arguments}}
        return {"content": [], "structuredContent": {"success": True, "projectRoot": str(self.root)}}


class AutoSelect(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()  # macOS: /var is a link to /private/var
        self.registry = games.Registry(self.base / "lib")
        self.frog = make_project(self.base, "Frog Post")
        self.registry.upsert(str(self.frog))
        self.registry.bind(games.game_id(self.frog), "st-frog", PROFILE)
        self.broker = guard_broker(self.registry)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_games_conversation_starts_with_its_game_selected_and_is_told(self):
        lane = Lane((PROFILE, "st-frog"))
        engine = lane.engine = EngineStub(self.frog)
        self.broker.select_bound_game(lane, engine)
        self.assertEqual(engine.calls[0], ("project_select", {"projectPath": str(self.frog / "frog-post.gbsproj")}))
        self.assertEqual(lane.selected_root, os.path.realpath(self.frog))
        self.assertIn("Frog Post", lane.pending_notice)
        engine.calls.clear()
        self.broker.select_bound_game(lane, engine)  # already selected: nothing more
        self.assertEqual(engine.calls, [])

    def test_a_failed_sync_after_a_good_select_still_records_the_game(self):
        lane = Lane((PROFILE, "st-frog"))
        engine = lane.engine = EngineStub(self.frog)

        def broken(_lane):
            raise RuntimeError("status timed out")

        self.broker._sync_selection = broken
        self.broker.select_bound_game(lane, engine)
        self.assertEqual(lane.selected_root, os.path.realpath(self.frog))

    def test_a_failed_select_is_not_retried_on_every_call(self):
        lane = Lane((PROFILE, "st-frog"))
        engine = lane.engine = EngineStub(self.frog)

        def refuse(tool, arguments, timeout=None):
            engine.calls.append(tool)
            return {"isError": True}

        engine.call_tool = refuse
        self.broker.select_bound_game(lane, engine)
        self.broker.select_bound_game(lane, engine)
        self.assertEqual(engine.calls, ["project_select"])

    def test_other_conversations_are_left_alone(self):
        lane = Lane((PROFILE, "plain-chat"))
        engine = EngineStub(self.frog)
        self.broker.select_bound_game(lane, engine)
        self.assertEqual(engine.calls, [])
        self.assertIsNone(lane.selected_root)


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


PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000020000000100806000000"
    "1f15c4890000000d49444154789c636001000000050001a5f645400000000049454e44ae426082"
)


class AssetRpc(unittest.TestCase):
    def setUp(self):
        isolated = isolated_home(self)
        self.base, self.home = isolated.base, isolated.data  # self.home: the plugin data folder
        (self.home / "frames").mkdir(parents=True)
        self.frog = make_project(self.base, "Frog Post")
        hermes_host._registry().upsert(str(self.frog))
        rpc_asset = assets_rpcs.rpc_asset(mock.Mock())
        self.asset = lambda params: rpc_asset({"root": str(self.frog), **params})  # Frog Post's own Build page

    def test_a_sprite_in_a_game_comes_with_its_size_and_frames(self):
        sprite = self.frog / "assets" / "sprites" / "frog.png"
        sprite.parent.mkdir(parents=True, exist_ok=True)
        sprite.write_bytes(PNG_1x1)
        (sprite.parent / "frog.png.gbsres").write_text(
            json.dumps({"name": "Frog", "canvasWidth": 16, "canvasHeight": 16, "animSpeed": 15})
        )
        answer = self.asset({"path": str(sprite)})
        self.assertTrue(answer["ok"], answer)
        self.assertEqual(
            (answer["width"], answer["height"], answer["kind"], answer["relative"]),
            (32, 16, "sprite", "assets/sprites/frog.png"),
        )
        self.assertEqual(answer["sprite"], {"name": "Frog", "frameWidth": 16, "frameHeight": 16, "animSpeed": 15})
        self.assertTrue(answer["dataUrl"].startswith("data:image/png;base64,"))

    def test_saved_frames_are_served_and_everything_else_is_refused(self):
        frame = self.home / "frames" / "f.png"
        frame.write_bytes(PNG_1x1)
        self.assertEqual(self.asset({"path": "file://" + str(frame)})["kind"], "frame")
        outside = self.base / "secret.png"
        outside.write_bytes(PNG_1x1)
        self.assertEqual(self.asset({"path": str(outside)})["code"], "OUTSIDE")
        link = self.frog / "escape.png"
        link.symlink_to(outside)
        self.assertEqual(
            self.asset({"path": str(link)})["code"], "OUTSIDE", "a link out of the game is followed, then refused"
        )
        text = self.frog / "notes.txt"
        text.write_text("hi")
        self.assertEqual(self.asset({"path": str(text)})["code"], "NOT_IMAGE")
        self.assertEqual(self.asset({"path": "assets/frog.png"})["code"], "INVALID")
        self.assertEqual(self.asset({"path": str(self.frog / "gone.png")})["code"], "MISSING")

    def test_another_games_images_are_never_shown_on_this_games_page(self):
        cat = make_project(self.base, "Cat Field")
        hermes_host._registry().upsert(str(cat))
        theirs = cat / "cover.png"
        theirs.write_bytes(PNG_1x1)
        refused = self.asset({"path": str(theirs)})
        self.assertEqual(refused["code"], "OTHER_GAME", "Frog Post's page asked for Cat Field's cover")
        self.assertEqual(self.asset({"root": str(cat), "path": str(theirs)})["kind"], "image")  # on its own page
        for params in ({}, {"root": ""}, {"root": "Cat Field"}, {"root": str(self.base)}):
            answer = assets_rpcs.rpc_asset(mock.Mock())({**params, "path": str(theirs)})
            self.assertEqual(answer["code"], "OTHER_GAME", f"no game's page, or not a library game: {params}")
        info = assets_rpcs.rpc_asset_info(mock.Mock())({"root": str(self.frog), "path": str(theirs)})
        self.assertEqual(info["code"], "OUTSIDE")
        restore = assets_rpcs.rpc_asset_restore(mock.Mock())(
            {"root": str(self.frog), "path": str(theirs), "version": "1"}
        )
        self.assertEqual(restore["code"], "INVALID")
        frame = self.home / "frames" / "f.png"
        frame.write_bytes(PNG_1x1)
        self.assertEqual(assets_rpcs.rpc_asset(mock.Mock())({"path": str(frame)})["kind"], "frame")  # any page

    def test_a_game_inside_another_games_folder_keeps_its_own_images(self):
        inner = self.frog / "Pond"
        (inner / "assets" / "sprites").mkdir(parents=True)
        (inner / "Pond.gbsproj").write_text("{}")
        hermes_host._registry().upsert(str(inner))
        sprite = inner / "assets" / "sprites" / "lily.png"
        sprite.write_bytes(PNG_1x1)
        self.assertEqual(self.asset({"path": str(sprite)})["code"], "OTHER_GAME", "Pond's sprite on Frog Post's page")
        answer = self.asset({"root": str(inner), "path": str(sprite)})
        self.assertEqual((answer["kind"], answer["relative"]), ("sprite", "assets/sprites/lily.png"))

    def test_a_game_whose_details_cannot_be_read_still_owns_its_images(self):
        inner = self.frog / "Pond"
        inner.mkdir()
        hermes_host._registry().upsert(str(inner))
        sprite = inner / "lily.png"
        sprite.write_bytes(PNG_1x1)
        with mock.patch.object(type(hermes_host._registry()), "library", return_value=[]):
            self.assertEqual(self.asset({"path": str(sprite)})["code"], "OTHER_GAME")

    def test_a_nested_games_pictures_are_not_in_the_outer_games_list(self):
        sprites = self.frog / "assets" / "sprites"
        (sprites / "Pond").mkdir(parents=True)
        (sprites / "frog.png").write_bytes(PNG_1x1)
        (sprites / "Pond" / "lily.png").write_bytes(PNG_1x1)
        hermes_host._registry().upsert(str(sprites / "Pond"))
        listed = assets_rpcs.rpc_assets(mock.Mock())({"root": str(self.frog)})
        self.assertEqual([item["file"] for item in listed["assets"]], ["cover.png", "frog.png"])

    def test_a_restore_never_writes_through_a_temporary_file_already_there(self):
        cover = self.frog / "cover.png"
        cover.write_bytes(PNG_1x1)
        os.utime(cover, ns=(10**18, 10**18))
        version = assets_rpcs.rpc_asset_info(mock.Mock())({"root": str(self.frog), "path": str(cover)})["versions"][0]
        cover.write_bytes(PNG_1x1 + b"later")
        outside = self.base / "outside.png"
        outside.write_bytes(b"theirs")
        (self.frog / ".cover.png.restore").symlink_to(outside)
        restored = assets_rpcs.rpc_asset_restore(mock.Mock())(
            {"root": str(self.frog), "path": str(cover), "version": version["id"]}
        )
        self.assertTrue(restored["ok"], restored)
        self.assertEqual((cover.read_bytes(), outside.read_bytes()), (PNG_1x1, b"theirs"))


if __name__ == "__main__":
    unittest.main()

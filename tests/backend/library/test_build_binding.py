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

from backend.library import games  # noqa: E402
from backend.hermes import host as hermes_host  # noqa: E402
from backend.broker.broker import Broker, Denied, Lane  # noqa: E402
from tests.backend.library.test_games import make_project  # noqa: E402

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
        self.registry.bind(self.game, "st-2", PROFILE, replace=True)   # the old one was deleted
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
        entry = self.registry.observe("project_create", {"select": True}, {"projectRoot": str(made)}, False,
                                      lane_root=None, conversation_id="st-new", profile=PROFILE)
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
        self.registry.observe("project_select", {}, {"projectRoot": str(self.root)}, False,
                              lane_root=None, conversation_id="st-new", profile=PROFILE)
        self.assertIsNone(self.registry.get(self.game).get("session"))
        self.assertEqual(self.registry.binding_for(PROFILE, ["st-new"])[0], "pending")

    def test_another_profiles_conversation_is_never_replaced(self):
        self.registry.bind(self.game, "st-1", "/profiles/other")
        with self.assertRaises(games.BindingError) as refused:
            self.registry.bind(self.game, "st-2", PROFILE, replace=True)
        self.assertEqual(refused.exception.code, "OTHER_PROFILE")

    def test_a_pending_conversation_keeps_its_place_after_compression(self):
        self.registry.build_start("st-new", PROFILE)
        self.registry.note_alias(PROFILE, "st-new", "st-new-rotated")
        self.assertEqual(self.registry.binding_for(PROFILE, ["st-new-rotated"])[0], "pending")

    def test_stop_editing_frees_the_game_and_only_its_own_conversation(self):
        self.registry.bind(self.game, "st-1", PROFILE)
        self.assertFalse(self.registry.unbind(self.game, "st-old", PROFILE))       # a stale page
        self.assertEqual(self.registry.get(self.game)["session"]["storedId"], "st-1")
        self.assertTrue(self.registry.unbind(self.game, "st-1", PROFILE))
        self.assertIsNone(self.registry.get(self.game).get("session"))
        self.assertEqual(self.registry.binding_for(PROFILE, ["st-1"]), (None, None))
        self.assertFalse(self.registry.unbind(self.game, "st-1", PROFILE))         # already free
        self.registry.bind(self.game, "st-2", PROFILE)                             # editable again, no replace
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
    broker = Broker.__new__(Broker)
    broker.lanes, broker.writer_leases = {}, {}
    broker.table_lock = threading.RLock()
    broker.games = registry
    broker.events = []
    broker.trace = lambda **record: broker.events.append(record)
    return broker


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

    def test_a_new_game_conversation_makes_a_project_but_cannot_take_a_bound_game(self):
        self.registry.build_start("st-new", PROFILE)
        self.guard("st-new", "project_create", {"name": "Z", "destinationPath": str(self.base / "z")})
        self.guard("st-new", "project_select", {"projectPath": str(self.comet)})   # unbound: it may adopt it
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
        self.broker.select_bound_game(lane, engine)                 # already selected: nothing more
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
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        home = self.base / "hermes" / "profiles" / "studio" / "plugin-data" / "hermretro"
        home.mkdir(parents=True)
        self.patches = [
            mock.patch.dict(os.environ, {"HERMRETRO_LIBRARY_DIR": str(self.base / "lib"),
                                         "HERMRETRO_GAMES_DIR": str(self.base / "games"),
                                         "HERMRETRO_RUNTIME_DIR": str(self.base / "run")}),
            mock.patch.object(hermes_host, "_data_dir", lambda: home),
            mock.patch.object(hermes_host, "try_connect", lambda _dir: (None, None)),
        ]
        for patch in self.patches:
            patch.start()
        self.rpc = hermes_host.rpc_build(mock.Mock())
        self.frog = make_project(self.base, "Frog Post")
        hermes_host._registry().upsert(str(self.frog))
        self.game = games.game_id(self.frog)

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.tmp.cleanup()

    def test_start_bind_and_the_games_list(self):
        self.assertTrue(self.rpc({"action": "start", "stored": "st-new", "name": "Lamplight"})["ok"])
        answer = self.rpc({"action": "bind", "game": self.game, "stored": "st-frog"})
        self.assertEqual((answer["ok"], answer["session"]["storedId"]), (True, "st-frog"))
        again = self.rpc({"action": "bind", "game": self.game, "stored": "st-other"})
        self.assertEqual((again["ok"], again["code"]), (False, "HAS_CONVERSATION"))
        listed = hermes_host.rpc_games(mock.Mock(get_config=lambda key, default=None: default))({})
        self.assertEqual(listed["games"][0]["session"]["storedId"], "st-frog")
        self.assertIs(listed["games"][0]["session"]["thisProfile"], True)
        self.assertNotIn("profile", listed["games"][0]["session"])
        self.assertIsNone(listed["games"][0]["session"]["exists"])     # no session database in this test
        self.assertEqual([item["storedId"] for item in listed["pending"]], ["st-new"])
        self.assertTrue(self.rpc({"action": "cancel", "stored": "st-new"})["cancelled"])
        self.assertTrue(self.rpc({"action": "unbind", "game": self.game, "stored": "st-frog"})["unbound"])
        self.assertIsNone(hermes_host.build_context(session_id="st-frog"))
        self.assertEqual(self.rpc({"action": "unbind", "game": "nope", "stored": "st-frog"})["code"], "INVALID")
        self.assertFalse(self.rpc({"action": "nope"})["ok"])

    def test_each_turn_of_a_games_conversation_is_told_its_game(self):
        self.rpc({"action": "bind", "game": self.game, "stored": "st-frog"})
        context = hermes_host.build_context(session_id="st-frog")["context"]
        self.assertIn("Frog Post", context)
        self.assertIn(str(self.frog), context)
        self.rpc({"action": "start", "stored": "st-new", "name": "Lamplight"})
        context = hermes_host.build_context(session_id="st-new", is_first_turn=True)["context"]
        self.assertIn("chromatic_project_create", context)
        self.assertIn('called "Lamplight"', context)
        self.assertIn("chromatic_present_game", context)
        self.assertNotIn("their message is the idea", hermes_host.build_context(session_id="st-new")["context"])
        self.rpc({"action": "start", "stored": "st-plan", "plan": True})
        self.assertIn("hermretro:game-planning",
                      hermes_host.build_context(session_id="st-plan", is_first_turn=True)["context"])
        self.assertIsNone(hermes_host.build_context(session_id="plain-chat"))
        self.assertIsNone(hermes_host.build_context())

PNG_1x1 = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000020000000100806000000"
                        "1f15c4890000000d49444154789c636001000000050001a5f645400000000049454e44ae426082")


class AssetRpc(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.home = self.base / "plugin-data"
        (self.home / "frames").mkdir(parents=True)
        self.patches = [
            mock.patch.dict(os.environ, {"HERMRETRO_LIBRARY_DIR": str(self.base / "lib"),
                                         "HERMRETRO_RUNTIME_DIR": str(self.base / "run")}),
            mock.patch.object(hermes_host, "_data_dir", lambda: self.home),
        ]
        for patch in self.patches:
            patch.start()
        self.frog = make_project(self.base, "Frog Post")
        hermes_host._registry().upsert(str(self.frog))
        self.asset = hermes_host.rpc_asset(mock.Mock())

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.tmp.cleanup()

    def test_a_sprite_in_a_game_comes_with_its_size_and_frames(self):
        sprite = self.frog / "assets" / "sprites" / "frog.png"
        sprite.parent.mkdir(parents=True, exist_ok=True)
        sprite.write_bytes(PNG_1x1)
        (sprite.parent / "frog.png.gbsres").write_text(json.dumps({"name": "Frog", "canvasWidth": 16, "canvasHeight": 16, "animSpeed": 15}))
        answer = self.asset({"path": str(sprite)})
        self.assertTrue(answer["ok"], answer)
        self.assertEqual((answer["width"], answer["height"], answer["kind"], answer["relative"]), (32, 16, "sprite", "assets/sprites/frog.png"))
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
        self.assertEqual(self.asset({"path": str(link)})["code"], "OUTSIDE", "a link out of the game is followed, then refused")
        text = self.frog / "notes.txt"
        text.write_text("hi")
        self.assertEqual(self.asset({"path": str(text)})["code"], "NOT_IMAGE")
        self.assertEqual(self.asset({"path": "assets/frog.png"})["code"], "INVALID")
        self.assertEqual(self.asset({"path": str(self.frog / "gone.png")})["code"], "MISSING")

    def test_large_images_are_not_sent(self):
        big = self.frog / "big.png"
        big.write_bytes(PNG_1x1 + b"\0" * (hermes_host.ASSET_MAX_BYTES + 1))
        self.assertEqual(self.asset({"path": str(big)})["code"], "TOO_LARGE")


if __name__ == "__main__":
    unittest.main()

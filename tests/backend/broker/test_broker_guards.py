"""Races and failure paths an independent review found: each test fails on the code before the fix."""

import json
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.broker.broker import Broker, Denied, Lane  # noqa: E402 - the repository root goes on sys.path first


class FakeEngine:
    def __init__(self):
        self.closed = False

    def alive(self):
        return not self.closed

    def close(self, grace=None):
        self.closed = True


def bare_broker():
    broker = Broker.__new__(Broker)  # no sockets, no engine: only the coordination state
    broker.lanes, broker.writer_leases = {}, {}
    broker.table_lock = threading.RLock()
    broker.writer_handoff_idle, broker.lane_idle = 45, 1800
    broker.events = []
    broker.trace = lambda **record: broker.events.append(record)
    return broker


def lane(broker, name, root="/games/one"):
    made = Lane(("profile", name))
    made.selected_root = root
    broker.lanes[made.owner] = made
    return made


class WriterLease(unittest.TestCase):
    def test_a_quiet_holder_that_starts_writing_keeps_the_lease(self):
        broker = bare_broker()
        a, b = lane(broker, "a"), lane(broker, "b")
        broker.acquire_writer(a)
        a.last_write = time.monotonic() - 600  # quiet for ten minutes, nothing in flight
        broker.acquire_writer(a)  # A begins a write; the in-flight count is not raised yet
        with self.assertRaises(Denied) as refused:
            broker.acquire_writer(b)  # B arrives in that gap
        self.assertEqual(refused.exception.code, "PROJECT_WRITER_BUSY")
        self.assertEqual(broker.writer_leases["/games/one"], a.owner)

    def test_a_holder_that_really_is_quiet_still_hands_over(self):
        broker = bare_broker()
        a, b = lane(broker, "a"), lane(broker, "b")
        broker.acquire_writer(a)
        a.last_write = time.monotonic() - 600
        broker.acquire_writer(b)
        self.assertEqual(broker.writer_leases["/games/one"], b.owner)
        with self.assertRaises(Denied):
            broker.acquire_writer(a)  # and B is now protected the same way


class IdleClose(unittest.TestCase):
    def test_an_idle_worker_is_closed_and_its_lease_released(self):
        broker = bare_broker()
        a = lane(broker, "a")
        a.engine, a.last_used = FakeEngine(), time.monotonic() - 3600
        broker.acquire_writer(a)
        self.assertTrue(broker.close_lane_if_idle(a))
        self.assertTrue(a.engine.closed)
        self.assertNotIn("/games/one", broker.writer_leases)

    def test_a_call_that_arrived_first_keeps_its_worker(self):
        broker = bare_broker()
        a = lane(broker, "a")
        a.engine, a.last_used = FakeEngine(), time.monotonic() - 3600
        a.last_used = time.monotonic()  # what a call does before it fetches the engine
        self.assertFalse(broker.close_lane_if_idle(a))
        self.assertFalse(a.engine.closed)

    def test_work_in_flight_or_a_live_player_is_never_closed(self):
        broker = bare_broker()
        for field in ("inflight", "live_surface"):
            a = lane(broker, field)
            a.engine, a.last_used = FakeEngine(), time.monotonic() - 3600
            setattr(a, field, 1 if field == "inflight" else True)
            self.assertFalse(broker.close_lane_if_idle(a))
            self.assertFalse(a.engine.closed)

    def test_an_engine_preview_nobody_called_for_four_idle_periods_is_closed(self):
        # The user plays in the Studio's own player; an abandoned engine preview would otherwise pin the
        # worker and the project's recording lock forever, blocking every other chat's emulator.
        broker = bare_broker()
        a = lane(broker, "a")
        a.engine, a.live_surface, a.preview_url = FakeEngine(), True, "http://127.0.0.1:1/x/"
        a.last_used = time.monotonic() - broker.lane_idle * 4 - 1
        self.assertTrue(broker.close_lane_if_idle(a))
        self.assertTrue(a.engine.closed)
        self.assertFalse(a.live_surface)
        self.assertIsNone(a.preview_url)


class Selection(unittest.TestCase):
    def test_the_selected_root_can_be_taken_from_the_select_result(self):
        broker = bare_broker()
        a = lane(broker, "a", root=None)
        broker._apply_selection(a, {"projectRoot": "/games/two", "projectPath": "/games/two/project.gbsproj"})
        self.assertEqual(a.selected_root, "/games/two")
        self.assertEqual(broker.writer_leases["/games/two"], a.owner)

    def test_creating_a_project_without_selecting_it_does_not_change_the_selection(self):
        from backend.broker.broker import selects_project

        self.assertTrue(selects_project("project_select", {"projectPath": "/games/two"}))
        self.assertTrue(selects_project("project_create_blank", {"select": True}))
        self.assertFalse(selects_project("project_create", {}))  # select defaults to false
        self.assertFalse(selects_project("project_create_blank", {"select": False}))
        self.assertFalse(selects_project("rom_build", {"select": True}))


class ScriptedEngine:
    """Answers web_preview / web_preview_close from a script, and records what was called."""

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def call_tool(self, tool, arguments, timeout=None):
        self.calls.append(tool)
        return self.answers.pop(0)


def opened(url):
    return {"content": [], "structuredContent": {"success": True, "url": url}}


FAILED = {
    "content": [],
    "structuredContent": {"success": False, "error": "Browser recording close acknowledgement is UNKNOWN."},
}
CLOSED = {"content": [], "structuredContent": {"success": True}}


class LivePlayer(unittest.TestCase):
    """The preview a real session got stuck in: the engine could not replace a running preview, kept
    the old one bound to the previous build, and the player then refused to install to the device."""

    def test_a_preview_that_cannot_be_replaced_is_closed_and_opened_fresh(self):
        broker = bare_broker()
        a = lane(broker, "a")
        a.preview_url = "http://127.0.0.1:1/old/"
        engine = ScriptedEngine(FAILED, CLOSED, opened("http://127.0.0.1:2/new/"))
        player = broker.refresh_player(a, engine)
        self.assertEqual(engine.calls, ["web_preview", "web_preview_close", "web_preview"])
        self.assertEqual((player["ready"], player["url"], player["moved"]), (True, "http://127.0.0.1:2/new/", True))
        self.assertEqual(a.preview_url, "http://127.0.0.1:2/new/")

    def test_if_it_cannot_be_closed_either_the_player_is_reported_stale(self):
        broker = bare_broker()
        a = lane(broker, "a")
        a.preview_url = "http://127.0.0.1:1/old/"
        engine = ScriptedEngine(FAILED, FAILED)
        player = broker.refresh_player(a, engine)
        self.assertEqual((player["ready"], player["stale"]), (False, True))
        self.assertIn("UNKNOWN", player["error"])
        self.assertEqual(engine.calls, ["web_preview", "web_preview_close"])

    def test_an_ordinary_refresh_keeps_its_address_and_closes_nothing(self):
        broker = bare_broker()
        a = lane(broker, "a")
        a.preview_url = "http://127.0.0.1:1/same/"
        engine = ScriptedEngine(opened("http://127.0.0.1:1/same/"))
        player = broker.refresh_player(a, engine)
        self.assertEqual((player["ready"], player["moved"], player["first"]), (True, False, False))
        self.assertEqual(engine.calls, ["web_preview"])

    def test_a_first_preview_that_fails_leaves_nothing_stale(self):
        broker = bare_broker()
        a = lane(broker, "a")
        player = broker.refresh_player(a, ScriptedEngine(FAILED))
        self.assertEqual((player["ready"], player["stale"]), (False, False))

    def build_result(self, player):
        from backend.hermes import results

        response = {"ok": True, "result": {"content": [], "structuredContent": {"success": True}}, "player": player}
        return json.loads(results.encode(response, "chromatic_rom_build", None, False))

    def test_the_agent_is_told_when_the_player_is_out_of_date(self):
        payload = self.build_result({"ready": False, "error": "close acknowledgement is UNKNOWN", "stale": True})
        self.assertEqual(payload["player"]["showsThisBuild"], False)
        for phrase in (
            "could NOT be updated",
            "Do not claim the new build is in a player",
            "Install on Chromatic",
            "chromatic_web_preview_close",
            "chromatic_present_game",
        ):
            self.assertIn(phrase, payload["nextStep"])

    def test_a_moved_engine_preview_changes_nothing_for_the_agent(self):
        # The user plays in the Studio emulator, which reads the web copy from disk: the engine's own
        # preview address is never offered, so a restarted preview needs no reopening.
        payload = self.build_result({"ready": True, "url": "http://127.0.0.1:2/new/", "first": False, "moved": True})
        self.assertNotIn("url", payload["player"])
        self.assertIn("call chromatic_present_game", payload["nextStep"])
        self.assertNotIn("http://127.0.0.1:2/new/", json.dumps(payload))


class Delivery(unittest.TestCase):
    RESPONSE = {"ok": True, "result": {"content": [], "structuredContent": {"success": True}}}

    def deliver(self, encode):
        with (
            mock.patch.object(hermes_host, "_data_dir", return_value=Path("/nonexistent")),
            mock.patch.object(hermes_host, "_attach_images", return_value=False),
        ):
            return json.loads(hermes_host._deliver(self.RESPONSE, "chromatic_rom_build", encode=encode))

    def test_a_result_whose_images_cannot_be_saved_is_still_delivered(self):
        def encode(response, name, image_dir, attach):
            if image_dir is not None:
                raise OSError(28, "No space left on device")
            return json.dumps({"success": True})

        payload = self.deliver(encode)
        self.assertEqual(payload["success"], True)
        self.assertIn("The tool ran", payload["deliveryProblem"])

    def test_a_call_that_never_ran_is_not_reported_as_run(self):
        def encode(response, name, image_dir, attach):
            raise ValueError("broken")

        with (
            mock.patch.object(hermes_host, "_data_dir", return_value=Path("/nonexistent")),
            mock.patch.object(hermes_host, "_attach_images", return_value=False),
        ):
            denied = json.loads(hermes_host._deliver({"denied": {"code": "X", "message": "no"}}, "t", encode=encode))
        self.assertEqual(denied["dispatched"], False)

    def test_if_nothing_can_be_delivered_the_model_still_learns_the_tool_ran(self):
        def encode(response, name, image_dir, attach):
            raise ValueError("broken")

        payload = self.deliver(encode)
        self.assertEqual((payload["code"], payload["dispatched"]), ("RESULT_NOT_DELIVERED", True))
        self.assertIn("do not simply repeat it", payload["guidance"])


if __name__ == "__main__":
    unittest.main()

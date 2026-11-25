"""Races and failure paths an independent review found: each test fails on the code before the fix."""

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tests.backend.broker.bare import bare_broker  # noqa: E402 - the repository root goes on sys.path first
from backend.broker.broker import Denied, Lane  # noqa: E402 - the repository root goes on sys.path first


class FakeEngine:
    def __init__(self):
        self.closed = False

    def alive(self):
        return not self.closed

    def close(self, grace=None):
        self.closed = True


def guards_broker():
    return bare_broker(writer_handoff_idle=45, lane_idle=1800)


def lane(broker, name, root="/games/one"):
    made = Lane(("profile", name))
    made.selected_root = root
    broker.lanes[made.owner] = made
    return made


class WriterLease(unittest.TestCase):
    def test_a_quiet_holder_that_starts_writing_keeps_the_lease(self):
        broker = guards_broker()
        a, b = lane(broker, "a"), lane(broker, "b")
        broker.acquire_writer(a)
        a.last_write = time.monotonic() - 600  # quiet for ten minutes, nothing in flight
        broker.acquire_writer(a)  # A begins a write; the in-flight count is not raised yet
        with self.assertRaises(Denied) as refused:
            broker.acquire_writer(b)  # B arrives in that gap
        self.assertEqual(refused.exception.code, "PROJECT_WRITER_BUSY")
        self.assertEqual(broker.writer_leases["/games/one"], a.owner)

    def test_a_holder_that_really_is_quiet_still_hands_over(self):
        broker = guards_broker()
        a, b = lane(broker, "a"), lane(broker, "b")
        broker.acquire_writer(a)
        a.last_write = time.monotonic() - 600
        broker.acquire_writer(b)
        self.assertEqual(broker.writer_leases["/games/one"], b.owner)
        with self.assertRaises(Denied):
            broker.acquire_writer(a)  # and B is now protected the same way


class IdleClose(unittest.TestCase):
    def test_an_idle_worker_is_closed_and_its_lease_released(self):
        broker = guards_broker()
        a = lane(broker, "a")
        a.engine, a.last_used = FakeEngine(), time.monotonic() - 3600
        broker.acquire_writer(a)
        self.assertTrue(broker.close_lane_if_idle(a))
        self.assertTrue(a.engine.closed)
        self.assertNotIn("/games/one", broker.writer_leases)

    def test_a_call_that_arrived_first_keeps_its_worker(self):
        broker = guards_broker()
        a = lane(broker, "a")
        a.engine, a.last_used = FakeEngine(), time.monotonic() - 3600
        a.last_used = time.monotonic()  # what a call does before it fetches the engine
        self.assertFalse(broker.close_lane_if_idle(a))
        self.assertFalse(a.engine.closed)

    def test_work_in_flight_or_a_live_player_is_never_closed(self):
        broker = guards_broker()
        for field in ("inflight", "live_surface"):
            a = lane(broker, field)
            a.engine, a.last_used = FakeEngine(), time.monotonic() - 3600
            setattr(a, field, 1 if field == "inflight" else True)
            self.assertFalse(broker.close_lane_if_idle(a))
            self.assertFalse(a.engine.closed)

    def test_an_engine_preview_nobody_called_for_four_idle_periods_is_closed(self):
        # The user plays in the Studio's own player; an abandoned engine preview would otherwise pin the
        # worker and the project's recording lock forever, blocking every other chat's emulator.
        broker = guards_broker()
        a = lane(broker, "a")
        a.engine, a.live_surface, a.preview_url = FakeEngine(), True, "http://127.0.0.1:1/x/"
        a.last_used = time.monotonic() - broker.lane_idle * 4 - 1
        self.assertTrue(broker.close_lane_if_idle(a))
        self.assertTrue(a.engine.closed)
        self.assertFalse(a.live_surface)
        self.assertIsNone(a.preview_url)


class Selection(unittest.TestCase):
    def test_the_selected_root_can_be_taken_from_the_select_result(self):
        broker = guards_broker()
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
        broker = guards_broker()
        a = lane(broker, "a")
        a.preview_url = "http://127.0.0.1:1/old/"
        engine = ScriptedEngine(FAILED, CLOSED, opened("http://127.0.0.1:2/new/"))
        player = broker.refresh_player(a, engine)
        self.assertEqual(engine.calls, ["web_preview", "web_preview_close", "web_preview"])
        self.assertEqual((player["ready"], player["url"], player["moved"]), (True, "http://127.0.0.1:2/new/", True))
        self.assertEqual(a.preview_url, "http://127.0.0.1:2/new/")

    def test_if_it_cannot_be_closed_either_the_player_is_reported_stale(self):
        broker = guards_broker()
        a = lane(broker, "a")
        a.preview_url = "http://127.0.0.1:1/old/"
        engine = ScriptedEngine(FAILED, FAILED)
        player = broker.refresh_player(a, engine)
        self.assertEqual((player["ready"], player["stale"]), (False, True))
        self.assertIn("UNKNOWN", player["error"])
        self.assertEqual(engine.calls, ["web_preview", "web_preview_close"])

    def test_an_ordinary_refresh_keeps_its_address_and_closes_nothing(self):
        broker = guards_broker()
        a = lane(broker, "a")
        a.preview_url = "http://127.0.0.1:1/same/"
        engine = ScriptedEngine(opened("http://127.0.0.1:1/same/"))
        player = broker.refresh_player(a, engine)
        self.assertEqual((player["ready"], player["moved"], player["first"]), (True, False, False))
        self.assertEqual(engine.calls, ["web_preview"])

    def test_a_copy_that_plays_another_rom_is_not_reported_ready(self):
        from tests.support import isolated_home, make_project

        root = make_project(isolated_home(self).base, "Other Rom")
        broker = guards_broker()
        a = lane(broker, "a", root=str(root))
        self.assertTrue(broker.refresh_player(a, ScriptedEngine(opened("http://127.0.0.1:1/x/")))["ready"])
        (root / "build" / "game.gbc").write_bytes(b"\7" * 512)  # the web copy still plays the earlier bytes
        player = broker.refresh_player(a, ScriptedEngine(opened("http://127.0.0.1:1/x/")))
        self.assertEqual(
            (player["ready"], player["error"]),
            (False, "The playable copy was made, but it does not play this build's ROM."),
        )

    def test_a_first_preview_that_fails_leaves_nothing_stale(self):
        broker = guards_broker()
        a = lane(broker, "a")
        player = broker.refresh_player(a, ScriptedEngine(FAILED))
        self.assertEqual((player["ready"], player["stale"]), (False, False))


if __name__ == "__main__":
    unittest.main()


class ActivityFrame(unittest.TestCase):
    def remember(self, made, frame, data):
        result = {
            "structuredContent": {"frame": frame},
            "content": [{"type": "image", "mimeType": "image/png", "data": data}],
        }
        made.remember("emulator_step", "tool", result, 0.1)

    def test_an_image_too_large_to_keep_moves_the_frame_on_without_a_picture(self):
        made = Lane(("profile", "chat"))
        self.remember(made, 10, "small")
        self.remember(made, 20, "x" * 400_000)  # a scaled contact sheet
        self.assertEqual((made.last_frame["frame"], made.last_frame["data"]), (20, None))

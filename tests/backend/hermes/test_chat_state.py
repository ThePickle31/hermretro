"""backend/hermes/chat_state.py: after a context compaction, the chat's next engine result says where it stands.

Run alone: python -m unittest tests.backend.hermes.test_chat_state
"""

import base64
import json
import unittest
from unittest import mock

from backend.hermes import chat_state, host, results
from tests.support import FakeBrokerClient, isolated_home

BUILD_SHA = "1070263e2c99a7e3ad0441e86be79004703673147742678fd3563ffa84181782"
OLDER_SHA = "ae25df96ab60a9107fa8bfd5be4b52bc3a57d3f85870a101a66a20890751b06c"
ROM = "/games/Lantern/build/game.gbc"
RECORDING = "/games/Lantern/artifacts/playtests/session-1"
SESSION = "a" * 32
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"fake-image-bytes").decode()


def answered(structured, *, error=False, content=None) -> dict:
    """A broker response for an engine result that reached the engine."""
    result = {"structuredContent": structured, "content": content or []}
    return {"ok": True, "dispatched": True, "result": {**result, "isError": True} if error else result}


def recording(status="recording", branch="branch-0001", path=RECORDING, session=SESSION) -> dict:
    """A recording as the engine's worker reports one (``Recording.snapshot``)."""
    return {"recordingPath": path, "sessionId": session, "status": status, "branchId": branch, "frame": 180}


class ChatState(unittest.TestCase):
    def setUp(self):
        isolated_home(self)
        chat_state.reset()
        self.addCleanup(chat_state.reset)
        self.project = mock.Mock(return_value=None)

    def engine(self, tool, structured=None, args=None, session="s1", conversation="c1", response=None):
        return chat_state.engine_result(
            tool,
            args or {},
            response or answered(structured or {}),
            session_id=session,
            conversation_id=conversation,
            project=self.project,
        )

    def viewed(self, args, session="s1", conversation="c1", status="ok"):
        chat_state.observe(
            tool_name="skill_view", args=args, status=status, session_id=session, conversation_id=conversation
        )

    def note(self, tool="emulator_observe", structured=None, **options) -> str:
        text = self.engine(tool, structured, **options)
        self.assertIsNotNone(text, "the note is delivered")
        return text

    def played(self):
        self.viewed({"name": "hermretro:authoring"})
        self.viewed({"name": "hermretro:authoring", "file_path": "references/event-cookbook.md"})
        self.engine("project_inspect", {"projectRoot": "/games/Lantern"})
        self.engine("rom_build", {"success": True, "rom": {"path": ROM, "sha256": BUILD_SHA}})
        self.engine("emulator_run", {"romPath": ROM, "romSha256": BUILD_SHA, "frame": 180, "recording": recording()})
        self.engine(
            "emulator_step",
            {
                "frame": 5620,
                "recordingSpan": {"recordingPath": RECORDING, "sessionId": SESSION, "branchId": "branch-0001"},
            },
        )

    def test_nothing_is_said_until_a_compaction(self):
        self.played()
        self.assertIsNone(self.engine("emulator_observe", {"frame": 5620}))

    def test_the_first_engine_result_after_a_compaction_says_where_the_chat_stands_once(self):
        self.played()
        chat_state.compacted(session_id="s1", old_session_id="", kind="summarize")
        text = self.note("emulator_observe", {"frame": 5620})
        for part in (
            "Project: /games/Lantern.",
            f"Last build: {ROM} (sha256 {BUILD_SHA[:12]}…).",
            f"Emulator: frame 5620 of {ROM}",
            f"Recording: {RECORDING} (session {SESSION}, branch-0001, recording).",
            "hermretro:authoring, hermretro:authoring references/event-cookbook.md",
        ):
            self.assertIn(part, text)
        self.assertNotIn("not the last build", text)
        self.assertIsNone(self.engine("emulator_observe", {"frame": 5620}))

    def test_the_note_describes_the_result_that_carries_it(self):
        self.played()
        chat_state.compacted(session_id="s1", kind="summarize")
        text = self.note("emulator_close", {"closed": True})
        self.assertNotIn("Emulator", text)
        self.assertIn(f"Recording: {RECORDING} (session {SESSION}, branch-0001, stopped).", text)
        chat_state.compacted(session_id="s1", kind="summarize")
        self.assertIn("frame 120 of", self.note("emulator_run", {"romPath": ROM, "romSha256": BUILD_SHA, "frame": 120}))

    def test_a_result_that_did_not_reach_the_engine_leaves_the_note_due(self):
        self.played()
        chat_state.compacted(session_id="s1", kind="summarize")
        denied = {"ok": False, "denied": {"code": "LEASE_REQUIRED", "message": "No."}}
        self.assertIsNone(self.engine("emulator_step", response=denied))
        self.assertIn("frame 5620", self.note())

    def test_an_engine_error_still_carries_the_note_and_changes_nothing(self):
        self.played()
        chat_state.compacted(session_id="s1", kind="summarize")
        text = self.note("emulator_close", response=answered({"code": "BUSY"}, error=True))
        self.assertIn("Emulator: frame 5620", text)

    def test_the_handler_leads_a_result_with_images_with_the_note(self):
        self.played()
        chat_state.compacted(session_id="s1", kind="summarize")
        step = answered(
            {
                "frame": 6000,
                "recordingSpan": {"recordingPath": RECORDING, "sessionId": SESSION, "branchId": "branch-0001"},
            },
            content=[{"type": "image", "mimeType": "image/png", "data": PNG}],
        )
        ctx = mock.Mock()
        ctx.get_config = lambda key, default=None: default
        with (
            mock.patch.object(host, "ensure_broker", lambda **_: FakeBrokerClient(step)),
            mock.patch.object(host, "_attach_images", lambda: True),
            mock.patch.object(host, "_chat_project", return_value="/games/Lantern 2") as chat_project,
        ):
            delivered = host.make_tool_handler(ctx, {"name": "emulator_step"})(
                {"buttons": ["right"], "frames": 380}, session_id="s1", conversation_id="c1"
            )
        self.assertTrue(delivered["_multimodal"])
        payload = json.loads(delivered["content"][0]["text"])
        self.assertEqual(next(iter(payload)), results.CONTEXT_KEY, "first, so a shortened result still holds it")
        self.assertIn("Emulator: frame 6000 of", payload[results.CONTEXT_KEY])
        self.assertIn("Project: /games/Lantern 2.", payload[results.CONTEXT_KEY])
        chat_project.assert_called_with("c1", "s1")
        self.assertEqual(delivered["content"][1]["image_url"]["url"], "data:image/png;base64," + PNG)

    def test_the_chat_project_hermretro_knows_now_wins(self):
        self.played()
        self.project.return_value = "/games/Lantern 2"
        chat_state.compacted(session_id="s1", kind="summarize")
        self.assertIn("Project: /games/Lantern 2.", self.note())

    def test_a_rotated_session_keeps_its_chat(self):
        self.played()
        chat_state.compacted(session_id="s2", old_session_id="s1", kind="summarize")
        self.assertIn("frame 5620", self.note(session="s2", conversation=""))

    def test_a_delegated_subagent_never_reads_adds_to_or_marks_its_parents_state(self):
        self.played()
        chat_state.child_started(child_session_id="k1")
        # The child reports its parent's conversation id, as Hermes's delegate tool gives it.
        self.viewed({"name": "hermretro:rom-debugging"}, session="k1")
        self.engine("project_inspect", {"projectRoot": "/games/Other"}, session="k1")
        chat_state.compacted(session_id="k1", kind="summarize")
        child = self.note(session="k1")
        self.assertIn("/games/Other", child)
        self.assertNotIn("Lantern", child)
        self.assertIsNone(self.engine("emulator_observe", {"frame": 5620}), "the parent's note was never due")
        chat_state.compacted(session_id="s1", kind="summarize")
        parent = self.note()
        self.assertIn("Project: /games/Lantern.", parent)
        self.assertNotIn("rom-debugging", parent)
        chat_state.child_stopped(child_session_id="k1")
        self.assertNotIn("k1", chat_state._chats)
        self.assertNotIn("k1", chat_state._keys)

    def test_a_fresh_unrecorded_boot_clears_the_recording(self):
        self.played()
        self.engine("emulator_run", {"romPath": ROM, "romSha256": BUILD_SHA, "frame": 120}, args={"restart": True})
        chat_state.compacted(session_id="s1", kind="summarize")
        text = self.note()
        self.assertIn(f"Emulator: frame 120 of {ROM}", text)
        self.assertNotIn("Recording", text)

    def test_reading_an_older_attempt_leaves_the_live_one(self):
        self.played()
        older = recording("failed", "branch-0003", "/games/Lantern/artifacts/playtests/session-0", "b" * 32)
        self.engine("emulator_recording", older, args={"action": "status", "recordingPath": older["recordingPath"]})
        self.engine("emulator_recording", {**older, "actions": []}, args={"action": "export"})
        chat_state.compacted(session_id="s1", kind="summarize")
        text = self.note()
        self.assertIn(f"Recording: {RECORDING} (session {SESSION}, branch-0001, recording).", text)
        self.assertNotIn("session-0", text)
        # The live attempt's own status is taken (it can fail at a recording limit).
        self.engine("emulator_recording", recording("failed"), args={"action": "status"})
        chat_state.compacted(session_id="s1", kind="summarize")
        self.assertIn("branch-0001, failed).", self.note())

    def test_a_stopped_recording_keeps_what_resumes_it(self):
        self.played()
        self.engine("emulator_recording", recording("cancelled"), args={"action": "stop", "outcome": "cancelled"})
        chat_state.compacted(session_id="s1", kind="summarize")
        self.assertIn(f"Recording: {RECORDING} (session {SESSION}, branch-0001, cancelled).", self.note())

    def test_a_replay_pairs_its_hash_with_the_rom_it_was_given(self):
        self.played()
        replayed = {
            "romSha256": OLDER_SHA,
            "frame": 900,
            "recording": {"recordingPath": RECORDING + "-replay", "sessionId": "c" * 32, "branchId": "branch-0001"},
        }
        self.engine("emulator_replay", replayed, args={"romPath": "build/game.gbc", "recordingPath": RECORDING})
        chat_state.compacted(session_id="s1", kind="summarize")
        text = self.note()
        self.assertIn(f"Emulator: frame 900 of build/game.gbc (sha256 {OLDER_SHA[:12]}…), not the last build.", text)
        self.assertIn(f"Recording: {RECORDING}-replay (session {'c' * 32}, branch-0001, recording).", text)
        # finishRecording stopped it in the same call.
        replayed["recording"] = {**replayed["recording"], "status": "stopped", "outcome": "passed"}
        self.engine("emulator_replay", replayed, args={"romPath": "build/game.gbc", "finishRecording": True})
        chat_state.compacted(session_id="s1", kind="summarize")
        self.assertIn(f"Recording: {RECORDING}-replay (session {'c' * 32}, branch-0001, stopped).", self.note())
        self.engine("emulator_replay", {"romSha256": OLDER_SHA, "frame": 40}, args={"recording": False})
        chat_state.compacted(session_id="s1", kind="summarize")
        text = self.note()
        self.assertIn(f"Emulator: frame 40 of a ROM (sha256 {OLDER_SHA[:12]}…)", text)
        self.assertNotIn(ROM + " (sha256 " + OLDER_SHA[:12], text)
        self.assertNotIn("Recording", text)

    def test_a_checkpoint_restore_is_the_whole_session_and_a_save_changes_nothing(self):
        self.played()
        self.engine(
            "emulator_checkpoint", {"checkpointId": "x", "frame": 1, "branchId": "branch-0009"}, args={"action": "save"}
        )
        chat_state.compacted(session_id="s1", kind="summarize")
        self.assertIn("frame 5620", self.note())
        restored = {"romPath": ROM, "romSha256": BUILD_SHA, "frame": 3000, "recording": recording(branch="branch-0002")}
        self.engine("emulator_checkpoint", restored, args={"action": "restore", "checkpointId": "x"})
        chat_state.compacted(session_id="s1", kind="summarize")
        text = self.note()
        self.assertIn("frame 3000", text)
        self.assertIn("branch-0002, recording).", text)

    def test_an_emulator_on_an_older_build_is_named(self):
        self.played()
        self.engine("rom_build", {"success": True, "rom": {"path": ROM, "sha256": OLDER_SHA}})
        chat_state.compacted(session_id="s1", kind="summarize")
        self.assertIn("not the last build", self.note())

    def test_errors_and_failed_calls_change_nothing(self):
        self.engine(
            "rom_build", response=answered({"success": True, "rom": {"path": ROM, "sha256": BUILD_SHA}}, error=True)
        )
        self.viewed({"name": "hermretro:authoring"}, status="error")
        chat_state.compacted(session_id="s1", kind="summarize")
        self.assertIsNone(self.engine("emulator_observe", response=answered("not an object")))

    def test_pruning_old_results_is_not_a_compaction_that_needs_the_note(self):
        self.played()
        chat_state.compacted(session_id="s1", kind=chat_state.PRUNE_ONLY)
        self.assertIsNone(self.engine("emulator_observe", {"frame": 5620}))

    def test_chats_are_kept_apart_and_bounded(self):
        self.played()
        self.engine("project_inspect", {"projectRoot": "/games/Other"}, session="t1", conversation="d1")
        chat_state.compacted(session_id="t1", kind="summarize")
        self.assertIsNone(self.engine("emulator_observe"))
        text = self.note(session="t1", conversation="d1")
        self.assertIn("/games/Other", text)
        self.assertNotIn("Lantern", text)
        for number in range(chat_state.MAX_CHATS + 5):
            self.viewed({"name": "x"}, session=f"n{number}", conversation=f"m{number}")
        self.assertLessEqual(len(chat_state._chats), chat_state.MAX_CHATS)
        self.assertLessEqual(len(chat_state._keys), chat_state.MAX_CHATS)

    def test_a_hook_never_raises(self):
        self.project.side_effect = RuntimeError("broker gone")
        self.played()
        chat_state.compacted(session_id="s1", kind="summarize")
        self.assertIn("Project: /games/Lantern.", self.note())
        self.assertIsNone(self.engine("rom_build", response={"ok": True, "result": object()}))
        chat_state.observe(tool_name="skill_view", args=None, session_id="s1")
        chat_state.compacted(session_id=None)
        chat_state.child_started()
        chat_state.child_stopped()


if __name__ == "__main__":
    unittest.main()

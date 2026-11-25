"""backend/hermes/chat_state.py: after a context compaction, the chat's next tool result says where it stands.

Run alone: python -m unittest tests.backend.hermes.test_chat_state
"""

import json
import unittest
from unittest import mock

from backend.hermes import chat_state, host
from tests.support import isolated_home

BUILD_SHA = "1070263e2c99a7e3ad0441e86be79004703673147742678fd3563ffa84181782"
OLDER_SHA = "ae25df96ab60a9107fa8bfd5be4b52bc3a57d3f85870a101a66a20890751b06c"
ROM = "/games/Lantern/build/game.gbc"


def engine(structured, **extra) -> str:
    return json.dumps({"structuredContent": structured, **extra})


class ChatState(unittest.TestCase):
    def setUp(self):
        isolated_home(self)
        chat_state.reset()
        self.addCleanup(chat_state.reset)
        patcher = mock.patch.object(host, "_chat_project", return_value=None)
        self.chat_project = patcher.start()
        self.addCleanup(patcher.stop)

    def observe(self, tool, structured=None, args=None, session="s1", conversation="c1", **extra):
        result = engine(structured or {}, **extra) if tool.startswith("chromatic_") else "{}"
        chat_state.observe(
            tool_name=tool,
            args=args or {},
            result=result,
            status="ok",
            session_id=session,
            conversation_id=conversation,
        )

    def deliver(self, result='{"ok": true}', session="s1", conversation="c1"):
        return chat_state.deliver(tool_name="terminal", result=result, session_id=session, conversation_id=conversation)

    def played(self):
        self.observe("skill_view", args={"name": "hermretro:authoring"})
        self.observe("skill_view", args={"name": "hermretro:authoring", "file_path": "references/event-cookbook.md"})
        self.observe("chromatic_project_inspect", {"projectRoot": "/games/Lantern"})
        self.observe("chromatic_rom_build", {"success": True, "rom": {"path": ROM, "sha256": BUILD_SHA}})
        self.observe(
            "chromatic_emulator_run",
            {
                "romPath": ROM,
                "romSha256": BUILD_SHA,
                "frame": 180,
                "recording": {"sessionId": "r" * 32, "status": "recording"},
            },
        )
        self.observe("chromatic_emulator_step", {"frame": 5620, "recordingSpan": {"sessionId": "r" * 32}})

    def test_nothing_is_added_until_a_compaction(self):
        self.played()
        self.assertIsNone(self.deliver())

    def test_the_first_result_after_a_compaction_says_where_the_chat_stands_once(self):
        self.played()
        chat_state.compacted(session_id="s1", old_session_id="", kind="summarize")
        note = json.loads(self.deliver())
        self.assertTrue(note["ok"])
        text = note[chat_state.KEY]
        for part in (
            "Project: /games/Lantern.",
            f"Last build: {ROM} (sha256 {BUILD_SHA[:12]}…).",
            f"Emulator: frame 5620 of {ROM}",
            f"Recording: {'r' * 32} (recording).",
            "hermretro:authoring, hermretro:authoring references/event-cookbook.md",
        ):
            self.assertIn(part, text)
        self.assertNotIn("not the last build", text)
        self.assertIsNone(self.deliver())

    def test_text_gains_a_line_and_a_result_with_images_waits(self):
        self.played()
        chat_state.compacted(session_id="s1", kind="summarize")
        envelope = {"_multimodal": True, "content": [], "text_summary": "{}"}
        self.assertIsNone(chat_state.deliver(result=envelope, session_id="s1", conversation_id="c1"))
        delivered = self.deliver("plain output")
        self.assertTrue(delivered.startswith("plain output\n\n[hermretro] The context was just compacted."))

    def test_the_chat_project_hermretro_knows_now_wins(self):
        self.played()
        self.chat_project.return_value = "/games/Lantern 2"
        chat_state.compacted(session_id="s1", kind="summarize")
        self.assertIn("Project: /games/Lantern 2.", json.loads(self.deliver())[chat_state.KEY])
        self.chat_project.assert_called_with("c1", "s1")

    def test_a_rotated_session_keeps_its_chat(self):
        self.played()
        chat_state.compacted(session_id="s2", old_session_id="s1", kind="summarize")
        self.assertIn("frame 5620", json.loads(self.deliver(session="s2", conversation=""))[chat_state.KEY])

    def test_an_emulator_on_an_older_build_is_named_and_closing_forgets_it(self):
        self.played()
        self.observe("chromatic_rom_build", {"success": True, "rom": {"path": ROM, "sha256": OLDER_SHA}})
        chat_state.compacted(session_id="s1", kind="summarize")
        self.assertIn("not the last build", json.loads(self.deliver())[chat_state.KEY])
        self.observe("chromatic_emulator_close", {"closed": True})
        chat_state.compacted(session_id="s1", kind="summarize")
        text = json.loads(self.deliver())[chat_state.KEY]
        self.assertNotIn("Emulator", text)
        self.assertNotIn("Recording", text)

    def test_a_stopped_recording_says_so(self):
        self.played()
        self.observe("chromatic_emulator_recording", {"sessionId": "r" * 32}, args={"action": "stop"})
        chat_state.compacted(session_id="s1", kind="summarize")
        self.assertIn("(stopped)", json.loads(self.deliver())[chat_state.KEY])

    def test_errors_and_failed_calls_change_nothing(self):
        self.observe("chromatic_rom_build", {"success": True, "rom": {"path": ROM, "sha256": BUILD_SHA}}, isError=True)
        chat_state.observe(
            tool_name="chromatic_project_inspect",
            result=engine({"projectRoot": "/elsewhere"}),
            status="error",
            session_id="s1",
            conversation_id="c1",
        )
        chat_state.compacted(session_id="s1", kind="summarize")
        self.assertIsNone(self.deliver())

    def test_pruning_old_results_is_not_a_compaction_that_needs_the_note(self):
        self.played()
        chat_state.compacted(session_id="s1", kind=chat_state.PRUNE_ONLY)
        self.assertIsNone(self.deliver())

    def test_chats_are_kept_apart_and_bounded(self):
        self.played()
        self.observe("chromatic_project_inspect", {"projectRoot": "/games/Other"}, session="t1", conversation="d1")
        chat_state.compacted(session_id="t1", kind="summarize")
        self.assertIsNone(self.deliver())
        text = json.loads(self.deliver(session="t1", conversation="d1"))[chat_state.KEY]
        self.assertIn("/games/Other", text)
        self.assertNotIn("Lantern", text)
        for number in range(chat_state.MAX_CHATS + 5):
            self.observe("skill_view", args={"name": "x"}, session=f"n{number}", conversation=f"m{number}")
        self.assertLessEqual(len(chat_state._chats), chat_state.MAX_CHATS)
        self.assertLessEqual(len(chat_state._keys), chat_state.MAX_CHATS)

    def test_a_hook_never_raises(self):
        self.chat_project.side_effect = RuntimeError("broker gone")
        self.played()
        chat_state.compacted(session_id="s1", kind="summarize")
        self.assertIn("Project: /games/Lantern.", json.loads(self.deliver())[chat_state.KEY])
        chat_state.observe(tool_name="chromatic_rom_build", args=None, result=object(), session_id="s1")
        chat_state.compacted(session_id=None)
        self.assertIsNone(chat_state.deliver(result=None))


if __name__ == "__main__":
    unittest.main()

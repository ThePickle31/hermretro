"""tools/dev/script_model.py: the sandbox's scripted model picks a script by the user's words, plays one step per
completion, calls tools through Hermes's `tool_call` door when it must, and streams in the OpenAI format."""

import importlib.util
import json
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

TOP = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("script_model", TOP / "tools" / "dev" / "script_model.py")
script_model = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script_model)

SCRIPT = {
    "match": "make the robot brighter",
    "file": "t.json",
    "steps": [
        {"say": "Repainting.", "call": [{"tool": "chromatic_rom_build", "args": {"outputPath": "{GAMES}/x.gbc"}}]},
        {"say": "Here it is."},
    ],
}


def turn(*replies: str) -> list[dict]:
    messages = [
        {"role": "system", "content": "you are"},
        {"role": "user", "content": "Please MAKE THE ROBOT BRIGHTER."},
    ]
    for reply in replies:
        messages += [{"role": "assistant", "content": reply}, {"role": "tool", "content": "{}"}]
    return messages


class ScriptModelTest(unittest.TestCase):
    def test_steps_follow_the_replies_since_the_user_spoke(self):
        self.assertEqual(script_model.next_step(turn(), [SCRIPT]), (SCRIPT["steps"][0], "t.json"))
        self.assertEqual(script_model.next_step(turn("Repainting."), [SCRIPT]), (SCRIPT["steps"][1], "t.json"))
        self.assertEqual(script_model.next_step(turn("a", "b"), [SCRIPT]), ({}, "t.json"))

    def test_unmatched_words_get_one_plain_reply(self):
        messages = [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
        self.assertEqual(script_model.next_step(messages, [SCRIPT])[0], {"say": script_model.UNMATCHED})
        self.assertEqual(script_model.next_step([*messages, {"role": "assistant", "content": "x"}], [SCRIPT])[0], {})

    def test_names_fill_strings_at_any_depth(self):
        filled = script_model.fill(SCRIPT["steps"][0], {"GAMES": "/g"})
        self.assertEqual(filled["call"][0]["args"]["outputPath"], "/g/x.gbc")
        self.assertEqual(script_model.fill("{UNKNOWN}", {}), "{UNKNOWN}")

    def test_tools_hermes_has_not_loaded_go_through_its_tool_call_door(self):
        step = {"call": [{"tool": "chromatic_rom_build", "args": {"a": 1}}, {"tool": "clarify", "args": {}}]}
        calls = script_model.tool_calls(step, {"tool_call", "clarify"})
        self.assertEqual(calls[0]["function"]["name"], "tool_call")
        self.assertEqual(
            json.loads(calls[0]["function"]["arguments"]),
            {"calls": [{"name": "chromatic_rom_build", "arguments": {"a": 1}}]},
        )
        self.assertEqual(calls[1]["function"]["name"], "clarify")

    def test_the_server_streams_words_then_tool_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "t.json").write_text(json.dumps(SCRIPT), encoding="utf-8")
            script_model.Handler.folder = Path(folder)
            script_model.Handler.names = {"GAMES": "/g"}
            script_model.Handler.log = None
            server = ThreadingHTTPServer(("127.0.0.1", 0), script_model.Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                body = {"stream": True, "messages": turn(), "tools": [{"function": {"name": "tool_call"}}]}
                request = urllib.request.Request(
                    f"http://127.0.0.1:{server.server_address[1]}/v1/chat/completions", data=json.dumps(body).encode()
                )
                with urllib.request.urlopen(request, timeout=10) as answer:
                    events = [line[6:] for line in answer.read().decode().splitlines() if line.startswith("data: ")]
            finally:
                server.shutdown()
                server.server_close()
        chunks = [json.loads(event) for event in events[:-1]]
        self.assertEqual(events[-1], "[DONE]")
        words = "".join(chunk["choices"][0]["delta"].get("content", "") for chunk in chunks)
        self.assertEqual(words, "Repainting.")
        calls = [call for chunk in chunks for call in chunk["choices"][0]["delta"].get("tool_calls", [])]
        self.assertEqual(calls[0]["function"]["name"], "tool_call")
        self.assertEqual(chunks[-1]["choices"][0]["finish_reason"], "tool_calls")


if __name__ == "__main__":
    unittest.main()

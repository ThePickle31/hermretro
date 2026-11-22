"""The sandbox's model: an OpenAI-compatible endpoint that plays committed scripts instead of thinking.

    python tools/dev/script_model.py <port file> <scripts dir> [NAME=VALUE ...]

Started by `python tools/dev studio up` on a free loopback port (written to <port file>). A script
(`tools/dev/scripts/*.json`, read again for every request, so an edit applies at once) answers the user message that contains its `match` text:

    {"match": "make comet drift", "steps": [
        {"say": "Setting it up.", "call": [{"tool": "chromatic_project_create", "args": {...}}]},
        {"say": "Building it.", "call": [{"tool": "chromatic_rom_build", "args": {}}]},
        {"say": "Comet Drift is ready to play."}]}

Each completion of one user turn plays the next step: its words, then its tool calls (Hermes runs them and
asks again), until a step without calls ends the turn. `{NAME}` in a string is replaced by the NAME=VALUE
given at start (the sandbox passes GAMES, the games folder). A step with `"hold": true` sends its words
and waits until `POST /control/release`, so a turn can be photographed while it works. A message no script
matches gets one plain reply. Standard library only; development only.
"""

from __future__ import annotations

import json
import re
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MODEL = "script"
UNMATCHED = "(The sandbox's scripted model has no script for this message.)"
release = threading.Condition()
released = {"generation": 0}


def load_scripts(folder: Path) -> list[dict]:
    scripts = []
    for path in sorted(folder.glob("*.json")):
        script = json.loads(path.read_text(encoding="utf-8"))
        script["file"] = path.name
        scripts.append(script)
    return scripts


def fill(value, names: dict[str, str]):
    """``value`` with every ``{NAME}`` the sandbox defined replaced, in strings at any depth."""
    if isinstance(value, str):
        return re.sub(r"\{([A-Z_]+)\}", lambda match: names.get(match.group(1), match.group(0)), value)
    if isinstance(value, list):
        return [fill(item, names) for item in value]
    if isinstance(value, dict):
        return {key: fill(item, names) for key, item in value.items()}
    return value


def text_of(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, list):
        return " ".join(part.get("text", "") for part in content if isinstance(part, dict))
    return content if isinstance(content, str) else ""


def next_step(messages: list[dict], scripts: list[dict]) -> tuple[dict, str]:
    """The step this completion plays, and the script it comes from: the latest user message picks the
    script, and the number of assistant replies since then is the step."""
    last_user = max((index for index, message in enumerate(messages) if message.get("role") == "user"), default=-1)
    if last_user < 0:
        return {"say": UNMATCHED}, ""
    said = text_of(messages[last_user]).lower()
    replies = sum(1 for message in messages[last_user + 1 :] if message.get("role") == "assistant")
    for script in scripts:
        if script["match"].lower() in said:
            steps = script["steps"]
            return (steps[replies] if replies < len(steps) else {}), script["file"]
    return ({"say": UNMATCHED} if replies == 0 else {}), ""


def tool_calls(step: dict, offered: set[str]) -> list[dict]:
    """The step's calls in the request's form. Hermes may offer a tool only through its `tool_call` door
    (tools it has not loaded yet): then the call goes through that door."""
    calls = []
    for call in step.get("call", []):
        name, args = call["tool"], call.get("args", {})
        if name not in offered and "tool_call" in offered:
            name, args = "tool_call", {"calls": [{"name": name, "arguments": args}]}
        calls.append(
            {
                "id": f"call_{uuid.uuid4().hex[:12]}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
        )
    return calls


class Handler(BaseHTTPRequestHandler):
    folder: Path = Path()
    names: dict[str, str] = {}
    log: Path | None = None

    def log_message(self, *args) -> None:  # quiet: the sandbox log keeps what matters
        pass

    def reply_json(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/v1/models":
            self.reply_json(200, {"object": "list", "data": [{"id": MODEL, "object": "model", "owned_by": "sandbox"}]})
        else:
            self.reply_json(404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/control/release":
            with release:
                released["generation"] += 1
                release.notify_all()
            self.reply_json(200, {"ok": True})
            return
        if self.path.rstrip("/") != "/v1/chat/completions":
            self.reply_json(404, {"error": {"message": "not found"}})
            return
        offered = {tool.get("function", {}).get("name") for tool in body.get("tools") or []}
        step, script = next_step(body.get("messages") or [], load_scripts(self.folder))
        step = fill(step, self.names)
        calls = tool_calls(step, offered)
        if self.log:
            entry = {
                "at": time.time(),
                "script": script,
                "say": step.get("say", ""),
                "calls": calls,
                "offered": sorted(offered),
            }
            with self.log.open("a", encoding="utf-8") as out:
                out.write(json.dumps(entry) + "\n")
        if body.get("stream"):
            self.stream(step, calls)
        else:
            message = {"role": "assistant", "content": step.get("say") or None}
            if calls:
                message["tool_calls"] = calls
            self.reply_json(200, completion(message, "tool_calls" if calls else "stop"))

    def stream(self, step: dict, calls: list[dict]) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        ident, created = f"chatcmpl-{uuid.uuid4().hex[:12]}", int(time.time())

        def send(delta: dict, finish: str | None = None) -> None:
            chunk = {
                "id": ident,
                "object": "chat.completion.chunk",
                "created": created,
                "model": MODEL,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            self.wfile.flush()

        send({"role": "assistant"})
        for word in re.findall(r"\S+\s*", step.get("say", "")):
            send({"content": word})
        if step.get("hold"):
            with release:
                generation = released["generation"]
                release.wait_for(lambda: released["generation"] != generation)
        for index, call in enumerate(calls):
            send({"tool_calls": [{"index": index, **call}]})
        send({}, "tool_calls" if calls else "stop")
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def completion(message: dict, finish: str) -> dict:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL,
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def main(argv: list[str]) -> int:
    port_file, folder, *pairs = argv
    Handler.folder = Path(folder)
    Handler.names = dict(pair.split("=", 1) for pair in pairs)
    Handler.log = Path(port_file).with_name("model.jsonl")
    # The port the sandbox's config already names, when there is one, so a restart keeps it.
    known = Path(port_file).read_text(encoding="utf-8").strip() if Path(port_file).is_file() else ""
    server = ThreadingHTTPServer(("127.0.0.1", int(known) if known.isdigit() else 0), Handler)
    server.daemon_threads = True
    Path(port_file).write_text(str(server.server_address[1]), encoding="utf-8")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""A fake engine and a game folder for the chromatic_playtest tests (test_playtest.py, test_playtest_run.py): recordings
as the engine's worker leaves them and replay results as emulator_replay answers them, verdict included."""

import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.assets import versions as host_assets
from backend.hermes import host as hermes_host
from backend.library import plan_checks, playtest, playtest_run
from tests.support import isolated_home

ROM = b"\x00" * 0x150 + b"lantern"
ROM_SHA = hashlib.sha256(ROM).hexdigest()
SESSION = "0123456789abcdef0123456789abcdef"
OTHER = "fedcba9876543210fedcba9876543210"
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()
MiB = 1024 * 1024


def answer(structured: dict, *, error: bool = False, images: int = 0) -> dict:
    """A broker response holding an engine result."""
    content = [{"type": "image", "data": PNG, "mimeType": "image/png"}] * images
    return {"ok": True, "result": {"structuredContent": structured, "content": content, "isError": error}}


def write_recording(folder: Path, *, session=SESSION, rom=ROM, status="stopped", outcome=None, **fields) -> Path:
    """A recording folder as the engine leaves it (only what hermretro reads): recording.json and its journal."""
    folder.mkdir(parents=True)
    played = {"sha256": hashlib.sha256(rom).hexdigest(), "cgb": True}
    manifest = {
        "schemaVersion": 1,
        "kind": "gb-studio-playtest",
        "sessionId": session,
        "createdAt": "2026-11-25T10:00:00+00:00",
        "rom": played,
        "status": status,
        "branchId": "branch-0001",
        "branches": [{"branchId": "branch-0001", "frame": 300}],
        "bytesUsed": MiB,
        "limits": {"maxBytes": 64 * MiB},
        **({"outcome": outcome} if outcome else {}),
        **fields,
    }
    (folder / "recording.json").write_text(json.dumps(manifest))
    journal = [{"kind": "header", "sessionId": session, "rom": played}]
    if status != "recording":
        journal.append({"kind": "finish", "status": status, **({"outcome": outcome} if outcome else {})})
    (folder / "events.jsonl").write_text("".join(json.dumps(row) + "\n" for row in journal))
    return folder


def replayed(
    outcome="passed",
    *,
    status="matched",
    actions=6,
    replayed_actions=None,
    mode="source",
    coverage="every-frame",
    problems=(),
    observed=None,
    unreadable=None,
    rom=ROM_SHA,
    session=SESSION,
    ended=None,
    recording=None,
):
    """emulator_replay's answer: a replay of ``actions`` actions with the engine's verdict ``outcome``."""
    diverged = status == "diverged"
    roles = ["expected", "actual"] if diverged else ["end"]
    report = {
        "status": status,
        "replayedActions": actions if replayed_actions is None else replayed_actions,
        "toActionIndex": actions,
        "comparedFrames": 301,
        "coverage": coverage,
        "deterministic": True,
        "source": {"recordingPath": "source", "sessionId": session, "branchId": "branch-0001", "actionCount": actions},
        **({"endedSession": ended} if ended else {}),
    }
    if diverged:
        report["divergence"] = {"frame": 140, "actionIndex": 2, "lastMatchedFrame": 139, "expectedSha256": "e"}
    verdict = {"outcome": outcome, "problems": list(problems)}
    verdict.update({"observed": observed} if observed else {})
    verdict.update({"unreadable": unreadable} if unreadable else {})
    structured = {
        "romSha256": rom,
        "frame": 300,
        "debugMode": mode,
        "replay": report,
        "verdict": verdict,
        "images": [{"role": role} for role in roles],
        **({"recording": recording} if recording else {}),
    }
    return answer(structured, images=len(roles))


def finished(outcome="passed", *, written=None, **options):
    """emulator_replay's answer to a recorded, finished replay: writes the recording where it was asked for, stopped
    with ``written`` (default ``outcome``) as its outcome."""

    def respond(arguments):
        folder = Path(arguments["recording"]["outputPath"])
        ended = written or outcome
        write_recording(folder, status="failed" if ended == "failed" else "stopped", outcome=ended)
        block = {"recordingPath": str(folder), "sessionId": OTHER, "branchId": "branch-0001", "status": "stopped"}
        return replayed(outcome, recording={**block, "outcome": ended}, **options)

    return respond


class FakeEngine:
    """Answers each engine call with the next scripted response for that tool (a response, or a function of the
    call's arguments that gives one), and keeps the calls."""

    def __init__(self, **responses):
        self.responses = {tool: list(values) for tool, values in responses.items()}
        self.calls = []

    def __call__(self, tool, arguments):
        self.calls.append((tool, arguments))
        response = self.responses[tool].pop(0)
        return response(arguments) if callable(response) else response


class PlaytestCase(unittest.TestCase):
    """A game with a ROM, a three-check test plan and helpers to record, bind and run."""

    def setUp(self):
        isolated_home(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name).resolve()
        self.root = self.base / "lantern"
        (self.root / "build").mkdir(parents=True)
        (self.root / "build" / "game.gbc").write_bytes(ROM)
        self.plan("T1 | the gate stays shut | not run", "T2 | the lamp lights | not run", "F1 | the ending | not run")
        self.saved = []
        for patch in (
            mock.patch.object(hermes_host, "_chat_project", lambda *_ids: str(self.root)),
            mock.patch.object(host_assets, "_keep_paths"),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def plan(self, *rows):
        path = plan_checks.plan_path(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("| ID | Then | Status |\n|---|---|---|\n" + "".join(f"| {row} |\n" for row in rows))

    def recording(self, name="session-1", **options):
        return write_recording(self.root / "artifacts" / "playtests" / name, **options)

    def save(self, result):
        paths = [str(self.base / f"image-{len(self.saved) + index}.png") for index, _ in enumerate(result["content"])]
        self.saved += paths
        return paths

    def bind(self, check="T1", recording="artifacts/playtests/session-1", engine=None, **options):
        return playtest.bind(
            self.root,
            engine or FakeEngine(),
            check,
            recording,
            options.get("branch_id"),
            options.get("to_action_index"),
            options.get("expect"),
        )

    def play(self, engine, only=None):
        result, why = playtest_run.run(self.root, engine, self.save, only)
        self.assertIsNone(why)
        return result

    def kept(self, rom=ROM_SHA):
        """The results that stand on ``rom``, by check key: their result words."""
        plan = plan_checks.read_plan(self.root)
        return {key: value["result"] for key, value in playtest.current(plan, playtest.read(self.root), rom).items()}

"""``chromatic_playtest``: bind the game's test-plan checks to recorded attempts and replay every bound check on the
game's ROM as it is now (``playtest.py``, ``playtest_run.py``). Taken into ``tools.py``'s TOOLS."""

from __future__ import annotations

import json
from pathlib import Path

from ..hermes import host, results
from ..hermes.declare import Tool
from . import plan_checks, playtest, playtest_run
from .tool_args import tool_error, tool_project

logger = host.logger

ACTIONS = ("run", "bind", "unbind")
BOUND = (
    "chromatic_playtest {} replays every bound check on the game's ROM as it is now: run it after every rebuild "
    "instead of replaying by hand."
)

PLAYTEST_TOOL = {
    "name": "chromatic_playtest",
    "description": (
        "Run the game's test plan (docs/game/TEST-PLAN.md) on its ROM as it is now. Each check can be bound to a "
        "recorded attempt that shows it passing: action 'bind' with check, the recording (its recordingPath or "
        "session id, from a fresh boot with recording:{}), toActionIndex (the recordingSpan's toActionIndex of the "
        "step where the check passed; required while the recording is still being made) and expect: frames 'match' "
        "(the default: every frame as recorded) or a scene and variable values where the inputs end (read in source "
        "debug mode, so frames may change). F1 binds a whole run stopped with outcome passed. Bind each check as it "
        "passes; binding again replaces the check's binding and its result. Action 'run' (the default) replays every "
        "bound check with chromatic_emulator_replay and answers passed, sampled (frames matched where the recording "
        "kept them), failed or error (it could not be judged) for each, with the first differing frame, the state "
        "it ended in and the saved images; F1's replay is recorded and finished in the same call, and finishRun "
        "names it when it passed or failed. Run it after every rebuild instead of replaying by hand; "
        "chromatic_build_report holds its checks to the last results on this ROM. A run ends the emulator session "
        "(endedSession names it) and leaves the last replay's open; it never touches a device."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": list(ACTIONS), "description": "run (default), bind or unbind."},
            "check": {
                "type": "string",
                "minLength": 1,
                "maxLength": plan_checks.MAX_CHECK_ID,
                "description": "bind, unbind: the check's ID in the test plan, e.g. 'T3'.",
            },
            "recording": {
                "type": "string",
                "minLength": 1,
                "maxLength": 4096,
                "description": "bind: the recordingPath (or session id) of the attempt that passed the check.",
            },
            "branchId": {
                "type": "string",
                "pattern": "^branch-[0-9]{4,}$",
                "description": "bind: the attempt's branch to replay; default its current branch.",
            },
            "toActionIndex": {
                "type": "integer",
                "minimum": 0,
                "description": "bind: replay the attempt's actions up to this one, the recordingSpan's toActionIndex "
                "where the check passed; default all of them.",
            },
            "expect": {
                "type": "object",
                "additionalProperties": False,
                "description": "bind: what the replay must end in.",
                "properties": {
                    "frames": {
                        "type": "string",
                        "enum": list(playtest.FRAMES),
                        "description": "match: every frame as recorded (the default without scene or variables).",
                    },
                    "scene": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": playtest.MAX_NAME,
                        "description": "The scene's name where the inputs end.",
                    },
                    "variables": {
                        "type": "object",
                        "maxProperties": playtest.MAX_VARIABLES,
                        "additionalProperties": {"type": "integer", "minimum": -32768, "maximum": 65535},
                        "description": "Variable names (or symbols) and their values where the inputs end.",
                    },
                },
            },
            "checks": {
                "type": "array",
                "maxItems": plan_checks.MAX_CHECKS,
                "items": {"type": "string", "minLength": 1, "maxLength": plan_checks.MAX_CHECK_ID},
                "description": "run: only these bound checks; default every bound check.",
            },
            "project": {
                "type": "string",
                "maxLength": 4096,
                "description": "Optional absolute project folder. Default: this chat's current project.",
            },
        },
        "additionalProperties": False,
    },
}
FIELDS = {
    "run": {"action", "checks", "project"},
    "bind": {"action", "check", "recording", "branchId", "toActionIndex", "expect", "project"},
    "unbind": {"action", "check", "project"},
}


def _saved(result: dict) -> list[str]:
    """The replay's images, saved where every engine result's images are."""
    return [image["path"] for image in results.save_images(result, host._data_dir() / "frames")]


class _Engine:
    """Engine calls as this chat, keeping what the answer must carry from them: the broker's notices and, after a
    compaction, where the chat stands (the first engine result after it carries that note)."""

    def __init__(self, kwargs: dict):
        self.kwargs = kwargs
        self.context: str | None = None
        self.notices: list[str] = []

    def __call__(self, tool: str, arguments: dict) -> dict:
        response, context = host.engine_call(tool, arguments, self.kwargs)
        self.context = context or self.context
        if response.get("notice") and response["notice"] not in self.notices:
            self.notices.append(response["notice"])
        return response

    def answer(self, payload: dict) -> str:
        """``payload`` as the tool answers it: the note first, as an engine result has it, and the notices."""
        leading = {results.CONTEXT_KEY: self.context} if self.context else {}
        notices = {"notice": " ".join(self.notices)} if self.notices else {}
        return json.dumps({**leading, **payload, **notices})


def _run(root: str, args: dict, engine: _Engine) -> str:
    only = args.get("checks")
    if only is not None and not (isinstance(only, list) and all(isinstance(value, str) for value in only)):
        return tool_error("checks must be a list of check IDs.", "INVALID_ARGUMENTS")
    answer, why = playtest_run.run(Path(root), engine, _saved, only)
    if why:
        return engine.answer(
            {
                "ok": False,
                "error": why,
                "code": "NOT_RUN",
                "nextStep": "Nothing was kept. Do what the error says, then call chromatic_playtest again.",
            }
        )
    return engine.answer(answer)


def _bind(root: str, args: dict, engine: _Engine) -> str:
    binding, problems = playtest.bind(
        Path(root),
        engine,
        args.get("check"),
        args.get("recording"),
        args.get("branchId"),
        args.get("toActionIndex"),
        args.get("expect"),
    )
    if problems:
        return engine.answer(
            {
                "ok": False,
                "code": "INVALID_BINDING",
                "problems": problems,
                "error": "Nothing was bound. " + " ".join(problems),
                "nextStep": "Fix every listed problem and call chromatic_playtest with action bind again.",
            }
        )
    plan = plan_checks.read_plan(Path(root))
    cover = playtest.coverage(plan, playtest.read(Path(root))) if plan else {}
    return engine.answer({"ok": True, "binding": playtest.public(Path(root), binding), **cover, "nextStep": BOUND})


def _unbind(root: str, args: dict) -> str:
    removed = playtest.unbind(Path(root), args.get("check"))
    plan = plan_checks.read_plan(Path(root))
    cover = playtest.coverage(plan, playtest.read(Path(root))) if plan else {}
    return json.dumps({"ok": True, "removed": removed, **cover})


def playtest_handler(args: dict, **kwargs) -> str:
    """``chromatic_playtest``: bind, unbind or run the game's bound test-plan checks."""
    try:
        args = args if isinstance(args, dict) else {}
        action = args.get("action", "run")
        if action not in ACTIONS:
            return tool_error(f"action must be one of {', '.join(ACTIONS)}.", "INVALID_ARGUMENTS")
        unknown = sorted(set(args) - FIELDS[action])
        if unknown:
            return tool_error(f"{action} takes no {', '.join(unknown)}.", "INVALID_ARGUMENTS")
        # Every action changes the game's test-plan state or drives its emulator: the main conversation's work.
        if host._is_child(str(kwargs.get("session_id") or "")):
            return tool_error("Only the main conversation binds or runs the test plan.", "PARENT_ONLY")
        root, refused = tool_project("chromatic_playtest", args, kwargs)
        if refused or root is None:  # narrows root to str for pyright: tool_project gives one or the other
            return refused or tool_error("chromatic_playtest: no project folder.", "NO_PROJECT")
        if action == "unbind":
            return _unbind(root, args)
        engine = _Engine(kwargs)
        return _bind(root, args, engine) if action == "bind" else _run(root, args, engine)
    except host.OtherCopyBusy as error:
        return json.dumps(
            host.other_copy_busy(error, str(kwargs.get("conversation_id") or ""), str(kwargs.get("session_id") or ""))
        )
    except host.BrokerRestarting as error:
        return json.dumps(host.broker_restarting(error))
    except host.BrokerUnavailable as error:
        return json.dumps(host.broker_unavailable(error))
    except Exception as error:  # a handler must never raise
        logger.exception("chromatic_playtest failed")
        return tool_error(f"hermretro adapter error: {type(error).__name__}: {error}", "ADAPTER_ERROR")


TOOLS = (Tool(PLAYTEST_TOOL, playtest_handler, step_words=("Running the test plan", "Ran the test plan")),)

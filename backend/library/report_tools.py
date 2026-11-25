"""The Build page's build card: ``chromatic_build_report``, its schema and handler. Taken into ``tools.py``'s TOOLS."""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..hermes import host
from ..hermes.declare import Tool
from ..system.events import emit
from . import games as library
from . import finish_run, pipeline, plan_checks, playtest
from .report_plan import plan_problems, playtest_problems
from .tool_args import other_game_refusal, tool_error

logger = host.logger


REPORT_LIMITS = {
    "title": 48,
    "summary": 280,
    "change": 100,
    "tested": 80,
    "untested": 80,
    "notes": 160,
    "suggestions": 40,
    "check": 80,
    "difficulty": 200,
}
REPORT_COUNTS = {
    "changes": 8,
    "tested": 6,
    "untested": 6,
    "notes": 3,
    "suggestions": 4,
    "checks": plan_checks.MAX_CHECKS,
}
REPORT_KINDS = ("added", "changed", "removed")
# A test-plan check's result on this build (the plan's own status words, superseded aside).
CHECK_RESULTS = ("passed", "failed", "not run", "blocked", "needs review")
REPORT_MESSAGE = (
    "The Build page shows this as the build card. Keep your written reply to one or two short "
    "sentences; do not repeat the report. When nobody will answer (the user asked you to work on your own, or you "
    "have no clarify tool), end with what you did and chose, never a question."
)


def _report_list(key: str, limit: int, item_description: str, description: str) -> dict:
    return {
        "type": "array",
        "maxItems": REPORT_COUNTS[key],
        "description": description,
        "items": {"type": "string", "minLength": 1, "maxLength": limit, "description": item_description},
    }


BUILD_REPORT_TOOL = {
    "name": "chromatic_build_report",
    "description": (
        "Report what this turn did to the game, for the hermretro Build page. Call it once at the end of every "
        "turn that changed or built the game: after chromatic_rom_build and your own playtest, and after "
        "chromatic_present_game when you present. Never call it in a subagent. The page draws the title, summary, "
        "changes (with the images they made or edited), tested and untested checks, notes and suggestions as a "
        "build card, so the written reply after it should be one or two short sentences (for example a "
        "question about a note, when someone will answer it), not a recap. When the game has a test plan "
        "(docs/game/TEST-PLAN.md), checks and difficulty are required: a result for every check it lists (a bound "
        "check's must agree with "
        "chromatic_playtest's results on this ROM; one it could not judge is passed only with evidence), and "
        "finishRun when its F1 (the one run from power-on the plan describes) passed or failed. It waits until the "
        "game's ROM is its latest build and that plan's bound checks and F1 passed on it (unfinished says why a turn "
        "ends before that; the card then shows it unfinished). Reads the test plan and the recordings, keeps the "
        "checks it took on their own evidence for chromatic_present_game, and writes nothing else; never touches a "
        "device."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "minLength": 1,
                "maxLength": REPORT_LIMITS["title"],
                "description": "Short name for this build, e.g. 'Robin in the sky' or 'Chubbier robin'.",
            },
            "summary": {
                "type": "string",
                "minLength": 1,
                "maxLength": REPORT_LIMITS["summary"],
                "description": "One or two plain sentences on what the user can do now.",
            },
            "changes": {
                "type": "array",
                "maxItems": REPORT_COUNTS["changes"],
                "description": "What changed in the game this turn.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["kind", "text"],
                    "properties": {
                        "kind": {"type": "string", "enum": list(REPORT_KINDS)},
                        "text": {"type": "string", "minLength": 1, "maxLength": REPORT_LIMITS["change"]},
                        "asset": {
                            "type": "string",
                            "maxLength": 4096,
                            "description": "Optional path (absolute or relative to the project) "
                            "of an image this change made or edited.",
                        },
                    },
                },
            },
            "tested": _report_list(
                "tested", REPORT_LIMITS["tested"], "One check.", "What you verified yourself in the emulator."
            ),
            "untested": _report_list(
                "untested",
                REPORT_LIMITS["untested"],
                "One check.",
                "What you did not check (sound, edge cases, the real Chromatic...).",
            ),
            "checks": {
                "type": "array",
                "maxItems": REPORT_COUNTS["checks"],
                "description": "The result of every check in docs/game/TEST-PLAN.md not marked superseded, on this "
                "build's ROM. A check you did not play on this ROM is 'not run', even if it passed on an earlier "
                "build; one the user must judge (sound, the real Chromatic) is 'needs review'.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["id", "text", "result"],
                    "properties": {
                        "id": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": plan_checks.MAX_CHECK_ID,
                            "description": "The check's ID in the test plan, e.g. 'T3'.",
                        },
                        "text": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": REPORT_LIMITS["check"],
                            "description": "The check in a few words, e.g. 'Locked gate with 2 of 3 seeds'.",
                        },
                        "result": {"type": "string", "enum": list(CHECK_RESULTS)},
                        "evidence": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 4096,
                            "description": "A recording of this ROM (recordingPath or session id) that shows the "
                            "result, for a check chromatic_playtest could not judge (its result is error).",
                        },
                    },
                },
            },
            "difficulty": {
                "type": "string",
                "minLength": 1,
                "maxLength": REPORT_LIMITS["difficulty"],
                "description": "How hard the game is, from your own play of this build: whether you finished it in "
                "one run from power-on with no checkpoint restores, where a player fails or gets stuck, and what you "
                "tuned. Required when the game has a test plan.",
            },
            "finishRun": {
                "type": "string",
                "minLength": 1,
                "maxLength": 4096,
                "description": "The recordingPath (or session id) of your one run from power-on to the ending on this "
                "build's ROM: started with chromatic_emulator_run restart:true and recording:{}, no checkpoint "
                "restores, then stopped (outcome 'passed' when it reached the ending). Checked against the game's "
                "ROM.",
            },
            pipeline.OVERRIDE: {
                "type": "string",
                "minLength": 1,
                "maxLength": pipeline.MAX_OVERRIDE,
                "description": "Only when this turn ends before the game's bound test-plan checks and F1 pass on its "
                "latest build (the user asked for it as it is, a failure you could not fix, or a turn that built "
                "nothing): why, in a few words. The card shows the build unfinished, with this and what is not "
                "verified.",
            },
            "notes": _report_list("notes", REPORT_LIMITS["notes"], "One note.", "Things the user might notice."),
            "suggestions": _report_list(
                "suggestions",
                REPORT_LIMITS["suggestions"],
                "Phrased as the user's own request, e.g. 'Make it fly faster'.",
                "Next steps the user can pick.",
            ),
            "project": {
                "type": "string",
                "maxLength": 4096,
                "description": "Optional absolute project folder. Default: this chat's current project.",
            },
        },
        "required": ["title", "summary"],
        "additionalProperties": False,
    },
}


def _report_text(value, name: str, limit: int, problems: list) -> str | None:
    if not isinstance(value, str):
        problems.append(f"{name} must be a string.")
        return None
    text = " ".join(value.split())
    if not text:
        problems.append(f"{name} is empty.")
        return None
    if len(text) > limit:
        problems.append(f"{name} is {len(text)} characters; at most {limit}.")
        return None
    return text


def _report_asset(raw: str, root: Path | None) -> tuple[str | None, str | None]:
    """An absolute path for a change's image inside the project, or (None, why it was left out)."""
    text = raw.strip()
    if text.startswith("file://"):
        text = text[len("file://") :]
    candidate = Path(text).expanduser()
    if root is None:
        # Without this chat's game there is no folder to check it against: it could be another game's picture.
        return None, f"{raw}: this chat has no game project"
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        real = candidate.resolve()
        base = root.resolve()
    except (OSError, RuntimeError):
        return None, f"{raw}: not a usable path"
    if real != base and base not in real.parents:
        return None, f"{raw}: outside the project"
    if not real.is_file():
        return None, f"{raw}: no such file in the project"
    return str(real), None


def _report_checks(values, problems: list) -> list[dict]:
    """The reported test-plan checks, each ``{id, text, result}`` and its ``evidence`` when given; a problem for each
    malformed one."""
    if not isinstance(values, list):
        problems.append("checks must be a list of objects with id, text and result.")
        return []
    if len(values) > REPORT_COUNTS["checks"]:
        problems.append(f"checks has {len(values)} items; at most {REPORT_COUNTS['checks']}.")
        return []
    checks, seen = [], set()
    for index, check in enumerate(values, 1):
        where = f"checks[{index}]"
        if not isinstance(check, dict):
            problems.append(f"{where} must be an object with id, text and result.")
            continue
        problems += [
            f"{where} has unknown field {key!r}." for key in sorted(set(check) - {"id", "text", "result", "evidence"})
        ]
        identifier = _report_text(check.get("id"), f"{where}.id", plan_checks.MAX_CHECK_ID, problems)
        key = plan_checks.check_key(identifier or "")
        if identifier and key in seen:
            problems.append(f"{where}: {identifier} is reported twice.")
        seen.add(key)
        if check.get("result") not in CHECK_RESULTS:
            problems.append(f"{where}.result must be one of {', '.join(CHECK_RESULTS)}.")
        text = _report_text(check.get("text"), f"{where}.text", REPORT_LIMITS["check"], problems)
        item = {"id": identifier, "text": text, "result": check.get("result")}
        evidence = check.get("evidence")
        if evidence is not None:
            if isinstance(evidence, str) and evidence.strip() and len(evidence) <= 4096:
                item["evidence"] = evidence.strip()
            else:
                problems.append(f"{where}.evidence must be a recording's path or session id.")
        checks.append(item)
    return checks


def _shown(report: dict) -> dict[str, str]:
    """What the report shows passed on this ROM with its own evidence, ``{check ID: the recording}``: a check
    ``chromatic_playtest`` could not judge, verified with a recording (its ``playtest.verifiedBy``), and F1 reported
    passed with a finish run that ended passed."""
    shown = {
        check["id"]: check["playtest"]["verifiedBy"]
        for check in report["checks"]
        if (check.get("playtest") or {}).get("verifiedBy")
    }
    finish = plan_checks.check_key(plan_checks.FINISH_CHECK)
    run = report["finishRun"] or {}
    for check in report["checks"]:
        if (
            plan_checks.check_key(check["id"] or "") == finish
            and check["result"] == "passed"
            and run.get("outcome") == "passed"
        ):
            shown[check["id"]] = run["recordingPath"]
    return shown


def _held(root: Path | None, shown: dict[str, str]) -> dict | None:
    """The pipeline gate's refusal for the report's game (``pipeline.gate``, the report's own evidence ``shown``
    counted), None when it may be reported. Nothing holds a chat with no project, or a folder the library does not
    know that has no ROM; a library game with no ROM is held like any other (a turn that built nothing says why)."""
    if root is None:
        return None
    entry = host._registry().get(library.game_id(str(root)))
    if entry is None and finish_run.current_rom(root)[0] is None:
        return None
    return pipeline.gate("chromatic_build_report", root, (entry or {}).get("lastBuild"), list(shown))


def build_report_handler(args: dict, **kwargs) -> str:
    """``chromatic_build_report``: check the turn's build card and hand it back for the Build page.
    Stores nothing; the page reads it from the tool call."""
    try:
        args = args if isinstance(args, dict) else {}
        if host._is_child(str(kwargs.get("session_id") or "")):
            return tool_error("Only the main conversation reports a build.", "PARENT_ONLY")
        problems: list[str] = []
        known = set(BUILD_REPORT_TOOL["parameters"]["properties"])
        problems += [f"Unknown field {key!r}." for key in sorted(set(args) - known)]
        root = None
        project = args.get("project")
        if project is not None:
            if (
                not isinstance(project, str)
                or not project.strip()
                or not Path(project).expanduser().is_absolute()
                or not Path(project).expanduser().is_dir()
            ):
                problems.append("project must be an absolute path of an existing project folder.")
            else:
                root = Path(project).expanduser()
                refused = other_game_refusal(
                    "chromatic_build_report",
                    root,
                    str(kwargs.get("conversation_id") or ""),
                    str(kwargs.get("session_id") or ""),
                )
                if refused:
                    return refused
        else:
            try:
                found = host._chat_project(
                    str(kwargs.get("conversation_id") or ""), str(kwargs.get("session_id") or "")
                )
            except Exception:
                logger.debug("hermretro: no project for the build report", exc_info=True)
                found = None
            root = Path(found) if found and Path(found).is_dir() else None
            refused = root and other_game_refusal(
                "chromatic_build_report",
                root,
                str(kwargs.get("conversation_id") or ""),
                str(kwargs.get("session_id") or ""),
            )
            if refused:
                return refused
        report: dict = {}
        for key in ("title", "summary"):
            if key not in args:
                problems.append(f"{key} is required.")
            else:
                report[key] = _report_text(args[key], key, REPORT_LIMITS[key], problems)
        warnings: list[str] = []
        changes = args.get("changes", [])
        report["changes"] = []
        if not isinstance(changes, list):
            problems.append("changes must be a list.")
        elif len(changes) > REPORT_COUNTS["changes"]:
            problems.append(f"changes has {len(changes)} items; at most {REPORT_COUNTS['changes']}.")
        else:
            for index, change in enumerate(changes, 1):
                where = f"changes[{index}]"
                if not isinstance(change, dict):
                    problems.append(f"{where} must be an object with kind and text.")
                    continue
                problems += [
                    f"{where} has unknown field {key!r}." for key in sorted(set(change) - {"kind", "text", "asset"})
                ]
                if change.get("kind") not in REPORT_KINDS:
                    problems.append(f"{where}.kind must be one of {', '.join(REPORT_KINDS)}.")
                item = {
                    "kind": change.get("kind"),
                    "text": _report_text(change.get("text"), f"{where}.text", REPORT_LIMITS["change"], problems),
                }
                asset = change.get("asset")
                if asset is not None:
                    if not isinstance(asset, str) or not asset.strip() or len(asset) > 4096:
                        problems.append(f"{where}.asset must be a file path.")
                    else:
                        resolved, why = _report_asset(asset, root)
                        if resolved:
                            item["asset"] = resolved
                        else:
                            warnings.append(f"{where}.asset left out ({why}).")
                report["changes"].append(item)
        for key in ("tested", "untested", "notes", "suggestions"):
            values = args.get(key, [])
            report[key] = []
            if not isinstance(values, list):
                problems.append(f"{key} must be a list of strings.")
            elif len(values) > REPORT_COUNTS[key]:
                problems.append(f"{key} has {len(values)} items; at most {REPORT_COUNTS[key]}.")
            else:
                report[key] = [
                    _report_text(value, f"{key}[{index}]", REPORT_LIMITS[key], problems)
                    for index, value in enumerate(values, 1)
                ]
        report["checks"] = _report_checks(args.get("checks", []), problems)
        report["difficulty"] = (
            _report_text(args["difficulty"], "difficulty", REPORT_LIMITS["difficulty"], problems)
            if "difficulty" in args
            else None
        )
        report["finishRun"] = None
        if "finishRun" in args:
            value = args["finishRun"]
            if not isinstance(value, str) or not value.strip() or len(value) > 4096:
                problems.append("finishRun must be a recording's path or session id.")
            elif root is None:
                problems.append("finishRun: this chat has no game project to check the recording against.")
            else:
                report["finishRun"], why = finish_run.read_run(root, value.strip())
                if why:
                    problems.append(why)
        if root is not None:
            missed, unplanned = plan_problems(
                root, report["checks"], "difficulty" in args, report["finishRun"], "finishRun" in args
            )
            problems += missed
            warnings += unplanned
            refuted, unplayed = playtest_problems(root, report["checks"])
            problems += refuted
            warnings += unplayed
        unfinished, why = pipeline.override(args.get(pipeline.OVERRIDE))
        if why:
            problems.append(why)
        shown = _shown(report)
        held = _held(root, shown)
        if held and unfinished:
            # The card shows both: an overridden report never looks fully tested.
            report[pipeline.OVERRIDE] = unfinished
            report["notVerified"] = held["reasons"]
            warnings.append(f"Reported unfinished ({unfinished}): {held['error']}")
        elif held and not problems:
            return json.dumps(held)
        elif held:
            problems.append(f"{held['error']} {held['nextStep']}")
        if problems:
            return json.dumps(
                {
                    "ok": False,
                    "code": "INVALID_REPORT",
                    "problems": problems,
                    "error": "The build report was not shown. " + " ".join(problems),
                    "nextStep": "Fix every listed problem and call chromatic_build_report again with the whole report.",
                }
            )
        if root is not None and shown and (plan := plan_checks.read_plan(root)) is not None:
            rom_sha256 = finish_run.current_rom(root)[1]
            if rom_sha256:
                playtest.verify(root, plan, rom_sha256, shown)  # chromatic_present_game counts it on this ROM
        # The card shows each image as it is now, even after a later turn rewrites it (assets listens).
        emit(
            "library.build_reported",
            game=library.game_id(root) if root else None,
            assets=[change["asset"] for change in report["changes"] if change.get("asset")],
        )
        answer = {
            "ok": True,
            "report": report,
            "reportedAt": time.time_ns() / 1_000_000,
            "project": str(root) if root else None,
            "message": REPORT_MESSAGE,
        }
        if warnings:
            answer["warnings"] = warnings
        return json.dumps(answer)
    except Exception as error:  # a handler must never raise
        logger.exception("chromatic_build_report failed")
        return tool_error(f"hermretro adapter error: {type(error).__name__}: {error}", "ADAPTER_ERROR")


TOOLS = (Tool(BUILD_REPORT_TOOL, build_report_handler, step_words=None),)  # drawn as the turn's build card instead

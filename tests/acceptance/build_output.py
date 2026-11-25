"""What a project build returns: the end of the compiler output, its full log, and GB Studio's notices as diagnostics."""

import json
import shutil
from pathlib import Path

from tests.acceptance.fixture import OWNER_B, structured

DEPRECATED = {
    "id": "acceptance-if-value",
    "command": "EVENT_IF_VALUE",
    "args": {"variable": "0", "operator": "==", "comparator": 0, "__collapseElse": False},
    "children": {"true": [], "false": []},
}
BROKEN = {"id": "acceptance-bad-gbvm", "command": "EVENT_GBVM_SCRIPT", "args": {"script": "VM_NOT_AN_OPERATION 1"}}


def check(suite, client_b, built: dict):
    """``built``: project A's first successful build. Project B is built twice more with a deprecated event."""
    log = Path(built.get("logPath") or "")
    rom = Path(built.get("outputPath") or "")
    logged = log.read_text() if log.is_file() else ""
    suite.check(
        "B1",
        "A successful build returns the tail of the compiler output and writes the whole of it to the project's "
        "build/logs, named from the ROM's file name",
        built.get("success") is True
        and log == suite.project_a / "build" / "logs" / f"{rom.name}.log"
        and not rom.with_suffix(".build.log").exists()
        and len(built["stdout"].splitlines()) == 20
        and built.get("stdoutOmittedLines", 0) > 0
        and built["stdout"] in logged
        and logged.count("\n") > built["stdoutOmittedLines"]
        and "warnings" not in built
        and "DEP0190" not in json.dumps(built),
        log=str(log),
        returned_lines=len(built.get("stdout", "").splitlines()),
        omitted=built.get("stdoutOmittedLines"),
        keys=sorted(built),
    )

    # The log's place is taken by a folder: the build still succeeds and returns all of its output instead.
    blocked = suite.project_b / "build" / "logs" / f"{rom.name}.log"
    blocked.unlink(missing_ok=True)  # the log of B's first build
    blocked.mkdir()
    try:
        result = build_with(suite, client_b, [DEPRECATED])
    finally:
        shutil.rmtree(blocked, ignore_errors=True)
    notices = [item for item in result.get("diagnostics", []) if item.get("code") == "DEPRECATED_EVENT"]
    suite.check(
        "B2",
        "A deprecated GB Studio event is a build diagnostic, once, and not repeated in the returned stderr",
        result.get("success") is True
        and len(notices) == 1
        and notices[0].get("event") == "EVENT_IF_VALUE"
        and notices[0].get("severity") == "warning"
        and "is deprecated" not in result.get("stderr", ""),
        diagnostics=result.get("diagnostics"),
        stderr=result.get("stderr", "")[-600:],
        error=result.get("error"),
    )
    suite.check(
        "B3",
        "A build whose log cannot be written says why and returns the whole compiler output",
        result.get("success") is True
        and "logPath" not in result
        and str(blocked) in result.get("logError", "")
        and "stdoutOmittedLines" not in result
        and len(result.get("stdout", "").splitlines()) > 20,
        log_error=result.get("logError"),
        returned_lines=len(result.get("stdout", "").splitlines()),
        keys=sorted(result),
    )

    failed = build_with(suite, client_b, [DEPRECATED, BROKEN])
    severities = [item.get("severity") for item in failed.get("diagnostics", [])]
    suite.check(
        "B4",
        "A failed build lists its errors before GB Studio's notices",
        failed.get("success") is False
        and "warning" in severities
        and severities[0] == "error"
        and severities == sorted(severities, key=lambda severity: severity != "error"),
        diagnostics=failed.get("diagnostics"),
        log=failed.get("logPath"),
    )


def build_with(suite, client_b, script: list) -> dict:
    """Build project B with its first scene's start script replaced by ``script``, then put the scene back."""
    scene_file = next((suite.project_b / "project" / "scenes").glob("*/scene.gbsres"))
    saved = scene_file.read_text()
    scene_file.write_text(json.dumps({**json.loads(saved), "script": script}, indent=2))
    try:
        return structured(client_b.call(OWNER_B, "rom_build", {}))
    finally:
        scene_file.write_text(saved)

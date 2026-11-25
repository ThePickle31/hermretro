"""What a project build returns: the end of the compiler output, its full log, and GB Studio's notices as diagnostics."""

import json
from pathlib import Path

from tests.acceptance.fixture import OWNER_B, structured


def check(suite, client_b, built: dict):
    """``built``: project A's first successful build. Project B is built once more with a deprecated event."""
    log = Path(built.get("logPath") or "")
    rom = Path(built.get("outputPath") or "")
    logged = log.read_text() if log.is_file() else ""
    suite.check(
        "B1",
        "A successful build returns the tail of the compiler output and writes the whole of it to a log beside the ROM",
        built.get("success") is True
        and log == rom.with_suffix(".build.log")
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

    scene_file = next((suite.project_b / "project" / "scenes").glob("*/scene.gbsres"))
    saved = scene_file.read_text()
    deprecated = {
        "id": "acceptance-if-value",
        "command": "EVENT_IF_VALUE",
        "args": {"variable": "0", "operator": "==", "comparator": 0, "__collapseElse": False},
        "children": {"true": [], "false": []},
    }
    scene_file.write_text(json.dumps({**json.loads(saved), "script": [deprecated]}, indent=2))
    try:
        result = structured(client_b.call(OWNER_B, "rom_build", {}))
    finally:
        scene_file.write_text(saved)
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

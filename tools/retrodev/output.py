"""How retrodev answers: human text or one JSON object (--json), and the exit codes agents branch on.

    0 ok   1 failed (fix it and run again)   2 still waiting (run again later)   3 needs the owner

Every failure ends with a line starting "FIX:" naming the exact command or change.
"""

from __future__ import annotations

import json
import sys

OK, FAILED, WAITING, OWNER = 0, 1, 2, 3
CODE_NAMES = {OK: "ok", FAILED: "failed", WAITING: "waiting", OWNER: "needs the owner"}


class Failure(Exception):
    """A refusal: what is wrong and why the rule exists, the fix, and the exit code."""

    def __init__(self, message: str, fix: str, code: int = FAILED, data: dict | None = None):
        super().__init__(message)
        self.message, self.fix, self.code, self.data = message, fix, code, data or {}


class Out:
    """Collects a command's result; prints lines as it goes in human mode, one JSON object at the end in --json."""

    def __init__(self, as_json: bool = False, stream=None):
        self.as_json = as_json
        self.stream = stream
        self.data: dict = {}
        self.lines: list[str] = []

    def _write(self, text: str) -> None:
        stream = self.stream or sys.stdout
        stream.write(text + "\n")
        stream.flush()

    def say(self, text: str = "") -> None:
        """A line for people; kept in `lines` (and left out of the JSON) in --json mode."""
        self.lines.append(text)
        if not self.as_json:
            self._write(text)

    def set(self, **values) -> None:
        self.data.update(values)

    def finish(self, command: str, code: int = OK, failure: Failure | None = None) -> int:
        if failure is not None:
            code = failure.code
            self.data.update(failure.data)
        if self.as_json:
            body = {"command": command, "ok": code == OK, "code": code, "status": CODE_NAMES.get(code, "failed")}
            body.update(self.data)
            if failure is not None:
                body["error"] = {"message": failure.message, "fix": failure.fix}
            self._write(json.dumps(body, indent=2, default=str))
        elif failure is not None:
            self._write(failure.message)
            self._write("FIX: " + failure.fix)
        return code

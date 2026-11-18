"""Run the reviewer: one headless, read-only Hermes chat, and read its JSON verdict.

    hermes -p <profile> chat --ignore-user-config --query-file <brief> --oneshot -Q
           --provider <provider> -m <model> --reasoning <level> -t file

Everything comes from a settings dict (DEFAULTS fill the gaps). The profile has no default: without one, reviews
are skipped. The process runner is injectable so tests never start Hermes.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

DEFAULTS = {
    "profile": None,
    "provider": "openai-codex",
    "model": "gpt-6.1-sol",
    "reasoning": "high",
    "toolsets": "file",
    "hermes": "hermes",
    "timeout": 40 * 60,
    "probe_timeout": 90,
}
NO_PROFILE = "no reviewer profile configured"
SEVERITIES = ("high", "medium", "low")
FINDING_KEYS = ("severity", "file", "line", "problem", "fix", "evidence")
SESSION = re.compile(r"^\s*(?:session_id|Session)\s*:\s*(\S+)\s*$", re.M | re.I)
# Lines a login shell or prompt framework prints into captured output (zsh's zle, gitstatus, powerlevel10k).
NOISE = re.compile(r"^\s*(?:zle|gitstatus|_?p9k|\[?gitstatus|compinit|compdef|zsh:)", re.I)
TROUBLE = re.compile(
    r"rate.?limit|\b429\b|quota|unauthori[sz]ed|\b401\b|\b403\b|usage limit|too many requests|"
    r"overloaded|\b5\d\d\b|not logged in|login required|expired|connection (?:error|refused)",
    re.I,
)
RETRY_PROMPT = (
    "Your last reply was not valid review JSON ({errors}). Reply again with ONLY the JSON object described in "
    "the brief (verdict, findings, checked), nothing before or after it. Do not call any tool."
)


@dataclass
class Completed:
    returncode: int
    output: str
    seconds: float
    timed_out: bool = False


Runner = Callable[[list[str], Path, float], Completed]


def settings_with_defaults(settings: dict | None) -> dict:
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in (settings or {}).items() if v is not None})
    return merged


def command(
    settings: dict,
    *,
    brief: Path | None = None,
    query: str | None = None,
    resume: str | None = None,
    reasoning: str | None = None,
) -> list[str]:
    s = settings_with_defaults(settings)
    if not s["profile"]:
        raise ValueError(NO_PROFILE)
    cmd = [s["hermes"], "-p", s["profile"], "chat", "--ignore-user-config"]
    cmd += ["--query-file", str(brief)] if brief is not None else ["-q", query or ""]
    if resume:
        cmd += ["--resume", resume]
    cmd += ["--oneshot", "-Q", "--provider", s["provider"], "-m", s["model"]]
    cmd += ["--reasoning", reasoning or s["reasoning"], "-t", s["toolsets"]]
    return cmd + list(s.get("extra_args") or [])


def subprocess_runner(cmd: list[str], cwd: Path, timeout: float) -> Completed:
    """Run ``cmd`` in its own process group with stdin closed; stdout and stderr together."""
    start = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        out, _ = proc.communicate(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            out, _ = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            out, _ = proc.communicate()
        timed_out = True
    text = out.decode(errors="replace")
    return Completed(proc.returncode if not timed_out else -1, text, time.monotonic() - start, timed_out)


def session_id(text: str) -> str | None:
    found = SESSION.findall(text)
    return found[-1] if found else None


def strip_noise(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not NOISE.match(line) and not SESSION.match(line))


def find_json(text: str):
    """The last outermost JSON object in ``text`` that has a verdict (else the last one), or None."""
    decoder = json.JSONDecoder()
    text = strip_noise(text)
    found, i = [], 0
    while (i := text.find("{", i)) != -1:
        try:
            obj, end = decoder.raw_decode(text, i)
        except ValueError:
            i += 1
            continue
        if isinstance(obj, dict):
            found.append(obj)
            i = end
        else:
            i += 1
    with_verdict = [obj for obj in found if "verdict" in obj]
    return (with_verdict or found or [None])[-1]


def validate(obj) -> list[str]:
    """Every way ``obj`` misses the review schema; empty when it is valid."""
    if not isinstance(obj, dict):
        return ["no JSON object in the reply"]
    errors = []
    verdict = obj.get("verdict")
    if verdict not in ("clean", "findings"):
        errors.append(f"verdict must be 'clean' or 'findings', not {verdict!r}")
    findings = obj.get("findings", [] if verdict == "clean" else None)
    if not isinstance(findings, list):
        return errors + ["findings must be a list"]
    if verdict == "clean" and findings:
        errors.append("a clean verdict must have no findings")
    if verdict == "findings" and not findings:
        errors.append("verdict 'findings' with an empty findings list")
    for n, item in enumerate(findings):
        if not isinstance(item, dict):
            errors.append(f"finding {n} is not an object")
            continue
        missing = [k for k in FINDING_KEYS if k not in item]
        if missing:
            errors.append(f"finding {n} lacks {', '.join(missing)}")
        if "severity" in item and item["severity"] not in SEVERITIES:
            errors.append(f"finding {n} severity {item['severity']!r} is not high, medium or low")
        if "line" in item and (not isinstance(item["line"], int) or isinstance(item["line"], bool)):
            errors.append(f"finding {n} line must be a whole number")
        for k in ("file", "problem", "fix", "evidence"):
            if k in item and not isinstance(item[k], str):
                errors.append(f"finding {n} {k} must be text")
    if "checked" in obj and not isinstance(obj["checked"], list):
        errors.append("checked must be a list")
    return errors


def parse(text: str) -> tuple[dict | None, list[str]]:
    obj = find_json(text)
    errors = validate(obj)
    return (obj if not errors else None), errors


def _write(path: Path, text: str, append: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a" if append else "w", encoding="utf-8") as f:
        f.write(text)


def run_review(
    settings: dict,
    brief: Path,
    cwd: Path,
    out: Path,
    runner: Runner | None = None,
    retry: bool = True,
) -> dict:
    """Run the reviewer on ``brief`` with ``cwd`` as its folder, saving everything it printed to ``out``.

    An invalid reply gets one follow-up in the same session (``--resume <id>``), or one fresh run when no session
    id was printed. Returns {result, errors, session_ids, attempts: [{cmd, returncode, seconds, timed_out}],
    output, seconds}; ``result`` is the validated JSON or None."""
    s = settings_with_defaults(settings)
    runner = runner or subprocess_runner
    attempts, sessions = [], []

    def once(cmd: list[str], append: bool) -> tuple[dict | None, list[str], str | None]:
        done = runner(cmd, cwd, s["timeout"])
        header = f"\n===== retry: {' '.join(cmd[:4])} ...\n" if append else ""
        _write(out, header + done.output, append)
        sid = session_id(done.output)
        if sid and sid not in sessions:
            sessions.append(sid)
        attempts.append(
            {
                "cmd": cmd,
                "returncode": done.returncode,
                "seconds": round(done.seconds, 1),
                "timed_out": done.timed_out,
                "session_id": sid,  # None: this run's tool calls cannot be audited, so the round cannot count
            }
        )
        if done.timed_out:
            return None, [f"timed out after {s['timeout']} s"], sid
        result, errors = parse(done.output)
        if errors and done.returncode:
            errors.append(f"hermes exited with {done.returncode}: {_last_line(done.output)}")
        return result, errors, sid

    result, errors, sid = once(command(s, brief=brief), append=False)
    if result is None and retry and not attempts[-1]["timed_out"]:
        if sid:
            follow = command(s, query=RETRY_PROMPT.format(errors="; ".join(errors)[:300]), resume=sid)
        else:
            follow = command(s, brief=brief)
        result, errors, _ = once(follow, append=True)
    return {
        "result": result,
        "errors": errors if result is None else [],
        "session_ids": sessions,
        "attempts": attempts,
        "output": str(out),
        "seconds": round(sum(a["seconds"] for a in attempts), 1),
    }


def _last_line(text: str) -> str:
    lines = [line for line in strip_noise(text).splitlines() if line.strip()]
    return lines[-1][:200] if lines else "(no output)"


def probe(settings: dict, runner: Runner | None = None, cwd: Path | None = None) -> dict:
    """A quick 'Reply with exactly: OK' at low reasoning: is the reviewer's provider up and not rate limited?

    Returns {available, reason, seconds}."""
    s = settings_with_defaults(settings)
    if not s["profile"]:
        return {"available": False, "reason": NO_PROFILE, "seconds": 0.0}
    runner = runner or subprocess_runner
    cmd = command(s, query="Reply with exactly: OK", reasoning="low")
    try:
        done = runner(cmd, cwd or Path.cwd(), s["probe_timeout"])
    except OSError as e:
        return {"available": False, "reason": f"cannot start hermes: {e}", "seconds": 0.0}
    seconds = round(done.seconds, 1)
    if done.timed_out:
        return {"available": False, "reason": f"no reply within {s['probe_timeout']} s", "seconds": seconds}
    reply = [line.strip() for line in strip_noise(done.output).splitlines() if line.strip()]
    if done.returncode == 0 and reply and reply[-1].strip("`*\"'. ") == "OK":
        return {"available": True, "reason": "ok", "seconds": seconds}
    trouble = TROUBLE.search(done.output)
    what = _last_line(done.output)
    if trouble:
        reason = f"provider unavailable ({trouble.group(0)}): {what}"
    else:
        reason = f"unexpected probe reply (exit {done.returncode}): {what}"
    return {"available": False, "reason": reason, "seconds": seconds}

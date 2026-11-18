"""`engine update <version>`: docs/dev/ENGINE-UPDATE.md as a checklist, gated on the owner's words.

    engine update <version> --owner-words "<the owner's exact words>" [--done N ...] [--dry-run]

Anything under engine/ needs the owner (the agent guide's rule 2): without their words it refuses with exit 3, a
dry run included. With them it checks the branch is chore/engine-<version> (one deliberate pull request), records
the words in <state>/engine/<version>.json, then walks the guide's numbered steps in order, judging from the tree
which are done (the vendored folder's version, the local patch, the pins folder, ENGINE_VERSION). It runs only the
read-only helpers a step names (tools/engine/manifest.py verify, the lock-step test); a helper that writes, a
download and the copy of the new engine stay the agent's and owner's to do, so each is printed with the version
filled in. A step the tree cannot show (comparing the skills, the full checks) is manual: after doing it, record it
with --done <its number> (the time and who, kept in the same record). Exit 2 while a step is left, a manual one
not recorded included (the next one is named), 0 when every step is done. It never changes engine/ itself.
--dry-run records nothing and runs nothing: it prints the gates and the whole checklist.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys

from . import repo, state
from .output import FAILED, OK, OWNER, WAITING, Failure
from .output import cmd as quoted


def cmd(*parts) -> str:
    """A printed command, with this Python shown as `python` (as the guide writes it)."""
    return quoted(*["python" if part == sys.executable else part for part in parts])


GUIDE = "docs/dev/ENGINE-UPDATE.md"
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
STEP = re.compile(r"^(\d+)\. (?:\*\*(.+?)\*\*(.*)|(.*))$")
ENGINE = "engine/modretro-chromatic"
PATCHED = ("dist/server.js", "dist/device-capture/linux-helper.js")
INFO = ("live_server_info", "pinned_server_info")  # the reconciliation report's engine versions


def steps(text: str) -> list[dict]:
    """The guide's numbered steps: {number, title, text} (a step's text runs to the next numbered line)."""
    found: list[dict] = []
    for line in text.splitlines():
        match = STEP.match(line)
        if match:
            title = (match.group(2) or match.group(4)).rstrip(":.")
            found.append({"number": int(match.group(1)), "title": title, "text": match.group(3) or match.group(4)})
        elif found and line.startswith("   "):
            found[-1]["text"] += " " + line.strip()
        elif found and line.strip() and not line.startswith(" "):
            break
    for step in found:
        step["text"] = step["text"].strip().lstrip(":").strip()
    return found


def current_version(top) -> str | None:
    paths = top / "backend" / "system" / "paths.py"
    found = (
        re.search(r'^ENGINE_VERSION = "([^"]+)"', paths.read_text(encoding="utf-8"), re.M) if paths.is_file() else None
    )
    return found.group(1) if found else None


def vendored_version(top) -> str | None:
    package = top / ENGINE / "package.json"
    try:
        return json.loads(package.read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError):
        return None


def judge(ctx, step: dict, version: str, run_helpers: bool) -> dict:
    """{state: done | todo | manual, why, commands, ran} for one step, from the tree (read-only)."""
    top, title = ctx.top, step["title"].lower()
    pins = top / "engine" / "pins" / version
    commands = [part.replace("<v>", version) for part in re.findall(r"`(python [^`]+)`", step["text"])]
    result = {"state": "manual", "why": "by hand; then go on", "commands": commands, "ran": []}
    folder_new = vendored_version(top) == version
    if "replace the folder" in title:
        result |= {
            "state": "done" if folder_new else "todo",
            "why": f"{ENGINE}/package.json says {vendored_version(top)}",
        }
    elif "local patch" in title:
        patched = folder_new and all(
            (top / ENGINE / name).is_file() and "/dev/fd/6" in (top / ENGINE / name).read_text(errors="replace")
            for name in PATCHED
        )
        result |= {"state": "done" if patched else "todo", "why": "/dev/fd/6 in " + " and ".join(PATCHED)}
    elif "record the new files" in title:
        manifest = pins / "manifest.json"
        result["state"], result["why"] = "todo", f"engine/pins/{version}/manifest.json is missing"
        if manifest.is_file():
            verify = [sys.executable, "tools/engine/manifest.py", "verify", str(manifest.relative_to(top))]
            result["commands"] = [cmd(*verify)]
            if run_helpers:
                code, out, err = repo.run(verify, top, timeout=600)
                result["ran"].append({"command": cmd(*verify), "code": code, "tail": (out + err).strip()[-300:]})
                ok = code == 0 and "local_patches" in manifest.read_text(encoding="utf-8")
                result["state"] = "done" if ok else "todo"
                result["why"] = (
                    "the manifest verifies" if ok else "verify failed, or the local_patches entry is missing"
                )
            else:
                result["why"] = "would run the read-only verify"
    elif "pin the tool contracts" in title:
        ok, why = reconciled(pins, version)
        pinned = f"engine/pins/{version}"
        reconcile = cmd(
            "python", "tools/engine/reconcile_schemas.py", f"{pinned}/tools.json", f"{pinned}/schema-reconcile.json"
        )
        result |= {"state": "done" if ok else "todo", "why": why, "commands": [reconcile]}
    elif "bump the version" in title:
        now = current_version(top)
        result |= {"state": "done" if now == version else "todo", "why": f"backend/system/paths.py says {now}"}
    elif "new or renamed tools" in title:
        result |= _lockstep(ctx, version, run_helpers)
    elif "check.py full" in step["text"]:
        result["commands"] = ["python tools/retrodev check --full", "python tools/ci/clean_install_check.py"]
    return result


def reconciled(pins, version: str) -> tuple[bool, str]:
    """(done, why) for the pinned contracts: a passing reconciliation report of this tools.json and version."""
    where = f"engine/pins/{version}"
    tools, report = pins / "tools.json", pins / "schema-reconcile.json"
    if not tools.is_file():
        return False, f"{where}/tools.json is missing"
    if not report.is_file():
        return False, f"{where}/schema-reconcile.json is missing: the reconciliation has not been run"
    try:
        found = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        found = None
    if not isinstance(found, dict):
        return False, f"{where}/schema-reconcile.json is not a reconciliation report (not a JSON object)"
    if found.get("passed") is not True:
        return False, f"{where}/schema-reconcile.json says the reconciliation did not pass"
    if found.get("pinned_file_sha256") != hashlib.sha256(tools.read_bytes()).hexdigest():
        return False, f"{where}/schema-reconcile.json is stale: it reconciled another tools.json"
    live, pinned = (found.get(key) if isinstance(found.get(key), dict) else {} for key in INFO)
    if live.get("version") != version or pinned.get("version", version) != version:
        engine = live.get("version") or pinned.get("version")
        return False, f"{where}/schema-reconcile.json is for engine {engine}, not {version}"
    return True, f"{where}/schema-reconcile.json passed for this tools.json and engine {version}"


def _lockstep(ctx, version: str, run_helpers: bool) -> dict:
    test = [sys.executable, "-m", "unittest", "tests.repo.test_lockstep"]
    found = {"commands": [cmd(*test)], "ran": []}
    if current_version(ctx.top) != version:
        return found | {"state": "todo", "why": "after the version bump"}
    if not run_helpers:
        return found | {"state": "todo", "why": "would run the lock-step test"}
    code, out, err = repo.run(test, ctx.top, timeout=600)
    found["ran"].append({"command": cmd(*test), "code": code, "tail": (out + err).strip()[-600:]})
    return found | {
        "state": "done" if code == 0 else "todo",
        "why": "the lock-step test " + ("passes" if code == 0 else "names what is left"),
    }


def acknowledged(ctx, version: str, guide_steps: list[dict], done: list[int], dry_run: bool) -> dict:
    """{step number: {at, by}}: the manual steps recorded as done, earlier and now (--done N)."""
    path = state.root(ctx.top) / "engine" / f"{version}.json"
    try:
        acks = dict(json.loads(path.read_text(encoding="utf-8")).get("done", {}))
    except (OSError, ValueError):
        acks = {}
    if done and dry_run:
        raise Failure("--done records a manual step, and a dry run records nothing", "run it again without --dry-run")
    numbers = {step["number"]: step for step in guide_steps}
    for number in done:
        step = numbers.get(number)
        if step is None:
            raise Failure(f"{GUIDE} has no step {number}", f"use a step number from 1 to {max(numbers, default=0)}")
        if judge(ctx, step, version, run_helpers=False)["state"] != "manual":
            raise Failure(
                f"step {number} ({step['title']}) is judged from the tree, so it cannot be marked done by hand",
                "do what the step says; the next engine update run sees it",
            )
        acks[str(number)] = {"at": state.now(), "by": "the agent"}
    return acks


def run(ctx, version: str, words: str | None, dry_run: bool = False, done: list[int] | None = None) -> int:
    out = ctx.out
    if not (words or "").strip():
        raise Failure(
            "an engine update changes engine/, which needs the owner: their words are not given",
            f"ask the owner; with their go, python tools/retrodev engine update {version} --owner-words '<their exact words>'",
            OWNER,
        )
    if not VERSION.match(version):
        raise Failure(f"'{version}' is not an engine version", "use the form X.Y.Z, e.g. 1.0.35")
    guide = ctx.top / GUIDE
    if not guide.is_file():
        raise Failure(f"{GUIDE} is missing", f"git checkout -- {GUIDE}")
    branch = repo.branch(ctx.top)
    wanted = f"chore/engine-{version}"
    on_branch = branch == wanted
    out.set(version=version, current=current_version(ctx.top), branch=branch, dry_run=dry_run)
    out.say(f"engine update {current_version(ctx.top)} -> {version}  (the owner said: {words.strip()!r})")
    gate = "ok" if on_branch else f"on {branch or 'a detached HEAD'}"
    out.say(f"gate: branch {wanted}: {gate}")
    if not on_branch and not dry_run:
        raise Failure(
            f"an engine update is one deliberate pull request on {wanted}; this checkout is on {branch}",
            f"python tools/retrodev start {wanted} --no-plan, then run this there",
        )
    guide_steps = steps(guide.read_text(encoding="utf-8"))
    acks = acknowledged(ctx, version, guide_steps, done or [], dry_run)
    if not dry_run:
        record = {"version": version, "words": words.strip(), "at": state.now(), "branch": branch, "done": acks}
        state.write_atomic(state.root(ctx.top) / "engine" / f"{version}.json", json.dumps(record, indent=2) + "\n")
    rows, waiting, outstanding = [], None, []
    for step in guide_steps:
        result = judge(ctx, step, version, run_helpers=not dry_run)
        ack = acks.get(str(step["number"])) if result["state"] == "manual" else None
        if ack:
            result |= {"state": "done", "why": f"done by hand: recorded {ack['at']} by {ack['by']}"}
        elif result["state"] == "manual":
            outstanding.append(step)
        rows.append({"number": step["number"], "title": step["title"], **result})
        out.say(f"[{result['state']:>6}] {step['number']}. {step['title']}: {result['why']}")
        for ran in result["ran"]:
            out.say(f"         ran {ran['command']}: exit {ran['code']}")
        if result["state"] != "done":
            for command in result["commands"]:
                out.say(f"         {command}")
            if result["state"] == "manual" or not result["commands"]:
                out.say(f"         {step['text'][:300]}")
            waiting = waiting or step
    out.set(steps=rows, outstanding=[step["number"] for step in outstanding])
    if dry_run:
        out.say("dry run: nothing recorded, no helper run, nothing changed")
        return OK
    again = f"python tools/retrodev engine update {version} --owner-words ..."
    if outstanding:
        listed = ", ".join(f"{step['number']} ({step['title']})" for step in outstanding)
        out.say(f"manual steps not yet recorded as done: {listed}")
    if waiting is not None:
        number = waiting["number"]
        by_hand = waiting in outstanding
        tail = f" by hand, then {again} --done {number}" if by_hand else f", then {again} again"
        out.say(f"next: step {number} ({waiting['title']}){tail}")
        out.set(next=f"step {number}")
        return WAITING
    out.say("every step is done (the tree's and those recorded by hand); next: commit, then python tools/retrodev ship")
    return OK if rows else FAILED

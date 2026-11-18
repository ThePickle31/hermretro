"""`engine update <version>`: docs/dev/ENGINE-UPDATE.md as a checklist, gated on the owner's words.

    engine update <version> --owner-words "<the owner's exact words>" [--dry-run]

Anything under engine/ needs the owner (the agent guide's rule 2): without their words it refuses with exit 3, a
dry run included. With them it checks the branch is chore/engine-<version> (one deliberate pull request), records
the words in <state>/engine/<version>.json, then walks the guide's numbered steps in order, judging from the tree
which are done (the vendored folder's version, the local patch, the pins folder, ENGINE_VERSION). It runs only the
read-only helpers a step names (tools/engine/manifest.py verify, the lock-step test); a helper that writes, a
download and the copy of the new engine stay the agent's and owner's to do, so each is printed with the version
filled in. Exit 2 while a step is left (the next one is named), 0 when every step is done. It never changes
engine/ itself. --dry-run records nothing and runs nothing: it prints the gates and the whole checklist.
"""

from __future__ import annotations

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
        have = [name for name in ("tools.json", "schema-reconcile.json") if (pins / name).is_file()]
        result["state"] = "done" if len(have) == 2 else "todo"
        result["why"] = (
            f"engine/pins/{version}/ has {', '.join(have) or 'neither'} of tools.json, schema-reconcile.json"
        )
    elif "bump the version" in title:
        now = current_version(top)
        result |= {"state": "done" if now == version else "todo", "why": f"backend/system/paths.py says {now}"}
    elif "new or renamed tools" in title:
        result |= _lockstep(ctx, version, run_helpers)
    elif "check.py full" in step["text"]:
        result["commands"] = ["python tools/retrodev check --full", "python tools/ci/clean_install_check.py"]
    return result


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


def run(ctx, version: str, words: str | None, dry_run: bool = False) -> int:
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
    if not dry_run:
        record = {"version": version, "words": words.strip(), "at": state.now(), "branch": branch}
        state.write_atomic(state.root(ctx.top) / "engine" / f"{version}.json", json.dumps(record, indent=2) + "\n")
    rows, first_todo = [], None
    for step in steps(guide.read_text(encoding="utf-8")):
        result = judge(ctx, step, version, run_helpers=not dry_run)
        rows.append({"number": step["number"], "title": step["title"], **result})
        out.say(f"[{result['state']:>6}] {step['number']}. {step['title']}: {result['why']}")
        for ran in result["ran"]:
            out.say(f"         ran {ran['command']}: exit {ran['code']}")
        if result["state"] != "done":
            for command in result["commands"]:
                out.say(f"         {command}")
            if result["state"] == "manual" or not result["commands"]:
                out.say(f"         {step['text'][:300]}")
        if result["state"] == "todo" and first_todo is None:
            first_todo = step
    out.set(steps=rows)
    if dry_run:
        out.say("dry run: nothing recorded, no helper run, nothing changed")
        return OK
    if first_todo is not None:
        out.say(
            f"next: step {first_todo['number']} ({first_todo['title']}), then python tools/retrodev engine update {version} --owner-words ... again"
        )
        out.set(next=f"step {first_todo['number']}")
        return WAITING
    out.say("every step the tree shows is done; next: python tools/retrodev check --full, commit, ship")
    return OK if rows else FAILED

"""What an engine update changed, written for the maintainer: tools/engine/update.py calls it.

The report is notes/engine-update-<version>/report.md, with the diffs it names beside it. dist/server.js is one
bundle, so its diff is split into the modules the bundler marks (`// dist/<module>.js`); a module whose only change
is the bundler renumbering its names (`process3` for `process2`) is listed as renamed, not changed.
"""

from __future__ import annotations

import difflib
import json
import re
import subprocess
from pathlib import Path

ENGINE = "engine/modretro-chromatic"
BUNDLE = "dist/server.js"
LOCK = "scripts/runtime-package-lock.json"
MODULE = re.compile(r"^// ((?:\.\./)*(?:dist|node_modules|scripts|src)/\S+)$", re.M)
NUMBERED = re.compile(r"\b([A-Za-z_$][\w$]*?)\d+\b")
AREAS = ("dist/", "scripts/", "skills/", "docs/", "examples/", "assets/", "native/", "third-party/")


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout


def show(root: Path, ref: str, rel: str) -> str:
    """A file of the engine at ref, or "" when it is not there."""
    done = subprocess.run(["git", "show", f"{ref}:{ENGINE}/{rel}"], cwd=root, capture_output=True, text=True)
    return done.stdout if done.returncode == 0 else ""


def modules(bundle: str) -> dict[str, str]:
    """The bundle's modules by name; a module the bundler wrote twice gets both parts, in order."""
    found: dict[str, str] = {}
    marks = list(MODULE.finditer(bundle))
    if marks:
        found["(bundle header)"] = bundle[: marks[0].start()]
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(bundle)
        name = re.sub(r"^(\.\./)+", "", mark.group(1))
        found[name] = found.get(name, "") + bundle[mark.start() : end]
    return found


def compare_modules(old: str, new: str) -> dict[str, list[str]]:
    """Module names by what happened to them: added, removed, changed, renamed (renumbered names only)."""
    before, after = modules(old), modules(new)
    result: dict[str, list[str]] = {"added": [], "removed": [], "changed": [], "renamed": []}
    for name in sorted(set(before) | set(after)):
        if name not in before:
            result["added"].append(name)
        elif name not in after:
            result["removed"].append(name)
        elif before[name] != after[name]:
            same = NUMBERED.sub(r"\1", before[name]) == NUMBERED.sub(r"\1", after[name])
            result["renamed" if same else "changed"].append(name)
    return result


def unified(old: str, new: str, name: str) -> str:
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"a/{name}", f"b/{name}", n=3))


def lock_versions(text: str) -> dict[str, str]:
    """Each package the runtime lock file installs, by its path in node_modules."""
    if not text:
        return {}
    packages = json.loads(text).get("packages", {})
    return {path.removeprefix("node_modules/"): p.get("version", "") for path, p in packages.items() if path}


def area(rel: str) -> str:
    return next((a.rstrip("/") for a in AREAS if rel.startswith(a)), "other")


def write(
    root: Path, out: Path, old_tag: str, new_tag: str, ours_before: str, conflicts: list[str], tools: dict | None
) -> Path:
    """Write the report and its diffs into out; returns report.md. ours_before is the commit the merge started from."""
    out.mkdir(parents=True, exist_ok=True)
    upstream = [
        line.split("\t") for line in git(root, "diff", "--name-status", old_tag, new_tag, "--", ENGINE).splitlines()
    ]
    changed = {fields[-1].removeprefix(ENGINE + "/"): fields[0] for fields in upstream}
    ours = {
        p.removeprefix(ENGINE + "/")
        for p in git(root, "diff", "--name-only", old_tag, ours_before, "--", ENGINE).split()
    }
    lines = [f"# Engine update: {old_tag} to {new_tag}", ""]

    lines += ["## Our changes", ""]
    both = sorted(ours & set(changed))
    lines.append(f"- Files we changed that ModRetro also changed: {', '.join(both) or 'none'}")
    lines.append(f"- Left with conflict markers (resolve them): {', '.join(conflicts) or 'none'}")
    lines.append(f"- Files we changed: {len(ours)} (`git diff {old_tag} HEAD -- {ENGINE}`)")
    lines.append("")

    lines += ["## Files ModRetro changed", ""]
    by_area: dict[str, list[str]] = {}
    for rel, status in sorted(changed.items()):
        by_area.setdefault(area(rel), []).append(f"{status} {rel}")
    for name, entries in sorted(by_area.items()):
        lines.append(f"- **{name}** ({len(entries)}): " + ", ".join(f"`{e}`" for e in entries[:40]))
        if len(entries) > 40:
            lines.append(f"  and {len(entries) - 40} more (`git diff --name-status {old_tag} {new_tag}`)")
    lines.append("")

    old_bundle, new_bundle = show(root, old_tag, BUNDLE), show(root, new_tag, BUNDLE)
    lines += [f"## Code in {BUNDLE}, by module", ""]
    if old_bundle == new_bundle:
        lines += ["Unchanged.", ""]
    else:
        split = compare_modules(old_bundle, new_bundle)
        before, after = modules(old_bundle), modules(new_bundle)
        folder = out / "modules"
        folder.mkdir(exist_ok=True)
        for name in split["changed"] + split["added"] + split["removed"]:
            safe = re.sub(r"[^\w.-]+", "_", name)
            (folder / f"{safe}.diff").write_text(unified(before.get(name, ""), after.get(name, ""), name))
        for kind in ("changed", "added", "removed", "renamed"):
            own = [n for n in split[kind] if "node_modules/" not in n]
            dependencies = len(split[kind]) - len(own)
            text = ", ".join(f"`{n}`" for n in own) or "none"
            lines.append(f"- **{kind}**: {text}" + (f" (and {dependencies} in node_modules)" if dependencies else ""))
        lines += ["", "Each changed, added or removed module's diff: `modules/<module>.diff`.", ""]

    lines += ["## Tool contracts", ""]
    if tools is None:
        lines += [
            "Not compared (a conflict, or no Node): run `python tools/engine/reconcile_schemas.py` (update.py's last lines).",
            "",
        ]
    else:
        for key in ("missing_from_live", "extra_in_live"):
            lines.append(f"- {'Removed' if key == 'missing_from_live' else 'Added'}: {', '.join(tools[key]) or 'none'}")
        altered = [f"{name} ({', '.join(d['fields'] + d['key_difference'])})" for name, d in tools["altered"].items()]
        lines.append(f"- Changed: {', '.join(altered) or 'none'}")
        lines.append(f"- Server info: {tools['pinned_server_info']} to {tools['live_server_info']}")
        lines.append("")

    skills = git(root, "diff", old_tag, new_tag, "--", f"{ENGINE}/skills")
    lines += ["## Skills", ""]
    if skills:
        (out / "skills.diff").write_text(skills)
        lines += ["Carry real changes into `skills/` by hand: `skills.diff`.", ""]
    else:
        lines += ["Unchanged.", ""]

    old_lock, new_lock = lock_versions(show(root, old_tag, LOCK)), lock_versions(show(root, new_tag, LOCK))
    moved = [
        f"{name} {old_lock.get(name, '(new)')} to {new_lock.get(name, '(removed)')}"
        for name in sorted(set(old_lock) | set(new_lock))
        if old_lock.get(name) != new_lock.get(name)
    ]
    lines += ["## Runtime dependencies", ""]
    lines += [f"- {m}" for m in moved] or ["Unchanged."]
    lines += ["", "Check `.github/SECURITY.md`'s accepted advisories against these.", ""]

    report = out / "report.md"
    report.write_text("\n".join(lines))
    return report

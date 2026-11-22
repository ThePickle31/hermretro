#!/usr/bin/env python3
"""Update the vendored engine to a new ModRetro release, keeping the maintainer's changes.

    python tools/engine/update.py <release folder>

The release folder is the new engine as ModRetro ships it, e.g. Codex's copy in
~/.codex/plugins/cache/openai-curated-remote/modretro-chromatic/<version>. Run it on a clean branch from dev; it:

1. tags the release, without the files hermretro leaves out, as engine-upstream-<version>, whose parent is the
   current release's tag;
2. merges ModRetro's changes since the current release into engine/modretro-chromatic (git merge-tree, three ways):
   a file we never changed takes the new release, a file we changed keeps our changes, lines both sides changed get
   conflict markers, and a file one side deleted and the other changed (or a binary file both changed) keeps ours
   and is listed as a conflict;
3. moves the pins to engine/pins/<version>/ (the manifest; the tool contracts when the merge is clean) and bumps
   the version in backend/system/paths.py, the adapted skills and THIRD_PARTY_NOTICES.md;
4. writes notes/engine-update-<version>/report.md: what ModRetro changed, by module, tool, skill and dependency.

It needs a clean working tree and Git 2.40 or newer. It stages and commits nothing; what is left is printed at the
end, and so is how to start over when it stops partway.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import manifest  # noqa: E402 - tools/engine goes on sys.path first
import report  # noqa: E402
from engine_dev import REPO_ROOT, paths  # noqa: E402

ENGINE = report.ENGINE


class UpdateError(Exception):
    pass


# The release's bytes and modes go into the tag as they are, whatever the user's git settings.
EXACT = (
    "-c",
    "core.autocrlf=false",
    "-c",
    "core.fileMode=true",
    "-c",
    "core.symlinks=true",
    "-c",
    "core.safecrlf=false",
)


def git(root: Path, *args: str, stdin: str | None = None, env: dict | None = None, check: bool = True):
    done = subprocess.run(
        ["git", *EXACT, *args], cwd=root, input=stdin, capture_output=True, text=True, env={**os.environ, **(env or {})}
    )
    if check and done.returncode not in (0, *(() if check is True else check)):
        raise UpdateError(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done


def tag_name(version: str) -> str:
    return f"engine-upstream-{version}"


def release_version(release: Path) -> str:
    try:
        return json.loads((release / "package.json").read_text())["version"]
    except (OSError, ValueError, KeyError) as error:
        raise UpdateError(f"{release} is not an engine release (package.json: {error})") from error


def check_start(root: Path, old: str, new: str) -> None:
    if new == old:
        raise UpdateError(f"the engine is already {old}")
    if git(root, "rev-parse", "-q", "--verify", f"refs/tags/{tag_name(old)}", check=False).returncode:
        raise UpdateError(f"no tag {tag_name(old)}: fetch the tags (git fetch --tags)")
    if git(root, "status", "--porcelain").stdout:
        raise UpdateError("the working tree has uncommitted changes: commit or discard them first")


def tag_release(root: Path, release: Path, old: str, new: str) -> str:
    """Commit the release (without the left-out files) at engine/modretro-chromatic and tag it. A tag of the same
    release from an earlier run that stopped partway is kept; a tag of anything else stops the update."""
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / "tree"
        shutil.copytree(release, stage / ENGINE, symlinks=True)
        for rel in manifest.LEFT_OUT:
            (stage / ENGINE / rel).unlink(missing_ok=True)
        index = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
        git(root, f"--work-tree={stage}", "add", "-A", "--", ENGINE, env=index)
        tree = git(root, "write-tree", env=index).stdout.strip()
    existing = git(root, "rev-parse", "-q", "--verify", f"refs/tags/{tag_name(new)}^{{tree}}", check=False)
    if not existing.returncode:
        if existing.stdout.strip() != tree:
            raise UpdateError(f"tag {tag_name(new)} exists and holds a different release")
        return tag_name(new)
    parent = git(root, "rev-parse", f"{tag_name(old)}^{{commit}}").stdout.strip()
    message = (
        f"engine: ModRetro Chromatic {new}, as released\n\nThe engine hermretro vendors, without the files it leaves "
        "out (ModRetro's packed CLI archives and the Linux\ncapture ffmpeg builds). hermretro's changes on top: "
        "engine/CHANGES.md.\n"
    )
    commit = git(root, "commit-tree", tree, "-p", parent, stdin=message).stdout.strip()
    git(root, "tag", "-a", tag_name(new), "-m", f"ModRetro Chromatic {new}, as released", commit)
    return tag_name(new)


def merge(root: Path, old_tag: str, new_tag: str) -> list[str]:
    """Merge ModRetro's changes between the two tags into our engine, in the working tree only (nothing staged);
    returns the files left as conflicts."""
    done = git(
        root,
        "merge-tree",
        "--write-tree",
        "--name-only",
        "--no-messages",
        "-z",
        f"--merge-base={old_tag}",
        "HEAD",
        new_tag,
        check=(1,),
    )
    tree, *conflicted = [p for p in done.stdout.split("\0") if p]
    git(root, "read-tree", "-m", "-u", "HEAD", tree)
    git(root, "reset", "-q")
    return sorted({p.removeprefix(ENGINE + "/") for p in conflicted})


def move_pins(root: Path, release: Path, old: str, new: str, conflicts: list[str]) -> Path:
    """engine/pins/<new>/ with the manifest of our engine; the left-out files' entries come from the release. With
    conflicts it holds the release's own manifest, for manifest.py write to start from once they are resolved."""
    folder = root / "engine" / "pins" / new
    folder.mkdir(parents=True, exist_ok=True)
    recorded = manifest.build(release)
    written = recorded if conflicts else manifest.build(root / ENGINE, recorded)
    (folder / "manifest.json").write_text(json.dumps(written, indent=1) + "\n")
    shutil.rmtree(root / "engine" / "pins" / old)
    return folder


def bump(root: Path, old: str, new: str) -> None:
    """The engine version everywhere tests/repo/test_lockstep.py checks it."""
    edits = [(root / "backend/system/paths.py", f'ENGINE_VERSION = "{old}"', f'ENGINE_VERSION = "{new}"')]
    edits += [(skill, f"\nversion: {old}\n", f"\nversion: {new}\n") for skill in sorted(root.glob("skills/*/SKILL.md"))]
    for path, before, after in edits:
        text = path.read_text()
        if before in text:
            path.write_text(text.replace(before, after))
    notices = root / "THIRD_PARTY_NOTICES.md"
    notices.write_text(re.sub(rf"(?<![\w.]){re.escape(old)}(?!\.?\w)", new, notices.read_text()))


def pin_tools(folder: Path, old_pins: dict) -> dict | None:
    """Pin the new engine's contracts; the comparison with the old ones goes in the report. None without Node."""
    import reconcile_schemas

    if not paths.find_node().get("path"):
        return None
    try:
        live = reconcile_schemas.live_contracts(paths.ENGINE_ROOT)
    except Exception as error:  # any failure to start the engine leaves the pinning to the maintainer
        print(f"could not start the new engine to pin its tool contracts: {error}")
        return None
    pinned = {key: live[key] for key in ("initialize", "tools", "pages")}
    (folder / "tools.json").write_text(json.dumps(pinned, indent=1) + "\n")
    check = reconcile_schemas.compare(pinned, live, folder / "tools.json")
    (folder / "schema-reconcile.json").write_text(json.dumps(check, indent=2) + "\n")
    return reconcile_schemas.compare(old_pins, live, folder / "tools.json")


def start_over(root: Path, new: str) -> str:
    return f"to start over: git -C {root} reset -q --hard && git -C {root} clean -fdq engine/ && git tag -d {tag_name(new)}"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    root, release = REPO_ROOT, Path(sys.argv[1]).expanduser().resolve()
    old, new = paths.ENGINE_VERSION, None
    try:
        new = release_version(release)
        check_start(root, old, new)
        old_pins = json.loads(paths.PINNED_TOOLS.read_text())
        start = git(root, "rev-parse", "HEAD").stdout.strip()
        new_tag = tag_release(root, release, old, new)
        conflicts = merge(root, tag_name(old), new_tag)
        folder = move_pins(root, release, old, new, conflicts)
        bump(root, old, new)
        tools = None
        if not conflicts:
            # The version moved: the new pins are the ones paths would read in a fresh process.
            paths.ENGINE_PINS, paths.PINNED_TOOLS = folder, folder / "tools.json"
            tools = pin_tools(folder, old_pins)
        out = root / "notes" / f"engine-update-{new}"
        written = report.write(root, out, tag_name(old), new_tag, start, conflicts, tools)
    except (UpdateError, OSError, ValueError, KeyError) as error:
        print(f"engine update stopped: {error}")
        if new and new != old:
            print(start_over(root, new))
        return 1
    print(f"engine {old} to {new}; report: {written.relative_to(root)}; nothing is staged")
    left = []
    if conflicts:
        left.append(
            f"resolve the conflicts in {', '.join(conflicts)} (markers in text files; a binary file or a file one side "
            "deleted keeps ours), then: python tools/engine/manifest.py write"
        )
    if tools is None:
        left.append(
            f"pin the tool contracts: engine/pins/{new}/tools.json and schema-reconcile.json "
            "(python tools/engine/reconcile_schemas.py names the differences; needs Node)"
        )
    left += [
        "carry real skill changes into skills/ (the report's Skills section)",
        "update engine/CHANGES.md for any of our changes the merge made unnecessary",
        "python tools/check.py full, then commit as chore/engine-" + new,
        f"git push origin {new_tag}",
    ]
    print("left to do:\n" + "\n".join(f"  {n}. {step}" for n, step in enumerate(left, 1)))
    print(start_over(root, new))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

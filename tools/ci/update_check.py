"""`python tools/ci/clean_install_check.py --update-from [REF]`: an installed release updated to this commit.
How to run it and what it needs: .agents/skills/hermretro-dev-testing/references/testing.md, "The clean install and update checks".

Installs REF (default: the newest v* release tag on origin/main, the version users have) from a local copy of this
repository into a throwaway Hermes home and uses it the way the page does: the studio profile linked to the
install, a game in the library with a thumbnail, a New Game conversation, a running broker. Then it moves the
copy's default branch to HEAD, runs `hermes plugins update hermretro` and checks: the update needed no prompt,
the new code registers its agent side only in hermretro and still matches plugin.yaml, it reads the user's
games and library back, the old broker is replaced on the first call, a gateway of a published release still running
(Hermes not yet restarted) keeps the broker the new version started, and nothing the old version left in the plugin
folder gets in the way. The page calls run in Hermes's own Python (`inside`), through its plugin loader.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from clean_install_check import ROOT, registers_only_in_studio, runner
from update_inside import OldGateway, alive, drive_holding, hold_open, inside_command, inside_environment


def _git(*args: str, cwd: Path = ROOT) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120
    )
    if done.returncode:
        raise SystemExit(
            f"git {' '.join(args)} failed in {cwd}:\n{done.stderr.strip()}\n"
            "FIX: the checkout needs its history and tags (CI: actions/checkout with fetch-depth: 0)"
        )
    return done.stdout.strip()


def _stable_release(commit: str) -> bool:
    """Whether a published stable release (a `v*` tag without a prerelease suffix) is this commit."""
    return any("-" not in tag for tag in _git("tag", "--points-at", commit, "--list", "v*").split())


def latest_release() -> str:
    """The newest stable `v*` tag on origin/main (local main without an origin): the version users have now."""
    base = "origin/main"
    if subprocess.run(["git", "rev-parse", "-q", "--verify", base], cwd=ROOT, capture_output=True).returncode:
        base = "main"
    tags = [tag for tag in _git("tag", "--merged", base, "--list", "v*", "--sort=-v:refname").split() if "-" not in tag]
    if not tags:
        raise SystemExit(f"no v* release tag is reachable from {base}\nFIX: git fetch --tags origin, or pass a REF")
    return tags[0]


def update(args, hermes: list[str], tmp: Path, root: Path) -> int:
    started = time.monotonic()
    ref = latest_release() if args.update_from == "latest-release" else args.update_from
    old = _git("rev-parse", "--verify", f"{ref}^{{commit}}")
    new = _git("rev-parse", "HEAD")
    if _git("merge-base", old, new) != old:
        raise SystemExit(
            f"{ref} is not an ancestor of HEAD, so `hermes plugins update` (a pull) cannot reach HEAD from it"
            "\nFIX: pass a REF that HEAD contains"
        )
    # A copy of this repository whose default branch is the release, as GitHub's main is before a release.
    # Pushed, not cloned: CI checks out a detached merge commit that no branch holds.
    origin = tmp / "hermretro.git"
    _git("init", "--quiet", "--bare", str(origin))
    _git("symbolic-ref", "HEAD", "refs/heads/main", cwd=origin)
    _git("push", "--quiet", "--no-verify", str(origin), f"{old}:refs/heads/main")

    fix = f" --update-from {ref}"
    run = runner(hermes, tmp, fix=fix)
    studio = root / "profiles" / "hermretro"
    plugin = root / "plugins" / "hermretro"
    brokers: list[int | None] = []
    held = kept = None
    print(f"updating from {ref} ({old[:10]}) to HEAD ({new[:10]})", flush=True)
    try:
        # As a user does: install into their own profile; the page then creates the studio profile, which
        # links to that install (one copy; `hermes plugins update` runs where it was installed).
        run(root, "plugins", "install", f"file://{origin}", "--enable", "--yes-deps")
        run(root, "profile", "create", "hermretro", "--no-alias", "--no-skills")
        before = _drive(args, tmp, root, "old", brokers)
        # The old broker idles out a minute after its last connection closes (the drive sets that), which
        # the steps up to the new drive can outlast: a broker gone by itself proves no replacement. An open,
        # silent connection holds it (an idle exit waits for none) until the new drive has replaced it.
        held = hold_open(before["broker_socket"])
        # A gateway of the old version that Hermes has not restarted. Only a published release's with the backend/
        # layout: their handshake rule never changes (paths.release_fingerprint), while one between releases may not
        # match the next, and one from before backend/ reads adapter/, which the update removes.
        if _stable_release(old) and _git("ls-tree", old, "backend/system/paths.py"):
            kept = OldGateway(args, tmp, root, fix)
            kept.wait_ready()
        run(studio, "plugins", "enable", "hermretro")  # what the page's studio_profile RPC runs in the profile
        problems = []
        dirty = _git("status", "--porcelain", cwd=plugin)
        if dirty:
            problems.append(
                f"using {ref} left files git does not ignore in the plugin folder, so an update may refuse:\n"
                f"{dirty}\nFIX: ignore them in .gitignore, or stop writing them into the plugin folder"
            )

        # Bytecode of the old modules, as a Python that writes it leaves: git keeps the ignored files of folders
        # the update removes, so the new code must load (and the next update work) with them around. Not for
        # adapter/: with that folder gone, the release's broker fails its own handshake, the harder case.
        compile_all = [sys.executable, "-m", "compileall", "-q", "-x", "/(engine|adapter)/", str(plugin)]
        subprocess.run(compile_all, capture_output=True, timeout=300)

        _git("push", "--quiet", "--no-verify", str(origin), f"{new}:refs/heads/main")  # the release reaches main
        run(root, "plugins", "update", "hermretro")
        if _git("rev-parse", "HEAD", cwd=plugin) != new:
            problems.append(
                "`hermes plugins update hermretro` did not move the plugin folder to HEAD"
                f"\nFIX: reproduce with python tools/ci/clean_install_check.py{fix}"
            )
        problems += _leftovers(plugin, fix)
        problems += registers_only_in_studio(run, root, studio)
        # Registers the agent side as in the hermretro profile; the counts must still match plugin.yaml.
        report = runner(hermes, tmp, {"HERMRETRO_EVERY_PROFILE": "1"}, fix)(root, "plugins", "validate", str(plugin))
        if "matches registrations" not in report or re.search(
            r"register\(\) did not|declared (tools|hooks) .*(undeclared|not)", report
        ):
            problems.append(
                report[-2000:] + "\nFIX: after the update `hermes plugins validate` no longer matches plugin.yaml; "
                "check __init__.register and provides_tools / provides_hooks"
            )
        after = drive_holding(held, before["broker_pid"], alive, lambda: _drive(args, tmp, root, "new", brokers), fix)
        problems += _compare(before, after, fix)
        if kept is not None:
            problems += kept.problems(after)
    finally:
        clean_up(held, kept, brokers)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    broker_fate = "kept (same code)" if before.get("broker_code") == after.get("code") else "replaced (new code)"
    print(
        f"ok: {ref} updates cleanly to HEAD with `hermes plugins update` ({time.monotonic() - started:.0f} s): "
        f"games and library kept, the broker {broker_fate}, the agent side only in hermretro"
    )
    return 0


def clean_up(held, kept, brokers: list) -> None:
    """Whatever happened, leave nothing of the throwaway home running: the held connection, the old version's gateway,
    and each broker once, the drives' and the one that gateway reached (one it started in place of the new one)."""
    if held is not None:
        held.close()
    if kept is not None:
        kept.stop()
    for pid in dict.fromkeys([*brokers, kept.broker_pid if kept is not None else None]):
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass


def _leftovers(plugin: Path, fix: str) -> list[str]:
    """What the old version left that git does not track any more. Untracked and not ignored: this or the next
    update may refuse. Ignored is fine only for bytecode caches (Python never imports those without sources)."""
    problems = []
    untracked = _git("status", "--porcelain", cwd=plugin)
    if untracked:
        problems.append(
            f"after the update the plugin folder has files git does not ignore:\n{untracked}\n"
            "FIX: ignore them in .gitignore, or stop writing them into the plugin folder" + fix
        )
    # Every ignored path on its own: plain --ignored folds a folder holding only ignored files into `!! dir/`,
    # which hides what is inside. With these flags a folder is listed only when an ignore rule names it.
    listing = _git("status", "--porcelain", "-z", "--ignored=matching", "--untracked-files=all", cwd=plugin)
    return problems + ignored_problems(listing, fix)


def ignored_problems(listing: str, fix: str) -> list[str]:
    """Judge each ignored entry of `git status --porcelain -z --ignored=matching --untracked-files=all`."""
    problems = []
    for entry in listing.split("\0"):
        if not entry.startswith("!! "):
            continue
        path = entry[3:]
        if not is_bytecode(path):
            problems.append(
                f"after the update the plugin folder holds {path} (ignored by git, not a bytecode cache)\n"
                "FIX: make sure the new code never reads it, or keep it out of the plugin folder" + fix
            )
    return problems


def is_bytecode(path: str) -> bool:
    """A bytecode cache folder, a file inside one, or a compiled module."""
    return "__pycache__" in path.rstrip("/").split("/") or path.endswith((".pyc", ".pyo"))


def _compare(before: dict, after: dict, fix: str) -> list[str]:
    problems = [f"{problem}\nFIX: {after.get('fix')}{fix}" for problem in after.get("problems", [])]
    if after.get("hermretro_home") != before["hermretro_home"]:
        problems.append(
            f"the user's folder moved: {before['hermretro_home']} -> {after.get('hermretro_home')}"
            "\nFIX: keep backend/system/paths.hermretro_home() where the release kept it, or migrate it"
        )
    kept = {game["id"]: game.get("title") for game in after.get("games", [])}
    for game in before["games"]:
        if kept.get(game["id"]) != game.get("title"):
            problems.append(
                f"the library lost or renamed {game}; the new games RPC lists {kept}"
                "\nFIX: read the library (games.json) the way the release wrote it"
            )
    if sorted(after.get("pending", [])) != sorted(before["pending"]):
        problems.append(
            f"New Game conversations changed: {before['pending']} -> {after.get('pending')}"
            "\nFIX: read the library's pending records the way the release wrote them"
        )
    # The broker is replaced only when its code changed (a different fingerprint); with the same code it is kept.
    replaced = after.get("broker_pid") != before["broker_pid"]
    if before.get("broker_code") != after.get("code") and not replaced:
        problems.append(
            "the broker the release started still answers after the update"
            "\nFIX: backend/broker/client.ensure_broker must replace a broker whose code_fingerprint differs"
        )
    elif before.get("broker_code") == after.get("code") and replaced:
        problems.append(
            "the broker was restarted although its code did not change"
            "\nFIX: backend/broker/client.ensure_broker must keep a broker whose code_fingerprint matches"
        )
    return problems


def _drive(args, tmp: Path, root: Path, phase: str, brokers: list) -> dict:
    """Run `inside` with Hermes's own Python in the throwaway home and return what it found. The broker it reached goes
    into ``brokers`` for the cleanup, whether the run worked or failed after starting one."""
    out = tmp / f"{phase}.json"
    done = subprocess.run(
        inside_command(args, phase, out),
        env=inside_environment(tmp, root),
        cwd=tmp,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=300,
    )
    print(f"$ page RPCs of the {phase} version through Hermes's plugin loader  [{root.name}] -> {done.returncode}")
    found = json.loads(out.read_text()) if out.is_file() else {"fatal": (done.stdout + done.stderr)[-3000:]}
    brokers.append(found.get("broker_pid"))
    if done.returncode or "fatal" in found:
        raise SystemExit(
            found.get("fatal", "") + f"\nFIX: the {phase} version's page calls failed in a clean Hermes home "
            f"after {'installing' if phase == 'old' else 'updating'}; "
            f"reproduce with python tools/ci/clean_install_check.py --update-from {args.update_from}"
        )
    return found

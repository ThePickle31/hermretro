"""Is this machine ready for the workflow? Each item that is not says exactly how to fix it.

    doctor [--json]

git and gh, gh's login (and that it is the configured github_account), git's identity, Python and Node versions,
the pinned npm tools and ruff, Hermes and a hermes-agent source for the install scan, the main checkout on the
base branch and clean, a writable worktree root and a short temp folder for Unix sockets. With --all also the
reviewer: review_profile set, and a live probe of its provider (a few seconds).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

from . import github, repo, reviews, state
from .checks import short_tmp
from .review import runner as review_runner
from .output import Failure, cmd


def item(name: str, ok: bool, detail: str, fix: str = "") -> dict:
    return {"name": name, "ok": ok, "detail": detail, "fix": "" if ok else fix}


def _version(command: list[str]) -> str | None:
    code, out, err = repo.run(command, Path.cwd(), timeout=20)
    return ((out + err).strip().splitlines() or [""])[0] if code == 0 else None


def tools(ctx) -> list[dict]:
    found = []
    for name in ("git", "gh"):
        path = shutil.which(name)
        found.append(
            item(
                f"{name} installed",
                bool(path),
                path or "not on PATH",
                f"install {name} (https://cli.github.com for gh)",
            )
        )
    login = github.login(ctx) if shutil.which("gh") or ctx.gh_runner else None
    want = ctx.get("github_account")
    if not login:
        found.append(item("gh logged in", False, "gh answers no account", "gh auth login"))
    elif want and login != want:
        found.append(
            item(
                "gh account",
                False,
                f"gh is logged in as {login}, the setting says {want}",
                f"gh auth switch --user {want} (or python tools/retrodev config set github_account {login})",
            )
        )
    else:
        found.append(item("gh logged in", True, f"as {login}" + (" (the configured account)" if want else "")))
    for key, env in (("user.name", "GIT_AUTHOR_NAME"), ("user.email", "GIT_AUTHOR_EMAIL")):
        value = repo.git(["config", key], ctx.top, check=False).strip() or os.environ.get(env, "")
        found.append(
            item(
                f"git {key}",
                bool(value),
                value or "not set",
                f"git config {key} '<yours>' (in this repository, or globally)",
            )
        )
    found.append(
        item(
            "Python 3.11 or newer",
            sys.version_info >= (3, 11),
            sys.version.split()[0],
            "run retrodev with python3.11 or newer",
        )
    )
    node = _version(["node", "--version"]) if shutil.which("node") else None
    major = int(re.match(r"v(\d+)", node).group(1)) if node and re.match(r"v(\d+)", node) else 0
    found.append(
        item(
            "Node 22 or newer",
            major >= 22,
            node or "not installed",
            "install Node 22 or newer (the page tools need it)",
        )
    )
    return found


def npm_current(top: Path) -> tuple[bool, str]:
    lock = top / "tools" / "npm" / "package-lock.json"
    installed = top / "tools" / "npm" / "node_modules" / ".package-lock.json"
    if not installed.is_file():
        return False, "tools/npm/node_modules is not installed"
    want = json.loads(lock.read_text()).get("packages", {})
    have = json.loads(installed.read_text()).get("packages", {})
    # Optional packages for other systems (esbuild's per-platform builds) are never installed here.
    wrong = sorted(
        name
        for name, spec in want.items()
        if name
        and have.get(name, {}).get("version") != spec.get("version")
        and (name in have or not spec.get("optional"))
    )
    if wrong:
        return False, f"{len(wrong)} package(s) differ from the lockfile, e.g. {wrong[0]}"
    return True, f"{len(have)} installed packages match the lockfile"


def ruff_current(top: Path) -> tuple[bool, str]:
    stamp, ruff = top / ".dev" / "py" / "requirements.sha256", top / ".dev" / "py" / "bin" / "ruff"
    pinned = hashlib.sha256((top / "tools" / "py" / "requirements.txt").read_bytes()).hexdigest()
    if not ruff.is_file():
        return False, "ruff is not installed in .dev/py"
    if not stamp.is_file() or stamp.read_text().strip() != pinned:
        return False, "the ruff in .dev/py is not the one tools/py/requirements.txt pins"
    return True, "the pinned ruff is set up"


def hermes_source() -> Path:
    """Where tools/check.py looks for a hermes-agent checkout for the scan."""
    return Path(os.environ.get("HERMES_SOURCE") or Path.home() / ".hermes" / "hermes-agent")


def checkout(ctx) -> list[dict]:
    top, found = ctx.top, []
    if (top / "tools" / "npm" / "package-lock.json").is_file():
        ok, detail = npm_current(top)
        found.append(item("npm tools", ok, detail, "npm ci --prefix tools/npm --ignore-scripts --no-audit --no-fund"))
    if (top / "tools" / "py" / "requirements.txt").is_file():
        ok, detail = ruff_current(top)
        found.append(item("ruff", ok, detail, "python tools/py/setup.py"))
    hermes = shutil.which("hermes")
    found.append(
        item(
            "hermes on PATH",
            bool(hermes),
            hermes or "not found",
            "install Hermes Agent (the clean install check runs it)",
        )
    )
    source = hermes_source()
    ok = (source / "tools" / "plugin_guard.py").is_file()
    found.append(
        item(
            "hermes-agent source for the scan",
            ok,
            str(source),
            "set HERMES_SOURCE to a hermes-agent checkout (the scan runs its scanner)",
        )
    )
    main = ctx.main()
    branch = repo.branch(main)
    changes = repo.dirty(main)
    found.append(
        item(
            "main checkout on the base branch",
            branch == ctx.base,
            f"{main} on {branch}",
            f"ask the owner to switch {main} to {ctx.base}",
        )
    )
    found.append(
        item(
            "main checkout clean",
            not changes,
            f"{len(changes)} uncommitted change(s)",
            f"ask the owner about {cmd('git', '-C', main, 'status')}",
        )
    )
    root = ctx.worktree_root()
    probe = root if root.exists() else root.parent
    found.append(
        item(
            "worktree root writable",
            os.access(probe, os.W_OK),
            str(root),
            "python tools/retrodev config set worktree_root <a writable folder>",
        )
    )
    tmp = short_tmp()
    try:
        with tempfile.TemporaryDirectory(dir=tmp) as made:
            usable = len(made) + 30 < 104
    except OSError:
        usable = False
    found.append(
        item(
            "short temp folder for sockets",
            usable,
            tmp,
            "set XDG_RUNTIME_DIR to a short writable folder, or make /tmp writable",
        )
    )
    return found


def reviewer(ctx) -> list[dict]:
    """With --all: the reviewer is configured, and a live probe (a few seconds) says its provider answers.

    Without either, land skips the reviews and merges on green CI; so these are reported, not required."""
    settings = reviews.settings(ctx)
    configured = bool(settings["profile"])
    found = [
        item(
            "reviewer configured",
            configured,
            f"profile {settings['profile']}, {settings['provider']} {settings['model']} ({settings['reasoning']})"
            if configured
            else "no review_profile: land skips the reviews",
            "python tools/retrodev config set review_profile <the Hermes profile to run the reviewer from>",
        )
    ]
    if configured:
        probe = review_runner.probe(settings, ctx.fakes.get("review_run"))
        found.append(
            item(
                "reviewer answers",
                bool(probe.get("available")),
                f"{probe.get('reason')} ({probe.get('seconds')} s)",
                "check the provider's login and limits (hermes -p <profile> auth); land skips reviews while it is down",
            )
        )
    return found


def run(ctx, everything: bool = False) -> int:
    warning = state.override_warning()
    if warning:
        ctx.out.say(warning)
        ctx.out.set(state_override=os.environ["RETRODEV_STATE_DIR"])
    rows = tools(ctx) + checkout(ctx)
    for row in rows:
        ctx.out.say(f"  {'ok' if row['ok'] else 'NO':>2}  {row['name']}: {row['detail']}")
        if not row["ok"]:
            ctx.out.say(f"      FIX: {row['fix']}")
    if everything:
        extra = reviewer(ctx)
        for row in extra:
            ctx.out.say(f"  {'ok' if row['ok'] else 'NO':>2}  {row['name']}: {row['detail']}")
            if not row["ok"]:
                ctx.out.say(f"      FIX: {row['fix']}")
        rows += extra
    bad = [row for row in rows if not row["ok"]]
    ctx.out.set(items=rows, ready=not bad)
    if bad:
        raise Failure(
            f"{len(bad)} item(s) need fixing: " + ", ".join(row["name"] for row in bad),
            bad[0]["fix"] + (" (and the other FIX lines above)" if len(bad) > 1 else ""),
        )
    ctx.out.say("ready")
    return 0

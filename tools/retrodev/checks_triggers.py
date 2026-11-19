"""Which checks a branch's changes call for beyond the fast ones (policy.toml [checks.triggers]), and which a
`check` run selects. A generated bundle whose banner says its body is unchanged (``body: sha256``) changed in its
header alone (``sources:``, after an edit that did not change what it bundles): that calls for nothing.
"""

from __future__ import annotations

import re

from . import repo
from .output import Failure

BODY = re.compile(r"^ \* body: sha256 ([0-9a-f]{64})$", re.M)  # tools/bundle/bundle.mjs's banner line


def body_hash(text: str | None) -> str | None:
    """The ``body: sha256`` of a generated file's opening banner (None without one)."""
    head = (text or "")[:4096]
    found = BODY.search(head) if head.startswith("/**\n") else None
    return found.group(1) if found else None


def banner_only(top, base: str, path: str) -> bool:
    """The branch changed ``path`` only in its banner: both sides carry the same body hash."""
    point = repo.merge_base(top, base)
    file = top / path
    if not point or not file.is_file():
        return False
    now = body_hash(file.read_text(encoding="utf-8", errors="replace")[:4096])
    code, before, _err = repo.run(["git", "show", f"{point}:{path}"], top)
    return bool(now) and not code and body_hash(before) == now


def known(ctx) -> list[str]:
    return list(ctx.policy["checks"]["inputs"])


def triggered(ctx) -> dict[str, str]:
    """{check: why} for the checks the branch's changes call for beyond the fast ones."""
    changed = repo.changed_files(ctx.top, ctx.remote_base)
    if changed is None:
        return {}
    generated = set(ctx.policy["generated"]["files"])
    changed = [p for p in changed if p not in generated or not banner_only(ctx.top, ctx.remote_base, p)]
    found = {}
    for name, patterns in ctx.policy["checks"]["triggers"].items():
        hits = [path for path in changed if repo.matches(path, patterns)]
        if hits:
            found[name] = f"changed {hits[0]}" + (f" and {len(hits) - 1} more" if len(hits) > 1 else "")
    if "clean_install" in found:
        moved = repo.moved_or_deleted(ctx.top, ctx.remote_base)
        if moved:
            found["update"] = f"moved or deleted {moved[0]}" + (f" and {len(moved) - 1} more" if len(moved) > 1 else "")
    return found


def required(ctx) -> dict[str, str]:
    """What must pass on a tree before it may be shipped: the fast checks plus the triggered ones."""
    return {name: "fast" for name in ctx.policy["checks"]["fast"]} | triggered(ctx)


def select(ctx, names: list[str], full: bool, need: dict[str, str] | None = None) -> dict[str, str]:
    if names:
        unknown = [name for name in names if name not in known(ctx)]
        if unknown:
            raise Failure(f"unknown check: {', '.join(unknown)}", "use one of: " + ", ".join(known(ctx)))
        return {name: "asked" for name in names}
    wanted = dict(need if need is not None else required(ctx))
    if full:
        wanted |= {"scaffold": "--full", "acceptance": "--full", "clean_install": "--full"}
    return wanted

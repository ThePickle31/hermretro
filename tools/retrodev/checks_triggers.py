"""Which checks a branch's changes call for beyond the fast ones (policy.toml [checks.triggers]), and which a
`check` run selects. A generated bundle whose banner says its body is unchanged (``body: sha256``) changed in its
header alone (``sources:``, after an edit that did not change what it bundles): that calls for nothing. Nor does a
file [checks.trigger_ignore] lists for that check, or a change to a scaffold-parsed file made only of the lines `new`
itself writes there ([checks.new_lines]). A change to a file only the nested scaffold run reads
([checks.nested_triggers]: the tests the grown copy runs, which CI's page job runs with RD_SCAFFOLD_FULL=nested)
adds scaffold in that nested mode, so a test that reads the surrounding tree fails here as it would in CI; a
generated file there ([generated] files: the registration snapshot `new tool` and `new rpc` rewrite) never does.
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


def changed_lines(top, base: str, path: str) -> list[str] | None:
    """The lines the branch added or removed in ``path`` since it left ``base`` (None when git cannot say)."""
    point = repo.merge_base(top, base)
    if not point:
        return None
    code, out, _err = repo.run(["git", "diff", "-U0", "--no-color", "--no-ext-diff", point, "--", path], top)
    if code:
        return None
    return [line[1:] for line in out.splitlines() if line[:1] in "+-" and not line.startswith(("+++", "---"))]


def only_new_lines(top, base: str, path: str, patterns: list[str]) -> bool:
    """The branch's change to ``path`` is only lines `new` writes (each matches one of ``patterns``)."""
    lines = changed_lines(top, base, path) if patterns else None
    return bool(lines) and all(any(re.fullmatch(p, line) for p in patterns) for line in lines)


NESTED = "; run nested (RD_SCAFFOLD_FULL=nested), as CI's page job runs those tests in its grown copy"


def nested(why: str) -> bool:
    """The scaffold check was added for a file the nested mode reads: run it with RD_SCAFFOLD_FULL=nested."""
    return why.endswith(NESTED)


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
    ignore = ctx.policy["checks"].get("trigger_ignore", {})
    new_lines = ctx.policy["checks"].get("new_lines", {})
    for name, patterns in ctx.policy["checks"]["triggers"].items():
        hits = [
            path for path in changed if repo.matches(path, patterns) and not repo.matches(path, ignore.get(name, []))
        ]
        if name == "scaffold":
            hits = [p for p in hits if not only_new_lines(ctx.top, ctx.remote_base, p, new_lines.get(p, []))]
        if hits:
            found[name] = f"changed {hits[0]}" + (f" and {len(hits) - 1} more" if len(hits) > 1 else "")
    deep = [  # never a generated file (tests/repo/registration.json): `new tool` and `new rpc` rewrite it
        path
        for path in changed
        if path not in generated
        and repo.matches(path, ctx.policy["checks"].get("nested_triggers", {}).get("scaffold", []))
    ]
    if deep:
        found["scaffold"] = f"changed {deep[0]}" + (f" and {len(deep) - 1} more" if len(deep) > 1 else "") + NESTED
    if "clean_install" in found:
        moved = repo.moved_or_deleted(ctx.top, ctx.remote_base)
        if moved:
            found["update"] = f"moved or deleted {moved[0]}" + (f" and {len(moved) - 1} more" if len(moved) > 1 else "")
    return found


def required(ctx) -> dict[str, str]:
    """What must pass on a tree before it may be shipped: the fast checks plus the triggered ones."""
    return {name: "fast" for name in ctx.policy["checks"]["fast"]} | triggered(ctx)


def select(ctx, names: list[str], full: bool, need: dict[str, str] | None = None) -> dict[str, str]:
    """{check: why} for this run. The scaffold check's mode is the branch's, however it was asked for: on a branch
    that calls for it nested, a named `check scaffold`, `--again` and `--full` run it nested too, so their pass
    lands under the nested digest the shipping record asks for (a fast-mode pass there would revoke it)."""
    wanted = dict(need if need is not None else required(ctx))
    deep = {"scaffold": wanted["scaffold"]} if nested(wanted.get("scaffold", "")) else {}
    if names:
        unknown = [name for name in names if name not in known(ctx)]
        if unknown:
            raise Failure(f"unknown check: {', '.join(unknown)}", "use one of: " + ", ".join(known(ctx)))
        return {name: deep.get(name, "asked") for name in names}
    if full:
        wanted |= {"scaffold": "--full", "acceptance": "--full", "clean_install": "--full"} | deep
    return wanted

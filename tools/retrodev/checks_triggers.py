"""Which checks a branch's changes call for beyond the fast ones (policy.toml [checks.triggers]), and which a
`check` run selects. A generated bundle whose banner says its body is unchanged (``body: sha256``) changed in its
header alone (``sources:``, after an edit that did not change what it bundles): that calls for nothing. Nor does a
file [checks.trigger_ignore] lists for that check, or a change to a scaffold-parsed file made only of the lines `new`
itself writes there ([checks.new_lines]). A change to a file only the nested scaffold run reads
([checks.nested_triggers]: the tests the grown copy runs, which CI's page job runs with RD_SCAFFOLD_FULL=nested)
adds scaffold in that nested mode, so a test that reads the surrounding tree fails here as it would in CI; a
generated file there ([generated] files: the registration snapshot `new tool` and `new rpc` rewrite) never does, nor
a change to one made only of comments, docstrings and blank lines (comment_only: no test runs differently).
A branch whose only change is plugin.yaml's ``version:`` line (a release's version pull request) calls for the clean
install but not acceptance, as CI's tools/ci/changes.py decides for the integration tier (the same rule, kept apart:
tools/ci and retrodev import nothing of each other). The backend reads that line (backend/system/paths.py), but the
real-engine run only records it; unit (tests/repo/test_version.py) and the clean install check what a new value does.
"""

from __future__ import annotations

import re

from . import comment_only, repo
from .output import Failure

# diff output to parse, whatever the user's git config says (color.ui=always would prefix every line with escapes)
PLAIN = ("--no-color", "--no-ext-diff")

BODY = re.compile(r"^ \* body: sha256 ([0-9a-f]{64})$", re.M)  # tools/bundle/bundle.mjs's banner line
VERSION_LINE = re.compile(r"^version:[ \t]*[\"']?([^\"'\s#]+)[\"']?.*$")  # release.VERSION_LINE, one line at a time


def only_version_line(diff: str) -> bool:
    """A `git diff -U0` of plugin.yaml that removes one `version:` line and adds one, and changes nothing else."""
    changed = [line for line in diff.splitlines() if line[:1] in "+-" and not line.startswith(("+++", "---"))]
    removed = [line[1:] for line in changed if line[0] == "-"]
    added = [line[1:] for line in changed if line[0] == "+"]
    return len(removed) == len(added) == 1 and all(VERSION_LINE.match(line) for line in removed + added)


def version_only(top, base: str) -> bool:
    """The branch (committed or not) changed plugin.yaml's version line and nothing else in it."""
    point = repo.merge_base(top, base)
    if not point:
        return False
    code, diff, _err = repo.run(["git", "diff", *PLAIN, "-U0", point, "--", "plugin.yaml"], top)
    return not code and only_version_line(diff)


def beyond_version(top, old: str, new: str) -> str | None:
    """None when ``old``..``new`` changes only plugin.yaml's version line; else what it changes besides."""
    names = repo.git(["diff", *PLAIN, "--name-only", old, new], top).split()
    diff = repo.git(["diff", *PLAIN, "-U0", old, new, "--", "plugin.yaml"], top)
    if names == ["plugin.yaml"] and only_version_line(diff):
        return None
    lines = [line for line in diff.splitlines() if line[:1] in "+-" and not line.startswith(("+++", "---"))]
    return (", ".join(names) or "no file") + ("; plugin.yaml: " + " | ".join(lines[:6]) if lines else "")


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


def comments_changed(top, base: str, path: str) -> bool:
    """The branch changed only comments, docstrings or blank lines of ``path`` (comment_only; False when unsure)."""
    point = repo.merge_base(top, base)
    file = top / path
    if not point or not file.is_file():
        return False
    code, before, _err = repo.run(["git", "show", f"{point}:{path}"], top)
    after = file.read_text(encoding="utf-8", errors="replace")
    return not code and comment_only.comments_only(path, before, after)


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
    bumped = changed == ["plugin.yaml"] and version_only(ctx.top, ctx.remote_base)  # as CI: nothing else changed
    ignore = ctx.policy["checks"].get("trigger_ignore", {})
    new_lines = ctx.policy["checks"].get("new_lines", {})
    for name, patterns in ctx.policy["checks"]["triggers"].items():
        hits = [
            path for path in changed if repo.matches(path, patterns) and not repo.matches(path, ignore.get(name, []))
        ]
        if name == "acceptance" and bumped:
            hits = [path for path in hits if path != "plugin.yaml"]  # the version line alone: no engine run
        if name == "scaffold":
            hits = [p for p in hits if not only_new_lines(ctx.top, ctx.remote_base, p, new_lines.get(p, []))]
        if hits:
            found[name] = f"changed {hits[0]}" + (f" and {len(hits) - 1} more" if len(hits) > 1 else "")
    deep = [  # never a generated file (tests/repo/registration.json): `new tool` and `new rpc` rewrite it
        path
        for path in changed
        if path not in generated
        and repo.matches(path, ctx.policy["checks"].get("nested_triggers", {}).get("scaffold", []))
        and not comments_changed(ctx.top, ctx.remote_base, path)
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

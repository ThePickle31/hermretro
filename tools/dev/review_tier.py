"""A change's review tier, from the paths it changes (tools/review/README.md, "Tiers"), and what commits after a pass
still need. Standard library only."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass

LIGHT, STANDARD, SENSITIVE = "light", "standard", "sensitive"
# Changed lines past which a change is sensitive for its size alone (lockfiles and generated files not counted).
LARGE = 1000

# What makes a path sensitive, in the README's order: (pattern, reason). fnmatch, so `*` also matches `/`.
SENSITIVE_PATHS = (
    ("backend/broker/*", "the broker and its handshake"),
    ("backend/system/paths.py", "the broker and its handshake"),
    ("backend/setup/*", "the prepared engine copy, setup, removal and the factory reset"),
    ("backend/hermes/hooks.py", "the hardware approvals"),
    ("backend/player/server.py", "the player's loopback server"),
    ("engine/scripts/*", "what runs on a user's machine from the engine"),
    ("__init__.py", "the plugin's entry point and manifest"),
    ("plugin.yaml", "the plugin's entry point and manifest"),
    (".github/workflows/*", "CI and the update and install checks"),
    (".github/actions/*", "CI and the update and install checks"),
    ("tools/ci/*", "CI and the update and install checks"),
)
# Generated files and lockfiles: their lines don't count towards a change's size.
UNCOUNTED = (
    "desktop/plugin.js",
    "player/frame-shim.js",
    "page/app/rpc-names.js",
    "page/pages/build/workflow.js",
    "engine/dist/server.js",
    "engine/contract/manifest.json",
    "*package-lock.json",
)
# Markdown an agent acts on: never light.
AGENT_FACING = ("skills/*", "profile/*", ".agents/*", "AGENTS.md", "tools/review/*")


@dataclass(frozen=True)
class Changed:
    path: str
    lines: int


@dataclass(frozen=True)
class Judged:
    tier: str
    reasons: tuple[str, ...]


def _matches(path: str, patterns) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def sensitive(path: str) -> str | None:
    """Why a path is sensitive, or None."""
    return next((reason for pattern, reason in SENSITIVE_PATHS if fnmatch.fnmatchcase(path, pattern)), None)


def is_test(path: str) -> bool:
    return path.startswith("tests/")


def is_documentation(path: str) -> bool:
    """Markdown nothing acts on: not what an agent reads (AGENT_FACING)."""
    return path.endswith(".md") and not _matches(path, AGENT_FACING)


def judge(changed: list[Changed]) -> Judged:
    reasons: list[str] = []
    for file in changed:
        reason = sensitive(file.path)
        if reason and reason not in reasons:
            reasons.append(reason)
    lines = sum(file.lines for file in changed if not _matches(file.path, UNCOUNTED))
    if lines > LARGE:
        reasons.append(f"{lines} changed lines")
    if reasons:
        return Judged(SENSITIVE, tuple(reasons))
    if all(is_documentation(file.path) or is_test(file.path) for file in changed):
        return Judged(LIGHT, ())
    return Judged(STANDARD, ())


# What commits after a pass need: nothing, a pass that reads the tests alone, or a pass.
NOTHING, TESTS, PASS = "nothing", "tests", "pass"


def later(changed: list[Changed]) -> str:
    """What the files changed since a pass need of the review (a test or a README on a sensitive path is read as part
    of the change)."""
    if any(sensitive(file.path) for file in changed):
        return PASS
    if all(is_documentation(file.path) for file in changed):
        return NOTHING
    if all(is_documentation(file.path) or is_test(file.path) for file in changed):
        return TESTS
    return PASS


def numstat(text: str) -> list[Changed]:
    """`git diff --numstat --no-renames -z` as changed files; a binary file counts no lines."""
    found = []
    for entry in text.split("\0"):
        fields = entry.lstrip("\n").split("\t", 2)
        if len(fields) == 3 and fields[2]:
            added, deleted, path = fields
            found.append(
                Changed(path, (int(added) if added.isdigit() else 0) + (int(deleted) if deleted.isdigit() else 0))
            )
    return found

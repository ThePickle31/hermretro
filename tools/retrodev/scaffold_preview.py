"""What `new --dry-run` says after its diff: the next steps the real run would print, as a preview.

A dry run writes nothing, so its steps are what to do once the files exist, and every `new` command in them keeps
`--dry-run` (an agent pastes a printed command verbatim: from a preview it must not write). A later `new --dry-run`
reads the tree as it is, so it does not see this preview's files: preview the next piece after this one is written.
"""

from __future__ import annotations

import re

# `python tools/retrodev new <kind> <args>` and its `| new <kind> <args>` alternatives: each ends before the next
# `|`, `;`, bracket or backtick (a command inside prose is quoted in backticks), or at the end of the step.
NEW = re.compile(r"((?:python tools/retrodev |(?<=\| ))new [a-z]+(?: [^|;()`\s]+)*)")
HEAD = (
    "once these files are written, the real run's next steps (a preview: a later new --dry-run reads the tree as it "
    "is, without these files):"
)


def previewed(step: str) -> str:
    """``step`` with `--dry-run` after every `new` command it names (unless that command has it already)."""
    return NEW.sub(lambda match: dry_command(match.group(1)), step)


def dry_command(command: str) -> str:
    """The scaffold hints use unquoted identifiers and flags; an identifier can contain the text of a flag."""
    return command if "--dry-run" in command.split() else command + " --dry-run"


def show(out, steps: list[str]) -> None:
    """Print the previewed steps under one heading, and keep them as the JSON's `next`."""
    shown = [previewed(step) for step in steps]
    out.set(next=shown)
    if shown:
        out.say(HEAD)
    for step in shown:
        out.say("would next: " + step)

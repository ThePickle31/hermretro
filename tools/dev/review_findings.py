"""A pass's findings as its reviewer writes them, one `## <label>: <where> <what>` heading each, and the author's
answer to every one (tools/review/README.md, "Findings and answers"). Standard library only."""

from __future__ import annotations

from dataclasses import dataclass

# Each label and the answers it takes: (answer, needs a reason).
ANSWERS = {
    "Important": (("fixed", False), ("wrong", True), ("intentional", True)),
    "Nit": (("fixed", False), ("declined", True)),
    "Pre-existing": (("noted", False),),
    "Question": (("changed", False), ("kept", True)),
    "Out of scope": (("noted", False),),
}
NITS = 3  # a pass's Nits past these go unanswered
NONE = "No findings."


class FindingsError(ValueError):
    """A findings or answers file that isn't as the README says."""


@dataclass(frozen=True)
class Finding:
    label: str
    what: str  # after the label: where, and what

    @property
    def heading(self) -> str:
        return f"## {self.label}: {self.what}"


@dataclass(frozen=True)
class Answered:
    finding: Finding
    answer: str
    reason: str


def parse(text: str) -> tuple[list[Finding], int]:
    """The findings in a reviewer's file, in order, and how many Nits past NITS it dropped."""
    if text.strip() == NONE:
        return [], 0
    findings = []
    for line in text.splitlines():
        if not line.startswith("## "):
            continue
        label, _, what = line[3:].partition(":")
        if label.strip() not in ANSWERS or not what.strip():
            labels = " | ".join(ANSWERS)
            raise FindingsError(f'"{line}" isn\'t a finding: each heading is ## <{labels}>: <path>:<line> <what>.')
        findings.append(Finding(label.strip(), what.strip()))
    if not findings:
        raise FindingsError(f"The findings hold no ## heading and don't say `{NONE}` alone.")
    headings = [finding.heading for finding in findings]
    twice = sorted({heading for heading in headings if headings.count(heading) > 1})
    if twice:
        raise FindingsError(f'"{twice[0]}" is the heading of two findings: each needs its own, to be answered.')
    kept, nits = [], 0
    for finding in findings:
        if finding.label == "Nit":
            nits += 1
            if nits > NITS:
                continue
        kept.append(finding)
    return kept, len(findings) - len(kept)


def skeleton(findings: list[Finding]) -> str:
    """The file the author answers in: each finding's heading with an `Answer:` line to fill."""
    lines = [
        "One answer under each finding: `Answer: <answer>`, then why where it asks for a reason.",
        "Important: fixed | wrong <why> | intentional <why>. Nit: fixed | declined <why>.",
        "Question: changed | kept <why>. Pre-existing and Out of scope: noted.",
    ]
    for finding in findings:
        lines += ["", finding.heading, "Answer:"]
    return "\n".join(lines) + "\n"


def answers(findings: list[Finding], text: str) -> list[Answered]:
    """Every finding with its answer from text, refusing one unanswered or answered as its label doesn't take."""
    lines = text.splitlines()
    answered = []
    for finding in findings:
        try:
            at = next(index for index, line in enumerate(lines) if line.rstrip() == finding.heading)
        except StopIteration:
            raise FindingsError(f'No answer to "{finding.heading}".') from None
        given = ""
        for line in lines[at + 1 :]:
            if line.startswith("## "):
                break
            if line.strip().startswith("Answer:"):
                given = line.strip().removeprefix("Answer:").strip()
                break
        if not given:
            raise FindingsError(f'No answer to "{finding.heading}".')
        word, _, reason = given.partition(" ")
        reason = reason.strip().lstrip("—-: ").strip()
        taken = dict(ANSWERS[finding.label])
        if word not in taken:
            raise FindingsError(f'"{finding.heading}" is answered "{given}": its answer is one of {", ".join(taken)}.')
        if taken[word] and not reason:
            raise FindingsError(f'"{finding.heading}" is {word}: say why after it.')
        answered.append(Answered(finding, word, reason))
    return answered

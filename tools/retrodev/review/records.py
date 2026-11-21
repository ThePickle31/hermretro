"""Review records: every round of a pull request, kept as JSON with a readable copy.

    <reviews root>/<pr>.json         the record (rounds, audits, answers, a skipped reviews' reason)
    <main checkout>/notes/reviews/pr<N>.md   the same, readable (notes/ is git-ignored)

A round entry: {round, sha, started, inputs, output, session_ids, result, errors, audit, void, seconds,
answers: {"<finding index>": text}}. ``next_action`` reads a record and says what landing does next.

How many rounds a pull request gets: record['depth'] = {rounds, why}, written by land (land_depth.py) from the
policy and the findings. After that many rounds the head that answers the last round's findings is accepted
(record['accepted'] = {head, at, round}) and merges without another round. MAX_ROUNDS is the hard limit: a push
after a clean round or after the accepted head is still reviewed, until that many rounds ran. A record without
'depth' (written before it existed) keeps MAX_ROUNDS.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from retrodev.review import inputs

MAX_ROUNDS = inputs.MAX_ROUNDS


def record_path(root: Path, pr: int) -> Path:
    return Path(root) / f"{pr}.json"


def notes_dir(repo: Path | str) -> Path | None:
    main = inputs.main_checkout(repo)
    return main / "notes" / "reviews" if main else None


def load(root: Path, pr: int) -> dict:
    path = record_path(root, pr)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"pr": pr, "rounds": [], "skipped": None, "probes": []}


def save(root: Path, record: dict, notes: Path | None = None) -> Path:
    path = record_path(root, record["pr"])
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{record['pr']}-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)
    if notes:
        Path(notes).mkdir(parents=True, exist_ok=True)
        (Path(notes) / f"pr{record['pr']}.md").write_text(markdown(record), encoding="utf-8")
    return path


def add_round(root: Path, pr: int, entry: dict, notes: Path | None = None) -> dict:
    record = load(root, pr)
    entry = {"started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "answers": {}, "void": False, **entry}
    record["rounds"].append(entry)
    record["skipped"] = None
    save(root, record, notes)
    return record


def add_probe(root: Path, pr: int, probe: dict, notes: Path | None = None) -> dict:
    record = load(root, pr)
    record.setdefault("probes", []).append({"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **probe})
    save(root, record, notes)
    return record


def mark_skipped(root: Path, pr: int, reason: str, notes: Path | None = None) -> dict:
    record = load(root, pr)
    record["skipped"] = {"reason": reason, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    save(root, record, notes)
    return record


def note_head(root: Path, pr: int, sha: str, notes: Path | None = None) -> dict:
    """Remember the PR's newest pushed head (fixes pushed after a round make the next one due)."""
    record = load(root, pr)
    record["head"] = sha
    save(root, record, notes)
    return record


def answer(
    pr: int,
    round_no: int,
    finding_index: int,
    text: str,
    *,
    repo: Path | str = ".",
    root: Path | None = None,
    notes: Path | None = None,
) -> dict:
    """Add the author's answer to one finding of a (valid) round: a fix's commit or a reasoned refusal with proof."""
    root = inputs.reviews_root(repo, root)
    record = load(root, pr)
    entry = _valid_round(record, round_no)
    findings = (entry.get("result") or {}).get("findings") or []
    if not 0 <= finding_index < len(findings):
        raise IndexError(f"round {round_no} has {len(findings)} findings; no finding {finding_index}")
    entry.setdefault("answers", {})[str(finding_index)] = text
    save(root, record, notes if notes is not None else notes_dir(repo))
    return record


def _valid_round(record: dict, round_no: int) -> dict:
    for entry in reversed(record["rounds"]):
        if entry["round"] == round_no and not entry.get("void"):
            return entry
    raise KeyError(f"PR #{record['pr']} has no valid round {round_no}")


def valid_rounds(record: dict) -> list[dict]:
    return [r for r in record["rounds"] if not r.get("void") and r.get("result") is not None]


def findings_and_answers(entry: dict) -> str:
    """One round's findings with the author's answers, as the next reviewer reads them."""
    lines = [f"Round {entry['round']} (head {entry['sha'][:7]}): verdict {entry['result']['verdict']}"]
    answers = entry.get("answers") or {}
    for n, f in enumerate(entry["result"].get("findings") or []):
        lines += [
            "",
            f"Finding {n} [{f.get('severity')}] {f.get('file')}:{f.get('line')}",
            f"  Problem: {f.get('problem')}",
            f"  Suggested fix: {f.get('fix')}",
            f"  Evidence: {f.get('evidence')}",
            f"  Author's answer: {answers.get(str(n), '(none yet)')}",
        ]
    return "\n".join(lines) + "\n"


def earlier_inputs(record: dict) -> tuple[dict[int, str], str | None]:
    """For the next round's folder: {round: findings-and-answers text}, and the head the last valid round saw."""
    rounds = valid_rounds(record)
    return {r["round"]: findings_and_answers(r) for r in rounds}, (rounds[-1]["sha"] if rounds else None)


def next_round(record: dict) -> int:
    return len(valid_rounds(record)) + 1


def depth(record: dict) -> int:
    """Rounds after which the answered findings are accepted without another round (1..MAX_ROUNDS)."""
    try:
        wanted = int((record.get("depth") or {}).get("rounds") or MAX_ROUNDS)
    except (TypeError, ValueError):
        wanted = MAX_ROUNDS
    return min(MAX_ROUNDS, max(1, wanted))


def accepted_head(record: dict) -> str | None:
    """The head accepted with the last valid round's fixes. An acceptance belongs to one round: a later round with
    findings of its own needs a new one (older records name no round: theirs was round MAX_ROUNDS)."""
    accepted = record.get("accepted") or {}
    rounds = valid_rounds(record)
    if not accepted.get("head") or not rounds or accepted.get("round", MAX_ROUNDS) != rounds[-1]["round"]:
        return None
    return accepted["head"]


def accept_head(root: Path, pr: int, sha: str, notes: Path | None = None) -> dict:
    """Remember the one head accepted with the last round's fixes (merged without another round)."""
    record = load(root, pr)
    if accepted_head(record) is None:
        last = valid_rounds(record)[-1]["round"]
        record["accepted"] = {"head": sha, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "round": last}
        save(root, record, notes)
    return record


def only_low(entry: dict) -> bool:
    """Every finding of the round is rated low (and there is one)."""
    found = (entry.get("result") or {}).get("findings") or []
    return bool(found) and all(f.get("severity") == "low" for f in found)


def reviewed_as(record: dict, head: str) -> str:
    """The reviewed head that ``head`` stands for: a head that only merged the base branch after it keeps its review
    (record['carried'], written by land_carry), else ``head`` itself."""
    for entry in record.get("carried") or []:
        if entry.get("head") == head:
            return entry["reviewed"]
    return head


def next_action(record: dict, ci_green: bool, head: str | None = None) -> str:
    """What landing does next.

    'merge-on-green' reviews were skipped (reason in record['skipped']); 'needs-owner' the last round was void
    twice; 'review' no valid round yet, or a push after the last round that no acceptance covers and fewer than
    MAX_ROUNDS ran; 'fix' the last round has findings and nothing new is pushed; 'fix-then-merge' the pull
    request's last due round (``depth``) had findings and this head is the one accepted with their fixes (or none
    is accepted yet: landing records this one); 'merge' the last round is clean on the current head and CI is
    green; 'wait-ci' clean, CI not green; 'reviews-exhausted' MAX_ROUNDS ran and the head moved past the reviewed
    (or accepted) head: the owner decides.

    Before MAX_ROUNDS, a head is accepted only when it differs from the reviewed one (fixes were pushed) or every
    finding was rated low: findings above low that are only disputed, with nothing pushed, get a round to judge the
    answers ('fix', which land turns into 'review' once all are answered).

    A clean verdict counts only for the head it reviewed, whatever the round count (or a head carried over from it:
    one that only merged the base branch after it, ``reviewed_as``)."""
    if record.get("skipped"):
        return "merge-on-green"
    if record["rounds"] and record["rounds"][-1].get("stopped"):
        return "needs-owner"
    rounds = valid_rounds(record)
    if not rounds:
        return "review"
    last = rounds[-1]
    head = reviewed_as(record, head or record.get("head") or last["sha"])
    exhausted = len(rounds) >= MAX_ROUNDS
    if last["result"]["verdict"] == "clean":
        if head == last["sha"]:
            return "merge" if ci_green else "wait-ci"
        return "reviews-exhausted" if exhausted else "review"
    if len(rounds) >= depth(record):
        accepted = accepted_head(record)
        if accepted == head:
            return "fix-then-merge"
        if accepted is not None:
            return "reviews-exhausted" if exhausted else "review"
        if exhausted or head != last["sha"] or only_low(last):
            return "fix-then-merge"
        return "fix"
    return "review" if head != last["sha"] else "fix"


def markdown(record: dict) -> str:
    out = [f"# Reviews of PR #{record['pr']}", ""]
    if record.get("skipped"):
        out += [f"Reviews skipped: {record['skipped']['reason']} ({record['skipped'].get('at', '')})", ""]
    if record.get("depth"):
        out += [f"Review depth: {record['depth'].get('why')}", ""]
    for p in record.get("probes", []):
        out.append(
            f"- probe {p.get('at', '')}: {'available' if p.get('available') else 'unavailable'}"
            f" ({p.get('reason')}, {p.get('seconds')} s)"
        )
    for entry in record["rounds"]:
        result = entry.get("result") or {}
        state = "VOID" if entry.get("void") else result.get("verdict", "no valid reply")
        out += ["", f"## Round {entry['round']}: {state}", ""]
        out.append(f"- head {entry.get('sha')}, started {entry.get('started')}, {entry.get('seconds')} s")
        out.append(f"- sessions: {', '.join(entry.get('session_ids') or []) or '(none)'}")
        out.append(f"- raw output: {entry.get('output')}")
        audit = entry.get("audit") or {}
        out.append(f"- audit: {'ok' if audit.get('ok') else 'FAILED'}; tools used {audit.get('tools', {})}")
        out += [f"  - {v}" for v in audit.get("violations", [])]
        out += [f"- reply error: {e}" for e in entry.get("errors") or []]
        for n, f in enumerate(result.get("findings") or []):
            out += [
                "",
                f"### Finding {n} [{f.get('severity')}] `{f.get('file')}:{f.get('line')}`",
                "",
                f"**Problem.** {f.get('problem')}",
                "",
                f"**Fix.** {f.get('fix')}",
                "",
                f"**Evidence.** {f.get('evidence')}",
                "",
                f"**Answer.** {(entry.get('answers') or {}).get(str(n), '(none yet)')}",
            ]
        if result.get("checked"):
            out += ["", "Checked:"] + [f"- {c}" for c in result["checked"]]
    for entry in record.get("carried") or []:
        out += [
            "",
            f"Head {entry['head']} only merged the base branch after the review of {entry['reviewed']}: the review "
            f"carries over (merge resolution, not reviewed: {entry['resolution_lines']} lines; {entry.get('at')})",
        ]
    return "\n".join(out) + "\n"

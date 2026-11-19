"""check.py's results as a table in GitHub Actions' run summary ($GITHUB_STEP_SUMMARY), with each failure's detail."""

from __future__ import annotations

import os


def write(rows: list[tuple[str, str, float, str]]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = ["| Check | Result | Time | Detail |", "|---|---|---|---|"]
    lines += [
        f"| {name} | {state} | {seconds:.1f} s | {detail.splitlines()[0][:150] if detail else ''} |"
        for name, state, seconds, detail in rows
    ]
    failures = [(name, detail) for name, state, _s, detail in rows if state == "FAILED"]
    for name, detail in failures:
        lines += ["", f"### {name}", "```", detail[-3000:], "```"]
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")

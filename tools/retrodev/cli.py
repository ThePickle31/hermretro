"""retrodev: hermretro's working agreement as commands, each refusing to skip a step.

  1 discuss   2 plan new / plan show   3 plan approve, start   4 check, ship   5 report
  6 approve <pr>   7 land <pr> (reviews, CI, merge; answer <pr> ... between rounds)   8 summary <pr>
  any time: status (the next step), doctor, sync, gc, config

Exit codes: 0 ok, 1 failed, 2 still waiting, 3 needs the owner. Every failure ends with a FIX: line.
--json prints one JSON object instead of text. Read tools/retrodev/README.md for the whole flow.
"""

from __future__ import annotations

import argparse
import functools
import os
from pathlib import Path

from . import approve, checks, config, doctor, gc, land, plan, report, ship, start, status, summary, sync, watch
from .output import FAILED, Failure, Out


@functools.cache
def parser() -> argparse.ArgumentParser:
    # --json works before or after the command (a subcommand's default must not reset it: SUPPRESS).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="print one JSON object")
    top = argparse.ArgumentParser(
        prog="python tools/retrodev",
        description=(__doc__ or "").strip().split("\n\n")[0],
        epilog="Exit codes: 0 ok, 1 failed, 2 still waiting, 3 needs the owner. Every command takes --json.",
    )
    top.add_argument("--json", action="store_true", help="print one JSON object (for agents)")
    sub = top.add_subparsers(dest="command", required=True, metavar="<command>")

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        return sub.add_parser(name, help=help_text, description=help_text, parents=[common])

    p = add("plan", "write, show and approve plans (notes/plans/<topic>.md)")
    plans = p.add_subparsers(dest="action", required=True, metavar="<action>")
    plans.add_parser("new", help="write a plan from the template", parents=[common]).add_argument("topic")
    plans.add_parser("show", help="a plan and its approval (none: all)", parents=[common]).add_argument(
        "topic", nargs="?"
    )
    approve = plans.add_parser("approve", help="record the owner's go with their exact words", parents=[common])
    approve.add_argument("topic")
    approve.add_argument("--words", required=True, help="the owner's exact words")
    plans.add_parser(
        "link", help="this branch works under a plan (one plan may cover several branches)", parents=[common]
    ).add_argument("topic")

    p = add("start", "a worktree on a new <kind>/<topic> branch from the base branch, set up")
    p.add_argument("branch", help="feat/<topic>, fix/<topic>, docs/<topic> or chore/<topic>")
    p.add_argument("--no-plan", action="store_true", help="docs/ and chore/ only: a small change without a plan")
    p.add_argument("--plan", metavar="TOPIC", help="the approved plan this branch is part of (default: its topic)")
    p.add_argument("--no-setup", action="store_true", help="skip npm ci and the ruff setup")

    p = add("check", "the checks whose inputs changed (cached passes print 'ok (cached)')")
    names = ", ".join(config.load_policy(Path(__file__).resolve().parents[2])["checks"]["inputs"])
    p.add_argument("names", nargs="*", help="only these checks: " + names)
    p.add_argument("--again", action="store_true", help="ignore earlier passes (with --watch: on its first run)")
    p.add_argument("--full", action="store_true", help="also the real-engine run and the clean install")
    p.add_argument("--watch", action="store_true", help="run again on every file change")

    p = add("ship", "push the branch and open (or update) its draft pull request")
    p.add_argument("--title", required=True, help="one plain sentence, no trailing period")
    p.add_argument("--body", required=True, help="a file with every pull request template section filled in")
    p.add_argument("--dry-run", action="store_true", help="run the gates and print what it would do")

    add("report", "the factual half of the step-5 report")

    p = add("approve", "record the owner's approval of a pull request (once); readies a draft")
    p.add_argument("pr", type=int)
    p.add_argument("--words", required=True, help="the owner's exact words")
    p = add("land", "review rounds, CI on the exact head and the squash merge of an approved pull request")
    p.add_argument("pr", type=int)
    p.add_argument("--no-review", action="store_true", help="skip the reviews (the owner's call), merge on green CI")
    p.add_argument("--ci-timeout", type=float, metavar="SECONDS", help="how long to wait for CI (policy default 1500)")
    p.add_argument("--dry-run", action="store_true", help="print the gates and the next step; change nothing")
    p = add("answer", "answer a review round's finding: the fix's commit, or why it is wrong with proof")
    p.add_argument("pr", type=int)
    p.add_argument("round", type=int)
    p.add_argument("index", nargs="?", type=int, help="the finding's number (as land printed it)")
    p.add_argument("text", nargs="?", help="the answer")
    p.add_argument("--all", metavar="TEXT", dest="every", help="the same answer for every finding of the round")
    add("summary", "the step-8 note's facts: added, changed, fixed, removed, reviews, CI, restarts").add_argument(
        "pr", type=int
    )
    add("sync", "merge the base branch in; generated-file conflicts are rebuilt, others stop")
    add("gc", "remove merged worktrees, their branches and records, bytecode-only leftovers").add_argument(
        "--dry-run", action="store_true"
    )
    add("doctor", "is this machine ready? each problem with its FIX").add_argument(
        "--all", action="store_true", help="also the optional items"
    )
    add("status", "where this change stands, and the next step")
    p = add("config", "personal settings (never committed)")
    p.add_argument("action", choices=["get", "set", "list"])
    p.add_argument("key", nargs="?")
    p.add_argument("value", nargs="?")
    return top


def dispatch(ctx: config.Context, args: argparse.Namespace) -> int:
    command = args.command
    if command == "plan":
        if args.action == "new":
            return plan.new(ctx, args.topic)
        if args.action == "show":
            return plan.show(ctx, args.topic)
        if args.action == "link":
            return plan.link(ctx, args.topic)
        return plan.approve(ctx, args.topic, args.words)
    if command == "start":
        return start.run(ctx, args.branch, no_plan=args.no_plan, setup=not args.no_setup, plan_topic=args.plan)
    if command == "check":
        if args.watch:
            return watch.watch(ctx, args.names, full=args.full, again=args.again)
        return checks.run(ctx, args.names, again=args.again, full=args.full)
    if command == "ship":
        return ship.run(ctx, args.title, args.body, dry_run=args.dry_run)
    if command == "report":
        return report.run(ctx)
    if command == "approve":
        return approve.approve(ctx, args.pr, args.words)
    if command == "answer":
        return approve.answer(ctx, args.pr, args.round, args.index, args.text, every=args.every)
    if command == "land":
        return land.run(ctx, args.pr, no_review=args.no_review, ci_timeout=args.ci_timeout, dry_run=args.dry_run)
    if command == "summary":
        return summary.run(ctx, args.pr)
    if command == "sync":
        return sync.run(ctx)
    if command == "gc":
        return gc.run(ctx, dry_run=args.dry_run)
    if command == "doctor":
        return doctor.run(ctx, everything=args.all)
    if command == "status":
        return status.run(ctx)
    return config.run(ctx, args.action, args.key, args.value)


def main(argv: list[str] | None = None, cwd: Path | str | None = None, gh_runner=None, stream=None, fakes=None) -> int:
    args = parser().parse_args(argv)
    out = Out(as_json=args.json, stream=stream)
    name = args.command + (f" {args.action}" if args.command in ("plan", "config") else "")
    try:
        ctx = config.Context.make(cwd or os.getcwd(), out, gh_runner=gh_runner, fakes=fakes)
        code = dispatch(ctx, args)
    except Failure as failure:
        return out.finish(name, failure=failure)
    except KeyboardInterrupt:
        return out.finish(name, failure=Failure("interrupted", "run the command again", FAILED))
    return out.finish(name, code)

"""retrodev: hermretro's working agreement as commands, each refusing to skip a step.

  1 discuss   2 plan new / plan show   3 plan approve, start (or takeover <branch>)   4 check, ship   5 report
  6 approve <pr>   7 land <pr> (reviews, CI, merge; answer <pr> ... between rounds)   8 summary <pr>
  any time: status (the next step), doctor, sync, gc, config
  reach: try <pr> (its full checks in a throwaway checkout), mac (the checks on a MacBook), preview (the page)
  build: new feature|rpc|tool|event|listener|page|tab|slot (code, tests, docs, registry line); stats; engine update <v>
  releases, only when the owner says 'make a release': release run (prepare, approve, land, publish up to the
  draft), or each step: release prepare, release publish, release verify

Exit codes: 0 ok, 1 failed, 2 still waiting, 3 needs the owner. Every failure ends with a FIX: line.
--json prints one JSON object instead of text. Read tools/retrodev/README.md for the whole flow.
"""

from __future__ import annotations

import argparse
import functools
import os
from pathlib import Path

from . import (
    approve,
    checks,
    config,
    doctor,
    engine_update,
    gc,
    land,
    mac,
    plan,
    preview,
    release,
    release_publish,
    release_run,
    release_verify,
    report,
    scaffold,
    ship,
    start,
    stats,
    status,
    summary,
    sync,
    takeover,
    trial,
    watch,
)
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

    p = add("takeover", "a teammate's pushed branch in a worktree tracking it, set up as start sets one up")
    p.add_argument("branch", help="the pushed branch, e.g. feat/<topic>")
    p.add_argument("--no-setup", action="store_true", help="skip npm ci and the ruff setup")

    p = add("check", "the checks whose inputs changed (cached passes print 'ok (cached)')")
    names = ", ".join(config.load_policy(Path(__file__).resolve().parents[2])["checks"]["inputs"])
    p.add_argument("names", nargs="*", help="only these checks: " + names)
    p.add_argument("--again", action="store_true", help="ignore earlier passes (with --watch: on its first run)")
    p.add_argument("--full", action="store_true", help="also the real-engine run and the clean install")
    p.add_argument("--watch", action="store_true", help="run again on every file change")

    p = add("ship", "push the branch and open (or update) its draft pull request")
    p.add_argument(
        "--title", help="one plain sentence, no trailing period (default: the title this branch last shipped with)"
    )
    p.add_argument(
        "--body",
        help="a file with every pull request template section filled in (default: the body this branch last shipped "
        "with, else notes/pr/<topic>.md in the main checkout; when that is missing, ship writes it from "
        ".github/pull_request_template.md and stops)",
    )
    p.add_argument("--new-body", action="store_true", help="write notes/pr/<topic>.md from the template, then stop")
    p.add_argument("--dry-run", action="store_true", help="run the gates and print what it would do")

    add("report", "the factual half of the step-5 report")

    p = add("approve", "record the owner's approval of a pull request (once); readies a draft")
    p.add_argument("pr", type=int)
    p.add_argument("--words", required=True, help="the owner's exact words")
    p = add("land", "review rounds, CI on the exact head and the squash merge of an approved pull request")
    p.add_argument("pr", type=int)
    p.add_argument("--no-review", action="store_true", help="skip the reviews (recorded), merge on green CI")
    p.add_argument(
        "--reason", metavar="TEXT", help="with --no-review: why the reviews were skipped (default 'land --no-review')"
    )
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
    add("stats", "landed pull requests, review rounds and findings, ship to merge, check times, friction")
    releases(sub, common)
    scaffolds(sub, common)
    p = add("engine", "the vendored engine (owner-gated): update <version> walks docs/dev/ENGINE-UPDATE.md")
    engine = p.add_subparsers(dest="action", required=True, metavar="<action>")
    update = engine.add_parser("update", help="the engine update checklist", parents=[common])
    update.add_argument("version")
    update.add_argument("--owner-words", help="the owner's exact words asking for the engine update")
    update.add_argument("--dry-run", action="store_true", help="print the gates and the checklist; change nothing")
    update.add_argument(
        "--done", type=int, action="append", default=[], metavar="N", help="record manual step N as done"
    )
    p = add("try", "a pull request's full checks in a throwaway checkout outside the repository")
    p.add_argument("pr", type=int)
    p.add_argument("--keep", action="store_true", help="keep the throwaway checkout (its path is printed)")
    p.add_argument("--no-setup", action="store_true", help="skip npm ci and the ruff setup there")
    p = add("mac", "the checks on the MacBook over ssh (optional; mac_host, mac_repo)")
    p.add_argument("--host", help="the ssh host (default: the mac_host setting)")
    p.add_argument("rest", nargs=argparse.REMAINDER, help="-- then tools/check.py's arguments")
    p = add("preview", "build the page's browser preview and print its path")
    p.add_argument("--serve", action="store_true", help="serve it on 127.0.0.1 on a free port")
    p.add_argument("--out", help="the output folder (default: <state>/preview)")
    p.add_argument("--desktop", help="a built Hermes Desktop source (default: $HERMES_SOURCE/apps/desktop)")
    p = add("config", "personal settings (never committed)")
    p.add_argument("action", choices=["get", "set", "list"])
    p.add_argument("key", nargs="?")
    p.add_argument("value", nargs="?")
    return top


def releases(sub, common) -> None:
    help_text = (
        "releases, only when the owner says 'make a release': run (up to the draft), or prepare, publish, verify"
    )
    p = sub.add_parser("release", help=help_text, description=help_text, parents=[common])
    steps = p.add_subparsers(dest="action", required=True, metavar="<action>")
    run = steps.add_parser(
        "run",
        help="prepare, approve and land the version pull request, publish the draft; never publishes it",
        parents=[common],
    )
    run.add_argument(
        "--owner-words", help="the owner's exact words asking for the release (also approve its pull request)"
    )
    run.add_argument("--rc", action="store_true", help="a release candidate (X.Y.Z-rc.M; main does not move)")
    run.add_argument("--version", help="the version the owner named (default: the next patch, or the one started)")
    run.add_argument("--dry-run", action="store_true", help="print what is done and what it would run; change nothing")
    prepare = steps.add_parser("prepare", help="the chore/release-X.Y.Z pull request", parents=[common])
    prepare.add_argument("--owner-words", help="the owner's exact words asking for the release")
    prepare.add_argument("--rc", action="store_true", help="a release candidate (X.Y.Z-rc.M; main does not move)")
    prepare.add_argument("--version", help="the version the owner named (default: the next patch)")
    publish = steps.add_parser("publish", help="main, the tag and the draft release, after the gates", parents=[common])
    publish.add_argument("version")
    publish.add_argument("--dry-run", action="store_true", help="print the gates and every command; change nothing")
    verify = steps.add_parser("verify", help="read the draft, check it, then (--publish) publish", parents=[common])
    verify.add_argument("version")
    verify.add_argument("--publish", action="store_true", help="publish it when every check is ok")


def scaffolds(sub, common) -> None:
    help_text = (
        "add a feature, rpc, tool, event, listener, page, tab or slot: code, its test, docs and the registry line"
    )
    p = sub.add_parser("new", help=help_text, description=help_text, parents=[common])
    kinds = p.add_subparsers(dest="kind", required=True, metavar="<kind>")
    shared = argparse.ArgumentParser(add_help=False, parents=[common])
    shared.add_argument("--dry-run", action="store_true", help="list the files; write nothing")
    shared.add_argument("--no-check", action="store_true", help="skip the checks afterwards")
    shared.add_argument(
        "--no-build", action="store_true", help="skip rebuilding the generated files (when several new run in a row)"
    )

    def kind(name: str, help_line: str, target: str | None, item: str, optional: bool = False):
        parser = kinds.add_parser(name, help=help_line, description=help_line, parents=[shared])
        if target:
            parser.add_argument("target", metavar=target)
        parser.add_argument("name", metavar=item, nargs="?" if optional else None)
        return parser

    kind("feature", "backend/<name>/: front door, README, tests, the registry lines", None, "name").add_argument(
        "--purpose", help="one line: what the feature does (the map and README say it)"
    )
    kind(
        "rpc",
        "an @rpc stub, its test, its CONTRACT section, the generated names: new rpc <feature> <name> or "
        "<feature>.<name> (RPC names are global and flat: the page calls plugin.hermretro.<name>)",
        "feature",
        "name",
        optional=True,
    ).add_argument(
        "--module",
        help="put the handler in backend/<feature>/<module>.py (e.g. <name>_rpcs); rpcs.py keeps a short @rpc "
        "declaration that calls it (suggested when rpcs.py is over 350 lines)",
    )
    tool = kind("tool", "a Tool stub, its test, plugin.yaml, the step words, CONTRACT", "feature", "name")
    tool.add_argument(
        "--step", nargs=2, metavar=("RUNNING", "DONE"), help="the Build page's words while it runs and once done"
    )
    tool.add_argument(
        "--module",
        help="write it in backend/<feature>/<module>.py with its own TOOLS, which tools.py's TOOLS takes in "
        "(automatic, as <tool>_tools, when tools.py is over 400 lines)",
    )
    tool.add_argument(
        "--project",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="a tool that acts on the game's project: a `project` schema property, tool_args.tool_project and "
        "tool_error, a test with isolated_home (default: on when the feature has tool_args.py, as library does)",
    )
    event = kind("event", "an EVENTS entry in the front door and its CONTRACT row", "feature", "name")
    event.add_argument(
        "--payload",
        action="append",
        help="the keyword arguments it carries: comma-separated ('game=<id>, root') or repeated (--payload game "
        "--payload root), or both",
    )
    event.add_argument(
        "--when",
        help="one line: when it is emitted, tool and RPC names in backticks, e.g. 'after `chromatic_build_report` "
        "accepted a card' (the EVENTS entry and the CONTRACT row say it)",
    )
    kind("listener", "an @on stub in backend/<feature>/listeners.py, its test, the README and docs", "feature", "event")
    kind("page", "page/pages/<id>/: descriptor, component, README, the registry line", None, "id").add_argument(
        "--label", help="its nav label (default: from the id)"
    )
    tab = kind("tab", "page/pages/<page>/<id>/index.js, listed in the page's tabs", "page", "id")
    tab.add_argument("--label", help="its tab label (default: from the id)")
    tab.add_argument(
        "--from-page",
        action="store_true",
        help="on a page without tabs: its own Page becomes this first tab (dropped from the descriptor)",
    )
    kind("slot", "a slot the page declares for other pages to fill", "page", "name").add_argument(
        "--doc", help="one line: where it is, and the props it passes"
    )


def dispatch(ctx: config.Context, args: argparse.Namespace) -> int:
    command = args.command
    if command == "new":
        for missing in ("target", "purpose", "step", "payload", "when", "module", "project", "label", "doc"):
            setattr(args, missing, getattr(args, missing, None))
        if isinstance(args.payload, list):  # --payload repeated: one comma-separated line
            args.payload = ", ".join(part.strip() for part in args.payload if part.strip()) or None
        return scaffold.run(ctx, args)
    if command == "engine":
        return engine_update.run(ctx, args.version, args.owner_words, dry_run=args.dry_run, done=args.done)
    if command == "stats":
        return stats.run(ctx)
    if command == "release":
        if args.action == "run":
            return release_run.run(ctx, args.owner_words, rc=args.rc, named=args.version, dry_run=args.dry_run)
        if args.action == "prepare":
            return release.prepare(ctx, args.owner_words, rc=args.rc, named=args.version)
        if args.action == "publish":
            return release_publish.run(ctx, args.version, dry_run=args.dry_run)
        return release_verify.run(ctx, args.version, publish=args.publish)
    if command == "try":
        return trial.run(ctx, args.pr, keep=args.keep, setup=not args.no_setup)
    if command == "mac":
        return mac.run(ctx, args.host, args.rest)
    if command == "preview":
        return preview.run(ctx, serve=args.serve, out_dir=args.out, desktop=args.desktop)
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
    if command == "takeover":
        return takeover.run(ctx, args.branch, setup=not args.no_setup)
    if command == "check":
        if args.watch:
            return watch.watch(ctx, args.names, full=args.full, again=args.again)
        return checks.run(ctx, args.names, again=args.again, full=args.full)
    if command == "ship":
        return ship.run(ctx, args.title, args.body, dry_run=args.dry_run, new_body=args.new_body)
    if command == "report":
        return report.run(ctx)
    if command == "approve":
        return approve.approve(ctx, args.pr, args.words)
    if command == "answer":
        return approve.answer(ctx, args.pr, args.round, args.index, args.text, every=args.every)
    if command == "land":
        return land.run(
            ctx,
            args.pr,
            no_review=args.no_review,
            ci_timeout=args.ci_timeout,
            dry_run=args.dry_run,
            reason=args.reason,
        )
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
    name = args.command + (f" {args.action}" if args.command in ("plan", "config", "release", "engine") else "")
    name += f" {args.kind}" if args.command == "new" else ""
    try:
        ctx = config.Context.make(cwd or os.getcwd(), out, gh_runner=gh_runner, fakes=fakes)
        code = dispatch(ctx, args)
    except Failure as failure:
        return out.finish(name, failure=failure)
    except KeyboardInterrupt:
        return out.finish(name, failure=Failure("interrupted", "run the command again", FAILED))
    return out.finish(name, code)

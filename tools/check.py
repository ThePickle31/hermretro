"""Run hermretro's checks, the same way here and in CI.

    python tools/check.py                fast checks: unit, bundle, engine, lint, page, scan (together, about 15 s)
    python tools/check.py full           fast checks plus the real-engine acceptance run
    python tools/check.py unit page      only the named checks
    python tools/check.py fix            apply the linters' automatic fixes and the Python formatting, then lint

Checks: unit (Python unit tests), bundle (generated files match page/), engine (the engine's dist/server.js is what
its modules build), lint (ESLint over page/: the boundaries between pages and a few correctness rules; ruff over the
Python: likely bugs, then one formatting for everyone, from .dev/py, made by python tools/py/setup.py), page (page
tests in jsdom), scan (Hermes's install scanner on exactly what a commit would ship: must be "safe"), acceptance
(real engine, compiler and emulator; needs a toolchain: tools/ci/prepare_toolchain.py).

Every failure ends with a line starting "FIX:". In GitHub Actions the results also go to the run summary.
Options: --hermes-source DIR (a hermes-agent checkout for the scan; default $HERMES_SOURCE, then
~/.hermes/hermes-agent), --strict (CI: a check that cannot run fails instead of being skipped).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HELPERS = str(Path(__file__).resolve().parent / "py")  # check.py's helpers
if HELPERS not in sys.path:
    sys.path.insert(0, HELPERS)
import dev_toolchain  # noqa: E402 - tools/py/ goes on sys.path first
import page_summary  # noqa: E402 - tools/py/ goes on sys.path first
import step_summary  # noqa: E402 - tools/py/ goes on sys.path first
import unit_shards  # noqa: E402 - tools/py/ goes on sys.path first
from lint_tools import (  # noqa: E402 - tools/py/ goes on sys.path first
    LINT_SETUP,
    RUFF_CHECK,
    RUFF_FORMAT,
    RUFF_SETUP,
    lint_tools_missing,
    page_lint,
    ruff_check,
    ruff_format_check,
    ruff_missing,
)

FAST = ["unit", "bundle", "engine", "lint", "page", "scan"]
ALL = FAST + ["acceptance"]


class Skip(Exception):
    """The check cannot run here (a tool is missing); a failure under --strict."""


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, **kwargs)


def tail(text: str, lines: int = 25) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def short_tmp() -> str:
    """A temp folder short enough for Unix sockets (macOS allows 104 characters, Linux 108)."""
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    return runtime if runtime and Path(runtime).is_dir() and len(runtime) < 40 else "/tmp"


def need(tool: str) -> str:
    found = shutil.which(tool)
    if not found:
        raise Skip(f"{tool} is not installed")
    return found


def check_unit(args) -> str:
    # In empty homes and empty TMPDIRs (tools/py/unit_home.py): a write meant for the real home, or a temp folder a
    # test never removed, shows up and names its test module. Several processes at once (tools/py/unit_shards.py).
    row, failure = unit_shards.run_suite(ROOT, lambda cmd, **kw: run(cmd, **kw), short_tmp())
    if failure:
        raise AssertionError(failure)
    return row


def check_bundle(args) -> str:
    node = need("node")
    result = run([node, "tools/bundle/bundle.mjs", "--check"] + (["--same-esbuild"] if args.strict else []))
    output = (result.stdout + result.stderr).strip()
    if "not found" in output and not args.strict and result.returncode:
        raise Skip(output.splitlines()[-1])
    if result.returncode:
        raise AssertionError(
            tail(output) + "\nFIX: node tools/bundle/bundle.mjs, then commit desktop/plugin.js, "
            "player/frame-shim.js and page/app/rpc-names.js with your sources (never edit them by hand)"
        )
    return output.splitlines()[-1] if output else "ok"


def check_engine(args) -> str:
    node = need("node")
    result = run([node, "tools/engine/bundle.mjs", "--check"])
    output = (result.stdout + result.stderr).strip()
    missing = next(
        (line for line in output.splitlines() if line.startswith("esbuild and the engine's packages were not found")),
        None,
    )
    if missing and result.returncode:
        raise Skip(f"{missing}\nFIX: python tools/dev setup")
    if result.returncode:
        # The bundler's own FIX line names its --check run; this one names the command to run instead.
        reason = "\n".join(line for line in output.splitlines() if not line.startswith("FIX:"))
        raise AssertionError(
            tail(reason) + "\nFIX: node tools/engine/bundle.mjs, then commit engine/dist/server.js "
            "with the engine's modules (never edit it by hand)"
        )
    return output.splitlines()[-1] if output else "ok"


def start(cmd: list[str]) -> subprocess.Popen:
    return subprocess.Popen(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def check_lint(args) -> str:
    # ESLint over page/ and ruff over the Python run at the same time (ruff takes a few hundredths of a second).
    node = shutil.which("node")
    eslint = start(page_lint(node, [])) if node else None
    missing = ruff_missing()  # the commands come from tools/py/lint_tools.py
    ruff = None if missing else (start(ruff_check(["."])), start(ruff_format_check(["."])))
    problems, done = [], []
    if ruff:
        (lint_out, _), (format_out, _) = ruff[0].communicate(), ruff[1].communicate()
        if ruff[0].returncode:
            problems.append(
                tail(lint_out, 40) + "\nruff's rules catch likely bugs (unused or undefined names, "
                "mistakes bugbear knows) and older syntax; `.dev/py/bin/ruff rule <CODE>` explains one.\n"
                "FIX: python tools/check.py fix for the automatic fixes, then fix the rest as each "
                "message says (a deliberate exception: # noqa: <CODE> - <reason> on its line)"
            )
        if ruff[1].returncode:
            files = [line.split(":", 1)[0] for line in format_out.splitlines() if "unformatted:" in line]
            problems.append(
                f"{len(files)} Python files are not in ruff's format (one style for everyone, so a "
                "diff shows only real changes):\n"
                + tail("\n".join(files), 10)
                + "\nFIX: python tools/check.py fix (or .dev/py/bin/ruff format --config "
                "tools/py/ruff.toml <file>)"
            )
        if not ruff[0].returncode and not ruff[1].returncode:
            done.append("python: ruff check and format clean")
    else:
        problems.append(f"{missing}\nFIX: {RUFF_SETUP}")
    if eslint is None:
        page_skip = "node is not installed"
    else:
        output = eslint.communicate()[0].strip()
        page_skip = None
        if "were not found" in output and eslint.returncode:
            page_skip = "eslint was not found (npm ci --prefix tools/npm --ignore-scripts)"
        elif eslint.returncode:
            problems.append(
                tail(output, 40) + "\nFIX: node tools/bundle/lint-page.mjs --fix (or python "
                "tools/check.py fix) for the automatic fixes, then fix the rest as each message says "
                "(a deliberate exception: // hermretro: allow <rule> \u2014 <reason> on its line)"
            )
        else:
            warned = ", ".join(r.split()[1].rsplit(":", 1)[0] for r in output.splitlines() if r[:9] == "warning: ")
            done.insert(0, "page: " + (output.splitlines() or ["ok"])[-1] + (warned and f" (warnings: {warned})"))
    if problems:
        raise AssertionError(("page lint skipped: " + page_skip + "\n" if page_skip else "") + "\n".join(problems))
    if page_skip and (args.strict or not done):
        raise Skip(page_skip)
    return "; ".join(done + ([f"page skipped ({page_skip})"] if page_skip else []))


def tree_digest() -> dict[str, str]:
    """A digest of every file a fix may rewrite, to report what it changed."""
    names = [name for name in shipped_files() if name.endswith((".py", ".js", ".mjs"))]
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}


def fix(args) -> int:
    """Apply every automatic fix (ruff's safe fixes and format, the page lint's), say what changed, lint."""
    if missing := ruff_missing():
        print(f"{missing}\nFIX: {RUFF_SETUP}")
        return 1
    before = tree_digest()
    steps = [RUFF_CHECK[:2] + ["--fix", "--quiet", *RUFF_CHECK[2:]], RUFF_FORMAT]
    if node := shutil.which("node"):
        steps.append([node, "tools/bundle/lint-page.mjs", "--fix"])
    else:
        print("node is not installed: the page lint's fixes were not applied")
    for cmd in steps:
        run(cmd)  # each reports again below, in the lint check
    after = tree_digest()
    changed = sorted(name for name in after if before.get(name) != after[name])
    print(f"fixed {len(changed)} files" + "".join(f"\n  {name}" for name in changed))
    return main(["lint", *(["--strict"] if args.strict else [])])


PAGE_TESTS = "tests/page/**/*test*.mjs"  # node's glob and Python's agree: ** also matches tests/page/ itself
# The reporter is named: without it node picks TAP whenever its output is captured (CI, this script), spec only on a
# terminal. page_summary reads both.
PAGE_COMMAND = ["--test", "--test-reporter=spec", PAGE_TESTS]


def check_page(args) -> str:
    node = need("node")
    result = run([node, *PAGE_COMMAND])
    output = result.stdout + result.stderr
    if "were not found" in output and result.returncode and not args.strict:
        raise Skip("react, react-dom and jsdom were not found (npm ci --prefix tools/npm --ignore-scripts)")
    if result.returncode:
        raise AssertionError(page_failure(output))
    return page_summary.summary(output, len(list(ROOT.glob(PAGE_TESTS))))


FAILING_AT = re.compile(r"^test at (tests/page/\S+?\.mjs):\d+:\d+$")  # each entry of the reporter's failing list
FAILED_ROW = re.compile(r"^✖ (.+) \([\d.]+ms\)$")
REPORTER_ROW = re.compile(r"^\s*[✔✖﹣ℹ] ")  # any row of the reporter itself (a test, a file, the totals)
ACT_NOISE = (
    "An update to ",
    "When testing, code that",
    "act(() => {",
    "  /* fire events",
    "});",
    "/* assert on",
    "This ens",
)


def own_output(lines: list[str], name: str) -> list[str]:
    """What the scenario file ``name`` printed itself (its assertion and stderr): the lines above its ✖ row up to the
    reporter's previous row (node prints a file's output just before its row), without React's act() warnings."""
    at = next((i for i, line in enumerate(lines) if line.startswith(f"✖ {name} (")), None)
    if at is None:
        return []
    start = at
    while start > 0 and not REPORTER_ROW.match(lines[start - 1]):
        start -= 1
    return [line for line in lines[start:at] if line.strip() and not line.startswith(ACT_NOISE)][-25:]


def page_failures(output: str) -> list[tuple[str, str, list[str]]]:
    """(file, test, what it said) for each entry of node --test's failing list. A scenario file on harness.mjs is one
    test named after the file, whose reason is only 'test failed': what it said is then its own output."""
    lines = output.splitlines()
    summary_at = next((i for i, line in enumerate(lines) if line.startswith("✖ failing tests")), len(lines))
    found = []
    for i, line in enumerate(lines[summary_at:], summary_at):
        if not (at := FAILING_AT.match(line)) or i + 1 >= len(lines) or not (row := FAILED_ROW.match(lines[i + 1])):
            continue
        reason = []
        for more in lines[i + 2 : i + 14]:
            if not more.startswith(" "):
                break
            reason.append(more.strip())
        if row[1] == at[1]:  # the whole file
            reason = own_output(lines[:summary_at], at[1]) + [r for r in reason if r != "'test failed'"]
        found.append((at[1], row[1], reason))
    return found


def page_failure(output: str) -> str:
    """check.py page's failure: node --test's summary says only 'test failed' for a scenario file, so each failing
    file's own output comes first (its assertion, name and message, and stderr), and the FIX names the file, and says
    when the test was stopped for taking too long."""
    failures = page_failures(output)
    if not failures:
        return tail(output, 40) + (
            "\nFIX: run the failing file alone for its full output (node tests/page/page-<name>.test.mjs, named in "
            "the failure above); after editing page/ run node tools/bundle/bundle.mjs first"
        )
    parts = []
    for file, test, said in failures:
        head = f"{file} failed:" if test == file else f"{file}: {test!r} failed:"
        parts.append(head + "\n" + ("\n".join("  " + line for line in said) or "  (it printed nothing)"))
    slow = [test for _file, test, said in failures if any("timed out" in line for line in said)]
    timed = (
        f"{', '.join(slow)} timed out (stopped for taking too long, not an assertion): find the wait that "
        if slow
        else ""
    )
    files = list(dict.fromkeys(file for file, _test, _said in failures))
    return (
        "\n".join(parts)
        + f"\nFIX: {timed + 'never ends; ' if slow else ''}run it alone: "
        + "; ".join(f"node {file}" for file in files)
        + " (after editing page/ run node tools/bundle/bundle.mjs first)"
    )


def shipped_files() -> list[str]:
    """What a commit of this tree would ship: tracked files plus new files git does not ignore."""
    result = run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"])
    if result.returncode:
        raise Skip("not a git checkout")
    return [name for name in result.stdout.split("\0") if name and (ROOT / name).is_file()]


SCAN = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from tools.plugin_guard import scan_plugin
result = scan_plugin(Path(sys.argv[2]))
bad = [{"severity": f.severity, "id": f.pattern_id, "file": f.file, "line": getattr(f, "line", None),
        "match": str(getattr(f, "match", ""))[:120]} for f in result.findings if f.severity in ("high", "critical")]
print(json.dumps({"verdict": result.verdict, "findings": len(result.findings), "bad": bad}))
"""


def check_scan(args) -> str:
    source = Path(args.hermes_source or os.environ.get("HERMES_SOURCE") or Path.home() / ".hermes" / "hermes-agent")
    if not (source / "tools" / "plugin_guard.py").is_file():
        raise Skip(f"no hermes-agent checkout at {source} (pass --hermes-source)")
    with tempfile.TemporaryDirectory(prefix="hermretro-scan-", dir=short_tmp()) as tmp:
        target = Path(tmp) / "hermretro"
        for name in shipped_files():
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, destination, follow_symlinks=False)
        result = subprocess.run(
            [sys.executable, "-I", "-c", SCAN, str(source), str(target)], text=True, capture_output=True
        )
    if result.returncode:
        raise AssertionError(tail(result.stderr) + "\nFIX: the scanner itself failed; check --hermes-source")
    report = json.loads(result.stdout.strip().splitlines()[-1])
    if report["verdict"] != "safe":
        lines = [f"  {b['severity']}: {b['id']} in {b['file']}:{b['line']}  {b['match']}" for b in report["bad"]]
        would = "be refused" if report["verdict"] == "dangerous" else "ask for confirmation"
        raise AssertionError(
            f"verdict {report['verdict']}; installs would {would}:\n"
            + "\n".join(lines)
            + '\nFIX: reword or remove those lines (see rule 3 in AGENTS.md, "Rules that protect users"); medium findings are fine'
        )
    return f"safe ({report['findings']} minor notes)"


# How long the real-engine suite may take. On a macOS CI runner it took about 17 of its first 20 minutes before the
# repeatable-build checks (R1-R4: a copy of a project, built and compiled for the web; signature edits) added about 10
# builds; this leaves room for those and the next stages, inside the integration job's 50 minutes.
ACCEPTANCE_MINUTES = 30


def acceptance_env(paths) -> tuple[dict, Path]:
    """The suite's environment and the toolchain it runs on: a short TMPDIR, and the toolchain folders absolute as
    this process resolved them (from the caller's folder), since the suite runs from the checkout root. With neither
    folder named, this machine's development toolchain (tools/py/dev_toolchain.py) when it has one, otherwise the
    one the hermretro page installed."""
    env, toolchain = {**os.environ, "TMPDIR": short_tmp()}, paths.setup_root()
    if env.get("GB_STUDIO_SETUP_ROOT"):
        env["GB_STUDIO_SETUP_ROOT"] = str(toolchain.absolute())
    if env.get("HERMRETRO_DEPS_ROOT"):
        env["HERMRETRO_DEPS_ROOT"] = str(paths.DEPS_ROOT)
    elif not env.get("GB_STUDIO_SETUP_ROOT") and (dev_toolchain.DEPS_ROOT / "toolchain").is_dir():
        env["HERMRETRO_DEPS_ROOT"] = str(dev_toolchain.DEPS_ROOT)
        toolchain = dev_toolchain.DEPS_ROOT / "toolchain"
    return env, toolchain


def check_acceptance(args) -> str:
    sys.path.insert(0, str(ROOT))
    from backend.system import paths  # noqa: E402 - the backend decides where setup put the toolchain

    env, toolchain = acceptance_env(paths)
    if not toolchain.is_dir():
        if env.get("GB_STUDIO_SETUP_ROOT"):
            fix = "point GB_STUDIO_SETUP_ROOT at a toolchain, or unset it"
        else:
            fix = (
                "python tools/ci/prepare_toolchain.py, once (about 700 MB): it makes the development toolchain "
                "every checkout uses, or the one HERMRETRO_DEPS_ROOT names when it is set"
            )
        raise Skip(f"no toolchain at {toolchain}\nFIX: {fix}")
    # The suite run by hand, as this run starts it: from the checkout root, with the same folders.
    folders = [
        f"{name}={shlex.quote(env[name])}"
        for name in ("TMPDIR", "HERMRETRO_DEPS_ROOT", "GB_STUDIO_SETUP_ROOT")
        if env.get(name)
    ]
    rerun = f"cd {shlex.quote(str(ROOT))} && {' '.join(folders)} python tests/acceptance/broker_acceptance.py"
    (ROOT / "notes" / "evidence" / "broker-acceptance.json").unlink(missing_ok=True)  # never report an old run
    try:
        result = run(
            [sys.executable, "tests/acceptance/broker_acceptance.py"], env=env, timeout=ACCEPTANCE_MINUTES * 60
        )
    except subprocess.TimeoutExpired as stopped:
        # What it printed up to then: the last check that passed shows where it stopped.
        printed = "\n".join(
            tail(output if isinstance(output, str) else (output or b"").decode(errors="replace"), 15)
            for output in (stopped.stdout, stopped.stderr)
        ).strip()
        raise AssertionError(
            f"the acceptance suite did not finish in {ACCEPTANCE_MINUTES} minutes\n{printed}\nFIX: {rerun} and see "
            "where it stops"
        )
    passed = sum(line.startswith("PASS ") for line in result.stdout.splitlines())
    failed = [line for line in result.stdout.splitlines() if line.startswith("FAIL ")]
    if result.returncode or failed:
        details = []
        evidence = ROOT / "notes" / "evidence" / "broker-acceptance.json"
        if evidence.is_file():
            for item in json.loads(evidence.read_text()).get("checks", []):
                if not item.get("passed"):
                    details.append(f"{item['id']}: {json.dumps(item.get('detail'), default=str)[:600]}")
        raise AssertionError(
            "\n".join(failed + details) + "\n" + tail(result.stderr, 15) + f"\nFIX: {rerun} and read its output"
        )
    return f"{passed} passed"


CHECKS = {name: globals()[f"check_{name}"] for name in ALL}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").strip().splitlines()[0])
    parser.add_argument("checks", nargs="*", help="fast (default), full, fix, or check names: " + ", ".join(ALL))
    parser.add_argument("--hermes-source")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    names = args.checks or ["fast"]
    if names == ["fix"]:
        return fix(args)
    wanted = [c for name in names for c in (FAST if name == "fast" else ALL if name == "full" else [name])]
    unknown = [name for name in wanted if name not in CHECKS]
    if unknown:
        parser.error("unknown check: " + ", ".join(unknown))

    # Missing lint tools fail at once, before the slow checks start: a fresh checkout learns it in a second.
    if "lint" in wanted and (missing := lint_tools_missing()):
        row = ("lint", "FAILED", 0.0, "; ".join(missing) + f"\nnothing else ran\nFIX: {LINT_SETUP}")
        print(f"{row[1]:>7}  {row[0]:<10} {row[2]:5.1f} s  " + row[3].replace("\n", "\n         "), flush=True)
        step_summary.write([row])
        return 1

    def one(name: str) -> tuple[str, str, float, str]:
        start = time.monotonic()
        state, detail = "FAILED", ""
        try:
            state, detail = "ok", CHECKS[name](args)
        except Skip as skip:
            state, detail = ("FAILED" if args.strict else "skipped"), str(skip)
            if args.strict and "\nFIX:" not in detail:  # a skip that names its own next step keeps it
                detail += "\nFIX: install what is missing (see AGENTS.md, \"Commands\")"
        except AssertionError as error:
            state, detail = "FAILED", str(error)
        return name, state, time.monotonic() - start, detail

    def show(row: tuple[str, str, float, str]) -> None:
        name, state, seconds, detail = row
        print(f"{state:>7}  {name:<10} {seconds:5.1f} s  {detail.splitlines()[0] if detail else ''}", flush=True)
        if state != "ok" and "\n" in detail:  # a skip's reason and next step show too
            print("\n".join("         " + line for line in detail.splitlines()[1:]), flush=True)

    # The fast checks are independent (each in its own processes and temp folders): run them together and
    # report each as it finishes. The real-engine run is heavy and goes alone, afterwards.
    ordered = list(dict.fromkeys(wanted))
    together = [name for name in ordered if name != "acceptance"]
    rows = []
    with ThreadPoolExecutor(max_workers=max(1, len(together))) as pool:
        for future in as_completed([pool.submit(one, name) for name in together]):
            rows.append(future.result())
            show(rows[-1])
    if "acceptance" in ordered:
        rows.append(one("acceptance"))
        show(rows[-1])
    rows.sort(key=lambda row: ordered.index(row[0]))
    step_summary.write(rows)  # GitHub Actions' run summary, when there is one
    return 1 if any(row[1] == "FAILED" for row in rows) else 0


if __name__ == "__main__":
    sys.exit(main())

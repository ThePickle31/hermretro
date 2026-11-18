"""Run hermretro's checks, the same way here and in CI.

    python tools/check.py                fast checks: unit, bundle, lint, page, scan (together, about 15 s)
    python tools/check.py full           fast checks plus scaffold and the real-engine acceptance run
    python tools/check.py unit page      only the named checks
    python tools/check.py fix            apply the linters' automatic fixes and the Python formatting, then lint

Checks: unit (Python unit tests), bundle (generated files match page/), lint (ESLint over page/: the
boundaries between pages and a few correctness rules; ruff over the Python: likely bugs, then one formatting
for everyone, from .dev/py, made by python tools/py/setup.py), page (page tests in jsdom),
scan (Hermes's install scanner on exactly what a commit would ship: must be "safe"), scaffold (`retrodev new`
of every kind on a copy of this tree, judged by the real checks; needs the npm tools and ruff), acceptance (real
engine, compiler and emulator; needs the toolchain from setup).

Every failure ends with a line starting "FIX:". In GitHub Actions the results also go to the run summary.
Options: --hermes-source DIR (a hermes-agent checkout for the scan; default $HERMES_SOURCE, then
~/.hermes/hermes-agent), --strict (CI: a check that cannot run fails instead of being skipped).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAST = ["unit", "bundle", "lint", "page", "scan"]
ALL = FAST + ["scaffold", "acceptance"]


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


def check_unit(_args) -> str:
    # Empty home (a write meant for the real one shows up); empty PYTHONPYCACHEPREFIX (-B alone still reads stale .pyc)
    with (
        tempfile.TemporaryDirectory(prefix="hermretro-home-", dir=short_tmp()) as home,
        tempfile.TemporaryDirectory(prefix="hermretro-pyc-") as bytecode,
    ):
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("HERMRETRO_") and key not in ("HERMES_HOME", "GB_STUDIO_SETUP_ROOT")
        }
        slowest = ["--durations", "3"] if sys.version_info >= (3, 12) else []
        result = run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-t", ".", *slowest],
            env={**env, "HOME": home, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPYCACHEPREFIX": bytecode},
        )
        leaked = sorted(str(path.relative_to(home)) for path in Path(home).rglob("*"))
    if result.returncode:
        raise AssertionError(
            tail(result.stderr, 40) + "\nFIX: read the failures above; run one file with "
            "PYTHONPYCACHEPREFIX=$(mktemp -d) python -B -m unittest tests/<area>/<feature>/test_<name>.py"
        )
    if leaked:
        raise AssertionError(
            "the tests wrote into the home folder: " + ", ".join(leaked[:8]) + "\nFIX: give "
            "those tests a temp folder (tests/support.py, HERMRETRO_HOME or the HERMRETRO_*_DIR "
            "variables)"
        )
    lines = result.stderr.splitlines()
    ran = [line for line in lines if line.startswith("Ran ")]
    # "Slowest test durations" lists "<seconds>s     <test>": name the slowest, so a slow system is explained.
    timed = [line.split(None, 1) for line in lines if line[:1].isdigit() and line.split(None, 1)[0].endswith("s")]
    slow = "; slowest: " + ", ".join(f"{name.split(' (')[0]} {seconds}" for seconds, name in timed[:3]) if timed else ""
    # tests/repo/test_layout.py prints what should be fixed soon (big files, missing READMEs) without failing.
    warnings = sum("layout warning: " in line for line in lines)
    noted = f"; {warnings} layout warnings (python -m unittest tests.repo.test_layout)" if warnings else ""
    return (ran[-1] if ran else "ok") + noted + slow


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


# ruff, pinned with hashes in tools/py/requirements.txt and installed by tools/py/setup.py into .dev/py (never by
# the checks). Its settings: tools/py/ruff.toml, whose paths are taken from the root (the checks run there).
RUFF = ROOT / ".dev" / "py" / "bin" / "ruff"
RUFF_CHECK = [str(RUFF), "check", "--config", "tools/py/ruff.toml", "--output-format", "concise", "."]
RUFF_FORMAT = [str(RUFF), "format", "--config", "tools/py/ruff.toml", "."]
RUFF_SETUP = "python tools/py/setup.py (once; about 5 s, then a no-op until tools/py/requirements.txt changes)"


def ruff_missing() -> str | None:
    """Why the pinned ruff cannot run, or None."""
    stamp = ROOT / ".dev" / "py" / "requirements.sha256"
    if not RUFF.is_file():
        return "ruff is not installed in .dev/py"
    pinned = hashlib.sha256((ROOT / "tools" / "py" / "requirements.txt").read_bytes()).hexdigest()
    if not stamp.is_file() or stamp.read_text().strip() != pinned:
        return "the ruff in .dev/py is not the one tools/py/requirements.txt pins"
    return None


def start(cmd: list[str]) -> subprocess.Popen:
    return subprocess.Popen(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def check_lint(args) -> str:
    # ESLint over page/ and ruff over the Python run at the same time (ruff takes a few hundredths of a second).
    node = shutil.which("node")
    eslint = start([node, "tools/bundle/lint-page.mjs"]) if node else None
    missing = ruff_missing()
    ruff = None if missing else (start(RUFF_CHECK), start([*RUFF_FORMAT, "--check", "--output-format", "concise"]))
    problems, done = [], []
    if ruff:
        (lint_out, _), (format_out, _) = ruff[0].communicate(), ruff[1].communicate()
        if ruff[0].returncode:
            problems.append(
                tail(lint_out, 40) + "\nruff's rules catch likely bugs (unused or undefined names, "
                "mistakes bugbear knows) and older syntax; `.dev/py/bin/ruff rule <CODE>` explains one.\n"
                "FIX: python tools/check.py fix for the automatic fixes, then fix the rest as each "
                "message says (a deliberate exception: # noqa: <CODE> \u2014 <reason> on its line)"
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
                "(a deliberate exception: // retrodev: allow <rule> \u2014 <reason> on its line)"
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
    """Apply every automatic fix (ruff's safe fixes, ruff format, the page lint's fixes), say what changed, lint."""
    missing = ruff_missing()
    if missing:
        print(f"{missing}\nFIX: {RUFF_SETUP}")
        return 1
    before = tree_digest()
    steps = [RUFF_CHECK[:2] + ["--fix", "--quiet", *RUFF_CHECK[2:]], RUFF_FORMAT]
    node = shutil.which("node")
    if node:
        steps.append([node, "tools/bundle/lint-page.mjs", "--fix"])
    else:
        print("node is not installed: the page lint's fixes were not applied")
    for cmd in steps:
        run(cmd)  # each reports again below, in the lint check
    after = tree_digest()
    changed = sorted(name for name in after if before.get(name) != after[name])
    print(f"fixed {len(changed)} files" + "".join(f"\n  {name}" for name in changed))
    return main(["lint", *(["--strict"] if args.strict else [])])


def check_page(args) -> str:
    node = need("node")
    result = run([node, "--test", "tests/page/**/*test*.mjs"])
    output = result.stdout + result.stderr
    if "were not found" in output and result.returncode and not args.strict:
        raise Skip("react, react-dom and jsdom were not found (npm ci --prefix tools/npm --ignore-scripts)")
    if result.returncode:
        raise AssertionError(
            tail(output, 40) + "\nFIX: run the failing file alone for its full output (node "
            "tests/page/page-<name>.test.mjs, named in the failure above); after editing "
            "page/ run node tools/bundle/bundle.mjs first"
        )
    counts = [line for line in output.splitlines() if line.startswith(("ℹ pass", "ℹ fail"))]
    return ", ".join(line[2:] for line in counts) or "ok"


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
        raise AssertionError(
            f"verdict {report['verdict']}; installs would "
            + ("be refused" if report["verdict"] == "dangerous" else "ask for confirmation")
            + ":\n"
            + "\n".join(lines)
            + "\nFIX: reword or remove those lines (see AGENTS.md, "
            "\"Install scanner\"); medium findings are fine"
        )
    return f"safe ({report['findings']} minor notes)"


def check_scaffold(_args) -> str:
    # A few seconds of nested checks: kept out of the fast unit run (the test skips there without RD_SCAFFOLD_FULL).
    if missing := ruff_missing() or (None if (ROOT / "tools/npm/node_modules").is_dir() else "no tools/npm tools"):
        raise Skip(f"{missing} (npm ci --prefix tools/npm --ignore-scripts; python tools/py/setup.py)")
    need("node")
    test = [sys.executable, "-m", "unittest", "-v", "tests.retrodev.test_scaffold_tree"]
    result = run(test, env={**os.environ, "RD_SCAFFOLD_FULL": "1"})
    if result.returncode or " skipped " in result.stderr:
        raise AssertionError(
            tail(result.stderr, 40) + "\nFIX: RD_SCAFFOLD_KEEP=1 RD_SCAFFOLD_FULL=1 " + " ".join(test[1:])
        )
    return "retrodev new of every kind passes the real checks"


def check_acceptance(args) -> str:
    sys.path.insert(0, str(ROOT))
    from backend.system import paths  # noqa: E402  (the backend decides where setup put the toolchain)

    if not paths.setup_root().is_dir():
        raise Skip(
            f"no toolchain at {paths.setup_root()}; run python tools/ci/prepare_toolchain.py (about a minute), "
            "or point HERMRETRO_DEPS_ROOT at a folder that has one"
        )
    env = {**os.environ, "TMPDIR": short_tmp()}
    (ROOT / "notes" / "evidence" / "broker-acceptance.json").unlink(missing_ok=True)  # never report an old run
    try:
        result = run([sys.executable, "tests/acceptance/broker_acceptance.py"], env=env, timeout=1200)
    except subprocess.TimeoutExpired:
        raise AssertionError(
            "the acceptance suite did not finish in 20 minutes\nFIX: rerun python "
            "tests/acceptance/broker_acceptance.py with TMPDIR=" + short_tmp() + " and see where it stops"
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
            "\n".join(failed + details) + "\n" + tail(result.stderr, 15) + "\nFIX: rerun python "
            "tests/acceptance/broker_acceptance.py with TMPDIR=" + short_tmp() + " and read its output"
        )
    return f"{passed} passed"


CHECKS = {name: globals()[f"check_{name}"] for name in ALL}


def summary(rows: list[tuple[str, str, float, str]]) -> None:
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

    def one(name: str) -> tuple[str, str, float, str]:
        start = time.monotonic()
        try:
            state, detail = "ok", CHECKS[name](args)
        except Skip as skip:
            state, detail = ("FAILED" if args.strict else "skipped"), str(skip)
            if args.strict:
                detail += "\nFIX: install what is missing (see AGENTS.md, \"Checks\")"
        except AssertionError as error:
            state, detail = "FAILED", str(error)
        return name, state, time.monotonic() - start, detail

    def show(row: tuple[str, str, float, str]) -> None:
        name, state, seconds, detail = row
        print(f"{state:>7}  {name:<10} {seconds:5.1f} s  {detail.splitlines()[0] if detail else ''}", flush=True)
        if state == "FAILED" and "\n" in detail:
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
    summary(rows)
    return 1 if any(row[1] == "FAILED" for row in rows) else 0


if __name__ == "__main__":
    sys.exit(main())

"""Run hermretro's checks, the same way here and in CI.

    python tools/check.py                fast checks: unit, bundle, page, scan (about 25 s)
    python tools/check.py full           fast checks plus the real-engine acceptance run
    python tools/check.py unit page      only the named checks

Checks: unit (Python unit tests), bundle (generated files match desktop-src/), page (page tests in jsdom),
scan (Hermes's install scanner on exactly what a commit would ship: must be "safe"), acceptance (real
engine, compiler and emulator; needs the toolchain from setup).

Every failure ends with a line starting "FIX:". In GitHub Actions the results also go to the run summary.
Options: --hermes-source DIR (a hermes-agent checkout for the scan; default $HERMES_SOURCE, then
~/.hermes/hermes-agent), --strict (CI: a check that cannot run fails instead of being skipped).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAST = ["unit", "bundle", "page", "scan"]
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


def check_unit(_args) -> str:
    # The suite runs with an empty home folder and no Hermes or hermretro locations set, so a test that
    # would write to the real Hermes home (games, library, toolchain, broker) shows up as a file here.
    with tempfile.TemporaryDirectory(prefix="hermretro-home-", dir=short_tmp()) as home:
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("HERMRETRO_") and key not in ("HERMES_HOME", "GB_STUDIO_SETUP_ROOT")}
        result = run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], env={**env, "HOME": home})
        leaked = sorted(str(path.relative_to(home)) for path in Path(home).rglob("*"))
    if result.returncode:
        raise AssertionError(tail(result.stderr, 40) + "\nFIX: read the failures above; run one file with "
                             "python -m unittest tests/<file>.py")
    if leaked:
        raise AssertionError("the tests wrote into the home folder: " + ", ".join(leaked[:8]) + "\nFIX: give "
                             "those tests a temp folder (tests/support.py, HERMRETRO_HOME or the HERMRETRO_*_DIR "
                             "variables)")
    ran = [line for line in result.stderr.splitlines() if line.startswith("Ran ")]
    return ran[-1] if ran else "ok"


def check_bundle(args) -> str:
    node = need("node")
    result = run([node, "tools/bundle.mjs", "--check"] + (["--same-esbuild"] if args.strict else []))
    output = (result.stdout + result.stderr).strip()
    if "not found" in output and not args.strict and result.returncode:
        raise Skip(output.splitlines()[-1])
    if result.returncode:
        raise AssertionError(tail(output) + "\nFIX: node tools/bundle.mjs, then commit desktop/plugin.js and "
                             "player/frame-shim.js with your sources (never edit them by hand)")
    return output.splitlines()[-1] if output else "ok"


def check_page(args) -> str:
    node = need("node")
    result = run([node, "--test", "tests/desktop/**/*test*.mjs"])
    output = result.stdout + result.stderr
    if "were not found" in output and result.returncode and not args.strict:
        raise Skip("react, react-dom and jsdom were not found (npm ci --prefix tools/dev --ignore-scripts)")
    if result.returncode:
        raise AssertionError(tail(output, 40) + "\nFIX: run node tests/desktop/wizard_test.mjs for the full "
                             "output; after editing desktop-src/ run node tools/bundle.mjs first")
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
        result = subprocess.run([sys.executable, "-I", "-c", SCAN, str(source), str(target)],
                                text=True, capture_output=True)
    if result.returncode:
        raise AssertionError(tail(result.stderr) + "\nFIX: the scanner itself failed; check --hermes-source")
    report = json.loads(result.stdout.strip().splitlines()[-1])
    if report["verdict"] != "safe":
        lines = [f"  {b['severity']}: {b['id']} in {b['file']}:{b['line']}  {b['match']}" for b in report["bad"]]
        raise AssertionError(f"verdict {report['verdict']}; installs would " +
                             ("be refused" if report["verdict"] == "dangerous" else "ask for confirmation") +
                             ":\n" + "\n".join(lines) + "\nFIX: reword or remove those lines (see AGENTS.md, "
                             "\"Install scanner\"); medium findings are fine")
    return f"safe ({report['findings']} minor notes)"


def check_acceptance(args) -> str:
    sys.path.insert(0, str(ROOT))
    from adapter import paths  # noqa: E402  (the adapter decides where setup put the toolchain)
    if not paths.setup_root().is_dir():
        raise Skip(f"no toolchain at {paths.setup_root()}; run python tools/prepare_toolchain.py (about a minute), "
                   "or point HERMRETRO_DEPS_ROOT at a folder that has one")
    env = {**os.environ, "TMPDIR": short_tmp()}
    (ROOT / "notes" / "evidence" / "broker-acceptance.json").unlink(missing_ok=True)  # never report an old run
    result = run([sys.executable, "tests/acceptance/broker_acceptance.py"], env=env, timeout=1200)
    passed = sum(line.startswith("PASS ") for line in result.stdout.splitlines())
    failed = [line for line in result.stdout.splitlines() if line.startswith("FAIL ")]
    if result.returncode or failed:
        details = []
        evidence = ROOT / "notes" / "evidence" / "broker-acceptance.json"
        if evidence.is_file():
            for item in json.loads(evidence.read_text()).get("checks", []):
                if not item.get("passed"):
                    details.append(f"{item['id']}: {json.dumps(item.get('detail'), default=str)[:600]}")
        raise AssertionError("\n".join(failed + details) + "\n" + tail(result.stderr, 15) + "\nFIX: rerun python "
                             "tests/acceptance/broker_acceptance.py with TMPDIR=" + short_tmp() + " and read its output")
    return f"{passed} passed"


CHECKS = {name: globals()[f"check_{name}"] for name in ALL}


def summary(rows: list[tuple[str, str, float, str]]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = ["| Check | Result | Time | Detail |", "|---|---|---|---|"]
    lines += [f"| {name} | {state} | {seconds:.1f} s | {detail.splitlines()[0][:150] if detail else ''} |"
              for name, state, seconds, detail in rows]
    failures = [(name, detail) for name, state, _s, detail in rows if state == "FAILED"]
    for name, detail in failures:
        lines += ["", f"### {name}", "```", detail[-3000:], "```"]
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").strip().splitlines()[0])
    parser.add_argument("checks", nargs="*", help="fast (default), full, or check names: " + ", ".join(ALL))
    parser.add_argument("--hermes-source")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    names = args.checks or ["fast"]
    wanted = [c for name in names for c in (FAST if name == "fast" else ALL if name == "full" else [name])]
    unknown = [name for name in wanted if name not in CHECKS]
    if unknown:
        parser.error("unknown check: " + ", ".join(unknown))

    rows, failed = [], False
    for name in dict.fromkeys(wanted):
        start = time.monotonic()
        try:
            state, detail = "ok", CHECKS[name](args)
        except Skip as skip:
            state, detail = ("FAILED" if args.strict else "skipped"), str(skip)
            if args.strict:
                detail += "\nFIX: install what is missing (see AGENTS.md, \"Checks\")"
        except AssertionError as error:
            state, detail = "FAILED", str(error)
        seconds = time.monotonic() - start
        failed |= state == "FAILED"
        rows.append((name, state, seconds, detail))
        print(f"{state:>7}  {name:<10} {seconds:5.1f} s  {detail.splitlines()[0] if detail else ''}", flush=True)
        if state == "FAILED" and "\n" in detail:
            print("\n".join("         " + line for line in detail.splitlines()[1:]), flush=True)
    summary(rows)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

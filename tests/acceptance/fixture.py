"""Run-scoped state and file/process helpers shared by the real-broker acceptance stages."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

from backend.broker.client import BrokerClient, spawn_broker
from backend.system import host as host_os, paths

HANDOFF = 3.0
OWNER_A = {"profile": "s01-profile", "conversation_id": "conv-A"}
OWNER_B = {"profile": "s01-profile", "conversation_id": "conv-B"}
OWNER_C = {"profile": "s01-profile", "conversation_id": "conv-C"}


class BrokerRun:
    def __init__(self, work: Path, run_name: str):
        self.work = work.resolve()  # macOS reports the real paths behind /tmp and /var
        self.name = run_name
        self.state = self.work / "state"
        self.state.mkdir(mode=0o700)
        self.compiler_temp = self.work / ("nested-" + "x" * 120)
        self.compiler_temp.mkdir()
        self.project_a = self.work / "projA"
        self.project_b = self.work / "projB"
        node = paths.find_node()
        self.node = node["path"]
        self.node_version = f"v{node['version']}" if node["version"] else None
        self.launches: list[subprocess.Popen] = []
        self.brokers: set[int] = set()
        self.checks: list[dict] = []
        self.observations: dict = {}

    def check(self, check_id: str, title: str, passed: bool, **detail) -> None:
        self.checks.append({"id": check_id, "title": title, "passed": bool(passed), "detail": detail})
        print(("PASS " if passed else "FAIL ") + check_id + " " + title, flush=True)

    def spawn_broker(self, state_dir: Path, node: str, *, deadline: float | None = None) -> subprocess.Popen:
        process = spawn_broker(state_dir, node, deadline=deadline)
        self.launches.append(process)
        return process

    def stop_brokers(self) -> None:
        """Ask for a clean shutdown, then stop and reap any remaining children this run launched."""
        stopping_pid = None
        try:
            with BrokerClient(self.state) as last:
                if last.request({"op": "shutdown", "force": True}).get("ok"):
                    stopping_pid = last.hello["pid"]
        except Exception:  # noqa: BLE001 - no broker running is the usual case
            pass
        # systemd-run --scope execs the broker in the same child as a direct launch.
        for process in self.launches:
            if process.poll() is not None:
                continue
            self.brokers.add(process.pid)
            if process.pid != stopping_pid:
                process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for pid in self.brokers:
            for path in fallback_dirs(pid):
                shutil.rmtree(path, ignore_errors=True)

    def write_evidence(self, passed: bool, crashed: str | None = None) -> Path:
        trace_file = self.state / "trace.jsonl"
        trace = [json.loads(line) for line in trace_file.read_text().splitlines()] if trace_file.exists() else []
        evidence = {
            "suite": "broker acceptance (real engine, outside Hermes)",
            "run": self.name,
            "passed": passed,
            "checks_passed": sum(c["passed"] for c in self.checks),
            "checks_total": len(self.checks),
            "crashed": crashed,
            "backend": {
                "version": paths.PLUGIN_VERSION,
                "protocol": paths.PROTOCOL,
                "code_fingerprint": paths.code_fingerprint(),
            },
            "engine": paths.verify_engine(),
            "host": {
                "node": self.node_version,
                "python": sys.version.split()[0],
                "platform": sys.platform,
            },
            "not_covered": [
                "Anything that needs Hermes itself",
                "Browser player and annotations",
                "Long-operation recovery",
                "Any hardware operation beyond a no-USB status read",
            ],
            "checks": self.checks,
            "observations": self.observations,
            "trace_events": len(trace),
            "trace_tail": trace[-40:] if not passed else [],
        }
        out = Path(__file__).resolve().parents[2] / "notes" / "evidence"  # git-ignored: run evidence stays local
        out.mkdir(parents=True, exist_ok=True)
        # Keep the home directory (and so the user name) out of it, in case it is shared.
        (out / "broker-acceptance.json").write_text(
            json.dumps(evidence, indent=2, default=str).replace(str(Path.home()), "~") + "\n"
        )
        return out / "broker-acceptance.json"


def structured(response: dict) -> dict:
    return (response.get("result") or {}).get("structuredContent") or {}


def snapshot(root: Path) -> dict[str, str]:
    out = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_file() and not rel.startswith(("build/", ".chromatic", "artifacts/", "captures/")):
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def diff(before: dict, after: dict) -> list[str]:
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


def alive(pid: int) -> bool:
    """Running and not a zombie (`ps` works the same on Linux and macOS)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(state) and not state.startswith("Z")


def fallback_dirs(broker: int) -> list[Path]:
    """The private temp folders one broker made for its workers (``hrt-<pid>-`` in the system temp root),
    only those this user owns."""
    root = Path(host_os.SYSTEM_TEMP).resolve()
    found = []
    for path in root.glob(f"hrt-{broker}-*"):
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid():
            found.append(path)
    return sorted(found)


def wait_gone(pids, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and any(alive(p) for p in pids):
        time.sleep(0.1)
    return not any(alive(p) for p in pids)

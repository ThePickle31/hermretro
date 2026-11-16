"""Recovering the engine's recording-access lease after its owner died. Stdlib only.

The engine guards each project's recordings and emulator with ``artifacts/.recording-access/lease.json``
(``{"schemaVersion":1,"pid":…,"token":…}``), created exclusively by the engine process that opens the
emulator and removed when it closes. The engine never takes a lease over and never checks whether the
owner is alive (its diagnostic says ``processLiveness: "unobserved"``, ``recoveryAuthorized: false``):
that decision belongs to the host. A worker killed with SIGKILL (a gateway restart, the OOM killer, a
crash, power loss) therefore leaves a lease that blocks the project's emulator forever.

``reclaim_stale`` makes that decision for the broker. It removes a lease only when it can prove the
owner is gone: no such process, or a process that started after the lease was written (the pid was
reused). A lease held by one of the broker's own live workers, by a process of another user, or by a
live process that could be its owner (for example another client such as the Codex plugin) is left
alone. The file must look exactly like an engine lease and must not change between the check and the
removal.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import stat
import subprocess
import time
from pathlib import Path

LEASE = Path("artifacts") / ".recording-access" / "lease.json"
_TOKEN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_SLACK = 2.0  # seconds of clock and filesystem timestamp slack when comparing start times


def is_lease_conflict(result: dict) -> bool:
    """True for the engine's refusal to create a lease because one already exists."""
    structured = result.get("structuredContent") if isinstance(result, dict) else None
    failure = structured.get("recordingAccessFailure") if isinstance(structured, dict) else None
    return isinstance(failure, dict) and failure.get("operation") == "create-exclusive-lease" \
        and (failure.get("category") == "already-exists" or failure.get("code") == "EEXIST")


def _read(path: Path) -> tuple[os.stat_result, bytes, dict]:
    """The lease's stat, bytes and record, or ValueError when it is not exactly an engine lease."""
    st = os.lstat(path)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != os.getuid() \
            or stat.S_IMODE(st.st_mode) != 0o600 or st.st_size > 4096:
        raise ValueError("not a plain owner-only lease file")
    for parent in (path.parent, path.parent.parent):
        pst = os.lstat(parent)
        if not stat.S_ISDIR(pst.st_mode) or pst.st_uid != os.getuid():
            raise ValueError("unexpected lease directory")
    raw = path.read_bytes()
    record = json.loads(raw.decode("utf-8"))
    if not isinstance(record, dict) or sorted(record) != ["pid", "schemaVersion", "token"] \
            or record["schemaVersion"] != 1 or not isinstance(record["pid"], int) or record["pid"] <= 0 \
            or not isinstance(record["token"], str) or not _TOKEN.match(record["token"]):
        raise ValueError("not an engine lease record")
    return st, raw, record


def process_start(pid: int) -> float | None:
    """Wall-clock start time of a process, or None when it cannot be read."""
    if platform.system() == "Linux":
        try:
            fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
            ticks = int(fields[19])  # field 22 (starttime), counted after the ")" of the command name
            boot = next(int(line.split()[1]) for line in Path("/proc/stat").read_text().splitlines()
                        if line.startswith("btime "))
            return boot + ticks / os.sysconf("SC_CLK_TCK")
        except (OSError, ValueError, IndexError, StopIteration):
            return None
    try:  # macOS and other POSIX: elapsed time as [[dd-]hh:]mm:ss
        out = subprocess.run(["ps", "-o", "etime=", "-p", str(pid)], capture_output=True, text=True,
                             timeout=5).stdout.strip()
        days, _, rest = out.rpartition("-")
        parts = [int(p) for p in rest.split(":")]
        while len(parts) < 3:
            parts.insert(0, 0)
        elapsed = int(days or 0) * 86400 + parts[0] * 3600 + parts[1] * 60 + parts[2]
        return time.time() - elapsed
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def owner_state(pid: int, lease_mtime: float, own_groups: set[int]) -> str:
    """``ours`` (a live worker of this broker), ``dead``, ``reused`` (the pid now belongs to a process
    started after the lease was written) or ``live`` (a process that may still own it)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return "dead"
    except PermissionError:
        return "live"  # another user's process: never ours to judge
    try:
        if os.getpgid(pid) in own_groups:
            return "ours"
    except ProcessLookupError:
        return "dead"
    started = process_start(pid)
    if started is not None and started > lease_mtime + _SLACK:
        return "reused"
    return "live"


def reclaim_stale(project_root: str | os.PathLike, own_groups: set[int]) -> dict:
    """Remove the project's recording lease if its owner is provably gone. Never raises."""
    path = Path(project_root) / LEASE
    try:
        st, raw, record = _read(path)
    except FileNotFoundError:
        return {"cleared": False, "reason": "no lease"}
    except (OSError, ValueError, UnicodeDecodeError) as error:
        return {"cleared": False, "reason": f"lease not recognised: {error}"}
    state = owner_state(record["pid"], st.st_mtime, own_groups)
    info = {"pid": record["pid"], "owner": state, "written": int(st.st_mtime)}
    if state not in ("dead", "reused"):
        return {"cleared": False, "reason": f"owner is {state}", **info}
    try:
        again = os.lstat(path)
        if (again.st_ino, again.st_mtime_ns, again.st_size) != (st.st_ino, st.st_mtime_ns, st.st_size) \
                or hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(raw).digest():
            return {"cleared": False, "reason": "lease changed while it was checked", **info}
        path.unlink()
    except FileNotFoundError:
        return {"cleared": False, "reason": "lease was released meanwhile", **info}
    except OSError as error:
        return {"cleared": False, "reason": f"could not remove the lease: {error}", **info}
    return {"cleared": True, **info}

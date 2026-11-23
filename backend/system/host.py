"""Everything that differs between Linux and macOS, in one place. Stdlib only.

hermretro supports Linux and macOS, Apple Silicon and Intel, with no difference a user can notice. Any
call that exists on only one of them belongs here, with the other system's branch beside it.
Windows is not supported: ``unsupported_reason`` says so before anything else loads.
"""

from __future__ import annotations

import os
import platform
import socket
import stat
import struct
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from uuid import UUID

LINUX = sys.platform.startswith("linux")
MACOS = sys.platform == "darwin"

# Network settings a child process needs to download through a proxy or a company certificate authority (setup
# downloads about 700 MB through Node). Passed on to the broker, the engine and setup scripts, both spellings.
NETWORK_ENV = (
    "HTTPS_PROXY",
    "https_proxy",
    "HTTP_PROXY",
    "http_proxy",
    "NO_PROXY",
    "no_proxy",
    "ALL_PROXY",
    "all_proxy",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "NODE_EXTRA_CA_CERTS",
)

# macOS <sys/un.h>: SOL_LOCAL, LOCAL_PEERCRED (struct xucred), LOCAL_PEERPID (pid_t). Python names none of them.
_SOL_LOCAL = 0
_LOCAL_PEERCRED = 0x001
_LOCAL_PEERPID = 0x002
# struct xucred: u_int cr_version; uid_t cr_uid; short cr_ngroups; gid_t cr_groups[16]
_XUCRED = struct.Struct("=IIh2x16I")


# GBDK 4.5 has a 128-byte install-prefix buffer. Leave room for GB Studio's generated build folder and
# the relative path to the copied compiler. Check the real path: GB Studio resolves temporary parents itself.
_ENGINE_TMP_MAX = 64
# The only fallback parent: the system's own temp root (/private/tmp on macOS), never one named by the
# environment, whose ancestors nobody here vouches for.
SYSTEM_TEMP = "/tmp"
TEMP_UNAVAILABLE = (
    "Game tools need a short, writable temporary directory. Free space in the system temporary directory, "
    "or set TMPDIR to a short, private folder and restart Hermes. If games are open in other chats, close "
    "them too: hermretro's game tools switch to the new folder once no game is running."
)


def _protected(info: os.stat_result, uid: int) -> bool:
    """Only this user or root can rename or replace the entries of this directory."""
    return info.st_uid in (0, uid) and (not info.st_mode & 0o022 or bool(info.st_mode & stat.S_ISVTX))


def _short_temp_parent(raw: str) -> Path | None:
    """A short writable directory with protected ancestors. Except for the system temp root, don't keep an
    alias: the worker inherits the raw pathname and an alias elsewhere could change after this check."""
    try:
        candidate = Path(raw)
        if not candidate.is_absolute():
            return None
        path = candidate.resolve(strict=True)
        if path != candidate and raw != SYSTEM_TEMP:
            return None
        info = path.stat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or len(os.fsencode(path)) > _ENGINE_TMP_MAX
            or not os.access(path, os.W_OK | os.X_OK)
        ):
            return None
        uid = os.getuid()
        if _protected(info, uid) and all(_protected(p.stat(), uid) for p in path.parents):
            return path
    except (OSError, RuntimeError, ValueError):
        pass
    return None


def _inherited_temp(env: Mapping[str, str]) -> Path | None:
    return _short_temp_parent(next((env[name] for name in ("TMPDIR", "TMP", "TEMP") if env.get(name)), SYSTEM_TEMP))


def engine_temp_ready(env: Mapping[str, str]) -> bool:
    """Whether a worker started with ``env`` gets a usable temp directory (without making one)."""
    return _inherited_temp(env) is not None or _short_temp_parent(SYSTEM_TEMP) is not None


def engine_tempdir(env: Mapping[str, str]) -> tempfile.TemporaryDirectory | None:
    """Give a worker a short private temp directory if Node's inherited one will not work.

    Leave a usable parent alone. Otherwise make one in the system's short sticky temp root, whose whole
    path only root can change. Its name carries this process's id (``hrt-<pid>-``) so a caller can tell the
    directories one broker made. The caller owns it until its worker exits, never the inherited directory.
    """
    if _inherited_temp(env) is not None:
        return None
    parent = _short_temp_parent(SYSTEM_TEMP)
    if parent is not None:
        try:
            directory = tempfile.TemporaryDirectory(
                prefix=f"hrt-{os.getpid()}-", dir=parent, ignore_cleanup_errors=True
            )
        except OSError:
            pass
        else:
            if len(os.fsencode(directory.name)) <= _ENGINE_TMP_MAX:
                return directory
            directory.cleanup()
    raise OSError(TEMP_UNAVAILABLE)


def unsupported_reason() -> str | None:
    """Why hermretro cannot run on this computer, or None."""
    if LINUX or MACOS:
        return None
    name = "Windows" if sys.platform.startswith(("win", "cygwin", "msys")) else platform.system() or sys.platform
    return f"hermretro supports Linux and macOS; {name} is not supported. Use hermretro on a Linux or macOS computer."


def boot_id() -> str | None:
    """The kernel's UUID for this boot, shared by gateway processes on the same host."""
    try:
        if LINUX:
            value = Path("/proc/sys/kernel/random/boot_id").read_text()
        elif MACOS:
            value = subprocess.check_output(["/usr/sbin/sysctl", "-n", "kern.bootsessionuuid"], text=True, timeout=2)
        else:
            return None
        return str(UUID(value.strip()))
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def peer_credentials(sock: socket.socket) -> tuple[int | None, int | None]:
    """(pid, uid) of the process at the other end of a connected Unix socket, as the kernel reports them.
    Either is None when the system will not say; the broker then relies on its private run folder and token."""
    if LINUX:
        try:
            pid, uid, _gid = struct.unpack(
                "3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
            )
            return pid, uid
        except OSError:
            return None, None
    if MACOS:
        uid = pid = None
        try:
            raw = sock.getsockopt(_SOL_LOCAL, _LOCAL_PEERCRED, _XUCRED.size)
            if len(raw) >= 8:
                version, uid = struct.unpack_from("=II", raw)
                uid = uid if version == 0 else None  # XUCRED_VERSION is 0
        except OSError:
            uid = None
        try:
            pid = struct.unpack("i", sock.getsockopt(_SOL_LOCAL, _LOCAL_PEERPID, 4))[0]
        except (OSError, struct.error):
            pid = None
        return pid, uid
    return None, None


@cache  # neither can change while the process runs
def _sysctl_flag(name: str) -> bool:
    try:
        out = subprocess.run(["/usr/sbin/sysctl", "-n", name], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return out.returncode == 0 and out.stdout.strip() == "1"


@cache
def rosetta() -> bool:
    """True when this process is an Intel build running under Rosetta on an Apple Silicon Mac."""
    return MACOS and _sysctl_flag("sysctl.proc_translated")


def native_arch() -> str:
    """The computer's own architecture, ``arm64`` or ``x64`` (or the raw machine name), never the one an
    emulated process sees: an Intel Python under Rosetta still reports ``arm64`` here, so downloads match
    the Node.js and tools that run natively."""
    machine = platform.machine().lower()
    arch = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(machine, machine)
    if arch == "x64" and (rosetta() or (MACOS and _sysctl_flag("hw.optional.arm64"))):
        return "arm64"
    return arch


def system_name() -> str:
    """``linux`` or ``darwin`` (the names Node.js and the engine use), else the lower-case system name."""
    return "linux" if LINUX else "darwin" if MACOS else platform.system().lower()


def describe() -> dict:
    """For status reports: the system, the native architecture and whether Rosetta is in the way."""
    return {
        "system": system_name(),
        "machine": native_arch(),
        "rosetta": rosetta(),
        "supported": unsupported_reason() is None,
    }

"""Everything that differs between Linux and macOS, in one place. Stdlib only.

hermretro supports Linux and macOS, Apple Silicon and Intel, with no difference a user can notice. Any
call that exists on only one of them belongs here, with the other system's branch beside it.
Windows is not supported: ``unsupported_reason`` says so before anything else loads.
"""
from __future__ import annotations

import platform
import socket
import struct
import subprocess
import sys
from functools import cache

LINUX = sys.platform.startswith("linux")
MACOS = sys.platform == "darwin"

# Network settings a child process needs to download through a proxy or a company certificate authority (setup
# downloads about 700 MB through Node). Passed on to the broker, the engine and setup scripts, both spellings.
NETWORK_ENV = ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "NO_PROXY", "no_proxy", "ALL_PROXY",
               "all_proxy", "SSL_CERT_FILE", "SSL_CERT_DIR", "NODE_EXTRA_CA_CERTS")

# macOS <sys/un.h>: SOL_LOCAL, LOCAL_PEERCRED (struct xucred), LOCAL_PEERPID (pid_t). Python names none of them.
_SOL_LOCAL = 0
_LOCAL_PEERCRED = 0x001
_LOCAL_PEERPID = 0x002
# struct xucred: u_int cr_version; uid_t cr_uid; short cr_ngroups; gid_t cr_groups[16]
_XUCRED = struct.Struct("=IIh2x16I")


def unsupported_reason() -> str | None:
    """Why hermretro cannot run on this computer, or None."""
    if LINUX or MACOS:
        return None
    name = "Windows" if sys.platform.startswith(("win", "cygwin", "msys")) else platform.system() or sys.platform
    return (f"hermretro supports Linux and macOS; {name} is not supported. "
            "Use hermretro on a Linux or macOS computer.")


def peer_credentials(sock: socket.socket) -> tuple[int | None, int | None]:
    """(pid, uid) of the process at the other end of a connected Unix socket, as the kernel reports them.
    Either is None when the system will not say; the broker then relies on its private run folder and token."""
    if LINUX:
        try:
            pid, uid, _gid = struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                                                                 struct.calcsize("3i")))
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
    return {"system": system_name(), "machine": native_arch(), "rosetta": rosetta(),
            "supported": unsupported_reason() is None}

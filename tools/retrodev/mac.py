"""mac [--host H] [-- <check.py args>]: the checks on a MacBook over ssh, when one is set up (optional).

The host is the personal setting mac_host (no default: unset means no mac, and CI's macOS runners cover it,
exit 0). It must answer `ssh -o ConnectTimeout=3 -o BatchMode=yes <host> true` (else exit 2: unreachable). Then on
the mac, in the clone at mac_repo (default ~/Projects/hermretro, the ~ expanded there), it fetches, checks out
this checkout's commit detached and runs `python3 tools/check.py [args]`, its output streamed here. The commit
must be on the remote (the mac fetches it from there). It never pushes from the mac.
"""

from __future__ import annotations

import shlex
import subprocess

from . import repo
from .output import OK, WAITING, Failure

PROBE = ["-o", "ConnectTimeout=3", "-o", "BatchMode=yes"]


def real_ssh(args: list[str], say) -> int:
    """Run ssh with these arguments, passing each output line to ``say``; its exit code."""
    try:
        with subprocess.Popen(
            ["ssh", *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL
        ) as process:
            assert process.stdout is not None
            for line in process.stdout:
                say(line.rstrip("\n"))
        return process.returncode
    except OSError as error:
        say(f"ssh: {error}")
        return 255


def ssh_runner(ctx):
    return ctx.fakes.get("ssh") or real_ssh


def host(ctx, given: str | None = None) -> str:
    return (given or ctx.get("mac_host")).strip()


def reachable(ctx, name: str) -> bool:
    return ssh_runner(ctx)([*PROBE, name, "true"], lambda _line: None) == 0


def remote_path(path: str) -> str:
    """A shell word for the path on the mac: a leading ~/ stays unquoted, so the mac's shell expands it."""
    if path == "~" or path.startswith("~/"):
        rest = path[2:]
        return "~/" + shlex.quote(rest) if rest else "~"
    return shlex.quote(path)


def script(ctx, sha: str, args: list[str]) -> str:
    folder = remote_path(ctx.get("mac_repo"))
    check = " ".join(shlex.quote(word) for word in ["python3", "tools/check.py", *args])
    return (
        f"cd {folder} && git fetch --quiet {shlex.quote(ctx.remote)} && "
        f"git -c advice.detachedHead=false checkout --quiet --detach {sha} && {check}"
    )


def doctor_item(ctx) -> dict:
    """doctor --all: the mac's reachability (optional: never a problem)."""
    name = host(ctx)
    if not name:
        detail = "no mac configured (mac_host); CI's macOS runners cover it"
    else:
        detail = f"{name} answers" if reachable(ctx, name) else f"{name} unreachable; CI covers macOS"
    return {"name": "mac", "ok": True, "detail": detail, "fix": "", "optional": True}


def run(ctx, given: str | None, args: list[str]) -> int:
    args = args[1:] if args[:1] == ["--"] else args
    name = host(ctx, given)
    if not name:
        ctx.out.say("no mac configured; CI's macOS runners cover it (python tools/retrodev config set mac_host <host>)")
        ctx.out.set(host=None, ran=False)
        return OK
    ctx.out.set(host=name, ran=False)
    if not reachable(ctx, name):
        raise Failure(
            f"{name} unreachable; CI covers macOS (ssh with a 3 s timeout and no password prompt got no answer)",
            f"wake the mac or check its network, then python tools/retrodev mac (ssh {name} true must answer)",
            WAITING,
        )
    sha = repo.head(ctx.top)
    remote = repo.git(["branch", "-r", "--contains", sha or "HEAD"], ctx.top, check=False).split()
    if not sha or not any(ref.startswith(f"{ctx.remote}/") for ref in remote):
        raise Failure(
            f"{(sha or 'HEAD')[:9]} is not on {ctx.remote}: the mac fetches the commit from there",
            "python tools/retrodev ship (it pushes the branch), then python tools/retrodev mac",
        )
    command = script(ctx, sha, args)
    ctx.out.say(f"on {name}: {command}")
    code = ssh_runner(ctx)([name, command], ctx.out.say)
    ctx.out.set(ran=True, sha=sha, command=command, exit=code)
    if code:
        raise Failure(
            f"the checks failed on {name} at {sha[:9]} (exit {code})",
            "read the output above (each failure has its FIX); fix it here, commit, ship, then mac again",
        )
    ctx.out.say(f"passed on {name} at {sha[:9]}")
    return OK

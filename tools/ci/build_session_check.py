"""Check that a Hermes answers the Build page's untitled session.create the way the page requires.

    "$HERMES_RUNTIME_PY" -I tools/ci/build_session_check.py     # in CI, with Hermes's own Python
    <python> tools/ci/build_session_check.py                    # locally, with your Hermes install's Python

The Build page (page/pages/build/chat/actions.js, createBuildChat) opens each conversation with
`session.create {hidden: true, source: 'gui', model?, provider?, reasoning_effort?, fast?}` and no title, and sends
the first message only when the answer has a fresh session with no history and, for a picked model, `info.model`
and `info.provider` equal to the pick. This asks a real Hermes, in a throwaway home with no credentials and no
turn, over both gateways Desktop can reach:

- the canonical gateway (`hermes-gateway-v1`, what local Desktop dials), through Hermes's own client
  (`hermes_cli.gateway_client.connect_gateway`), with the parameters Desktop's
  `CanonicalDesktopProtocol.prepareCreate` sends (`reasoning`, `service_tier` and a fresh `request_id`);
  each new conversation is then resumed to read its stored history;
- the standalone `hermes serve` socket (`/api/ws` without a session authority), with the page's parameters as is.

CI runs it on every pull request against the oldest supported Hermes (ci.yml's HERMES_REF) and nightly against
Hermes main. Every failure ends with a "FIX:" line.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python -I leaves the script's folder out

from clean_install_check import work_parent  # noqa: E402 - the script's folder goes on sys.path first

# Two picks on different providers (neither the throwaway profile's default) so a route swap cannot pass.
PICKS = (
    {"model": "claude-sonnet-4-6", "provider": "anthropic"},
    {"model": "gpt-5.5", "provider": "openai-codex"},
)
# Fast is sent for a Codex pick only. Desktop renames both optional fields on the canonical gateway.
PAGE_EXTRA = {"reasoning_effort": "high", "fast": True}
CONFIG = "model:\n  default: openai/gpt-oss-120b\n  provider: openrouter\n"
TOKEN = uuid.uuid4().hex  # the throwaway serve's dashboard token, never shown in output
PREFIX = "hermretro-build-session-"
FIX = (
    "FIX: the page's createBuildChat (page/pages/build/chat/actions.js) and this Hermes disagree on session.create; "
    "follow the answer shape this Hermes gives (docs/dev/STUDIO-PAGES.md, the Build gateway calls) or raise "
    "plugin.yaml requires_hermes"
)
IMPORT_FIX = (
    "FIX: run with a Python that imports Hermes and its dependencies (the Python of your Hermes install; "
    'docs/dev/TESTING.md, "The Hermes names check")'
)


def requests() -> list[tuple[str, dict, dict | None]]:
    """``(label, page params, pick)`` for every create the page makes: a pick, a pick with effort and fast mode, and
    the profile default (no pick)."""
    base = {"hidden": True, "source": "gui"}
    return [
        ("picked", {**base, **PICKS[0]}, PICKS[0]),
        ("picked with effort and fast", {**base, **PICKS[1], **PAGE_EXTRA}, PICKS[1]),
        ("default", dict(base), None),
    ]


def canonical_params(page: dict) -> dict:
    """The page's params as Desktop's CanonicalDesktopProtocol.prepareCreate sends them to the canonical gateway."""
    params = {key: value for key, value in page.items() if key not in PAGE_EXTRA}
    if "reasoning_effort" in page:
        params["reasoning"] = page["reasoning_effort"]
    if page.get("fast") is True:
        params["service_tier"] = "priority"
    return {**params, "request_id": uuid.uuid4().hex, "source": "gui"}


def problems(gateway: str, answers: list[dict]) -> list[str]:
    """What the page would refuse in *answers* (one per ``requests()`` row: ``{"result"}`` or ``{"error"}``, plus
    ``"history"`` when the gateway was asked for the stored conversation)."""
    found, seen = [], set()
    for (label, _page, pick), answer in zip(requests(), answers, strict=True):
        where = f"{gateway}, {label}"
        if "error" in answer:
            found.append(f"{where}: session.create was refused: {answer['error']}")
            continue
        result = answer.get("result") or {}
        runtime, stored = result.get("session_id"), result.get("stored_session_id") or result.get("session_id")
        if not runtime or not stored:
            found.append(f"{where}: no session_id / stored_session_id in {sorted(result)}")
            continue
        if ("runtime", runtime) in seen or ("stored", stored) in seen:
            found.append(f"{where}: returned a session an earlier create already returned ({runtime}, {stored})")
        seen.update((("runtime", runtime), ("stored", stored)))
        if result.get("message_count") or result.get("messages"):
            found.append(f"{where}: a new conversation came back with history ({result.get('message_count')})")
        history = answer.get("history")
        if history is not None and (history.get("message_count") or history.get("messages")):
            found.append(f"{where}: the stored conversation has history ({history.get('message_count')})")
        info = result.get("info") or {}
        if pick and (info.get("model"), info.get("provider")) != (pick["model"], pick["provider"]):
            found.append(
                f"{where}: info has model={info.get('model')!r} provider={info.get('provider')!r}, "
                f"not the pick {pick['model']!r} ({pick['provider']!r})"
            )
    return found


def evidence(gateway: str, answers: list[dict]) -> str:
    rows = []
    for (label, _page, _pick), answer in zip(requests(), answers, strict=True):
        result, info = answer.get("result") or {}, (answer.get("result") or {}).get("info") or {}
        history = answer.get("history") or {}
        rows.append(
            f"  {gateway}, {label}: session {result.get('session_id')} stored {result.get('stored_session_id')} "
            f"messages {result.get('message_count')}"
            + (f" (stored {history.get('message_count')})" if "history" in answer else "")
            + f", model {info.get('model')!r} provider {info.get('provider')!r}"
        )
    return "\n".join(rows)


async def _canonical_answers() -> list[dict]:
    """Attach to the disposable gateway owned by the parent process; discovery never starts another."""
    from hermes_cli.gateway_client import GatewayRPCError, connect_gateway
    from hermes_cli.gateway_runtime import discover_gateway_endpoint

    home = Path(os.environ["HERMES_HOME"])
    deadline = time.monotonic() + 40
    while True:
        found = await asyncio.to_thread(discover_gateway_endpoint, home)
        if found.state == "ready" and found.endpoint is not None:
            break
        if time.monotonic() > deadline:
            raise RuntimeError(f"the throwaway gateway did not come up: {found.state} ({found.reason_code})")
        await asyncio.sleep(0.25)

    answers = []
    async with connect_gateway(found.endpoint) as client:
        for _label, page, _pick in requests():
            try:
                result = await client.rpc("session.create", _timeout=120, **canonical_params(page))
            except GatewayRPCError as error:
                answers.append({"error": f"{error} {error.data}"})
                continue
            stored = result.get("stored_session_id") or result.get("session_id")
            resumed = await client.rpc("session.resume", _timeout=60, session_id=stored)
            answers.append({"result": result, "history": resumed})
    return answers


def environment(base: Path) -> dict[str, str]:
    """Keep only process basics; the gateway cannot see the caller's secrets or profile settings."""
    kept = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "LC_CTYPE") if key in os.environ}
    return {**kept, "HOME": str(base / "home"), "HERMES_HOME": str(base / "hermes-home"), "TMPDIR": str(base)}


@contextmanager
def run_hermes(
    base: Path, log: Path, args: list[str], extra_env: dict[str, str] | None = None
) -> Iterator[subprocess.Popen]:
    """Own the foreground child directly; never infer the process to stop from a PID file."""
    with log.open("w") as out:
        child = subprocess.Popen(
            [sys.executable, "-I", "-m", "hermes_cli.main", *args],
            env=environment(base) | (extra_env or {}),
            cwd=base,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.STDOUT,
        )
        try:
            yield child
        finally:
            child.terminate()
            try:
                child.wait(15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


def canonical(base: Path) -> list[dict]:
    log = base / "canonical.log"
    with run_hermes(base, log, ["gateway", "run"]):
        child = subprocess.run(
            [sys.executable, "-I", __file__, "--canonical"],
            env=environment(base),
            cwd=base,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=160,
        )
        if child.returncode:
            raise RuntimeError(f"the canonical gateway run failed:\n{child.stderr}\n{log.read_text()[-2000:]}")
        return json.loads(child.stdout.strip().splitlines()[-1])


def serve(base: Path) -> list[dict]:
    from websockets.sync.client import connect

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    log = base / "serve.log"
    args = ["serve", "--skip-build", "--host", "127.0.0.1", "--port", str(port)]
    with run_hermes(base, log, args, {"HERMES_DASHBOARD_SESSION_TOKEN": TOKEN}) as server:
        deadline = time.monotonic() + 40
        while True:
            try:
                ws = connect(f"ws://127.0.0.1:{port}/api/ws?token={TOKEN}", open_timeout=2, proxy=None)
                break
            except Exception as error:  # noqa: BLE001 - retried until serve is up or gone
                if time.monotonic() > deadline or server.poll() is not None:
                    raise RuntimeError(f"hermes serve did not come up ({error}):\n{log.read_text()[-2000:]}") from error
                time.sleep(0.3)
        answers = []
        with ws:
            for number, (_label, page, _pick) in enumerate(requests(), 1):
                ws.send(json.dumps({"jsonrpc": "2.0", "id": str(number), "method": "session.create", "params": page}))
                while (frame := json.loads(ws.recv(timeout=120))).get("id") != str(number):
                    pass
                answers.append({"error": frame["error"]} if "error" in frame else {"result": frame.get("result")})
        return answers


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--canonical"]:  # internal: never attach this probe to a user's gateway
        home = Path(os.environ.get("HERMES_HOME", "")).resolve()
        if home.name != "hermes-home" or not home.parent.name.startswith(PREFIX) or Path.home() != home.parent / "home":
            print("FIX: run this check without --canonical so it creates its own throwaway home", file=sys.stderr)
            return 1
        print(json.dumps(asyncio.run(_canonical_answers())))
        return 0
    try:
        import hermes_cli.gateway_client  # noqa: F401 - only proves this Python imports Hermes
        import websockets.sync.client  # noqa: F401 - the serve check dials with it
    except Exception as error:  # noqa: BLE001 - every import failure is reported with its text
        print(f"this Python ({sys.executable}) cannot import Hermes: {type(error).__name__}: {error}", file=sys.stderr)
        print(IMPORT_FIX, file=sys.stderr)
        return 1
    real_root = Path.home() / ".hermes"
    try:
        parent = work_parent(os.environ, real_root)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    found, shown = [], []
    with tempfile.TemporaryDirectory(prefix=PREFIX, dir=str(parent)) as tmp:
        base = Path(tmp).resolve()
        home = base / "hermes-home"
        if home.is_relative_to(real_root.resolve()):
            print(f"refusing to use {home}: it is inside the real Hermes home", file=sys.stderr)
            return 1
        home.mkdir()
        (base / "home").mkdir()
        (home / "config.yaml").write_text(CONFIG)
        for gateway, run in (("canonical gateway", canonical), ("hermes serve", serve)):
            try:
                answers = run(base)
            except Exception as error:  # noqa: BLE001 - reported with the gateway it came from
                found.append(f"{gateway}: {type(error).__name__}: {error}")
                continue
            shown.append(evidence(gateway, answers))
            found += problems(gateway, answers)
    print("\n".join(shown))
    if found:
        print("\n".join(found) + "\n" + FIX, file=sys.stderr)
        return 1
    print(
        f"ok: {len(requests())} untitled Build creates on each gateway: fresh sessions, no history, "
        "the picked model and provider confirmed"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The broker's side of installing and updating a game: ``BrokerWorkers`` holds the game in the broker while its
files are replaced (``hold_game`` / ``release_game``, ``backend/broker/holds.py``), so no conversation has it open or
opens it meanwhile. ``installs.update`` takes it as ``workers``; a gateway RPC passes ``BrokerWorkers()``, tests a fake.
``test_build`` builds a game installed with its source once (``backend/broker/installed.py``), which the broker
records under its hold (``install_build.record_test_build``); ``installs`` calls it after an install or update the
user allowed to build.

When no broker runs, no conversation has a game open, and there is nothing to hold.
"""

from __future__ import annotations

from pathlib import Path

from ..broker import game_hold, test_build
from ..hermes import host
from ..system import paths


class WorkersBusy(Exception):
    """The game is open in a conversation (``GAME_BUSY``) or the broker could not be asked."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class BrokerWorkers:
    def hold(self, root: Path) -> None:
        self._request(root, hold=True)

    def test_build(self, root: Path) -> dict:
        """Build a game installed with its source once, here, in the broker, which records it under its hold
        (``install_build.record_test_build``): ``{built, sha256, matches, commit, error}``. Raises ``WorkersBusy``
        while a conversation has the game open, the user has not allowed it (``BUILD_NOT_ALLOWED``), or the broker
        cannot be reached."""
        try:
            client = host.ensure_broker()
        except (host.BrokerUnavailable, OSError) as error:
            raise WorkersBusy("BROKER", f"The hermretro broker could not build the game: {error}")
        try:
            with client:
                answer = test_build(client, str(Path(root)))
        except (host.BrokerUnavailable, ValueError) as error:
            raise WorkersBusy("BROKER", f"The hermretro broker could not build the game: {error}")
        if answer.get("ok") is not True:
            denied = answer.get("denied") if isinstance(answer.get("denied"), dict) else {}
            raise WorkersBusy(
                denied.get("code") or "BROKER", denied.get("message") or answer.get("error") or "No answer."
            )
        return {key: answer.get(key) for key in ("built", "sha256", "matches", "commit", "error")}

    def release(self, root: Path) -> None:
        self._request(root, hold=False)

    def _request(self, root: Path, *, hold: bool) -> None:
        try:
            client, _ = host.try_connect(paths.runtime_dir())
        except (host.BrokerUnavailable, OSError) as error:
            raise WorkersBusy("BROKER", f"The hermretro broker could not be asked whether the game is open: {error}")
        if client is None:
            return
        try:
            with client:
                answer = game_hold(client, str(Path(root)), hold=hold)
        except (host.BrokerUnavailable, ValueError) as error:
            raise WorkersBusy("BROKER", f"The hermretro broker could not be asked whether the game is open: {error}")
        if answer.get("ok") is not True:
            denied = answer.get("denied") if isinstance(answer.get("denied"), dict) else {}
            raise WorkersBusy(
                denied.get("code") or "BROKER", denied.get("message") or answer.get("error") or "No answer."
            )


def build_installed(root: Path) -> dict:
    """``BrokerWorkers().test_build(root)``."""
    return BrokerWorkers().test_build(root)

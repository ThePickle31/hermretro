"""The broker's side of an installed game's update (backend/library/game_workers.py).

Run alone: python -m unittest tests.backend.library.test_game_workers
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.library import game_workers  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home  # noqa: E402


class Client:
    def __init__(self, answer):
        self.answer, self.requests = answer, []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def request(self, request):
        self.requests.append(request)
        return self.answer


class Workers(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)

    def test_no_broker_means_nothing_is_open(self):
        with mock.patch.object(game_workers.host, "try_connect", return_value=(None, None)):
            game_workers.BrokerWorkers().hold(self.home.base)

    def test_the_hold_is_asked_for_and_a_busy_game_refused(self):
        client = Client({"ok": True})
        with mock.patch.object(game_workers.host, "try_connect", return_value=(client, None)):
            game_workers.BrokerWorkers().hold(self.home.base)
            game_workers.BrokerWorkers().release(self.home.base)
        self.assertEqual([r["op"] for r in client.requests], ["hold_game", "release_game"])
        busy = Client({"ok": False, "denied": {"code": "GAME_BUSY", "message": "open"}})
        with (
            mock.patch.object(game_workers.host, "try_connect", return_value=(busy, None)),
            self.assertRaises(game_workers.WorkersBusy) as refused,
        ):
            game_workers.BrokerWorkers().hold(self.home.base)
        self.assertEqual((refused.exception.code, refused.exception.message), ("GAME_BUSY", "open"))


if __name__ == "__main__":
    unittest.main()

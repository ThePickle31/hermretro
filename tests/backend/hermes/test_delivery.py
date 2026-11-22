"""host._deliver and results.encode for a build the engine could not put in a fresh preview.

A tool that has already run must never read as one that did not: the delivery failures are the
contract, and the stale preview is the only proof of the agent-facing stale wording.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from backend.hermes import host as hermes_host
from backend.hermes import results


class Delivery(unittest.TestCase):
    RESPONSE = {"ok": True, "result": {"content": [], "structuredContent": {"success": True}}}

    def deliver(self):
        with (
            mock.patch.object(hermes_host, "_data_dir", return_value=Path("/nonexistent")),
            mock.patch.object(hermes_host, "_attach_images", return_value=False),
        ):
            return json.loads(hermes_host._deliver(self.RESPONSE, "chromatic_rom_build"))

    def broken(self, response, name, image_dir, attach):
        raise ValueError("broken")

    def test_a_result_whose_images_cannot_be_saved_is_still_delivered(self):
        def encode(response, name, image_dir, attach):
            if image_dir is not None:
                raise OSError(28, "No space left on device")
            return json.dumps({"success": True})

        with mock.patch.object(results, "encode", side_effect=encode):
            payload = self.deliver()
        self.assertEqual(payload["success"], True)
        self.assertIn("The tool ran", payload["deliveryProblem"])

    def test_a_call_that_never_ran_is_not_reported_as_run(self):
        with (
            mock.patch.object(hermes_host, "_data_dir", return_value=Path("/nonexistent")),
            mock.patch.object(hermes_host, "_attach_images", return_value=False),
            mock.patch.object(results, "encode", side_effect=self.broken),
        ):
            denied = json.loads(hermes_host._deliver({"denied": {"code": "X", "message": "no"}}, "t"))
        self.assertEqual(denied["dispatched"], False)

    def test_if_nothing_can_be_delivered_the_model_still_learns_the_tool_ran(self):
        with mock.patch.object(results, "encode", side_effect=self.broken):
            payload = self.deliver()
        self.assertEqual((payload["code"], payload["dispatched"]), ("RESULT_NOT_DELIVERED", True))
        self.assertIn("do not simply repeat it", payload["guidance"])


class StalePlayer(unittest.TestCase):
    def test_the_agent_is_told_when_the_player_is_out_of_date(self):
        player = {"ready": False, "error": "close acknowledgement is UNKNOWN", "stale": True}
        response = {
            "ok": True,
            "result": {"content": [], "structuredContent": {"success": True}},
            "player": player,
        }
        payload = json.loads(results.encode(response, "chromatic_rom_build", None, False))
        self.assertEqual(payload["player"]["showsThisBuild"], False)
        for phrase in (
            "could NOT be updated",
            "Do not claim the new build is in a player",
            "Install on Chromatic",
            "chromatic_web_preview_close",
            "chromatic_present_game",
        ):
            self.assertIn(phrase, payload["nextStep"])


if __name__ == "__main__":
    unittest.main()

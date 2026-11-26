"""host.make_pre_tool_call: hardware tools go through Hermes's approval prompt while hardware is on.

Run alone: python -m unittest tests.backend.hermes.test_hardware_approval
"""

import unittest

from backend.hermes import host


class _Ctx:
    def __init__(self, hardware):
        self.hardware = hardware

    def get_config(self, key, default=None):
        return self.hardware if key == "hardware_enabled" else default


def ask(tool, args, hardware=True):
    return host.make_pre_tool_call(_Ctx(hardware))(tool_name=tool, args=args)


class HardwareApproval(unittest.TestCase):
    def test_a_flash_asks_with_the_rom_and_a_key_for_that_request_only(self):
        args = {"requestId": "r1", "romPath": "/g/rom.gbc", "expectedSizeBytes": 32768, "expectedSha256": "ab"}
        answer = ask("chromatic_flash", args)
        self.assertEqual(answer["action"], "approve")
        self.assertIn("/g/rom.gbc", answer["message"])
        self.assertNotEqual(answer["rule_key"], ask("chromatic_flash", {**args, "requestId": "r2"})["rule_key"])

    def test_connecting_or_recording_the_capture_feed_asks(self):
        connect = ask(
            "chromatic_device_capture", {"action": "connect", "selection": {"videoLabel": "Chromatic - Player 01"}}
        )
        self.assertEqual(connect["action"], "approve")
        self.assertIn("Chromatic - Player 01", connect["message"])
        record = ask("chromatic_device_capture", {"action": "start_recording", "durationMs": 60_000})
        self.assertIn("60 s", record["message"])
        self.assertIn("180 s", ask("chromatic_device_capture", {"action": "start_recording"})["message"])
        self.assertNotEqual(connect["rule_key"], record["rule_key"])

    def test_reading_or_closing_the_capture_feed_does_not_ask(self):
        for action in ("open", "status", "list_devices", "live_frame", "screenshot", "stop_recording", "close", None):
            self.assertIsNone(ask("chromatic_device_capture", {"action": action}), action)

    def test_nothing_asks_while_hardware_is_off_or_for_other_tools(self):
        self.assertIsNone(ask("chromatic_device_capture", {"action": "connect"}, hardware=False))
        self.assertIsNone(ask("chromatic_flash", {}, hardware=False))
        self.assertIsNone(ask("chromatic_build", {}))


if __name__ == "__main__":
    unittest.main()

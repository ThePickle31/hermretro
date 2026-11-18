"""backend/hermes/declare.py: features declare RPCs, tools and hooks; several features' hooks on one name chain."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.features import FEATURES  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import declare  # noqa: E402 - the repository root goes on sys.path first


class Declarations(unittest.TestCase):
    def test_each_rpc_tool_and_hook_name_is_declared_once(self):
        found = declare.collect("backend", FEATURES)
        rpcs = [name for name, _factory in found.rpcs]
        tools = [tool.name for tool in found.tools]
        self.assertEqual(len(rpcs), len(set(rpcs)), "an RPC declared twice")
        self.assertEqual(len(tools), len(set(tools)), "a tool declared twice")
        self.assertEqual(
            found.hook_names(),
            ["pre_tool_call", "subagent_start", "subagent_stop", "pre_llm_call", "post_llm_call", "post_tool_call"],
        )

    def test_a_chain_calls_every_callback_and_answers_the_first_result(self):
        seen = []

        def first(tool_name=None, **_kwargs):
            seen.append(("first", tool_name))

        def second(tool_name=None):  # a narrow signature gets only what it declares
            seen.append(("second", tool_name))
            return {"action": "approve"}

        def third(**_kwargs):
            seen.append(("third",))
            return {"action": "later"}

        chained = declare.chain([first, second, third])
        self.assertEqual(chained(tool_name="x", args={}), {"action": "approve"})
        self.assertEqual(seen, [("first", "x"), ("second", "x"), ("third",)])
        self.assertEqual(chained.callbacks, (first, second, third))

    def test_the_device_cli_approval_is_chained_after_the_hardware_approvals(self):
        found = declare.collect("backend", FEATURES)
        owners = [function.__module__ for name, function, _ctx in found.hooks if name == "pre_tool_call"]
        self.assertEqual(owners, ["backend.hermes.host", "backend.setup.hooks"])


if __name__ == "__main__":
    unittest.main()

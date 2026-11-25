"""A studio chat as Hermes runs it, without Hermes or a model: the plugin's registered tools and its pre_tool_call
and post_tool_call hooks, called the way Hermes calls them, on the acceptance run's own broker, library and plugin
data folder."""

import os
from contextlib import contextmanager
from unittest import mock

from backend.features import FEATURES
from backend.hermes import declare, host
from backend.player import server as player_server
from tests.support import throwaway_profile


class Config:
    """The plugin's settings as a new studio profile has them (Hermes's ``ctx.get_config``)."""

    def get_config(self, _key, default=None):
        return default


class Studio:
    """One chat (``chat``: the ids Hermes gives every tool call and hook). ``call`` answers what the model reads,
    parsed; a call a hook blocks answers ``{"blocked": message}``."""

    def __init__(self, chat: dict):
        declared = declare.collect("backend", FEATURES)
        self.chat = chat
        self.tools = {tool.name: tool.handler_for(Config()) for tool in declared.tools}
        self.pre = declared.hook("pre_tool_call", Config())
        self.post = declared.hook("post_tool_call", Config())
        self.calls = 0

    def call(self, name: str, args: dict | None = None) -> dict:
        args = args or {}
        self.calls += 1
        call_id = f"call-{self.calls}"
        verdict = self.pre(tool_name=name, args=args, tool_call_id=call_id, **self.chat)
        if isinstance(verdict, dict) and verdict.get("action") == "block":
            return {"blocked": verdict.get("message")}
        result = self.tools[name](args, **self.chat)
        self.post(tool_name=name, args=args, result=result, status="ok", tool_call_id=call_id, **self.chat)
        return host.tool_result_payload(result) or {}

    def engine(self, name: str, args: dict | None = None) -> dict:
        """An engine tool's ``structuredContent``, with ``isError`` when the engine refused the call."""
        payload = self.call(name, args)
        return {**(payload.get("structuredContent") or {}), **({"isError": True} if payload.get("isError") else {})}


@contextmanager
def studio_chat(suite, chat: dict):
    """A ``Studio`` whose tools reach this run's broker and the library it writes (``paths.library_dir_for``: a
    test broker's state folder), and keep the plugin's data folder in the run."""
    environment = {
        "HERMRETRO_RUNTIME_DIR": str(suite.state),
        "HERMRETRO_LIBRARY_DIR": str(suite.state),
        "HERMRETRO_GAMES_DIR": str(suite.work / "games"),
    }
    with mock.patch.dict(os.environ, environment), throwaway_profile(suite.work / "studio"):
        try:
            yield Studio(chat)
        finally:
            close_player()


def close_player():
    """Stop the loopback player ``chromatic_present_game`` started in this process."""
    if player_server._server is not None:
        player_server._server.close()
        player_server._server = None

"""A studio chat as Hermes runs it, without Hermes or a model: the plugin loaded from its folder and registered
into a plugin ctx as Hermes does (``register(ctx)`` in the studio profile), and each tool call dispatched the way
Hermes dispatches it (hermes-agent ``model_tools.handle_function_call`` and ``tools/registry.py``): the
``pre_tool_call`` hook's directives, the arguments checked against the registered schema, the handler's result held
to Hermes's result contract, and the ``post_tool_call`` hook told the call's outcome. It runs on the acceptance run's
own broker and library, in an isolated home, with Hermes's scratch folder in the run."""

import functools
import importlib
import json
import os
import time
from contextlib import ExitStack, contextmanager
from unittest import mock

from backend.system import paths
from tests.backend.hermes.test_registration import load_plugin, plugin_storage
from tests.support import home_isolation

STUDIO_PROFILE = "hermretro"
# The JSON schema types each Python value parsed from JSON is.
KINDS = {
    str: {"string"},
    int: {"integer", "number"},
    float: {"number"},
    bool: {"boolean"},
    list: {"array"},
    dict: {"object"},
    type(None): {"null"},
}


class ToolFailure(Exception):
    """A call the chat cannot go on from: the tool did not run (a broker denial, an adapter error, a hook block),
    or the call broke Hermes's contract (arguments the schema refuses, an approval request, a result Hermes would
    not take). ``detail`` names the tool, the code and the error."""

    def __init__(self, tool: str, code: str | None, error):
        super().__init__(f"{tool}: {code}: {error}")
        self.detail = {"tool": tool, "code": code, "error": error}


class Stopped(Exception):
    """A chat's script ended at a step whose call did not go through (that step's check says why)."""


def step(check_id: str, title: str):
    """A named step and its check: the step function gets ``check(passed, **detail)`` in place of the suite, and a
    ``ToolFailure`` in it fails the check with what the tool answered and stops the script."""

    def wrap(function):
        @functools.wraps(function)
        def run(suite, *args):
            check = functools.partial(suite.check, check_id, title)
            try:
                return function(check, *args)
            except ToolFailure as failure:
                check(False, **failure.detail)
                raise Stopped(check_id) from failure

        return run

    return wrap


class PluginContext:
    """Hermes's plugin ctx as the studio profile gives it: the plugin's settings as a new profile has them, and what
    ``register`` hands Hermes."""

    profile_name = STUDIO_PROFILE

    def __init__(self):
        self.tools: dict[str, dict] = {}
        self.hooks: dict[str, object] = {}

    def get_config(self, _key, default=None):
        return default

    def register_tool(self, name, toolset, schema, handler, emoji=None):
        self.tools[name] = {"schema": schema, "handler": handler}

    def register_hook(self, name, handler):
        self.hooks[name] = handler

    def register_rpc(self, name, handler):
        pass

    def register_skill(self, name, path):
        pass

    def register_system_prompt_section(self, name, text, **options):
        pass


class Studio:
    """One chat (``chat``: the ids Hermes gives every tool call and hook). ``call`` answers what the model reads,
    parsed (a call a hook blocks reads ``{"error": message}``); ``outcomes`` is each call's ``(tool, status)`` as the
    post hook was told it (``ok``, ``error`` or ``blocked``)."""

    def __init__(self, plugin, chat: dict):
        self.ctx = PluginContext()
        plugin.register(self.ctx)
        self.chat = chat
        self.calls = 0
        self.outcomes: list[tuple[str, str]] = []

    def call(self, name: str, args: dict | None = None) -> dict:
        if name not in self.ctx.tools:
            raise ToolFailure(name, "UNKNOWN_TOOL", "not registered in the studio profile")
        self.calls += 1
        ids = {**self.chat, "tool_call_id": f"call-{self.calls}", "turn_id": "", "api_request_id": ""}
        args, blocked = self._pre(name, dict(args or {}), ids)
        if blocked is not None:
            result = json.dumps({"error": blocked})
            self._post(name, args, result, ids, ("blocked", "plugin_block", blocked), 0)
            return json.loads(result)
        tool = self.ctx.tools[name]
        problem = schema_problem(tool["schema"]["parameters"], args, "arguments")
        if problem:
            raise ToolFailure(name, "INVALID_ARGUMENTS", problem)
        start = time.monotonic()
        try:
            result = tool["handler"](args, **self.chat)
        except Exception as error:  # noqa: BLE001 - Hermes hands the model the error; the post hook is told it
            result = json.dumps({"error": f"Error executing {name}: {error}"})
            outcome = ("error", type(error).__name__, str(error))
        else:
            if not delivered(result):
                raise ToolFailure(name, "TOOL_RESULT_CONTRACT", f"the handler returned {type(result).__name__}")
            outcome = observed(result)
        self._post(name, args, result, ids, outcome, int((time.monotonic() - start) * 1000))
        return payload(result) or {}

    def engine(self, name: str, args: dict | None = None) -> dict:
        """An engine tool's ``structuredContent``, with ``isError`` when the engine refused the call. A call that
        never reached the engine (a broker denial, an adapter error, a block) raises ``ToolFailure``."""
        answer = self.call(name, args)
        if "structuredContent" not in answer and answer.get("error"):
            raise ToolFailure(name, answer.get("code") or self.outcomes[-1][1], answer["error"])
        return {**(answer.get("structuredContent") or {}), **({"isError": True} if answer.get("isError") else {})}

    def _pre(self, name, args, ids):
        """``(args, block message)`` as Hermes resolves the pre hook's directive: ``modify`` merges its arguments,
        ``block`` with a message stops the call. ``approve`` would ask the user, which no step may need."""
        hook = self.ctx.hooks.get("pre_tool_call")
        directive = hook(tool_name=name, args=args, middleware_trace=[], **ids) if hook else None
        if not isinstance(directive, dict):
            return args, None
        action, message = directive.get("action"), directive.get("message")
        if action == "modify" and isinstance(directive.get("args"), dict):
            return {**args, **directive["args"]}, None
        if action == "block" and isinstance(message, str) and message:
            return args, message
        if action == "approve":
            raise ToolFailure(name, "APPROVAL_REQUESTED", message)
        return args, None

    def _post(self, name, args, result, ids, outcome, duration_ms):
        status, error_type, error_message = outcome
        self.outcomes.append((name, status))
        hook = self.ctx.hooks.get("post_tool_call")
        if hook:
            hook(
                tool_name=name,
                args=args,
                result=result,
                duration_ms=duration_ms,
                status=status,
                error_type=error_type,
                error_message=error_message,
                middleware_trace=[],
                **ids,
            )


def delivered(result) -> bool:
    """Whether Hermes takes a handler's result: a string, or the multimodal envelope."""
    return isinstance(result, str) or (
        isinstance(result, dict) and result.get("_multimodal") is True and isinstance(result.get("content"), list)
    )


def payload(result) -> dict | None:
    """The result as the model reads it, parsed: the JSON text, or the multimodal envelope's text summary."""
    if isinstance(result, dict):
        result = result.get("text_summary")
    try:
        parsed = json.loads(result) if isinstance(result, str) else None
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def observed(result) -> tuple[str, str | None, str | None]:
    """``(status, error_type, error_message)`` for the post hook, as Hermes reads them off a result."""
    answer = payload(result) or {}
    error = answer.get("error")
    if error or answer.get("success") is False:
        return "error", "tool_error", str(error or answer.get("message") or "")
    return "ok", None, None


def schema_problem(schema: dict, value, where: str) -> str | None:
    """What in ``value`` the JSON schema refuses (the parts tool schemas use), or None."""
    expected = schema.get("type")
    if expected is not None:
        kinds = expected if isinstance(expected, list) else [expected]
        if not KINDS.get(type(value), set()) & set(kinds):
            return f"{where} is not {' or '.join(kinds)}"
    if "const" in schema and value != schema["const"]:
        return f"{where} is not {schema['const']!r}"
    if "enum" in schema and value not in schema["enum"]:
        return f"{where} is not one of {schema['enum']}"
    number = isinstance(value, (int, float)) and not isinstance(value, bool)
    if number and not schema.get("minimum", value) <= value <= schema.get("maximum", value):
        return f"{where} is out of range"
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        missing = [key for key in schema.get("required", []) if key not in value]
        if missing:
            return f"{where} lacks {', '.join(missing)}"
        unknown = [key for key in value if key not in properties] if schema.get("additionalProperties") is False else []
        if unknown:
            return f"{where} has {', '.join(unknown)}, not in the schema"
        for key, item in value.items():
            if key in properties and (problem := schema_problem(properties[key], item, f"{where}.{key}")):
                return problem
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            if problem := schema_problem(schema["items"], item, f"{where}[{index}]"):
                return problem
    branches = [schema_problem(branch, value, where) for branch in schema.get("anyOf", [])]
    if branches and all(branches):
        return f"{where} matches none of its forms ({branches[0]})"
    matched = [branch for branch in schema.get("oneOf", []) if not schema_problem(branch, value, where)]
    if "oneOf" in schema and len(matched) != 1:
        return f"{where} matches {len(matched)} of its exclusive forms"
    if "not" in schema and not schema_problem(schema["not"], value, where):
        return f"{where} has a form the schema excludes"
    return None


@contextmanager
def studio_chat(suite, chat: dict):
    """A ``Studio`` in an isolated home (``tests.support.home_isolation``) whose tools reach this run's broker and
    the library it writes (``paths.library_dir_for``: a test broker's state folder), with the prepared toolchain
    named by its folder, Hermes's home and scratch folder in the run, and the plugin's data folder in the run."""
    with ExitStack() as stack:
        isolated = stack.enter_context(home_isolation())
        profile = isolated.data.parents[1]
        scratch = profile / "cache" / "scratch"
        scratch.mkdir(parents=True, mode=0o700)
        environment = {
            "HERMES_HOME": str(profile),
            "HERMRETRO_DEPS_ROOT": str(paths.DEPS_ROOT),
            "HERMRETRO_RUNTIME_DIR": str(suite.state),
            "HERMRETRO_LIBRARY_DIR": str(suite.state),
            "HERMRETRO_GAMES_DIR": str(suite.work / "games"),
        }
        stack.enter_context(mock.patch.dict(os.environ, environment))
        plugin = load_plugin()  # after the environment: its copy of paths reads the toolchain folder as it loads
        stack.enter_context(plugin_storage(plugin, profile))
        api = importlib.import_module(f"{plugin.__name__}.backend.hermes.api")
        stack.enter_context(mock.patch.object(api, "scratch_dir", lambda: scratch))
        stack.callback(close_player, importlib.import_module(f"{plugin.__name__}.backend.player.server"))
        yield Studio(plugin, chat)


def close_player(server):
    """Stop the loopback player ``chromatic_present_game`` started in this process."""
    if server._server is not None:
        server._server.close()
        server._server = None

"""How a backend feature declares what it adds to Hermes. Stdlib only.

A feature declares, in its own folder (the plugin's ``__init__.register`` collects them in the order of
``backend/features.py``):

    rpcs.py    @rpc("name") on a factory ``rpc_x(ctx) -> handler``: a page RPC (``plugin.hermretro.name``)
    tools.py   TOOLS = (Tool(schema, handler, step_words=(...)), ...): plugin-owned agent tools
               (TOOLS may also be a function returning them)
    hooks.py   @hook("post_tool_call") on a callback, or @hook("pre_tool_call", needs_ctx=True) on a
               factory ``make(ctx) -> callback``: Hermes hooks
    prompt.py  skills(folder) and section(name, text, ...): skills and system-prompt sections

Declarations are recorded per declaring module, in the order they are made. Several features may hook the
same Hermes hook: it is registered once, at its first declaration's place, and calls every callback in
feature order (``chain``), answering the first result that is not None.
"""
from __future__ import annotations

import importlib
import inspect
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# Modules a feature may declare in; any other name is ignored.
PARTS = ("rpcs", "tools", "hooks", "prompt")

_declared: dict[str, list[tuple]] = {}   # declaring module -> [(kind, ...)] in declaration order


def _record(entry: tuple, depth: int = 2) -> None:
    module = sys._getframe(depth).f_globals.get("__name__", "?")
    _declared.setdefault(module, []).append(entry)


def rpc(name: str):
    """Declare a page RPC. Decorates ``rpc_x(ctx)``, which returns the handler ``(params, **kwargs)``."""
    def mark(factory: Callable):
        _record(("rpc", name, factory))
        return factory
    return mark


def hook(name: str, *, needs_ctx: bool = False):
    """Declare a Hermes hook callback (``needs_ctx``: the function is a factory given the plugin ctx)."""
    def mark(function: Callable):
        _record(("hook", name, function, needs_ctx))
        return function
    return mark


def section(name: str, text: str, **options) -> None:
    """Declare a system-prompt section (``ctx.register_system_prompt_section`` when Hermes has it)."""
    _record(("section", name, text, options))


def skills(folder: Path) -> None:
    """Declare every ``<folder>/<name>/SKILL.md`` as a skill, in name order."""
    _record(("skills", Path(folder)))


@dataclass(frozen=True)
class Tool:
    """A plugin-owned agent tool. ``handler(args, **kwargs)``, or ``make(ctx)`` returning the handler.
    ``step_words``: (while it runs, once it is done) for the Build page's step list; None hides the step
    (checked against page/pages/build/transcript/step-words.js by tests/repo/test_lockstep.py)."""
    schema: dict
    handler: Callable | None = None
    step_words: tuple[str, str] | None = None
    make: Callable | None = None
    emoji: str = "🎮"

    @property
    def name(self) -> str:
        return self.schema["name"]

    def handler_for(self, ctx) -> Callable:
        return self.make(ctx) if self.make is not None else self.handler


def chain(callbacks: list[Callable]) -> Callable:
    """One hook callback that calls each of ``callbacks`` in order with the keyword arguments it accepts
    (as Hermes does for separate callbacks) and answers the first result that is not None."""
    def call(callback, kwargs):
        try:
            parameters = inspect.signature(callback).parameters.values()
        except (TypeError, ValueError):
            return callback(**kwargs)
        if any(p.kind is p.VAR_KEYWORD for p in parameters):
            return callback(**kwargs)
        accepted = {p.name for p in parameters if p.kind in (p.KEYWORD_ONLY, p.POSITIONAL_OR_KEYWORD)}
        return callback(**{key: value for key, value in kwargs.items() if key in accepted})

    def chained(**kwargs):
        answer = None
        for callback in callbacks:
            result = call(callback, kwargs)
            if answer is None:
                answer = result
        return answer
    chained.callbacks = tuple(callbacks)
    return chained


@dataclass
class Declared:
    """Everything the features declared, in registration order."""
    rpcs: list[tuple[str, Callable]] = field(default_factory=list)
    tools: list[Tool] = field(default_factory=list)
    skills: list[tuple[str, Path]] = field(default_factory=list)
    hooks: list[tuple[str, Callable, bool]] = field(default_factory=list)
    sections: list[tuple[str, str, dict]] = field(default_factory=list)

    def hook_names(self) -> list[str]:
        return list(dict.fromkeys(name for name, _function, _needs_ctx in self.hooks))

    def hook(self, name: str, ctx=None) -> Callable:
        """The callback registered for ``name``: the one declared, or a ``chain`` of several."""
        callbacks = [function(ctx) if needs_ctx else function
                     for hook_name, function, needs_ctx in self.hooks if hook_name == name]
        if not callbacks:
            raise KeyError(name)
        return callbacks[0] if len(callbacks) == 1 else chain(callbacks)


def collect(package: str, features: list[str]) -> Declared:
    """Import each feature's declaration modules (``<package>.<feature>.<part>``) and gather what they
    declared. ``package`` is the backend package as imported (``backend`` or ``<plugin>.backend``)."""
    found = Declared()
    root = Path(importlib.import_module(package).__file__).parent
    for feature in features:
        for part in PARTS:
            if not (root / feature / f"{part}.py").is_file():
                continue
            module = importlib.import_module(f"{package}.{feature}.{part}")
            for entry in _declared.get(module.__name__, []):
                kind = entry[0]
                if kind == "rpc":
                    found.rpcs.append((entry[1], entry[2]))
                elif kind == "hook":
                    found.hooks.append(entry[1:])
                elif kind == "section":
                    found.sections.append(entry[1:])
                elif kind == "skills":
                    found.skills += [(child.name, child / "SKILL.md") for child in sorted(entry[1].iterdir())
                                     if child.is_dir() and (child / "SKILL.md").is_file()] if entry[1].is_dir() else []
            if part == "tools":
                declared = getattr(module, "TOOLS", ())
                found.tools += list(declared() if callable(declared) else declared)
    return found

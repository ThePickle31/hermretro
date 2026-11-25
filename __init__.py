"""hermretro for Hermes: plugin registration.

Registration is fast and offline. It starts no process, downloads nothing and touches no USB:
the broker and engine workers start lazily on the first tool call. In the hermretro profile it also puts this
release's SOUL in place of an unedited older one, and its compaction cap where the profile has none or an earlier
release's.

Every backend feature declares what it adds (backend/<feature>/rpcs.py, tools.py, hooks.py, prompt.py; see
backend/hermes/declare.py); this file registers them in the order of backend/features.py.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Linux and macOS only. Checked before the rest of the backend is imported (it uses POSIX-only modules), so
# Windows gets one plain sentence in `hermes plugins list` instead of an import error. backend.system.host is
# stdlib-only.
from .backend.system.host import unsupported_reason

_UNSUPPORTED = unsupported_reason()

if not _UNSUPPORTED:
    # backend.hermes first: importing it tells backend.system how to ask Hermes for its home.
    from .backend.hermes import contracts, declare, host as hermes_host
    from .backend.features import FEATURES
    from .backend.setup import studio_profile


def _profile(ctx) -> str | None:
    try:
        return ctx.profile_name
    except Exception:  # noqa: BLE001 - an older Hermes without it: the plugin's data folder names the profile
        return studio_profile.profile_name(hermes_host._data_dir().parents[1])


def register(ctx):
    if _UNSUPPORTED:
        raise RuntimeError(_UNSUPPORTED)
    declared = declare.collect(f"{__name__}.backend", FEATURES)
    # The page's RPCs answer in every profile the plugin is on: the profile it was installed into sets up
    # the hermretro profile and the shared library. Everything an agent sees (tools, skills, hooks, the
    # prompt section) exists only in the hermretro profile.
    for name, factory in declared.rpcs:
        ctx.register_rpc(name, factory(ctx))
    profile = _profile(ctx)
    if studio_profile.is_studio(profile):
        _register_agent(ctx, declared)
    if profile == studio_profile.STUDIO_PROFILE:  # never another profile, even one opted in for development
        _refresh_studio()


def _register_agent(ctx, declared):
    for tool in declared.tools:
        ctx.register_tool(
            name=tool.name,
            toolset=contracts.TOOLSET,
            schema=tool.schema,
            handler=tool.handler_for(ctx),
            emoji=tool.emoji,
        )
    for name, path in declared.skills:
        ctx.register_skill(name, path)
    # Each hook once, at its first declaration's place; several features' callbacks are chained in order.
    for name in declared.hook_names():
        ctx.register_hook(name, declared.hook(name, ctx))
    register_section = getattr(ctx, "register_system_prompt_section", None)
    if callable(register_section):
        for name, text, options in declared.sections:
            register_section(name, text, **options)


def _refresh_studio():
    """New chats read SOUL.md and the profile's config, so what an earlier release pinned there is replaced however the
    plugin was updated. It never stops registration."""
    for what, refresh in (
        ("SOUL.md", studio_profile.refresh_soul),
        ("compaction cap", studio_profile.refresh_compaction_cap),
        ("disabled toolsets", studio_profile.refresh_disabled_toolsets),
    ):
        try:
            refresh(hermes_host._data_dir().parents[1])
        except OSError:
            logger.warning("hermretro could not update the hermretro profile's %s", what, exc_info=True)
        except Exception:  # noqa: BLE001 - no Hermes storage or config to ask (an older Hermes, a test): it stays as it is
            logger.debug("hermretro could not find the hermretro profile's %s", what, exc_info=True)

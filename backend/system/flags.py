"""Feature flags: which are on. page/app/flags.js lists them and says how to add, show and ship one.

A flag is on when ``HERMRETRO_FLAGS`` in the gateway's environment names it (``name[,name]``), or when it has a
switch in Hermes's plugin settings (a ``flag_<name>`` bool in plugin.yaml's config_schema) and that switch is on.
"""

import os
import re
from collections.abc import Callable

from . import paths

ENV = "HERMRETRO_FLAGS"
SETTING_PREFIX = "flag_"


def switches(manifest: str) -> frozenset[str]:
    """The flags with a switch: each ``  flag_<name>:`` key of the manifest's config_schema. Read with a pattern
    rather than a YAML library, as paths reads the version: the broker runs on the standard library alone."""
    block = re.search(r"^config_schema:\n((?:[ \t]+.*\n|\n)*)", manifest, re.MULTILINE)
    keys = re.findall(rf"^  {SETTING_PREFIX}(\w+):", block.group(1) if block else "", re.MULTILINE)
    return frozenset(keys)


SWITCHES = switches((paths.PLUGIN_ROOT / "plugin.yaml").read_text(encoding="utf-8"))


def from_environment() -> set[str]:
    """The flags ``HERMRETRO_FLAGS`` names."""
    return {name.strip() for name in os.environ.get(ENV, "").split(",") if name.strip()}


def enabled(get_config: Callable) -> list[str]:
    """Every flag that is on, sorted. ``get_config`` is Hermes's plugin-settings getter, handed in by the caller."""
    switched = {name for name in SWITCHES if get_config(f"{SETTING_PREFIX}{name}", False)}
    return sorted(from_environment() | switched)

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
    """The flags with a switch: each ``  flag_<name>:`` key of the manifest's config_schema. Read line by line rather
    than with a YAML library, as paths reads the version (the broker runs on the standard library alone), so every
    key must be written as ``  name:``: one in any other form (quoted, say) raises instead of being skipped."""
    found = re.search(r"^config_schema:[ \t]*(?:#.*)?$", manifest, re.MULTILINE)
    names = set()
    for line in manifest[found.end() :].splitlines()[1:] if found else []:
        if line.strip() and not line[0].isspace() and not line.startswith("#"):
            break  # the next top-level key
        if not line.startswith("  ") or line.startswith("   ") or line.lstrip().startswith("#"):
            continue  # blank, a comment, or inside an entry
        key = re.fullmatch(r"  (\w+):[ \t]*(?:#.*)?", line)
        if not key:
            raise ValueError(f"plugin.yaml config_schema: {line.strip()!r} is not a plain `  name:` key")
        if key[1].startswith(SETTING_PREFIX):
            names.add(key[1].removeprefix(SETTING_PREFIX))
    return frozenset(names)


SWITCHES = switches((paths.PLUGIN_ROOT / "plugin.yaml").read_text(encoding="utf-8"))


def from_environment() -> set[str]:
    """The flags ``HERMRETRO_FLAGS`` names."""
    return {name.strip() for name in os.environ.get(ENV, "").split(",") if name.strip()}


def enabled(get_config: Callable) -> list[str]:
    """Every flag that is on, sorted. ``get_config`` is Hermes's plugin-settings getter, handed in by the caller."""
    switched = {name for name in SWITCHES if get_config(f"{SETTING_PREFIX}{name}", False)}
    return sorted(from_environment() | switched)

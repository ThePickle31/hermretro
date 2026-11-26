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


def config_schema(manifest: str) -> dict[str, dict[str, str]]:
    """plugin.yaml's config_schema as {key: {property: value as written}}. Read line by line rather than with a YAML
    library, as paths reads the version (the broker runs on the standard library alone), so it must be a block of
    ``  name:`` keys, each with ``    property: value`` lines: any other form raises instead of being misread."""
    found = re.search(r"^config_schema:(.*)$", manifest, re.MULTILINE)
    if not found:
        return {}
    if re.sub(r"#.*", "", found[1]).strip():
        raise ValueError("plugin.yaml config_schema must be a block of `  name:` keys, not written on one line")
    entries: dict[str, dict[str, str]] = {}
    entry = None
    for line in manifest[found.end() :].splitlines()[1:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue  # blank, or a comment
        if not line[0].isspace():
            break  # the next top-level key
        if re.match(r"  \S", line):
            key = re.fullmatch(r"  (\w+):[ \t]*(?:#.*)?", line)
            if not key:
                raise ValueError(f"plugin.yaml config_schema: {line.strip()!r} is not a plain `  name:` key")
            entry = entries.setdefault(key[1], {})
        elif entry is None:
            raise ValueError(f"plugin.yaml config_schema: {line.strip()!r} is not under a `  name:` key")
        elif prop := re.fullmatch(r"    (\w+):[ \t]*(.*?)[ \t]*(?:#.*)?", line):
            entry[prop[1]] = prop[2]
        # anything else is the continuation of a value (a folded description)
    return entries


def switches(manifest: str) -> frozenset[str]:
    """The flags with a switch: each ``flag_<name>`` key of the manifest's config_schema."""
    return frozenset(
        key.removeprefix(SETTING_PREFIX) for key in config_schema(manifest) if key.startswith(SETTING_PREFIX)
    )


SWITCHES = switches((paths.PLUGIN_ROOT / "plugin.yaml").read_text(encoding="utf-8"))


def from_environment() -> set[str]:
    """The flags ``HERMRETRO_FLAGS`` names."""
    return {name.strip() for name in os.environ.get(ENV, "").split(",") if name.strip()}


def enabled(get_config: Callable) -> list[str]:
    """Every flag that is on, sorted. ``get_config`` is Hermes's plugin-settings getter, handed in by the caller."""
    switched = {name for name in SWITCHES if get_config(f"{SETTING_PREFIX}{name}", False)}
    return sorted(from_environment() | switched)

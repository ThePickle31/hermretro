"""Every place hermretro reaches into Hermes itself, in one module. Stdlib only at import.

Hermes is imported inside each function, so this module loads anywhere (the broker, tests, CI without Hermes).
Some of these names are not a public plugin API yet (Hermes's validator warns about them): keeping them here
means a Hermes change breaks one file. `tools/ci/hermes_api_check.py` checks every name below: CI runs it on every
pull request against the oldest supported Hermes (`HERMES_REF` in `.github/workflows/ci.yml`) and nightly against
Hermes `main` (`nightly.yml`), before users update.
"""

from __future__ import annotations

import importlib
from pathlib import Path

# (module, attribute) for every Hermes name used below.
USED = (
    ("plugins.plugin_storage", "plugin_data_dir"),
    ("tools.vision_tools", "_should_use_native_vision_fast_path"),  # private: no public helper yet
    ("hermes_constants", "get_default_hermes_root"),
    ("hermes_cli.profiles", "get_profile_dir"),  # not in the plugin API yet
    ("hermes_cli.config", "load_config_readonly"),
    ("hermes_cli.config", "require_readable_config_before_write"),
    ("hermes_cli.default_soul", "DEFAULT_SOUL_MD"),
)


def missing() -> list[str]:
    """The names above that this Hermes does not have (empty when everything is there)."""
    gone = []
    for module, attribute in USED:
        try:
            if not hasattr(importlib.import_module(module), attribute):
                gone.append(f"{module}.{attribute}")
        except Exception:  # noqa: BLE001 - a module that fails to import is as good as missing
            gone.append(f"{module}.{attribute}")
    return gone


def plugin_data_dir(plugin_id: str) -> Path:
    """This profile's private data folder for the plugin."""
    from plugins.plugin_storage import plugin_data_dir as data_dir

    return Path(data_dir(plugin_id))


def tool_results_take_images() -> bool:
    """Whether the active model route takes images inside tool results. Any failure means no."""
    try:
        from tools.vision_tools import _should_use_native_vision_fast_path

        return bool(_should_use_native_vision_fast_path())
    except Exception:  # noqa: BLE001 - any failure means the route takes no images
        return False


def default_hermes_root() -> Path | None:
    """The Hermes home that holds every profile, or None when Hermes cannot be imported here."""
    try:
        from hermes_constants import get_default_hermes_root

        return Path(get_default_hermes_root())
    except Exception:  # noqa: BLE001 - no Hermes here: tests, CI, the broker's own process
        return None


def profile_dir(name: str) -> Path:
    from hermes_cli.profiles import get_profile_dir

    return Path(get_profile_dir(name))


def enabled_plugins() -> list[str]:
    """The plugins this profile's config turns on (read-only; empty when it cannot be read)."""
    try:
        from hermes_cli.config import load_config_readonly

        enabled = ((load_config_readonly() or {}).get("plugins") or {}).get("enabled") or []
        return [str(name) for name in enabled]
    except Exception:  # noqa: BLE001 - an unreadable config means no plugins are on
        return []


def profile_config(profile_home: Path) -> dict:
    """Read the settings explicitly written in a profile, raising on unreadable or malformed config."""
    from hermes_cli.config import require_readable_config_before_write

    return require_readable_config_before_write(profile_home / "config.yaml")


def default_soul() -> bytes:
    """The SOUL Hermes seeds when it creates a profile."""
    from hermes_cli.default_soul import DEFAULT_SOUL_MD

    return DEFAULT_SOUL_MD.encode("utf-8")

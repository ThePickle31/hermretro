"""Every place hermretro reaches into Hermes itself, in one module. Stdlib only at import.

Hermes is imported inside each function, so this module loads anywhere (the broker, tests, CI without Hermes).
Some of these names are not a public plugin API yet (Hermes's validator warns about them): keeping them here
means a Hermes change breaks one file. `tools/ci/hermes_api_check.py` checks every name below: CI runs it on every
pull request against the oldest supported Hermes (`HERMES_REF` in `.github/workflows/ci.yml`) and nightly against
Hermes `main` (`nightly.yml`), before users update.
"""

from __future__ import annotations

import contextlib
import importlib
from pathlib import Path

# (module, attribute) for every Hermes name used below.
USED = (
    ("plugins.plugin_storage", "plugin_data_dir"),
    ("tools.vision_tools", "_should_use_native_vision_fast_path"),  # private: no public helper yet
    ("hermes_constants", "get_default_hermes_root"),
    ("hermes_cli.profiles", "get_profile_dir"),  # not in the plugin API yet
    ("hermes_cli.config", "load_config_readonly"),
    ("hermes_cli.default_soul", "DEFAULT_SOUL_MD"),
    ("hermes_cli.profiles", "_bootstrap_profile_dir"),
    ("hermes_cli.profiles", "seed_profile_skills"),
    ("hermes_cli.profiles_initialization", "finish_profile_layout"),
    ("hermes_cli.config_backend", "supports_file_tooling"),
    ("hermes_constants", "named_profile_has_identity"),
    ("hermes_constants", "named_profile_is_deleted"),
    ("hermes_constants", "profile_tombstone_path"),
    ("hermes_cli.gateway_multiplex_served", "notify_multiplexer_profiles_changed"),
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


def prepare_profile(staging: Path, *, description: str, soul: str) -> None:
    """Build a private profile with the same model and sign-in setup as Hermes's profiles.create."""
    from hermes_cli.config_backend import supports_file_tooling
    from hermes_cli.profiles import _bootstrap_profile_dir, seed_profile_skills
    from hermes_cli.profiles_initialization import finish_profile_layout

    if not supports_file_tooling():
        raise ValueError("Creating the studio profile requires Hermes's local file configuration backend.")
    _bootstrap_profile_dir(staging, None)
    finish_profile_layout(staging, no_skills=True, clone_all=False, description=description, soul=soul)
    seed_profile_skills(staging, quiet=True)

    try:
        from hermes_cli.profile_provision import inherit_launch_model, mirror_launch_credentials
    except ModuleNotFoundError as error:
        if error.name != "hermes_cli.profile_provision":
            raise
        # The older split module's functions only work once bound to the gateway's globals.
        from tui_gateway.server import _inherit_launch_model as inherit_launch_model
        from tui_gateway.server import _mirror_launch_credentials

        _mirror_launch_credentials(staging, {"share_auth": True})
    else:
        mirror_launch_credentials(staging, {}, share_auth=True)
    # Hermes treats a model it cannot inherit as an optional part of creating the profile.
    with contextlib.suppress(Exception):
        inherit_launch_model(staging)


def default_soul() -> bytes | None:
    """The template Hermes CLI commands seed on first use of a home."""
    try:
        from hermes_cli.default_soul import DEFAULT_SOUL_MD
    except ImportError:
        return None
    return DEFAULT_SOUL_MD.encode("utf-8")


def profile_has_identity(profile_home: Path) -> bool:
    try:
        from hermes_constants import named_profile_has_identity
    except ImportError:
        # Older Hermes and callers outside the host use the same identity checks.
        markers = ("config.yaml", ".env", "SOUL.md", "profile.yaml", "auth.json", "state.db")
        return any((profile_home / name).is_file() or (profile_home / name).is_symlink() for name in markers)
    return named_profile_has_identity(profile_home)


def profile_is_deleted(profile_home: Path) -> bool:
    try:
        from hermes_constants import named_profile_is_deleted
    except ImportError:
        return profile_tombstone(profile_home).exists()
    return named_profile_is_deleted(profile_home)


def profile_tombstone(profile_home: Path) -> Path:
    try:
        from hermes_constants import profile_tombstone_path
    except ImportError:
        return profile_home.parent / ".deleted" / profile_home.name
    return profile_tombstone_path(profile_home)


def notify_profile_created(profile_home: Path) -> None:
    from hermes_cli.gateway_multiplex_served import notify_multiplexer_profiles_changed

    notify_multiplexer_profiles_changed(profile_home.name)

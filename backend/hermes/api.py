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
    ("hermes_constants", "get_scratch_dir"),
    ("hermes_cli.profiles", "get_profile_dir"),  # not in the plugin API yet
    ("hermes_cli.config", "load_config_readonly"),
    ("hermes_cli.config", "read_user_config_raw"),
    ("hermes_cli.auth", "PROVIDER_REGISTRY"),
    ("agent.secret_scope", "load_env_file"),
    # Private: Hermes's .env writer for an explicit path. Its public save_env_value also changes os.environ, which here
    # would be the installing profile's process.
    ("hermes_cli.config", "_env_write_lock"),
    ("hermes_cli.config", "_read_env_lines"),
    ("hermes_cli.config", "_write_env_lines"),
    ("hermes_cli.config", "_quote_env_value"),
    ("hermes_cli.config", "_env_line_defines_key"),
    ("hermes_cli.config", "validate_env_var_name_for_write"),
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


def scratch_dir() -> Path | None:
    """This profile's scratch folder, ``<Hermes home>/cache/scratch`` (also the ``TMPDIR`` Hermes gives the agent's
    commands), or None when Hermes cannot be imported here."""
    try:
        from hermes_constants import get_scratch_dir

        return Path(get_scratch_dir(prune=False))
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


def read_profile_config(profile_home: Path) -> dict:
    """A profile's config.yaml exactly as written: no defaults filled in (empty when it has none)."""
    from hermes_cli.config import read_user_config_raw

    return read_user_config_raw(profile_home / "config.yaml")


def read_profile_env(profile_home: Path) -> dict[str, str]:
    """A profile's .env as Hermes reads it (empty when it has none). Never touches ``os.environ``."""
    from agent.secret_scope import load_env_file

    return dict(load_env_file(profile_home / ".env"))


def set_profile_env(profile_home: Path, name: str, value: str | None) -> None:
    """Set (or with None remove) one name in a profile's .env, as Hermes writes it, without touching ``os.environ``."""
    from hermes_cli.config import (
        _env_line_defines_key,
        _env_write_lock,
        _quote_env_value,
        _read_env_lines,
        _write_env_lines,
        validate_env_var_name_for_write,
    )

    validate_env_var_name_for_write(name)
    path = profile_home / ".env"
    with _env_write_lock(path):
        existed = path.exists()
        lines = [line for line in (_read_env_lines(path) if existed else []) if not _env_line_defines_key(line, name)]
        if value is not None:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            single_line = value.replace("\n", "").replace("\r", "")
            lines.append(f"{name}={_quote_env_value(single_line)}\n")
        _write_env_lines(path, lines, preserve_mode=existed)


def provider_env_keys() -> set[str]:
    """The .env names Hermes's model providers read their API key and endpoint from (``OPENROUTER_API_KEY``...).
    Messaging bot tokens are not among them."""
    from hermes_cli.auth import PROVIDER_REGISTRY

    names = {"OPENROUTER_API_KEY"}  # OpenRouter, Hermes's built-in default route, is not in the registry
    for provider in PROVIDER_REGISTRY.values():
        names.update(name for name in getattr(provider, "api_key_env_vars", ()) or () if name)
        if base_url := getattr(provider, "base_url_env_var", None):
            names.add(base_url)
    return names


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

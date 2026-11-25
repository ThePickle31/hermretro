"""Keeps the studio profile on the model providers of the profile hermretro was installed into.

Hermes copies the installing profile's .env and model once, when setup makes the studio profile, and shares its
logins (auth.json). This adds what that leaves out and keeps it current: the provider routes (main model, providers,
fallbacks, subagents, auxiliary tasks), the provider plugins' settings, the providers' keys in .env, and the Claude
login DirectSDK needs (claude_login.py).

A value is copied when the studio profile does not have it yet, or still has the one last copied there: a value
changed in the studio profile itself is the user's and stays. Nothing is ever removed. The record of what was copied
holds hashes only, never the values. Only Hermes config commands write the studio's config and .env.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from collections.abc import Callable
from pathlib import Path

from ..hermes import api as hermes_api
from ..system import paths
from . import claude_login

RECORD = Path("plugin-data") / paths.PLUGIN_ID / "provider-sync.json"
# Whole sections that only choose providers and models.
SECTIONS = ("model", "providers", "custom_providers", "fallback_providers", "delegation")
# Per auxiliary task (vision, compression...), only its route: its other settings are the profile's own.
AUXILIARY_ROUTE = ("provider", "model", "base_url", "api_mode")
_MISSING = object()
# A key a copied provider entry reads from .env: ``api_key: ${MY_PROVIDER_KEY}``.
_ENV_REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

# One sync at a time in this process; finish() holds it too while it configures the profile.
lock = threading.Lock()


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _get(tree: dict, path: tuple[str, ...]):
    for part in path:
        if not isinstance(tree, dict) or part not in tree:
            return _MISSING
        tree = tree[part]
    return tree


def _leaves(value, path: tuple[str, ...]):
    """Every leaf under ``path``: a mapping is written key by key (`hermes config set` redirects a bare ``model`` and
    refuses a scalar over a mapping), lists and scalars whole. ``provider`` comes first in its mapping, so a route
    switch is applied before the fields that belong to the new route."""
    if isinstance(value, dict) and value:
        for key in sorted(value, key=lambda name: (name != "provider", str(name))):
            yield from _leaves(value[key], (*path, str(key)))
    elif value is not None and value != {}:
        yield path, value


def _config_leaves(source: dict, plugins: list[str]):
    for section in SECTIONS:
        if (value := source.get(section)) is not None:
            yield from _leaves(value, (section,))
    for task, route in (source.get("auxiliary") or {}).items():
        if isinstance(route, dict):
            for field in AUXILIARY_ROUTE:
                if field in route:
                    yield from _leaves(route[field], ("auxiliary", str(task), field))
    entries = (source.get("plugins") or {}).get("entries") or {}
    for name in plugins:
        settings = (entries.get(name) or {}).get("settings") or {}
        for key, value in settings.items():
            # The Claude login is the studio's own (claude_login.plan): another profile's folder is never copied as is.
            if (name, key) != (claude_login.PLUGIN, "claude_config_dir"):
                yield from _leaves(value, ("plugins", "entries", name, "settings", str(key)))


def _text(value) -> str:
    return value if isinstance(value, str) else json.dumps(value)


def _read_record(studio: Path) -> dict:
    try:
        record = json.loads((studio / RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return record if isinstance(record, dict) else {}


def _write_record(studio: Path, record: dict) -> None:
    target = studio / RECORD
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}")
    temporary.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
    os.replace(temporary, target)


def stamp(source: Path) -> list:
    """Changes when the installing profile's config or .env does, so a sync with nothing new to copy is skipped."""
    marks = []
    for name in ("config.yaml", ".env"):
        try:
            found = (source / name).stat()
            marks.append([name, found.st_mtime_ns, found.st_size])
        except OSError:
            marks.append([name, None, None])
    return marks


def sync(
    source: Path,
    studio: Path,
    run: Callable[..., None],
    *,
    plugins: list[str],
    environ=os.environ,
    login_options: dict | None = None,
) -> dict:
    """Bring the studio profile in line with ``source``. ``run(*arguments)`` runs one Hermes command in the studio
    profile; ``plugins`` are the provider plugins both profiles have on. Answers the names it copied and kept (never a
    value) and the Claude login's state."""
    read_config, read_env = hermes_api.read_profile_config, hermes_api.read_profile_env
    source_config, studio_config = read_config(source), read_config(studio)
    source_env, studio_env = read_env(source), read_env(studio)
    record = _read_record(studio)
    copied = dict(record.get("copied") or {})
    changed, kept = [], []

    def offer(key: str, wanted, current):
        digest = _digest(wanted)
        if current is not _MISSING and _digest(current) == digest:
            copied[key] = digest
            return
        if current is not _MISSING and copied.get(key) != _digest(current):
            kept.append(key)  # changed in the studio profile: the user's
            return
        run("config", "set", key, _text(wanted))
        copied[key] = digest
        changed.append(key)

    keys = set(hermes_api.provider_env_keys())
    for path, value in _config_leaves(source_config, plugins):
        offer(".".join(path), value, _get(studio_config, path))
        keys.update(_ENV_REFERENCE.findall(json.dumps(value)))
    if claude_login.PLUGIN in plugins:
        keys.add(claude_login.TOKEN)
    for name in sorted(keys):
        if value := (source_env.get(name) or "").strip():
            offer(name, value, studio_env[name] if (studio_env.get(name) or "").strip() else _MISSING)

    login = None
    if claude_login.PLUGIN in plugins:
        studio_env = read_env(studio) if any(key == claude_login.TOKEN for key in changed) else studio_env
        decision = claude_login.plan(source_config, studio_config, studio_env, environ, **(login_options or {}))
        if "set" in decision:
            run("config", "set", claude_login.SETTING, decision["set"])
            changed.append(claude_login.SETTING)
            studio_config = read_config(studio)
        login = claude_login.status(studio_config, studio_env, **(login_options or {}))

    _write_record(studio, {"copied": copied, "stamp": stamp(source)})
    return {"changed": changed, "kept": sorted(kept), "claude_login": login}


def is_current(source: Path, studio: Path) -> bool:
    """Whether nothing changed in the installing profile since the last sync."""
    return _read_record(studio).get("stamp") == stamp(source)

"""Keeps the studio profile on the model providers of the profile hermretro was installed into.

Hermes copies the installing profile's .env and model once, when setup makes the studio profile, and shares its
logins (auth.json). This adds what that leaves out and keeps it current: the provider routes (main model, providers,
fallbacks, the subagent and auxiliary routes), the provider plugins' settings, the providers' keys in .env, and the
Claude login DirectSDK needs (claude_login.py).

Each unit (a whole section, or one route's fields) is copied as a whole, so a route never mixes the two profiles'
providers. A unit is the sync's while the studio profile still has exactly what the sync last left there (or nothing):
then it follows the installing profile, including a removal. Once changed in the studio profile itself it is the
user's and stays. The record holds hashes only, written after every unit, so an interrupted sync resumes where it
stopped. Config goes through Hermes config commands; .env through Hermes's own .env writer (hermes_api.set_profile_env),
so a key never appears on a command line.
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
# Sections copied whole: they only choose providers and models.
SECTIONS = ("model", "providers", "custom_providers", "fallback_providers")
# A route inside a section with other settings (delegation's iteration limit, an auxiliary task's timeout): only these
# fields are the route.
ROUTE = ("provider", "model", "base_url", "api_mode", "api_key", "key_env", "api_key_env")
DELEGATION_ROUTE = (*ROUTE, "reasoning_effort")
# A key a copied entry reads from .env: ``api_key: ${MY_KEY}`` or ``key_env: MY_KEY``.
_ENV_REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_ENV_NAME_FIELDS = ("key_env", "api_key_env")
_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# One sync at a time in this process; finish() holds it too while it configures the profile.
lock = threading.Lock()


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _route(section, fields) -> dict | None:
    if not isinstance(section, dict):
        return None
    route = {field: section[field] for field in fields if section.get(field) not in (None, "")}
    return route or None


def _units(config: dict, plugins: list[str]) -> dict[str, dict]:
    """``{unit name: {"kind", "path", "value"}}``: what a profile's config holds of each provider unit."""
    units = {}
    for section in SECTIONS:
        units[section] = {"kind": "section", "path": section, "value": config.get(section) or None}
    delegation = _route(config.get("delegation"), DELEGATION_ROUTE)
    units["delegation"] = {"kind": "route", "path": "delegation", "value": delegation}
    for task, settings in (config.get("auxiliary") or {}).items():
        units[f"auxiliary.{task}"] = {"kind": "route", "path": f"auxiliary.{task}", "value": _route(settings, ROUTE)}
    entries = (config.get("plugins") or {}).get("entries") or {}
    for name in plugins:
        for key, value in ((entries.get(name) or {}).get("settings") or {}).items():
            # The Claude login is decided on its own (claude_login.inherited_dir); a dotted name cannot be addressed.
            if (name, key) != (claude_login.PLUGIN, "claude_config_dir") and "." not in str(key):
                path = f"plugins.entries.{name}.settings.{key}"
                units[path] = {"kind": "section", "path": path, "value": value}
    return units


def _env_names(value) -> set[str]:
    """Every .env name a copied unit reads its key from."""
    names = set(_ENV_REFERENCE.findall(json.dumps(value)))

    def walk(item):
        if isinstance(item, dict):
            for key, inner in item.items():
                if key in _ENV_NAME_FIELDS and isinstance(inner, str) and _ENV_NAME.fullmatch(inner):
                    names.add(inner)
                walk(inner)
        elif isinstance(item, list):
            for inner in item:
                walk(inner)

    walk(value)
    return names


def _text(value) -> str:
    return value if isinstance(value, str) else json.dumps(value)


def _write_unit(run, unit: dict, wanted, current) -> None:
    path = unit["path"]
    if unit["kind"] == "section":
        if wanted is None:
            run("config", "unset", path)
        else:
            # `hermes config set model <mapping>` needs --force to replace the section; the rest take a mapping as is.
            run("config", "set", *(["--force"] if path == "model" else []), path, _text(wanted))
        return
    wanted, current = wanted or {}, current or {}
    for field in sorted(wanted, key=lambda name: name != "provider"):  # a route's provider first
        if wanted[field] != current.get(field):
            run("config", "set", f"{path}.{field}", _text(wanted[field]))
    for field in current:
        if field not in wanted:
            run("config", "unset", f"{path}.{field}")


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


def is_current(source: Path, studio: Path) -> bool:
    """Whether nothing changed in the installing profile since the last sync."""
    return _read_record(studio).get("stamp") == stamp(source)


class _Sync:
    """One sync: what the studio profile holds of each unit the sync owns, kept on disk after every write."""

    def __init__(self, studio: Path):
        self.studio = studio
        self.owned = dict(_read_record(studio).get("owned") or {})
        self.changed, self.kept = [], []

    def offer(self, name: str, wanted, current, write: Callable, reread: Callable) -> None:
        """Make the studio's ``current`` the installing profile's ``wanted`` while the unit is the sync's.
        ``reread()`` answers what the studio holds afterwards: Hermes may adjust a value as it writes it."""
        mine = self.owned.get(name)
        if mine is not None and mine != _digest(current):
            self.kept.append(name)  # changed in the studio profile itself: the user's
            return
        if wanted == current:
            if wanted is not None and mine is None:
                self._own(name, current)  # already the same: the sync's from now on
            return
        if mine is None and current is not None:
            self.kept.append(name)  # there before the sync, and different: the user's
            return
        write(wanted, current)
        self._own(name, reread())
        self.changed.append(name)

    def _own(self, name: str, value) -> None:
        self.owned[name] = _digest(value)
        _write_record(self.studio, {**_read_record(self.studio), "owned": self.owned})


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
    profile; ``plugins`` are the provider plugins both profiles have on. Answers the unit names it changed and kept
    (never a value) and the Claude login's state."""
    marks = stamp(source)  # before reading, so a change made meanwhile is synced next time
    read_config, read_env = hermes_api.read_profile_config, hermes_api.read_profile_env
    source_config, source_env = read_config(source), read_env(source)
    state = _Sync(studio)

    source_units, studio_units = _units(source_config, plugins), _units(read_config(studio), plugins)
    keys = set(hermes_api.provider_env_keys())
    if claude_login.PLUGIN in plugins:
        keys.add(claude_login.TOKEN)
    for name in sorted({*source_units, *studio_units}):
        unit = source_units.get(name) or studio_units[name]
        wanted = (source_units.get(name) or {}).get("value")
        keys |= _env_names(wanted)
        state.offer(
            name,
            wanted,
            (studio_units.get(name) or {}).get("value"),
            lambda value, current, unit=unit: _write_unit(run, unit, value, current),
            lambda name=name: _units(read_config(studio), plugins).get(name, {}).get("value"),
        )

    studio_env = read_env(studio)
    for name in sorted(keys):
        state.offer(
            f"env:{name}",
            (source_env.get(name) or "").strip() or None,
            (studio_env.get(name) or "").strip() or None,
            lambda value, _current, name=name: hermes_api.set_profile_env(studio, name, value),
            lambda name=name: (read_env(studio).get(name) or "").strip() or None,
        )

    login = None
    if claude_login.PLUGIN in plugins:
        options = login_options or {}
        if not (read_env(studio).get(claude_login.TOKEN) or "").strip():
            state.offer(
                "claude_config_dir",
                claude_login.inherited_dir(source_config, environ, macos=options.get("macos")),
                claude_login.setting(read_config(studio)) or None,
                lambda value, _current: run(
                    *(
                        ("config", "set", claude_login.SETTING, value)
                        if value
                        else ("config", "unset", claude_login.SETTING)
                    )
                ),
                lambda: claude_login.setting(read_config(studio)) or None,
            )
        login = claude_login.status(read_config(studio), read_env(studio), check=options.get("check"))

    _write_record(studio, {"owned": state.owned, "stamp": marks})
    return {"changed": state.changed, "kept": sorted(state.kept), "claude_login": login}

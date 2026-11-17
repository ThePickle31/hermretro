"""Locations and environment discovery. Stdlib only; Hermes is consulted only if it can be imported."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from functools import lru_cache
from pathlib import Path

PLUGIN_ID = "hermretro"
ENGINE_VERSION = "1.0.34"
NODE_REQUIRED_MAJOR = 22
PROTOCOL = 2

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


# `version: X.Y.Z`, optionally quoted, optionally followed by a comment.
VERSION_LINE = r"^version:[ \t]*[\"']?([0-9]+\.[0-9]+\.[0-9]+)[\"']?[ \t]*(?:#.*)?\r?$"


def _manifest_version(manifest: Path) -> str:
    """The plugin's version, from ``plugin.yaml`` (its only home; a release changes it there and nowhere else).
    Read with a pattern rather than a YAML library: the broker runs on the standard library alone."""
    match = re.search(VERSION_LINE, manifest.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise RuntimeError(f"{manifest} has no x.y.z version line")
    return match.group(1)


PLUGIN_VERSION = _manifest_version(PLUGIN_ROOT / "plugin.yaml")
ENGINE_ROOT = PLUGIN_ROOT / "engine" / "modretro-chromatic"
# What this plugin pinned for the engine version it ships: its tool contracts and the hash of every engine file.
ENGINE_PINS = PLUGIN_ROOT / "engine" / "pins" / ENGINE_VERSION
PINNED_TOOLS = ENGINE_PINS / "tools.json"
ENGINE_MANIFEST = ENGINE_PINS / "manifest.json"

# Unix socket paths are capped at 104 bytes on macOS (108 on Linux); stay clear of both.
SOCKET_PATH_LIMIT = 100


def _hermes_root() -> Path:
    """The Hermes home that holds every profile (``~/.hermes`` by default), even when this process runs
    in a profile. Asks Hermes when it can be imported. The fallback (tests, CI, tools run outside Hermes)
    covers the plain cases only; the broker never relies on it, because the client hands it
    ``HERMRETRO_HOME``."""
    from . import hermes_api
    asked = hermes_api.default_hermes_root()
    if asked is not None:
        return asked
    configured = os.environ.get("HERMES_HOME", "").strip()
    if not configured:
        return Path.home() / ".hermes"
    home = Path(configured).expanduser()
    return home.parents[1] if home.parent.name == "profiles" else home


def hermretro_home() -> Path:
    """The one folder holding everything hermretro keeps per user, shared by every profile:
    ``<Hermes home>/hermretro`` with ``games/``, ``library/``, ``.cache/`` (toolchain and prepared engine,
    re-downloadable) and ``run/`` (the broker). Removing or updating the plugin leaves it in place.
    ``HERMRETRO_HOME`` overrides it; the client passes it on to the broker, whose environment is minimal."""
    override = os.environ.get("HERMRETRO_HOME", "").strip()
    # Absolute, so the gateway and the broker (which runs from the plugin folder) agree on a relative value.
    return Path(override).expanduser().absolute() if override else _hermes_root() / PLUGIN_ID


# Downloaded per user, under the hermretro home, so plugin updates and removal never touch it.
DEPS_ROOT = Path(os.environ.get("HERMRETRO_DEPS_ROOT") or hermretro_home() / ".cache").resolve()
# Named by engine version: two plugin copies (an installed one and a dev checkout) share this folder.
PREPARED_ENGINE = DEPS_ROOT / f"engine-{ENGINE_VERSION}"   # bundled engine + ModRetro's CLI for this computer
DEVICE_CLI_RECEIPT = DEPS_ROOT / f"device-cli-{ENGINE_VERSION}.json"
# ModRetro's proprietary CLI, packed for all platforms. A distributable build of the plugin leaves
# these two out; setup then fetches the CLI for one platform from ModRetro (see provision.py).
VENDOR_ARCHIVES = ("third-party/chromatic-cli/executables-v2.br", "third-party/chromatic-cli/notices.br")
# The engine's ffmpeg builds for capturing a real Chromatic's video on Linux (LGPL, built from a patched
# source that is not public, so this plugin does not ship them). Without them Linux device capture
# says it is unavailable; everything else, and capture on macOS, is unaffected.
CAPTURE_FFMPEG = ("native/capture/linux/x64/ffmpeg", "native/capture/linux/arm64/ffmpeg")


def default_runtime_dir() -> Path:
    """Where ``runtime_dir`` lives, without creating it: ``<hermretro home>/run``. When that would make the
    socket path too long for the system (a deep home folder), a short per-user folder under ``/tmp``.
    Never ``TMPDIR``: processes see different values of it and would elect two brokers."""
    override = os.environ.get("HERMRETRO_RUNTIME_DIR")
    if override:
        return Path(override)
    folder = hermretro_home() / "run"
    if len(os.fsencode(folder / "broker.sock")) <= SOCKET_PATH_LIMIT:
        return folder
    return Path("/tmp") / f"hermretro-{os.getuid()}"


def runtime_dir() -> Path:
    """User-only directory for the broker socket, token, lock and trace. Refuses a folder that is a link
    or belongs to another user (the short fallback lives in the shared ``/tmp``)."""
    base = default_runtime_dir()
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = base.lstat()
    if stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid():
        raise PermissionError(f"{base} is a link or belongs to another user (uid {info.st_uid}), so hermretro "
                              "will not use it; set HERMRETRO_RUNTIME_DIR to a private folder of your own")
    os.chmod(base, 0o700)
    return base


def library_dir() -> Path:
    """The game library (``games.json``, ``thumbs/``): ``<hermretro home>/library``."""
    override = os.environ.get("HERMRETRO_LIBRARY_DIR")
    return Path(override) if override else hermretro_home() / "library"


def library_dir_for(state_dir: Path) -> Path:
    """The library a broker writes: the per-user one for the real broker, and the broker's own state
    directory for any other (tests, acceptance runs), so scratch projects never reach the user's shelf."""
    try:
        same = Path(state_dir).resolve() == default_runtime_dir().resolve()
    except OSError:
        same = False
    return library_dir() if same else Path(state_dir)


def games_dir(create: bool = False) -> Path:
    """Where new games are made: ``<hermretro home>/games``. ``HERMRETRO_GAMES_DIR`` overrides it.
    Created on demand, because the engine only creates a project under an existing parent."""
    override = os.environ.get("HERMRETRO_GAMES_DIR")
    folder = Path(override).expanduser() if override else hermretro_home() / "games"
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    return folder


def setup_root() -> Path:
    """Where the engine's own setup keeps compilers and emulators: ``<hermretro home>/.cache/toolchain``."""
    override = os.environ.get("GB_STUDIO_SETUP_ROOT")
    return Path(override) if override else DEPS_ROOT / "toolchain"


def _node_version(path: str) -> tuple[int, ...] | None:
    try:
        out = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", out)
    return tuple(int(part) for part in match.groups()) if match else None


@lru_cache(maxsize=1)
def find_node() -> dict:
    """Find a usable Node.js. Desktop-launched apps often lack the shell's PATH, so also
    look in the engine's managed setup root and common per-user locations."""
    candidates: list[str] = []
    override = os.environ.get("HERMRETRO_NODE")
    if override:
        candidates.append(override)
    on_path = shutil.which("node")
    if on_path:
        candidates.append(on_path)
    managed = setup_root() / "node"
    if managed.is_dir():
        candidates.extend(str(p) for p in sorted(managed.glob("**/bin/node"), reverse=True))
    home = Path.home()
    # The Node.js Hermes installs for itself (~/.hermes/tools/node-<version>-<platform>/bin/node).
    candidates.extend(str(p) for p in sorted((home / ".hermes" / "tools").glob("node-*/bin/node"), reverse=True))
    # Apple Silicon Homebrew before /usr/local, where an Intel (Rosetta) Homebrew keeps its Node on the same Mac.
    candidates.extend(str(p) for p in (home / ".local/bin/node", Path("/opt/homebrew/bin/node"),
                                       Path("/usr/local/bin/node"), Path("/usr/bin/node")))
    candidates.extend(str(p) for p in sorted((home / ".nvm/versions/node").glob("*/bin/node"), reverse=True))
    best: dict | None = None
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen or not os.path.isfile(candidate) or not os.access(candidate, os.X_OK):
            continue
        seen.add(candidate)
        version = _node_version(candidate)
        if version is None:
            continue
        found = {"found": True, "path": candidate, "version": ".".join(map(str, version)),
                 "required": str(NODE_REQUIRED_MAJOR), "ok": version[0] >= NODE_REQUIRED_MAJOR}
        if found["ok"]:
            return found
        best = best or found
    return best or {"found": False, "path": None, "version": None, "required": str(NODE_REQUIRED_MAJOR), "ok": False}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _compare_tree(root: Path, expected: dict[str, str], optional: frozenset[str] = frozenset()) -> list[str]:
    """Every regular file under root against rel -> SHA-256. No extras, no symlinks."""
    problems: list[str] = []
    seen: set[str] = set()
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        rel = path.relative_to(root).as_posix()
        if "__pycache__" in rel:
            continue
        if stat.S_ISLNK(info.st_mode):
            problems.append(f"unexpected symlink {rel}")
        elif stat.S_ISREG(info.st_mode):
            seen.add(rel)
            if rel not in expected:
                problems.append(f"unexpected file {rel}")
            elif _file_sha256(path) != expected[rel]:
                problems.append(f"changed {rel}")
    problems.extend(f"missing {rel}" for rel in sorted(set(expected) - seen - optional))
    return problems


def _detail(problems: list[str]) -> str:
    return "; ".join(problems[:5]) + (f" (+{len(problems) - 5} more)" if len(problems) > 5 else "")


def _recorded() -> dict[str, str]:
    return {e["path"]: e["sha256"] for e in json.loads(ENGINE_MANIFEST.read_text())["entries"]}


@lru_cache(maxsize=1)
def verify_engine() -> dict:
    """Compare the bundled engine with its recorded manifest (every file, SHA-256).

    The two packed vendor archives and the Linux capture ffmpeg builds may be absent: that is the
    distributable form."""
    if not (ENGINE_ROOT / "scripts" / "start-mcp.mjs").is_file():
        return {"present": False, "version": None, "verified": False, "detail": "Bundled engine is missing."}
    try:
        problems = _compare_tree(ENGINE_ROOT, _recorded(), optional=frozenset(VENDOR_ARCHIVES + CAPTURE_FFMPEG))
        version = json.loads((ENGINE_ROOT / "package.json").read_text()).get("version")
        return {"present": True, "version": version, "verified": not problems, "detail": _detail(problems),
                "vendor_archives_bundled": all((ENGINE_ROOT / rel).is_file() for rel in VENDOR_ARCHIVES)}
    except (OSError, ValueError, KeyError) as error:
        return {"present": True, "version": None, "verified": False, "detail": f"Could not verify: {error}"}


def verify_prepared_engine() -> dict:
    """The per-user engine copy: the recorded engine, minus the packed vendor archives, plus exactly
    the files its receipt lists (vendor CLI for one platform, unpacked device artwork, manifest)."""
    try:
        receipt = json.loads(DEVICE_CLI_RECEIPT.read_text())
    except (OSError, ValueError):
        return {"present": False, "verified": False, "detail": ""}
    try:
        if receipt.get("engine_version") != ENGINE_VERSION:
            return {"present": True, "verified": False,
                    "detail": f"prepared for engine {receipt.get('engine_version')}, plugin now has {ENGINE_VERSION}"}
        expected = {rel: digest for rel, digest in _recorded().items() if rel not in VENDOR_ARCHIVES}
        expected.update(receipt["added"])
        expected["package.json"] = receipt["package_json_sha256"]
        problems = (_compare_tree(PREPARED_ENGINE, expected, optional=frozenset(CAPTURE_FFMPEG))
                    if PREPARED_ENGINE.is_dir() else ["missing engine copy"])
        return {"present": True, "verified": not problems, "detail": _detail(problems)}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {"present": True, "verified": False, "detail": f"Could not verify: {error}"}


def select_engine() -> dict:
    """Which engine tree a new worker starts from. The prepared copy wins only when it verifies."""
    prepared = verify_prepared_engine()
    if prepared["verified"]:
        return {"root": PREPARED_ENGINE, "prepared": True, "check": {**verify_engine(), "verified": True, "detail": ""}}
    answer = {"root": ENGINE_ROOT, "prepared": False, "check": verify_engine()}
    if prepared["present"]:
        answer["prepared_problem"] = prepared["detail"]
    return answer


def code_fingerprint() -> str:
    """Identity of the adapter build ON DISK, so a client never talks to a stale broker.

    Read fresh (cached per file stamp) rather than once per process: a gateway that loaded the plugin
    before its files changed would otherwise keep a stale fingerprint and shut down every broker the
    new files start, in a loop, until the plugin is reloaded."""
    folder = Path(__file__).resolve().parent
    sources = [*adapter_sources(folder), ("../plugin.yaml", folder.parent / "plugin.yaml")]   # holds the version
    stamp = tuple((rel, path.stat().st_mtime_ns, path.stat().st_size) for rel, path in sources)
    return _fingerprint_for(stamp)


def adapter_sources(folder: Path) -> list[tuple[str, Path]]:
    """Every Python file of the adapter, sub-packages included, as (posix path relative to folder, path),
    sorted. Caches are skipped; a change to any other file must retire a running broker."""
    return sorted((path.relative_to(folder).as_posix(), path) for path in folder.rglob("*.py")
                  if "__pycache__" not in path.relative_to(folder).parts)


@lru_cache(maxsize=4)
def _fingerprint_for(stamp: tuple) -> str:
    # The version comes in through plugin.yaml's bytes, read now, never the value this process imported.
    digest = hashlib.sha256(f"protocol:{PROTOCOL}".encode())
    folder = Path(__file__).resolve().parent
    for name, _mtime, _size in stamp:
        digest.update(name.encode())
        digest.update((folder / name).read_bytes())
    return digest.hexdigest()[:24]

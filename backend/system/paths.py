"""Locations and environment discovery. Stdlib only; Hermes is consulted only through hermes_home.py, which the
Hermes layer fills in (backend.system never imports backend.hermes)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import threading
import time
from functools import lru_cache
from pathlib import Path

from . import hermes_home

PLUGIN_ID = "hermretro"
NODE_REQUIRED_MAJOR = 22
PROTOCOL = 2

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
# backend/: every Python file in it is part of the code fingerprint (a change retires a running broker).
BACKEND_ROOT = Path(__file__).resolve().parents[1]


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
ENGINE_ROOT = PLUGIN_ROOT / "engine"


def engine_version(package: Path) -> str | None:
    """The bundled engine's version, from its ``package.json`` (its only home: the engine's server reports the same
    one). None when it cannot be read: that engine fails its manifest check too, so nothing is prepared or started."""
    try:
        version = json.loads(package.read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return version if isinstance(version, str) and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) else None


ENGINE_VERSION = engine_version(ENGINE_ROOT / "package.json")
# The emulator's device skins, one folder each (backend/player/skins.py); the engine reads its device art from here too.
SKINS_DIR = PLUGIN_ROOT / "player" / "skins"
# What this plugin pinned for the engine it ships: its tool contracts and the hash of every engine file. It is part
# of the record of the engine, not of the engine: the manifest and the prepared copy leave it out (engine_entries).
ENGINE_PINS = ENGINE_ROOT / "contract"
PINNED_TOOLS = ENGINE_PINS / "tools.json"
ENGINE_MANIFEST = ENGINE_PINS / "manifest.json"

# Unix socket paths are capped at 104 bytes on macOS (108 on Linux); stay clear of both.
SOCKET_PATH_LIMIT = 100


def _hermes_root() -> Path:
    """The Hermes home that holds every profile (``~/.hermes`` by default), even when this process runs
    in a profile. Asks Hermes when the Hermes layer has said how (hermes_home.py). The fallback (tests, CI,
    tools run outside Hermes) covers the plain cases only; the broker never relies on it, because the client
    hands it ``HERMRETRO_HOME``."""
    asked = hermes_home.asked()
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


def engine_identity() -> str:
    """The bundled engine's identity as its files say now: its version and the start of its manifest's digest, so an
    edited engine is a new identity. ENGINE_IDENTITY is the one this process loaded."""
    try:
        manifest = json.loads(ENGINE_MANIFEST.read_text())
    except (OSError, ValueError):
        manifest = None
    return _identity(engine_version(ENGINE_ROOT / "package.json"), manifest)


def _identity(version: str | None, manifest) -> str:
    if version is None:
        return "unknown"
    try:
        return f"{version}-{manifest['aggregate_sha256'][:12]}"
    except (KeyError, TypeError):
        return version


# Named by the engine it was made from, and never changed once made (backend/setup/provision.py): two plugin copies
# (an installed one and a dev checkout) share this folder, and a running worker keeps reading the copy it started in.
ENGINE_IDENTITY = engine_identity()
PREPARED_ENGINE = DEPS_ROOT / f"engine-{ENGINE_IDENTITY}"  # bundled engine + ModRetro's CLI for this computer
DEVICE_CLI_RECEIPT = DEPS_ROOT / f"device-cli-{ENGINE_IDENTITY}.json"
# ModRetro's proprietary CLI, packed for all platforms. A distributable build of the plugin leaves
# these two out; setup then fetches the CLI for one platform from ModRetro (see provision.py).
VENDOR_ARCHIVES = ("third-party/chromatic-cli/executables-v2.br", "third-party/chromatic-cli/notices.br")
# The engine's ffmpeg builds for capturing a real Chromatic's video on Linux (LGPL, built from a patched
# source that is not public, so this plugin does not ship them). Without them Linux device capture
# says it is unavailable; everything else, and capture on macOS, is unaffected.
CAPTURE_FFMPEG = ("native/capture/linux/x64/ffmpeg", "native/capture/linux/arm64/ffmpeg")


def write_json_atomic(path: Path, data, indent: int = 2) -> None:
    """Write ``data`` as JSON (``indent``, a final newline) so a reader in another process sees the old file or the
    new one, never half of it: a temp file beside ``path`` (same folder, so same file system), then ``os.replace``.
    For state a listener or a tool keeps for other processes; the folder must exist."""
    path = Path(path)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        temporary.write_text(json.dumps(data, indent=indent) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


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
        raise PermissionError(
            f"{base} is a link or belongs to another user (uid {info.st_uid}), so hermretro "
            "will not use it; set HERMRETRO_RUNTIME_DIR to a private folder of your own"
        )
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


def _node_stamp(path: str) -> tuple[int, ...] | None:
    try:
        info = os.stat(path)
        if stat.S_ISREG(info.st_mode) and os.access(path, os.X_OK):
            return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_mode
    except OSError:
        pass
    return None


def node_usable(path: str) -> bool:
    """Whether ``path`` is still an executable file (a broker's Node can be removed under it)."""
    return _node_stamp(path) is not None


class _UnverifiedNode(Exception):
    pass


@lru_cache(maxsize=16)
def _verified_node_version(path: str, _stamp: tuple[int, ...]) -> tuple[int, ...]:
    version = _node_version(path)
    if version is None:
        raise _UnverifiedNode  # lru_cache keeps no exception: failures go to _failed_probes instead
    return version


# A candidate whose probe failed (a stalled shim takes the whole 10 s timeout) is skipped for a while, so a
# Setup poll or a tool call is not slowed by it each time; a changed file (another stamp) is probed at once.
PROBE_RETRY_SECONDS = 60.0
_failed_probes: dict[str, tuple[tuple[int, ...], float]] = {}


def _installed_node_version(path: str, stamp: tuple[int, ...]) -> tuple[int, ...] | None:
    failed = _failed_probes.get(path)
    if failed is not None and failed[0] == stamp and time.monotonic() - failed[1] < PROBE_RETRY_SECONDS:
        return None
    try:
        version = _verified_node_version(path, stamp)
    except _UnverifiedNode:
        _failed_probes[path] = (stamp, time.monotonic())  # one entry per candidate path: bounded
        return None
    _failed_probes.pop(path, None)
    return version


def find_node() -> dict:
    """Discover Node again on refresh, but only probe the version of a new or changed executable."""
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
    # Desktop launched from Finder may not have the shell's PATH. Hermes's tool store follows its root,
    # including custom HERMES_HOME installations; keep the conventional location as an older install fallback.
    for store in dict.fromkeys((_hermes_root() / "tools", home / ".hermes" / "tools")):
        candidates.extend(str(p) for p in sorted(store.glob("node-*/bin/node"), reverse=True))
    # Apple Silicon Homebrew before /usr/local, where an Intel (Rosetta) Homebrew keeps its Node on the same Mac.
    candidates.extend(
        str(p)
        for p in (
            home / ".local/bin/node",
            Path("/opt/homebrew/bin/node"),
            Path("/usr/local/bin/node"),
            Path("/usr/bin/node"),
        )
    )
    candidates.extend(str(p) for p in sorted((home / ".nvm/versions/node").glob("*/bin/node"), reverse=True))
    best: dict | None = None
    for candidate in dict.fromkeys(candidates):
        stamp = _node_stamp(candidate)
        if stamp is None:
            continue
        version = _installed_node_version(candidate, stamp)
        if version is None:
            continue
        found = {
            "found": True,
            "path": candidate,
            "version": ".".join(map(str, version)),
            "required": str(NODE_REQUIRED_MAJOR),
            "ok": version[0] >= NODE_REQUIRED_MAJOR,
        }
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


def is_bytecode(name: str) -> bool:
    """Whether a file or folder name is Python's own bytecode, which running the engine's scripts writes."""
    return name == "__pycache__" or name.endswith(".pyc")


def is_left_beside(name: str) -> bool:
    """Whether a file or folder name is one the system writes beside the engine's files rather than part of it:
    Python's bytecode, or the .DS_Store macOS Finder leaves in a folder it showed (git ignores both, so an update
    keeps them). Never recorded in the manifest, compared with it nor copied into the prepared engine."""
    return is_bytecode(name) or name == ".DS_Store"


# hermretro's record of the engine, at its top: its contract (tool contracts and manifest) and its changelog.
ENGINE_RECORD = (ENGINE_PINS.name, "CHANGES.md")


def is_engine_record(root: Path | str, path: Path | str) -> bool:
    """Whether path is part of the engine's record (ENGINE_RECORD), which no copy or manifest of the engine holds: a
    note in the changelog is not a change to the engine."""
    return Path(path).parent == Path(root) and Path(path).name in ENGINE_RECORD


def engine_entries(root: Path, *, engine_folder: bool = True) -> list[Path]:
    """Every file and link under root, sorted, but Python's bytecode and, in an engine folder (the bundled engine or
    another checkout's), its record. A running script writes bytecode and renames it into place meanwhile, so it is
    left out by name from the folder listing, before anything stats it; a link is listed whatever its name. A copy of
    the engine holds no record, so one there is listed like any other file."""
    found: list[Path] = []
    folders = [root]
    while folders:
        with os.scandir(folders.pop()) as listing:
            for entry in listing:
                if entry.is_symlink():
                    found.append(Path(entry.path))
                elif is_left_beside(entry.name) or (engine_folder and is_engine_record(root, entry.path)):
                    continue
                elif entry.is_dir():
                    folders.append(Path(entry.path))
                else:
                    found.append(Path(entry.path))
    return sorted(found)


def _compare_tree(
    root: Path, expected: dict[str, str], optional: frozenset[str] = frozenset(), *, engine_folder: bool = True
) -> list[str]:
    """Every regular file under root against rel -> SHA-256. No extras, no symlinks."""
    problems: list[str] = []
    seen: set[str] = set()
    for path in engine_entries(root, engine_folder=engine_folder):
        info = path.lstat()
        rel = path.relative_to(root).as_posix()
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
        version = engine_version(ENGINE_ROOT / "package.json")
        if version is None:
            problems.append("package.json has no x.y.z version")
        return {
            "present": True,
            "version": version,
            "verified": not problems,
            "detail": _detail(problems),
            "vendor_archives_bundled": all((ENGINE_ROOT / rel).is_file() for rel in VENDOR_ARCHIVES),
        }
    except (OSError, ValueError, KeyError) as error:
        return {"present": True, "version": None, "verified": False, "detail": f"Could not verify: {error}"}


def prepared_package_json(target: str, source: Path | None = None) -> bytes:
    """The prepared copy's package.json: the bundled one (or ``source``, a staged copy of it), naming the CLI build it
    holds for this computer."""
    package = json.loads((source or ENGINE_ROOT / "package.json").read_text())
    package.pop("bundledChromaticFormat", None)
    package["bundledChromaticTarget"] = target
    return (json.dumps(package, indent=2) + "\n").encode()


def staged_engine_problems(stage: Path) -> list[str]:
    """Why a staged copy of the bundled engine (provision._prepare, before the CLI goes in) is not exactly the engine
    this process loaded, ENGINE_IDENTITY: its files against the manifest that identity names (read once, so an edit
    meanwhile cannot pass), and its package's version. Empty when it is that engine."""
    try:
        manifest = json.loads(ENGINE_MANIFEST.read_text())
        if _identity(ENGINE_VERSION, manifest) != ENGINE_IDENTITY:
            return ["the engine's manifest changed since this process loaded it"]
        expected = {e["path"]: e["sha256"] for e in manifest["entries"] if e["path"] not in VENDOR_ARCHIVES}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return [f"the engine's manifest cannot be read: {error}"]
    problems = _compare_tree(stage, expected, optional=frozenset(CAPTURE_FFMPEG), engine_folder=False)
    if engine_version(stage / "package.json") != ENGINE_VERSION:
        problems.append(f"its package.json is not version {ENGINE_VERSION}")
    return problems


def verify_prepared_engine() -> dict:
    """The per-user engine copy: the recorded engine, minus the packed vendor archives, plus exactly
    the files its receipt lists (vendor CLI for one platform, manifest)."""
    try:
        receipt = json.loads(DEVICE_CLI_RECEIPT.read_text())
    except (OSError, ValueError):
        return {"present": False, "verified": False, "detail": ""}
    if not isinstance(receipt, dict):
        return {"present": True, "verified": False, "detail": "unreadable receipt"}
    try:
        if receipt.get("engine_version") != ENGINE_VERSION:
            return {
                "present": True,
                "verified": False,
                "detail": f"prepared for engine {receipt.get('engine_version')}, plugin now has {ENGINE_VERSION}",
            }
        expected = {rel: digest for rel, digest in _recorded().items() if rel not in VENDOR_ARCHIVES}
        expected.update(receipt["added"])
        expected["package.json"] = hashlib.sha256(prepared_package_json(receipt["target"])).hexdigest()
        problems = (
            _compare_tree(PREPARED_ENGINE, expected, optional=frozenset(CAPTURE_FFMPEG), engine_folder=False)
            if PREPARED_ENGINE.is_dir()
            else ["missing engine copy"]
        )
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
    """Identity of the backend build ON DISK, so a client never talks to a stale broker.

    Read fresh (cached per file stamp) rather than once per process: a gateway that loaded the plugin
    before its files changed would otherwise keep a stale fingerprint and shut down every broker the
    new files start, in a loop, until the plugin is reloaded."""
    return loaded_fingerprints()[0]


def release_fingerprint() -> str | None:
    """The fingerprint by the published releases' rule: backend/ and plugin.yaml only (RELEASED_FILES). Their clients
    compare a broker's ``loaded_fingerprint`` with it, so a broker reports this one there (backend/broker/server.py): a
    gateway of such a release, still running after an update to this one, keeps the broker the new files start. None
    when one of those files is missing, which the releases could not fingerprint either."""
    return loaded_fingerprints()[1]


def loaded_fingerprints() -> tuple[str, str | None]:
    """``(code_fingerprint(), release_fingerprint())`` from one reading of the files: a broker names the code it loaded
    with both, and read apart, an update between the two readings could give each a different build."""

    def stamped() -> tuple:
        folder = BACKEND_ROOT
        sources = [*backend_sources(folder), *((f"../{rel}", folder.parent / rel) for rel in LOADED_FILES)]
        return tuple((rel, *_file_stamp(path)) for rel, path in sources)

    try:
        return _fingerprint_for(stamped())
    except FileNotFoundError:  # a file went between its stamp and its read: list and stamp them again
        return _fingerprint_for(stamped())


# A file's stamp when it is gone (an update can move a file this process loaded, and the fingerprint must still answer,
# as changed, so the page can offer the reload), and when it is there but cannot be looked at.
GONE, UNREADABLE = ("gone",), ("unreadable",)


def _file_stamp(path: Path) -> tuple:
    """What a file's fingerprint is cached by: its modification and change times (a permission change moves the
    second) and its size, or GONE or UNREADABLE."""
    try:
        info = path.stat()
    except FileNotFoundError:
        return GONE
    except OSError:
        return UNREADABLE
    return info.st_mtime_ns, info.st_ctime_ns, info.st_size


# The plugin's files outside backend/ that its code reads as it loads, relative to the plugin root: the entry point,
# the manifest (it holds the version), the engine's package.json and manifest (ENGINE_VERSION and ENGINE_IDENTITY, so
# an engine change retires a running broker) and the tool contract the tools register (and the broker starts) with.
LOADED_FILES = (
    "__init__.py",
    "plugin.yaml",
    "engine/package.json",
    "engine/contract/manifest.json",
    "engine/contract/tools.json",
)
# Those the published releases' rule covers too (release_fingerprint), as the fingerprint names them. A rule a release
# has shipped never changes: its gateways compare by it. A new rule gets a new handshake field (backend/broker/server.py).
RELEASED_FILES = ("../plugin.yaml",)


def backend_sources(folder: Path) -> list[tuple[str, Path]]:
    """Every Python file of the backend, sub-packages included, as (posix path relative to folder, path),
    sorted. Caches are skipped; a change to any other file must retire a running broker."""
    return sorted(
        (path.relative_to(folder).as_posix(), path)
        for path in folder.rglob("*.py")
        if "__pycache__" not in path.relative_to(folder).parts
    )


def _readable(path: Path) -> bytes | None:
    """A file's bytes, or None when it is there but cannot be read: only the rules that cover it lose their answer."""
    try:
        return path.read_bytes()
    except FileNotFoundError:
        raise  # it went since its stamp: the caller stamps the files again
    except OSError:
        return None


@lru_cache(maxsize=4)
def _fingerprint_for(stamp: tuple) -> tuple[str, str | None]:
    # The version comes in through plugin.yaml's bytes, read now, never the value this process imported.
    code = hashlib.sha256(f"protocol:{PROTOCOL}".encode())
    released = hashlib.sha256(f"protocol:{PROTOCOL}".encode())
    complete = True
    folder = BACKEND_ROOT
    for name, *state in stamp:
        state = tuple(state)
        data = b"(missing)" if state == GONE else None if state == UNREADABLE else _readable(folder / name)
        code.update(name.encode())
        code.update(b"(unreadable)" if data is None else data)
        if not name.startswith("../") or name in RELEASED_FILES:  # a file the releases' rule covers
            complete = complete and state != GONE and data is not None
            released.update(name.encode())
            released.update(b"" if data is None else data)
    return code.hexdigest()[:24], released.hexdigest()[:24] if complete else None

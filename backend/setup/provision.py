"""Per-user installation of the pieces the plugin does not ship. Stdlib only; no Hermes imports.

Everything lands under ``paths.DEPS_ROOT`` (``~/.hermes/hermretro/.cache/``):

* ``toolchain/``  the engine's own managed setup root (GB Studio CLI, GBDK, PyBoy ...). The engine
  fills it through its ``toolchain_prepare`` tool; this module only names the place.
* ``engine/``     a prepared copy of the bundled engine that also holds ModRetro's Chromatic CLI
  for this computer, fetched from ModRetro's own npm packages. The plugin never redistributes it.

The engine supports two layouts for the vendor CLI: one packed archive with all six platforms (how
the original distribution ships) and one plain directory for a single declared platform. The prepared
copy uses the second, so no engine code is changed: the engine still checks owner, modes, size and
SHA-256 of the executable before every vendor command, against the digests compiled into it.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import tarfile
import sys
import tempfile
import time
import urllib.request
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from ..system import host as host_os, paths
from .seed import _seed_source

CLI_DIR = "third-party/chromatic-cli"
REGISTRY_PREFIX = "https://registry.npmjs.org/@modretro/"
VENDOR_TERMS_URL = "https://modretro.com/eula"
_RUST_TARGETS = {
    "linux-x64-gnu": "x86_64-unknown-linux-gnu",
    "linux-arm64-gnu": "aarch64-unknown-linux-gnu",
    "darwin-arm64": "aarch64-apple-darwin",
    "darwin-x64": "x86_64-apple-darwin",
    "win32-x64": "x86_64-pc-windows-msvc",
    "win32-arm64": "aarch64-pc-windows-msvc",
}

_RESOLVE = """
import { resolveChromaticRuntime } from %(runtime)s;
const found = resolveChromaticRuntime();
process.stdout.write(JSON.stringify({ version: found.version, platform: found.platform, executable: found.executable }));
"""


class ProvisionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _node_platform(node_path: str | None = None) -> tuple[str, str] | None:
    """(platform, arch) as the Node.js that runs the engine reports them. The engine picks the CLI it accepts
    from its own ``process.platform``/``process.arch``, so a download must match Node, not this Python
    (they differ when one of them runs under Rosetta). node_path: the Node a worker runs with, else the one found."""
    node_path = node_path or paths.find_node().get("path")
    if not node_path:
        return None
    try:
        return _platform_of(node_path, os.stat(node_path).st_mtime_ns)
    except OSError:
        return None


@lru_cache(maxsize=8)
def _platform_of(node: str, _stamp: int) -> tuple[str, str] | None:
    """Asked once per Node executable (and again if it is replaced): the page polls status every few seconds."""
    try:
        out = subprocess.run(
            [node, "-p", "process.platform + ' ' + process.arch"], capture_output=True, text=True, timeout=10
        ).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return None
    return (out[0], out[1]) if len(out) == 2 else None


def host_target(node_path: str | None = None) -> dict:
    """The engine's name for this computer (as node_path, or the Node found, runs it), or why ModRetro's CLI cannot
    run here."""
    system, machine = platform.system(), platform.machine().lower()
    reported = _node_platform(node_path)
    node_system, node_arch = reported if reported else (host_os.system_name(), host_os.native_arch())
    arch = {"x64": "x64", "arm64": "arm64"}.get(node_arch)
    name = {"linux": "linux", "darwin": "darwin"}.get(node_system)
    if not arch or not name:
        return {"target": None, "reason": f"ModRetro publishes no Chromatic CLI for {system} {machine}."}
    if name == "linux":
        lib, version = platform.libc_ver()
        parts = tuple(int(p) for p in version.split(".")[:2]) if version.replace(".", "").isdigit() else ()
        if lib != "glibc" or parts < (2, 39):
            return {
                "target": None,
                "reason": "ModRetro's Chromatic CLI needs GNU/Linux with glibc 2.39 or newer "
                f"(found {lib or 'unknown libc'} {version}).",
            }
        return {"target": f"linux-{arch}-gnu", "reason": None}
    return {"target": f"{name}-{arch}", "reason": None}


def _pins(target: str) -> dict:
    """Digests for one platform, from the provenance record that ships with the engine."""
    record = json.loads((paths.ENGINE_ROOT / CLI_DIR / "PROVENANCE.json").read_text())
    files = [f for f in record["files"] if f["target"] == _RUST_TARGETS[target]]
    executable = next(f for f in files if f["kind"] == "executable")
    notice = next(f for f in files if f["kind"] == "notice")
    package = next(p for p in record["source"]["packages"] if p["name"] == executable["package"])
    if not package["url"].startswith(REGISTRY_PREFIX) or package["version"] != record["version"]:
        raise ProvisionError("PIN_INVALID", "The engine's provenance record names an unexpected download source.")
    return {"version": record["version"], "package": package, "executable": executable, "notice": notice}


def read_receipt() -> dict | None:
    try:
        receipt = json.loads(paths.DEVICE_CLI_RECEIPT.read_text())
        return receipt if isinstance(receipt, dict) else None
    except (OSError, ValueError):
        return None


def device_cli_status(selection: dict | None = None) -> dict:
    """Never downloads, never runs the vendor executable. May rebuild the prepared copy from files it holds already
    (select_engine), unless the caller already chose (selection)."""
    host = host_target()
    answer = {
        "state": "missing",
        "target": host["target"],
        "version": None,
        "location": None,
        "source": "ModRetro npm packages (@modretro/chromatic-cli-*)",
        "terms": VENDOR_TERMS_URL,
        "needed_for": "device discovery, streaming, capture and cartridge flashing only",
    }
    if host["target"] is None:
        answer.update(state="unsupported", detail=host["reason"])
        return answer
    selection = selection or select_engine()
    if selection["prepared"]:
        receipt = read_receipt() or {}
        answer.update(
            state="installed",
            version=receipt.get("cli_version"),
            location=str(selection["root"] / CLI_DIR / receipt.get("executable", "")),
            installed_at=receipt.get("installed_at"),
        )
    elif all((paths.ENGINE_ROOT / rel).is_file() for rel in paths.VENDOR_ARCHIVES):
        answer.update(state="bundled", detail="This copy of the plugin still carries the packed vendor archive.")
    elif selection.get("prepared_problem"):
        answer.update(detail="An earlier install no longer verifies and is ignored: " + selection["prepared_problem"])
    return answer


@contextmanager
def _lock():
    paths.DEPS_ROOT.mkdir(mode=0o755, parents=True, exist_ok=True)
    with open(paths.DEPS_ROOT / ".provision.lock", "a+") as handle:
        try:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:
            pass
        except OSError:
            raise ProvisionError("BUSY", "Another hermretro setup is running. Wait for it to finish.")
        yield


def _download(package: dict, opener=urllib.request.urlopen) -> bytes:
    limit = int(package["bytes"])
    request = urllib.request.Request(package["url"], headers={"User-Agent": f"hermretro/{paths.PLUGIN_VERSION}"})
    try:
        with opener(request, timeout=120) as response:
            data = response.read(limit + 1)
    except OSError as error:
        raise ProvisionError("DOWNLOAD_FAILED", f"Could not download {package['name']} from the npm registry: {error}")
    if len(data) != limit or hashlib.sha256(data).hexdigest() != package["sha256"]:
        raise ProvisionError(
            "CHECKSUM_MISMATCH",
            f"{package['name']} {package['version']} from the npm registry does not "
            "match the pinned size and SHA-256. Nothing was installed.",
        )
    return data


def _member(archive: tarfile.TarFile, name: str, pin: dict) -> bytes:
    try:
        info = archive.getmember(name)
    except KeyError:
        raise ProvisionError("ARCHIVE_UNEXPECTED", f"The vendor package has no {name}.")
    if not info.isreg() or info.size != int(pin["bytes"]):
        raise ProvisionError("ARCHIVE_UNEXPECTED", f"Unexpected type or size for {name} in the vendor package.")
    data = archive.extractfile(info).read()
    if hashlib.sha256(data).hexdigest() != pin["sha256"]:
        raise ProvisionError("CHECKSUM_MISMATCH", f"{name} in the vendor package does not match its pinned SHA-256.")
    return data


def _node(script: str, *args: str, cwd: Path, node_path: str | None = None) -> dict:
    """Run an engine script with node_path (a worker's Node), else the Node found."""
    found = paths.find_node()
    node_path = node_path or (found["path"] if found["ok"] else None)
    if not node_path:
        raise ProvisionError("NODE_REQUIRED", f"Node.js {found['required']} or newer is required.")
    env = {
        key: os.environ[key]
        for key in ("PATH", "HOME", "LANG", "USER", "LOGNAME", "TMPDIR", *host_os.NETWORK_ENV)
        if key in os.environ
    }
    try:
        done = subprocess.run(
            [node_path, "--input-type=module", "-e", script, *args],
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        raise ProvisionError("ENGINE_REFUSED", "The engine's own check did not finish in two minutes.") from None
    if done.returncode != 0:
        raise ProvisionError(
            "ENGINE_REFUSED",
            (done.stderr or done.stdout).strip().splitlines()[-1][:400]
            if (done.stderr or done.stdout).strip()
            else "The engine's own check failed.",
        )
    return json.loads(done.stdout)


def _tighten(root: Path) -> None:
    """The engine refuses group- or world-writable files and directories for an unpacked vendor CLI."""
    for current, directories, files in os.walk(root):
        for name in [*directories, *files]:
            target = Path(current) / name
            mode = stat.S_IMODE(target.lstat().st_mode)
            if mode & 0o022:
                os.chmod(target, mode & ~0o022)
    os.chmod(root, stat.S_IMODE(root.lstat().st_mode) & ~0o022)


def install_device_cli(accept_vendor_terms: bool, opener=urllib.request.urlopen) -> dict:
    """Fetch ModRetro's CLI for this computer and build the prepared engine copy. Touches no device."""
    if accept_vendor_terms is not True:
        raise ProvisionError(
            "TERMS_NOT_ACCEPTED",
            "ModRetro's Chromatic CLI is proprietary software downloaded from ModRetro. Install it "
            f"only after the user agrees to ModRetro's terms ({VENDOR_TERMS_URL}).",
        )
    host = host_target()
    if host["target"] is None:
        raise ProvisionError("UNSUPPORTED_HOST", host["reason"])
    target = host["target"]
    _require_bundled_engine()
    pins = _pins(target)
    with _lock():
        archive_bytes = _download(pins["package"], opener)
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
            executable = _member(archive, "package/" + pins["executable"]["path"].split("/", 1)[1], pins["executable"])
            notice = _member(archive, "package/" + pins["notice"]["path"].split("/", 1)[1], pins["notice"])
        _prepare(target, pins, executable, notice, installed_at=_now())

    selection = paths.select_engine()
    if not selection["prepared"]:
        raise ProvisionError(
            "VERIFY_FAILED",
            "The prepared engine did not verify after install: " + str(selection.get("prepared_problem")),
        )
    resolved = _node(
        _RESOLVE % {"runtime": json.dumps((paths.PREPARED_ENGINE / "scripts" / "chromatic-runtime.mjs").as_uri())},
        cwd=paths.PREPARED_ENGINE,
    )
    return {
        "installed": True,
        "target": target,
        "cli_version": resolved["version"],
        "executable": resolved["executable"],
        "executable_sha256": pins["executable"]["sha256"],
        "downloaded_from": pins["package"]["url"],
        "engine_root": str(paths.PREPARED_ENGINE),
        "receipt": str(paths.DEVICE_CLI_RECEIPT),
    }


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _require_bundled_engine() -> None:
    bundled = paths.verify_engine()
    if not bundled["verified"]:
        raise ProvisionError(
            "ENGINE_NOT_VERIFIED", "The bundled engine does not match its manifest: " + bundled["detail"]
        )


def _prepare(
    target: str, pins: dict, executable: bytes, notice: bytes, node_path: str | None = None, **dates: str | None
) -> None:
    """Build the prepared copy from the bundled engine and the verified CLI files, swap it in and write its receipt.
    The caller holds the provision lock."""
    exe_rel, notice_rel = pins["executable"]["path"], pins["notice"]["path"]  # e.g. linux-x64-gnu/bin/chromatic-cli
    stage = paths.DEPS_ROOT / f"engine.staging-{os.getpid()}"
    shutil.rmtree(stage, ignore_errors=True)
    skipped = {str(paths.ENGINE_ROOT / rel) for rel in paths.VENDOR_ARCHIVES}
    try:
        shutil.copytree(
            paths.ENGINE_ROOT,
            stage,
            symlinks=False,
            ignore=lambda folder, names: [n for n in names if str(Path(folder) / n) in skipped or paths.is_bytecode(n)],
        )
        for rel, data, mode in (
            (exe_rel, executable, int(pins["executable"]["mode"], 8)),
            (notice_rel, notice, int(pins["notice"]["mode"], 8)),
        ):
            destination = stage / CLI_DIR / rel
            destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            with open(destination, "xb") as handle:
                handle.write(data)
            os.chmod(destination, mode)

        package_json = paths.prepared_package_json(target)
        (stage / "package.json").write_bytes(package_json)
        os.chmod(stage / "package.json", 0o644)

        runtime = json.dumps((stage / "scripts" / "chromatic-runtime.mjs").as_uri())
        _tighten(stage)
        _node(
            _RESOLVE % {"runtime": runtime}, cwd=stage, node_path=node_path
        )  # the engine's admission, before the swap

        previous = None
        if paths.PREPARED_ENGINE.exists():
            previous = paths.DEPS_ROOT / f"engine.old-{int(time.time())}-{os.getpid()}"
            os.replace(paths.PREPARED_ENGINE, previous)
        os.replace(stage, paths.PREPARED_ENGINE)
        if previous is not None:
            shutil.rmtree(previous, ignore_errors=True)
    finally:
        shutil.rmtree(stage, ignore_errors=True)

    receipt = {
        "schema": 1,
        "engine_version": paths.ENGINE_VERSION,
        "target": target,
        "cli_version": pins["version"],
        "package": pins["package"]["name"],
        "url": pins["package"]["url"],
        "archive_sha256": pins["package"]["sha256"],
        "executable": exe_rel,
        "package_json_sha256": hashlib.sha256(package_json).hexdigest(),
        "added": {
            f"{CLI_DIR}/{exe_rel}": pins["executable"]["sha256"],
            f"{CLI_DIR}/{notice_rel}": pins["notice"]["sha256"],
        },
        "vendor_terms": VENDOR_TERMS_URL,
        "vendor_terms_accepted": True,
        **{key: value for key, value in dates.items() if value},
    }
    paths.write_json_atomic(paths.DEVICE_CLI_RECEIPT, receipt)


# -- keeping the prepared copy in step with the bundled engine -------------------------------------------
# Each copy is named by the engine it was made from (paths.ENGINE_IDENTITY) and never changed once made: a worker
# keeps reading from the copy it started in, even after the engine changes and a new copy appears beside it.

_COPY_NAME = re.compile(r"\d+\.\d+\.\d+(?:-[0-9a-f]{12})?")
_KINDS = ("executable", "notice")
_NOT_REUSABLE: set[tuple] = set()  # earlier copies looked at, by their files' stamps: not read again until one changes


def select_engine(node_path: str | None = None) -> dict:
    """``paths.select_engine``, after making the prepared copy for the bundled engine when the engine changed (the
    maintainer's edit or a new version) and an earlier copy holds the CLI build this engine pins. Nothing is
    downloaded and nothing is asked: the user accepted ModRetro's terms for that CLI when they installed it.
    node_path: the Node the worker runs with, which decides the CLI build."""
    selection = paths.select_engine()
    if selection.get("prepared") or not selection["check"].get("verified") or not refresh_prepared_engine(node_path):
        return selection
    return paths.select_engine()


def _earlier_copies() -> list[tuple[Path, Path]]:
    """(receipt, copy) of every prepared copy in the download folder, newest receipt first. A receipt
    device-cli-<name>.json belongs to the folder engine-<name>; any other name is ignored."""
    found = []
    for receipt in paths.DEPS_ROOT.glob("device-cli-*.json"):
        name = receipt.name.removeprefix("device-cli-").removesuffix(".json")
        copy = paths.DEPS_ROOT / f"engine-{name}"
        try:
            if _COPY_NAME.fullmatch(name) and copy.is_dir() and not copy.is_symlink():
                found.append((receipt.stat().st_mtime_ns, receipt, copy))
        except OSError:
            continue
    return [(receipt, copy) for _stamp, receipt, copy in sorted(found, reverse=True)]


def _reusable_cli(target: str, pins: dict) -> tuple[bytes, bytes, dict, Path, tuple] | None:
    """The pinned CLI files from an earlier copy, when the user accepted these terms for this CLI release on this
    computer: (executable, notice, receipt, copy, stamps)."""
    for receipt_path, copy in _earlier_copies():
        files = [copy / CLI_DIR / pins[kind]["path"] for kind in _KINDS]
        try:
            stamps = tuple((f.lstat().st_size, f.lstat().st_mtime_ns) for f in (receipt_path, *files))
        except OSError:
            continue
        key = (str(copy), stamps, pins["executable"]["sha256"], pins["notice"]["sha256"])
        if key in _NOT_REUSABLE:
            continue
        try:
            receipt = json.loads(receipt_path.read_text())
            usable = (
                isinstance(receipt, dict)
                and receipt.get("target") == target
                and receipt.get("cli_version") == pins["version"]
                and receipt.get("vendor_terms") == VENDOR_TERMS_URL
                and receipt.get("vendor_terms_accepted") is True
                and all(
                    f.is_file() and not f.is_symlink() and f.lstat().st_size == int(pins[kind]["bytes"])
                    for f, kind in zip(files, _KINDS, strict=True)
                )
            )
            found = [f.read_bytes() for f in files] if usable else []
        except (OSError, ValueError, KeyError, TypeError):
            found = []
        if found and all(
            hashlib.sha256(data).hexdigest() == pins[kind]["sha256"] for data, kind in zip(found, _KINDS, strict=True)
        ):
            return found[0], found[1], receipt, copy, key
        _NOT_REUSABLE.add(key)
    return None


def refresh_prepared_engine(node_path: str | None = None) -> bool:
    """Make the prepared copy for the bundled engine from an earlier copy's CLI files, then remove the copies older
    than that earlier one. False when there is none to reuse, another setup holds the lock, or the new copy does not
    verify (setup then offers the install)."""
    if not any(paths.DEPS_ROOT.glob("device-cli-*.json")):  # never installed: nothing to reuse
        return False
    target = host_target(node_path)["target"]
    if target is None:
        return False
    try:
        pins = _pins(target)
        with _lock():
            if paths.verify_prepared_engine()["verified"]:  # another process made it while this one waited
                return True
            found = _reusable_cli(target, pins)
            if found is None:
                return False
            executable, notice, receipt, source, key = found
            dates = {"installed_at": receipt.get("installed_at"), "refreshed_at": _now()}
            try:
                _prepare(target, pins, executable, notice, node_path=node_path, **dates)
            except (ProvisionError, OSError, ValueError, KeyError):
                _NOT_REUSABLE.add(key)
                return False
            if not paths.verify_prepared_engine()["verified"]:
                _NOT_REUSABLE.add(key)
                return False
            for receipt_path, copy in _earlier_copies():  # the one just read may still serve a running worker
                if copy not in (paths.PREPARED_ENGINE, source):
                    remove_tree(copy)
                    receipt_path.unlink(missing_ok=True)
        return True
    except (ProvisionError, OSError, ValueError, KeyError, StopIteration):  # BUSY included: tried again later
        return False


def summary() -> dict:
    """Where this install keeps its dependencies. Never downloads (device_cli_status)."""
    selection = select_engine()
    return {
        "root": str(paths.DEPS_ROOT),
        "toolchain_root": str(paths.setup_root()),
        "toolchain_cache_reused_from": _seed_source(),
        "engine_root": str(selection["root"]),
        "device_cli": device_cli_status(selection),
    }


def remove_downloads() -> dict:
    """Empty hermretro's download folder ``<hermretro home>/.cache`` (toolchain, prepared engine with ModRetro's
    CLI, receipts). Games and the library are elsewhere and untouched; links inside are removed, never followed.
    The caller holds the broker's election lock, so no broker or worker runs from it meanwhile. Refused when the
    location was configured by hand, since that folder is the user's."""
    if os.environ.get("HERMRETRO_DEPS_ROOT") or os.environ.get("GB_STUDIO_SETUP_ROOT"):
        raise ProvisionError(
            "CUSTOM_LOCATION",
            "The downloaded tools are in a folder you configured "
            "(HERMRETRO_DEPS_ROOT or GB_STUDIO_SETUP_ROOT); delete it yourself.",
        )
    root = paths.DEPS_ROOT
    home = paths.hermretro_home().resolve()
    if root != home / ".cache" or root.is_relative_to(paths.PLUGIN_ROOT) or root.is_symlink():
        raise ProvisionError(
            "UNEXPECTED_LOCATION", f"Refusing to delete {root}: it is not hermretro's download folder."
        )
    if not root.is_dir():
        return {"ok": True, "removed_bytes": 0, "left_bytes": 0, "root": str(root)}
    with _lock():  # no device-CLI install meanwhile
        # Inside .cache, so every move is a rename on the same filesystem; the folder empties at once.
        trash = Path(tempfile.mkdtemp(prefix=_TRASH_PREFIX, dir=root))
        for child in list(root.iterdir()):
            if child.name == ".provision.lock" or child.name.startswith(_TRASH_PREFIX):
                continue
            os.replace(child, trash / child.name)
    removed = 0
    for leftover in [p for p in root.iterdir() if p.name.startswith(_TRASH_PREFIX)]:  # also earlier, failed runs
        removed += folder_bytes(leftover)
        remove_tree(leftover)
    left = sum(folder_bytes(p) for p in root.iterdir() if p.name.startswith(_TRASH_PREFIX))
    return {
        "ok": not left,
        "removed_bytes": removed - left,
        "left_bytes": left,
        "root": str(root),
        **(
            {"code": "PARTLY_REMOVED", "error": f"{left // 1_000_000} MB could not be deleted from {root}."}
            if left
            else {}
        ),
    }


_TRASH_PREFIX = ".removing-"


def remove_tree(path: Path) -> None:
    """Delete a tree, making read-only folders (from extracted archives) writable when a delete is refused."""

    def retry(function, failed, _info):
        try:
            os.chmod(os.path.dirname(failed), 0o700)
            if os.path.isdir(failed) and not os.path.islink(failed):
                os.chmod(failed, 0o700)
            function(failed)
        except OSError:
            pass

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=retry)
    else:
        shutil.rmtree(path, onerror=retry)


def folder_bytes(path: Path) -> int:
    """Bytes in a whole file or folder tree (links counted as themselves, never followed)."""
    if path.is_symlink() or path.is_file():
        return path.lstat().st_size
    return sum(child.lstat().st_size for child in path.rglob("*") if not child.is_dir() or child.is_symlink())


if __name__ == "__main__":
    # Read-only on purpose: installing goes through the chromatic_studio_device_cli tool, which
    # asks the person for approval.
    print(json.dumps(summary(), indent=2))

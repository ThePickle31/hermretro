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
import shutil
import stat
import subprocess
import tarfile
import time
import urllib.request
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from ..system import engine_tree, host as host_os, paths
from . import copy_lease

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


def device_cli_status(selection: dict) -> dict:
    """Never downloads, never runs the vendor executable. ``selection``: the engine copy the caller chose
    (``prepared_copies.select_engine``, which may rebuild the prepared copy from files it holds already)."""
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
def lock():
    """One setup at a time changes the download folder: an install, a refresh, a pruning or emptying it."""
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
    _require_loaded_engine()  # first, and before the download: a gateway an engine change left stale says so at once
    _require_bundled_engine()
    pins = _pins(target)
    with lock():  # held to the end: nothing removes or replaces the copy before its runtime has accepted it
        receipt = read_receipt() or {}
        if (receipt.get("target"), receipt.get("cli_version")) == (target, pins["version"]) and (
            paths.verify_prepared_engine()["verified"]
        ):  # a copy of this build, kept as it is (a worker may run in it) unless its runtime refuses it
            try:
                return _installed(target, pins)
            except ProvisionError as error:
                if error.code != "ENGINE_REFUSED":
                    raise
        archive_bytes = _download(pins["package"], opener)
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
            executable = _member(archive, "package/" + pins["executable"]["path"].split("/", 1)[1], pins["executable"])
            notice = _member(archive, "package/" + pins["notice"]["path"].split("/", 1)[1], pins["notice"])
        _prepare(target, pins, executable, notice, installed_at=_now())
        return _installed(target, pins)


def _installed(target: str, pins: dict) -> dict:
    """What install_device_cli answers, once the copy verifies and its runtime resolves the CLI."""
    selection = paths.select_engine()
    if not selection["prepared"]:
        _require_loaded_engine()  # it changed after the copy was made: the copy is right, this process is not
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


# A copy is named by the engine this process loaded (paths.PREPARED_ENGINE), so it holds that engine or none: after an
# engine-only change, the process waits for Hermes's restart (the page asks for it) before it makes one.
ENGINE_CHANGED = "hermretro's engine changed after Hermes started. Restart Hermes, then try again."


IN_USE = "A game is running from hermretro's engine copy. Close the chats that are running games, then try again."


def _require_loaded_engine() -> None:
    if paths.engine_identity() != paths.ENGINE_IDENTITY:
        raise ProvisionError("ENGINE_CHANGED", ENGINE_CHANGED)


def _prepare(
    target: str, pins: dict, executable: bytes, notice: bytes, node_path: str | None = None, **dates: str | None
) -> None:
    """Build the prepared copy from the bundled engine and the verified CLI files, swap it in and write its receipt.
    The caller holds the provision lock. The staged copy must be exactly the engine this process loaded, checked
    after copying, so an edit made meanwhile publishes nothing."""
    _require_loaded_engine()
    exe_rel, notice_rel = pins["executable"]["path"], pins["notice"]["path"]  # e.g. linux-x64-gnu/bin/chromatic-cli
    stage = paths.DEPS_ROOT / f"engine.staging-{os.getpid()}"
    shutil.rmtree(stage, ignore_errors=True)
    skipped = {str(paths.ENGINE_ROOT / rel) for rel in paths.VENDOR_ARCHIVES}
    try:
        shutil.copytree(
            paths.ENGINE_ROOT,
            stage,
            symlinks=False,
            ignore=lambda folder, names: [
                n
                for n in names
                if str(Path(folder) / n) in skipped
                or engine_tree.is_left_beside(n)
                or engine_tree.is_engine_record(paths.ENGINE_ROOT, Path(folder) / n)
            ],
        )
        problems = paths.staged_engine_problems(stage)
        if problems:
            _require_loaded_engine()  # changed since this process loaded it: restart; otherwise it is just unverified
            raise ProvisionError(
                "ENGINE_NOT_VERIFIED",
                "The bundled engine does not match its manifest: " + engine_tree.describe_problems(problems),
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

        package_json = paths.prepared_package_json(target, stage / "package.json")  # the copied, checked one
        (stage / "package.json").write_bytes(package_json)
        os.chmod(stage / "package.json", 0o644)

        runtime = json.dumps((stage / "scripts" / "chromatic-runtime.mjs").as_uri())
        _tighten(stage)
        _node(
            _RESOLVE % {"runtime": runtime}, cwd=stage, node_path=node_path
        )  # the engine's admission, before the swap

        _require_loaded_engine()  # Node's admission ran meanwhile: still the engine this copy is named for
        previous = None
        with copy_lease.unused(paths.PREPARED_ENGINE) as unused:  # no worker starts in it while it is swapped
            if not unused:
                raise ProvisionError("IN_USE", IN_USE)
            if paths.PREPARED_ENGINE.exists():
                previous = paths.DEPS_ROOT / f"engine.old-{int(time.time())}-{os.getpid()}"
                os.replace(paths.PREPARED_ENGINE, previous)
            copy_lease.create(paths.PREPARED_ENGINE)  # published with its lease file: its workers' leases count
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


if __name__ == "__main__":
    # Read-only on purpose: installing goes through the chromatic_studio_device_cli tool, which
    # asks the person for approval. Imported here only, so importing provision never imports prepared_copies.
    from .prepared_copies import summary

    print(json.dumps(summary(), indent=2))

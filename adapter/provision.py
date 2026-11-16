"""Per-user installation of the pieces the plugin does not ship. Stdlib only; no Hermes imports.

Everything lands under ``<plugin>/deps/``:

* ``deps/toolchain/``  the engine's own managed setup root (GB Studio CLI, GBDK, PyBoy ...). The engine
  fills it through its ``toolchain_prepare`` tool; this module only names the place.
* ``deps/engine/``     a prepared copy of the bundled engine that also holds ModRetro's Chromatic CLI
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
from pathlib import Path

from . import paths

CLI_DIR = "third-party/chromatic-cli"
REGISTRY_PREFIX = "https://registry.npmjs.org/@modretro/"
VENDOR_TERMS_URL = "https://modretro.com/eula"
_RUST_TARGETS = {
    "linux-x64-gnu": "x86_64-unknown-linux-gnu", "linux-arm64-gnu": "aarch64-unknown-linux-gnu",
    "darwin-arm64": "aarch64-apple-darwin", "darwin-x64": "x86_64-apple-darwin",
    "win32-x64": "x86_64-pc-windows-msvc", "win32-arm64": "aarch64-pc-windows-msvc",
}

_UNPACK_ARTWORK = """
import { readPackedDeviceArtwork, CHROMATIC_ARTWORK_MEMBERS } from %(runtime)s;
import { writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import path from "node:path";
const directory = process.argv[1];
const written = {};
for (const [name, bytes] of readPackedDeviceArtwork(directory)) {
  const pin = CHROMATIC_ARTWORK_MEMBERS[name];
  const sha256 = createHash("sha256").update(bytes).digest("hex");
  if (!pin || pin.size !== bytes.length || pin.sha256 !== sha256 || path.basename(name) !== name) {
    throw new Error("Device artwork does not match the engine's pins: " + name);
  }
  writeFileSync(path.join(directory, name), bytes, { mode: 0o644, flag: "wx" });
  written[name] = sha256;
}
process.stdout.write(JSON.stringify(written));
"""

_RESOLVE = """
import { resolveChromaticRuntime } from %(runtime)s;
const found = resolveChromaticRuntime();
process.stdout.write(JSON.stringify({ version: found.version, platform: found.platform, executable: found.executable }));
"""


class ProvisionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def host_target() -> dict:
    """The engine's name for this computer, or why ModRetro's CLI cannot run here."""
    system, machine = platform.system(), platform.machine().lower()
    arch = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(machine)
    name = {"Linux": "linux", "Darwin": "darwin", "Windows": "win32"}.get(system)
    if not arch or not name:
        return {"target": None, "reason": f"ModRetro publishes no Chromatic CLI for {system} {machine}."}
    if name == "linux":
        lib, version = platform.libc_ver()
        parts = tuple(int(p) for p in version.split(".")[:2]) if version.replace(".", "").isdigit() else ()
        if lib != "glibc" or parts < (2, 39):
            return {"target": None, "reason": "ModRetro's Chromatic CLI needs GNU/Linux with glibc 2.39 or newer "
                                              f"(found {lib or 'unknown libc'} {version})."}
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


def device_cli_status() -> dict:
    """Passive. Never downloads, never runs the vendor executable."""
    host = host_target()
    answer = {"state": "missing", "target": host["target"], "version": None, "location": None,
              "source": "ModRetro npm packages (@modretro/chromatic-cli-*)", "terms": VENDOR_TERMS_URL,
              "needed_for": "device discovery, streaming, capture and cartridge flashing only"}
    if host["target"] is None:
        answer.update(state="unsupported", detail=host["reason"])
        return answer
    selection = paths.select_engine()
    if selection["prepared"]:
        receipt = read_receipt() or {}
        answer.update(state="installed", version=receipt.get("cli_version"),
                      location=str(selection["root"] / CLI_DIR / receipt.get("executable", "")),
                      installed_at=receipt.get("installed_at"))
    elif all((paths.ENGINE_ROOT / rel).is_file() for rel in paths.VENDOR_ARCHIVES):
        answer.update(state="bundled", detail="This copy of the plugin still carries the packed vendor archive.")
    elif selection.get("prepared_problem"):
        answer.update(detail="An earlier install no longer verifies and is ignored: " + selection["prepared_problem"])
    return answer


@contextmanager
def _lock():
    paths.DEPS_ROOT.mkdir(mode=0o755, parents=True, exist_ok=True)
    handle = open(paths.DEPS_ROOT / ".provision.lock", "a+")
    try:
        try:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:
            pass
        except OSError:
            raise ProvisionError("BUSY", "Another hermretro setup is running. Wait for it to finish.")
        yield
    finally:
        handle.close()


def _download(package: dict, opener=urllib.request.urlopen) -> bytes:
    limit = int(package["bytes"])
    request = urllib.request.Request(package["url"], headers={"User-Agent": f"hermretro/{paths.PLUGIN_VERSION}"})
    try:
        with opener(request, timeout=120) as response:
            data = response.read(limit + 1)
    except OSError as error:
        raise ProvisionError("DOWNLOAD_FAILED", f"Could not download {package['name']} from the npm registry: {error}")
    if len(data) != limit or hashlib.sha256(data).hexdigest() != package["sha256"]:
        raise ProvisionError("CHECKSUM_MISMATCH", f"{package['name']} {package['version']} from the npm registry does not "
                                                  "match the pinned size and SHA-256. Nothing was installed.")
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


def _node(script: str, *args: str, cwd: Path) -> dict:
    node = paths.find_node()
    if not node["ok"]:
        raise ProvisionError("NODE_REQUIRED", f"Node.js {node['required']} or newer is required.")
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "USER", "LOGNAME", "TMPDIR", "SYSTEMROOT")
           if key in os.environ}
    done = subprocess.run([node["path"], "--input-type=module", "-e", script, *args], cwd=str(cwd), env=env,
                          capture_output=True, text=True, timeout=120)
    if done.returncode != 0:
        raise ProvisionError("ENGINE_REFUSED", (done.stderr or done.stdout).strip().splitlines()[-1][:400]
                             if (done.stderr or done.stdout).strip() else "The engine's own check failed.")
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
        raise ProvisionError("TERMS_NOT_ACCEPTED",
                             "ModRetro's Chromatic CLI is proprietary software downloaded from ModRetro. Install it "
                             f"only after the user agrees to ModRetro's terms ({VENDOR_TERMS_URL}).")
    host = host_target()
    if host["target"] is None:
        raise ProvisionError("UNSUPPORTED_HOST", host["reason"])
    target = host["target"]
    bundled = paths.verify_engine()
    if not bundled["verified"]:
        raise ProvisionError("ENGINE_NOT_VERIFIED", "The bundled engine does not match its manifest: " + bundled["detail"])
    pins = _pins(target)
    exe_rel = pins["executable"]["path"]          # e.g. linux-x64-gnu/bin/chromatic-cli
    notice_rel = pins["notice"]["path"]
    with _lock():
        archive_bytes = _download(pins["package"], opener)
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
            executable = _member(archive, "package/" + exe_rel.split("/", 1)[1], pins["executable"])
            notice = _member(archive, "package/" + notice_rel.split("/", 1)[1], pins["notice"])

        stage = paths.DEPS_ROOT / f"engine.staging-{os.getpid()}"
        shutil.rmtree(stage, ignore_errors=True)
        skipped = {str(paths.ENGINE_ROOT / rel) for rel in paths.VENDOR_ARCHIVES}
        try:
            shutil.copytree(paths.ENGINE_ROOT, stage, symlinks=False,
                            ignore=lambda folder, names: [n for n in names
                                                          if str(Path(folder) / n) in skipped or n == "__pycache__"])
            for rel, data, mode in ((exe_rel, executable, int(pins["executable"]["mode"], 8)),
                                    (notice_rel, notice, int(pins["notice"]["mode"], 8))):
                destination = stage / CLI_DIR / rel
                destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                with open(destination, "xb") as handle:
                    handle.write(data)
                os.chmod(destination, mode)

            manifest = json.loads((paths.ENGINE_ROOT / "package.json").read_text())
            manifest.pop("bundledChromaticFormat", None)
            manifest["bundledChromaticTarget"] = target
            package_json = (json.dumps(manifest, indent=2) + "\n").encode()
            (stage / "package.json").write_bytes(package_json)
            os.chmod(stage / "package.json", 0o644)

            runtime = json.dumps((stage / "scripts" / "chromatic-runtime.mjs").as_uri())
            artwork = _node(_UNPACK_ARTWORK % {"runtime": runtime}, str(stage / "assets" / "devices"), cwd=stage)
            _tighten(stage)
            _node(_RESOLVE % {"runtime": runtime}, cwd=stage)   # the engine's own admission, before the swap

            previous = None
            if paths.PREPARED_ENGINE.exists():
                previous = paths.DEPS_ROOT / f"engine.old-{int(time.time())}-{os.getpid()}"
                os.replace(paths.PREPARED_ENGINE, previous)
            os.replace(stage, paths.PREPARED_ENGINE)
            if previous is not None:
                shutil.rmtree(previous, ignore_errors=True)
        finally:
            shutil.rmtree(stage, ignore_errors=True)

        added = {f"{CLI_DIR}/{exe_rel}": pins["executable"]["sha256"],
                 f"{CLI_DIR}/{notice_rel}": pins["notice"]["sha256"],
                 **{f"assets/devices/{name}": digest for name, digest in artwork.items()}}
        receipt = {
            "schema": 1, "engine_version": paths.ENGINE_VERSION, "target": target, "cli_version": pins["version"],
            "package": pins["package"]["name"], "url": pins["package"]["url"],
            "archive_sha256": pins["package"]["sha256"], "executable": exe_rel,
            "package_json_sha256": hashlib.sha256(package_json).hexdigest(), "added": added,
            "vendor_terms": VENDOR_TERMS_URL, "vendor_terms_accepted": True,
            "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        temporary = paths.DEVICE_CLI_RECEIPT.with_suffix(".tmp")
        temporary.write_text(json.dumps(receipt, indent=2) + "\n")
        os.replace(temporary, paths.DEVICE_CLI_RECEIPT)

    selection = paths.select_engine()
    if not selection["prepared"]:
        raise ProvisionError("VERIFY_FAILED", "The prepared engine did not verify after install: "
                             + str(selection.get("prepared_problem")))
    resolved = _node(_RESOLVE % {"runtime": json.dumps((paths.PREPARED_ENGINE / "scripts" / "chromatic-runtime.mjs").as_uri())},
                     cwd=paths.PREPARED_ENGINE)
    return {"installed": True, "target": target, "cli_version": resolved["version"],
            "executable": resolved["executable"], "executable_sha256": pins["executable"]["sha256"],
            "downloaded_from": pins["package"]["url"], "engine_root": str(paths.PREPARED_ENGINE),
            "receipt": str(paths.DEVICE_CLI_RECEIPT)}


# -- reuse of an existing download cache ---------------------------------------------------------

_SETUP_MARKER = ".gb-studio-setup.json"
_SEED_PARTS = ("downloads", "cache")
TOOLCHAIN_SEED_RECORD = "toolchain-seed.json"


def shared_setup_root() -> Path:
    """Where the engine keeps its toolchain when another app (ModRetro's Codex plugin) hosts it."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "modretro-chromatic"
    if system == "Windows":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "modretro-chromatic"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "modretro-chromatic"


def seed_toolchain_cache(source: Path | None = None) -> dict:
    """Copy another install's verified download cache into this plugin's own toolchain folder.

    Only the engine's download archives and package caches are copied, never an installed toolchain:
    the engine then installs from them into ``deps/toolchain`` exactly as it would after downloading,
    re-checking every archive against its pinned SHA-256. The other install is read, never changed.
    Happens only for a toolchain folder that does not exist yet."""
    destination = paths.setup_root()
    source = Path(source) if source is not None else shared_setup_root()
    if os.environ.get("GB_STUDIO_SETUP_ROOT"):
        return {"seeded": False, "reason": "a custom toolchain folder is configured"}
    if destination.exists():
        return {"seeded": False, "reason": "the toolchain folder already exists"}
    try:
        if source.resolve() == destination.resolve() or not source.is_dir() or source.is_symlink():
            return {"seeded": False, "reason": "no other install found"}
        marker = source / _SETUP_MARKER
        info = marker.lstat()
        owner = getattr(os, "getuid", lambda: info.st_uid)()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 4096 or info.st_uid != owner \
                or source.lstat().st_uid != owner \
                or json.loads(marker.read_text()).get("owner") != "codex-gb-studio-setup":
            return {"seeded": False, "reason": "the other install is not an engine-owned setup folder"}
        parts = [name for name in _SEED_PARTS if (source / name).is_dir() and not (source / name).is_symlink()]
        if "downloads" not in parts:
            return {"seeded": False, "reason": "the other install has no download cache"}
        paths.DEPS_ROOT.mkdir(mode=0o755, parents=True, exist_ok=True)
        stage = paths.DEPS_ROOT / f"toolchain.seeding-{os.getpid()}"
        shutil.rmtree(stage, ignore_errors=True)
        try:
            stage.mkdir(mode=0o700)
            for name in parts:
                shutil.copytree(source / name, stage / name, symlinks=True)
            shutil.copy2(marker, stage / _SETUP_MARKER)
            os.rename(stage, destination)   # fails if a toolchain folder appeared meanwhile
        finally:
            shutil.rmtree(stage, ignore_errors=True)
        record = {"seeded": True, "from": str(source), "parts": parts,
                  "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        (paths.DEPS_ROOT / TOOLCHAIN_SEED_RECORD).write_text(json.dumps(record, indent=2) + "\n")
        return record
    except (OSError, ValueError) as error:
        return {"seeded": False, "reason": f"could not reuse the other install's cache: {error}"}


def _seed_source() -> str | None:
    try:
        return json.loads((paths.DEPS_ROOT / TOOLCHAIN_SEED_RECORD).read_text()).get("from")
    except (OSError, ValueError):
        return None


def summary() -> dict:
    """Where this install keeps its dependencies. Passive."""
    return {"root": str(paths.DEPS_ROOT), "inside_plugin": paths.DEPS_ROOT.is_relative_to(paths.PLUGIN_ROOT),
            "toolchain_root": str(paths.setup_root()), "toolchain_cache_reused_from": _seed_source(),
            "engine_root": str(paths.select_engine()["root"]),
            "device_cli": device_cli_status()}


if __name__ == "__main__":
    # Read-only on purpose: installing goes through the chromatic_studio_device_cli tool, which
    # asks the person for approval.
    print(json.dumps(summary(), indent=2))

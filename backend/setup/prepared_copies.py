"""The prepared copies of the bundled engine (``paths.DEPS_ROOT``, beside the toolchain): which one a worker starts
from, making this engine's again from an earlier copy's device CLI when the engine changed, and removing the earlier
copies no worker runs in. Stdlib only; no Hermes imports.

A copy is made by ``provision._prepare``; this module only decides when, from which earlier copy, and what goes. It
reaches provision's helpers through the module (``provision._pins``, ``provision.lock`` ...), as the tests patch them
there (backend/setup/README.md, "Tests").
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ..system import paths
from . import copy_lease, provision
from .seed import _seed_source
from .trees import remove_tree

# -- keeping the prepared copy in step with the bundled engine -------------------------------------------
# Each copy is named by the engine it was made from (paths.ENGINE_IDENTITY) and never changed once made: a worker
# keeps reading from the copy it started in, even after the engine changes and a new copy appears beside it.

_COPY_NAME = re.compile(r"\d+\.\d+\.\d+(?:-[0-9a-f]{12})?")
_KINDS = ("executable", "notice")
_NOT_REUSABLE: set[tuple] = set()  # earlier copies looked at, by their files' stamps: not read again until one changes


def select_engine(node_path: str | None = None) -> dict:
    """``paths.select_engine``, after making the prepared copy for the bundled engine when the engine changed (an
    edit or a new version) and an earlier copy holds the CLI build this engine pins. Nothing is
    downloaded and nothing is asked: the user accepted ModRetro's terms for that CLI when they installed it.
    node_path: the Node the worker runs with, which decides the CLI build."""
    selection = paths.select_engine()
    if selection.get("prepared") or not selection["check"].get("verified") or not refresh_prepared_engine(node_path):
        return selection
    prune_prepared_copies()  # the earlier copies no worker runs in: this engine's copy now gives their CLI
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
        files = [copy / provision.CLI_DIR / pins[kind]["path"] for kind in _KINDS]
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
                and receipt.get("vendor_terms") == provision.VENDOR_TERMS_URL
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
    """Make the prepared copy for the bundled engine from an earlier copy's CLI files. False when there is none to
    reuse, another setup holds the lock, or the new copy does not verify (setup then offers the install). The earlier
    copies stay: a worker may still run in one (prune_prepared_copies removes those no worker runs in)."""
    if not any(paths.DEPS_ROOT.glob("device-cli-*.json")):  # never installed: nothing to reuse
        return False
    target = provision.host_target(node_path)["target"]
    if target is None:
        return False
    try:
        pins = provision._pins(target)
        with provision.lock():
            if paths.verify_prepared_engine()["verified"]:  # another process made it while this one waited
                return True
            found = _reusable_cli(target, pins)
            if found is None:
                return False
            executable, notice, receipt, source, key = found
            dates = {"installed_at": receipt.get("installed_at"), "refreshed_at": provision._now()}
            try:
                provision._prepare(target, pins, executable, notice, node_path=node_path, **dates)
            except provision.ProvisionError as error:
                if error.code not in ("ENGINE_CHANGED", "ENGINE_NOT_VERIFIED", "IN_USE"):  # not the CLI's fault
                    _NOT_REUSABLE.add(key)
                return False
            except (OSError, ValueError, KeyError):
                _NOT_REUSABLE.add(key)
                return False
            if not paths.verify_prepared_engine()["verified"]:
                if paths.engine_identity() == paths.ENGINE_IDENTITY:  # not because the engine changed since
                    _NOT_REUSABLE.add(key)
                return False
        return True
    except (provision.ProvisionError, OSError, ValueError, KeyError, StopIteration):  # BUSY included: tried again later
        return False


def prune_prepared_copies() -> int:
    """Remove every other engine's prepared copy that no worker runs in (its lease is free) and that holds the same CLI
    build as this engine's, with its receipt and lease, once this engine's copy verifies: it gives that CLI now. Returns how many went; none while another
    setup holds the lock or the engine on disk is not the one this process loaded (its copy may be the older one)."""
    if not paths.DEVICE_CLI_RECEIPT.is_file():  # no copy of this engine: nothing to keep, and no folder made for it
        return 0
    removed = 0
    try:
        with provision.lock():  # checked under it: a repair interrupted mid-swap leaves this engine's copy unverified
            if paths.engine_identity() != paths.ENGINE_IDENTITY or not paths.verify_prepared_engine()["verified"]:
                return 0  # an earlier copy may still have to give its CLI to this engine's
            cli = _cli_build(paths.DEVICE_CLI_RECEIPT)
            for receipt, copy in _earlier_copies():
                if copy == paths.PREPARED_ENGINE or _cli_build(receipt) != cli:
                    continue  # another checkout pinning another CLI build may still need its copy's
                try:
                    with copy_lease.unused(copy) as unused:
                        if unused:
                            remove_tree(copy)
                except OSError:  # its lease cannot be opened or locked (another user's, read-only): left as it is
                    continue
                if not copy.exists():  # all of it went: the receipt lists it for the next try until then
                    receipt.unlink(missing_ok=True)
                    copy_lease.path_for(copy).unlink(missing_ok=True)
                    removed += 1
            # A removal stopped before its receipt or lease file went leaves one without its copy.
            for receipt in paths.DEPS_ROOT.glob("device-cli-*.json"):
                _drop_without_copy(receipt, "engine-" + receipt.name.removeprefix("device-cli-").removesuffix(".json"))
            for lease in paths.DEPS_ROOT.glob("engine-*.lease"):
                _drop_without_copy(lease, lease.name.removesuffix(".lease"))
    except (
        provision.ProvisionError,
        OSError,
    ):  # BUSY, or the folder cannot be read: the next refresh or broker tries again
        pass
    return removed


def _cli_build(receipt: Path) -> tuple | None:
    """The CLI build a copy holds, by its receipt: (target, version), or None when the receipt is unreadable."""
    try:
        found = json.loads(receipt.read_text())
    except (OSError, ValueError):
        return None
    return (found.get("target"), found.get("cli_version")) if isinstance(found, dict) else None


def _drop_without_copy(leftover: Path, copy_name: str) -> None:
    copy = paths.DEPS_ROOT / copy_name
    if copy != paths.PREPARED_ENGINE and not copy.exists() and not copy.is_symlink():
        leftover.unlink(missing_ok=True)


def summary() -> dict:
    """Where this install keeps its dependencies. Never downloads (device_cli_status)."""
    selection = select_engine()
    return {
        "root": str(paths.DEPS_ROOT),
        "toolchain_root": str(paths.setup_root()),
        "toolchain_cache_reused_from": _seed_source(),
        "engine_root": str(selection["root"]),
        "device_cli": provision.device_cli_status(selection),
    }

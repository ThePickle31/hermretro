"""Preparing the machine and the studio profile: the toolchain install and its progress, removing downloads,
ModRetro's CLI (the chromatic_studio_device_cli tool and its approval), the hermretro profile, and the
Setup page RPCs.

Front door: what other features may use. Standard library only (the broker imports it): rpcs.py, tools.py,
hooks.py and studio_profile.py are never imported from here.
"""

from .progress import download_bytes, progress as install_progress
from .provision import folder_bytes, select_engine
from .seed import seed_toolchain_cache
from .recovery import (
    activity_mark,
    classify,
    explain,
    foreign_lock_hint,
    free_space,
    lock_path,
    lock_started,
    read_journal,
    recovered as recovered_install,
    settled,
    worker_left,
    write_journal,
)

__all__ = [
    "activity_mark",
    "classify",
    "download_bytes",
    "explain",
    "foreign_lock_hint",
    "folder_bytes",
    "free_space",
    "install_progress",
    "lock_path",
    "lock_started",
    "read_journal",
    "recovered_install",
    "seed_toolchain_cache",
    "select_engine",
    "settled",
    "worker_left",
    "write_journal",
]

EVENTS = {
    "setup.tools_removed": "Setup removed the downloaded tools; root=<the emptied download folder, str>",
    "setup.studio_profile_ready": "The hermretro studio profile was finished; profile=<the profile name, str>",
}

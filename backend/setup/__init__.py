"""Preparing the machine and the studio profile: the toolchain install and its progress, removing downloads,
ModRetro's CLI (the chromatic_studio_device_cli tool and its approval), the hermretro profile, and the
Setup page RPCs.

Front door: what other features may use. Standard library only (the broker imports it): rpcs.py, tools.py,
hooks.py and studio_profile.py are never imported from here.
"""

from .progress import download_bytes, progress as install_progress
from .provision import folder_bytes, seed_toolchain_cache
from .recovery import (
    activity_mark,
    explain,
    free_space,
    lock_path,
    read_journal,
    recovered as recovered_install,
    settled,
    write_journal,
)

__all__ = [
    "activity_mark",
    "download_bytes",
    "explain",
    "folder_bytes",
    "free_space",
    "install_progress",
    "lock_path",
    "read_journal",
    "recovered_install",
    "seed_toolchain_cache",
    "settled",
    "write_journal",
]

EVENTS = {
    "setup.tools_removed": "Setup removed the downloaded tools; root=<the emptied download folder, str>",
    "setup.studio_profile_ready": "The hermretro studio profile was finished; profile=<the profile name, str>",
}

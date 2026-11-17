"""Preparing the machine and the studio profile: the toolchain install and its progress, removing downloads,
ModRetro's CLI (the chromatic_studio_device_cli tool and its approval), the hermretro profile, and the
Setup page RPCs.

Front door: what other features may use. Standard library only (the broker imports it): rpcs.py, tools.py,
hooks.py and studio_profile.py are never imported from here.
"""

from .progress import directory_bytes, progress as install_progress
from .provision import seed_toolchain_cache

__all__ = ["directory_bytes", "install_progress", "seed_toolchain_cache"]

EVENTS = {
    "setup.tools_removed": "Setup removed the downloaded tools; root=<the emptied folder>",
    "setup.studio_profile_ready": "The hermretro studio profile was finished; profile=<its name>",
}

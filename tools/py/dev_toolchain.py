"""Where a developer's game toolchain lives: one folder for every checkout and worktree on this machine, made by
`python tools/ci/prepare_toolchain.py` and used by `python tools/check.py acceptance`.

It is the folder HERMRETRO_DEPS_ROOT would name (the toolchain goes in its `toolchain/`). It is neither the installed
hermretro's own `.cache`, which its page installs, nor under /tmp, which a restart empties.
"""

from __future__ import annotations

import os
from pathlib import Path

DEPS_ROOT = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "hermretro-dev" / "deps"

"""Entry point: python tools/retrodev <command> (see README.md beside this file)."""

import os
import sys
from pathlib import Path

# Python puts this folder first on the path; put tools/ there instead, so the package imports as `retrodev`
# and its module names (gc, status, ...) never shadow anything.
sys.path[0] = str(Path(__file__).resolve().parent.parent)

from retrodev.cli import main  # noqa: E402 — the path is set just above

try:
    sys.exit(main())
except BrokenPipeError:  # the reader went away (| head): stop quietly, as other command-line tools do
    os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    sys.exit(1)

"""Tests for the development CLI (tools/retrodev). The package imports as `retrodev`, as __main__.py does."""

import sys
from pathlib import Path

TOOLS = str(Path(__file__).resolve().parents[2] / "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

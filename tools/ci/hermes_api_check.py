"""Check that a Hermes still has every name hermretro uses from it (backend/hermes/api.py).

    "$HERMES_RUNTIME_PY" -I tools/ci/hermes_api_check.py      # in CI, with Hermes's own Python
    python tools/ci/hermes_api_check.py                       # locally, with a Python that can import Hermes

Run by CI against the oldest supported Hermes and nightly against the newest, so a rename in Hermes is caught
before users update.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.hermes import api as hermes_api  # noqa: E402


def main() -> int:
    gone = hermes_api.missing()
    if gone:
        print("this Hermes lacks: " + ", ".join(gone), file=sys.stderr)
        print("FIX: follow the rename in backend/hermes/api.py (keep the old name working while the oldest "
              "supported Hermes still has it)", file=sys.stderr)
        return 1
    print(f"ok: all {len(hermes_api.USED)} Hermes names hermretro uses are present")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Every call the plugin makes to register itself, in order, pinned in registration.json.

What hermretro registers with Hermes (RPCs, tools and their toolset, skills, hooks, the prompt section) is
collected from each feature's declarations in backend/features.py order. This test keeps that list exactly as
recorded, order included, for the studio profile and for any other profile, so a reorganization cannot drop,
rename, duplicate or reorder a registration unnoticed.

An intended change (a new RPC, tool or hook): run
    python tests/repo/test_registration_snapshot.py --write
and commit registration.json with the change; its diff is the review.
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.backend.hermes.test_registration import Recorder, load_plugin  # noqa: E402

SNAPSHOT = Path(__file__).with_name("registration.json")


def record() -> dict:
    plugin = load_plugin()
    found = {}
    clean = {k: v for k, v in os.environ.items() if k != "HERMRETRO_EVERY_PROFILE"}
    with mock.patch.dict(os.environ, {**clean, "HERMRETRO_HOME": "/nonexistent-hermretro-home"}, clear=True):
        for profile in ("hermretro", "default"):
            ctx = Recorder(profile)
            plugin.register(ctx)
            found[profile] = ctx.order
    return found


class RegistrationSnapshot(unittest.TestCase):
    def test_registration_matches_the_snapshot(self):
        expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        found = record()
        for profile in expected:
            want = [json.dumps(entry, sort_keys=True) for entry in expected[profile]]
            got = [json.dumps(entry, sort_keys=True) for entry in found[profile]]
            self.assertEqual(
                got,
                want,
                f"\nWhat the plugin registers in the {profile!r} profile changed (order "
                "included). Hermes sees exactly this list.\nFIX: if the change is intended, run python "
                "tests/repo/test_registration_snapshot.py --write and commit tests/repo/registration.json; "
                "otherwise restore the declaration (backend/<feature>/rpcs.py, tools.py, hooks.py) or the "
                "order in backend/features.py",
            )


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        found = record()
        body = ",\n".join(
            f" {json.dumps(profile)}: [\n"
            + ",\n".join("  " + json.dumps(entry, sort_keys=True) for entry in entries)
            + "\n ]"
            for profile, entries in found.items()
        )
        SNAPSHOT.write_text("{\n" + body + "\n}\n", encoding="utf-8")
        print(f"wrote {SNAPSHOT.relative_to(ROOT)}")
    else:
        unittest.main()

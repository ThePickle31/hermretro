"""Source files stay small enough to read (tools/layout.toml [size], with its listed [exceptions]).

Warnings (printed, never failing) mark what should be fixed soon: files over the warning size and every
deliberate exception (``hermretro: allow`` comments, tests/repo/allowances.py).

Run alone: python -m unittest tests.repo.test_layout
"""

import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.repo import allowances  # noqa: E402 - the repository root goes on sys.path first

LAYOUT = tomllib.loads((ROOT / "tools" / "layout.toml").read_text(encoding="utf-8"))


def warn(message: str) -> None:
    print("layout warning: " + message, file=sys.stderr)


def files() -> list[str]:
    """What a commit of this tree would hold: tracked files plus new files git does not ignore."""
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode()
    return sorted(name for name in out.split("\0") if name and (ROOT / name).is_file())


def measured(name: str) -> bool:
    size = LAYOUT["size"]
    return (
        name.endswith(tuple(size["extensions"]))
        and not name.startswith(tuple(size["exempt"]))
        and not (name.startswith("engine/pins/") and name.endswith(".json"))
    )


class Layout(unittest.TestCase):
    def test_source_files_stay_readable(self):
        size, exceptions = LAYOUT["size"], LAYOUT.get("exceptions", {})
        too_big = []
        for name in filter(measured, files()):
            lines = (ROOT / name).read_text(encoding="utf-8", errors="replace").count("\n")
            if lines > size["fail"] and name not in exceptions:
                too_big.append(f"{name}: {lines} lines")
            elif lines > size["warn"]:
                warn(
                    f"{name} has {lines} lines (warning above {size['warn']}, failure above {size['fail']})"
                    + (f"; allowed: {exceptions[name]}" if name in exceptions else "")
                )
        missing = [name for name in exceptions if not (ROOT / name).is_file()]
        self.assertEqual(
            missing, [], "tools/layout.toml [exceptions] names files that no longer exist\nFIX: remove those lines"
        )
        self.assertEqual(
            too_big,
            [],
            f"\nSource files over {size['fail']} lines are hard to review and usually "
            "hold more than one concern:\n  " + "\n  ".join(too_big) + "\nFIX: split the file by "
            "concern inside its feature folder; if it must stay whole, add it to [exceptions] in "
            "tools/layout.toml with the reason",
        )

    def test_every_allowance_has_a_reason_and_stays_visible(self):
        found = allowances.in_files(ROOT, files())
        allowances.warn(found)
        problems = [item.problem() for item in found if item.problem()]
        self.assertEqual(
            problems,
            [],
            "\nAn exception to a structure rule needs its reason, so the next person "
            "knows whether it still holds:\n  " + "\n  ".join(problems) + "\nFIX: write it as "
            "'# hermretro: allow <rule> — <reason>' (rules: " + ", ".join(sorted(allowances.RULES)) + ")",
        )


if __name__ == "__main__":
    unittest.main()

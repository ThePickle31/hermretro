"""Nothing personal is written into the repository.

Every location is computed at run time (backend/system/paths.py), so the plugin works for any user on Linux and
macOS. A hard-coded home folder, user id or a maintainer's machine or profile name works only on one computer and
leaks who built it. Test fixtures use the neutral users ``u`` and ``you``.

Run alone: python -m unittest tests.repo.test_portable
"""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_USERS = {"u", "you"}
# Vendored or generated files are not ours to change here.
SKIPPED = ("engine/", "desktop/plugin.js", "player/frame-shim.js", "player/web/", "tools/npm/")
HOME = re.compile(r"(?<![\w.#/-])/(?:home|Users)/([A-Za-z0-9._-]+)")
RUNTIME = re.compile(r"/run/user/\d+")
# Assembled so this file does not match itself.
# The public GitHub account that owns the repository (in its URLs) is not personal data.
NAMES = re.compile("|".join(["the" + r"pickle(?!31)", "dillon" + "lille", "lille" + "haug", "hermretro" + "-development"]),
                   re.I)


class Portable(unittest.TestCase):
    def test_no_personal_paths_or_names(self):
        out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                             capture_output=True, check=True).stdout.decode()
        hits = []
        for name in sorted(filter(None, out.split("\0"))):
            path = ROOT / name
            if name.startswith(SKIPPED) or not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for number, line in enumerate(text.splitlines(), 1):
                found = [m.group(0) for m in HOME.finditer(line) if m.group(1) not in FIXTURE_USERS]
                found += RUNTIME.findall(line) + NAMES.findall(line)
                hits += [f"{name}:{number}: {item}" for item in found]
        self.assertEqual(hits, [], "\nA personal home folder, user id or name only works on one computer and "
                         "leaks who built it:\n  " + "\n  ".join(hits[:40]) + "\nFIX: compute the location at run "
                         "time (backend/system/paths.py, Path.home(), tempfile), use the fixture users u or you in "
                         "tests, and keep personal settings in git-ignored local files")


if __name__ == "__main__":
    unittest.main()

"""Page sources never climb a folder: imports across folders use the aliases bundle.mjs declares.

The generated files themselves (`desktop/plugin.js`, `player/frame-shim.js`) are checked by
`node tools/bundle/bundle.mjs --check`, which runs as the fast `bundle` check: it owns the banner
hashes, the loader's import list, the scanner limits and the published-folder rules.
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "page"
CLIMBS = ".." + "/"


class PageSources(unittest.TestCase):
    def test_no_source_path_climbs_a_folder(self):
        # Imports across folders use the aliases in tools/bundle/bundle.mjs (#app/, #pages/, ...).
        offenders = [
            path.relative_to(ROOT).as_posix()
            for path in SOURCE.rglob("*.js")
            if CLIMBS in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()

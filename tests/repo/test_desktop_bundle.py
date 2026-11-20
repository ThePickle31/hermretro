"""The desktop half and the player frame shim are built, and the built files are what ship.

``desktop/plugin.js`` and ``player/frame-shim.js`` are generated from ``page/`` by
``tools/bundle/bundle.mjs`` and committed, because installing a plugin runs no build. These tests need neither
Node nor esbuild: each banner records a hash of the sources and a hash of the file's own body, so an
output that was not rebuilt after a source change, or that someone edited by hand, fails here. They
also hold the bundle to what Hermes Desktop's loader and the install scanner accept (the same rules
``node tools/bundle/bundle.mjs --check`` applies).
"""

import hashlib
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "desktop" / "plugin.js"
FRAME_SHIM = ROOT / "player" / "frame-shim.js"
SOURCE = ROOT / "page"
# The folders each banner's sources hash covers: what that output bundles (the `sources` of its target in
# tools/bundle/bundle.mjs, whose build fails when an output bundles a file outside them). Per output, so a
# page-only edit restamps desktop/plugin.js and leaves the frame shim alone.
SOURCES = {"desktop/plugin.js": ["page"], "player/frame-shim.js": ["page/frame", "page/shared"]}
# Modules and the art they import; dotfiles and editor leftovers are not hashed (tools/bundle/lint.mjs).
SOURCE_SUFFIXES = {".js", ".png"}
REBUILD = "run: node tools/bundle/bundle.mjs"
BANNER = re.compile(
    r"\A/\*\*\n(?: \*[^\n]*\n)*? \* build: esbuild (\S+)\n \* sources: sha256 ([0-9a-f]{64})\n"
    r" \* body: sha256 ([0-9a-f]{64})\n \*/\n"
)
# The only specifiers the app's loader resolves (apps/desktop/src/sdk/runtime.ts).
ALLOWED_IMPORTS = ["@hermes/plugin-sdk", "react", "react/jsx-runtime"]
IMPORT = re.compile(r'^import\s(?:[^;]*?\sfrom\s+)?"([^"]+)";$', re.M)
# Hermes's install scanner notes a single file over 1024 KB.
MAX_BYTES = 1_000_000
MAX_LINE = 2_000
# The characters the scanner treats as hidden text, and a path that climbs folders; both are
# assembled here so this file does not contain what it looks for.
INVISIBLE = "".join(
    map(
        chr,
        [
            0x200B,
            0x200C,
            0x200D,
            0x2060,
            0x2062,
            0x2063,
            0x2064,
            0xFEFF,
            *range(0x202A, 0x202F),
            *range(0x2066, 0x206A),
        ],
    )
)
CLIMBS_TWICE = ".." + "/.."
CLIMBS = ".." + "/"
# Constructs Hermes's admission lint refuses in a desktop plugin (hermes_cli/plugin_validate_desktop.py).
REFUSED = {
    "code evaluated from a string": re.compile(r"(?<![\w$.])" + "ev" + r"al\(|\bnew\s+Function\("),
    "a dynamic import": re.compile(r"\bimport\("),
    "an injected script": re.compile(r"createElement\(\s*['\"]script['\"]\s*\)|<" + r"script\b"),
    "a reach into the preview webview": re.compile(r"\(\s*[`'\"]webview\b"),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_files(folder: str, root: Path = ROOT) -> list[str]:
    base = root / folder
    return [
        path.relative_to(root).as_posix()
        for path in base.rglob("*")
        if path.is_file()
        and path.suffix in SOURCE_SUFFIXES
        and not any(part.startswith(".") for part in path.relative_to(base).parts)
    ]


def sources_hash(output: str, root: Path = ROOT) -> str:
    """The digest tools/bundle/bundle.mjs writes for `output`: over its source folders and the build tool,
    path, a zero byte, then the bytes, in path order."""
    files = [name for folder in SOURCES[output] for name in source_files(folder, root)]
    digest = hashlib.sha256()
    for rel in sorted([*files, "tools/bundle/bundle.mjs"]):
        digest.update(rel.encode() + b"\0" + (root / rel).read_bytes())
    return digest.hexdigest()


class DesktopBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = BUNDLE.read_bytes()
        cls.text = cls.data.decode("utf-8")

    def banner(self) -> re.Match:
        found = BANNER.match(self.text)
        if found is None:
            self.fail(f"desktop/plugin.js has no build banner; {REBUILD}")
        return found

    def test_the_bundle_was_not_edited_by_hand(self):
        banner = self.banner()
        body = self.text[banner.end() :].encode("utf-8")
        self.assertEqual(sha256(body), banner.group(3), f"edit page/ instead, then {REBUILD}")

    def test_the_bundle_was_built_from_the_current_sources(self):
        self.assertEqual(
            sources_hash("desktop/plugin.js"), self.banner().group(2), f"desktop/plugin.js is stale; {REBUILD}"
        )

    def test_the_bundle_imports_exactly_what_the_loader_allows(self):
        self.assertEqual(sorted(IMPORT.findall(self.text)), ALLOWED_IMPORTS)

    def test_the_bundle_stays_readable_and_inside_the_scanner_limits(self):
        self.assertLessEqual(len(self.data), MAX_BYTES)
        self.assertLessEqual(max(map(len, self.text.split("\n"))), MAX_LINE)
        self.assertEqual([char for char in INVISIBLE if char in self.text], [])
        self.assertNotIn(CLIMBS_TWICE, self.text)

    def test_the_bundle_stays_inside_the_sdk_surface(self):
        found = [what for what, pattern in REFUSED.items() if pattern.search(self.text)]
        self.assertEqual(found, [])

    def test_only_the_bundle_is_published(self):
        # The app copies desktop/ as it stands and lints every script in it; a plugin.js at the
        # repository root would be taken for the desktop half instead.
        self.assertEqual([path.name for path in BUNDLE.parent.iterdir()], ["plugin.js"])
        self.assertFalse(BUNDLE.is_symlink())
        self.assertFalse((ROOT / "plugin.js").exists())

    def test_no_source_path_climbs_a_folder(self):
        # Imports across folders use the aliases in tools/bundle/bundle.mjs (#app/, #pages/, ...).
        offenders = [
            path.relative_to(ROOT).as_posix()
            for path in SOURCE.rglob("*.js")
            if CLIMBS in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])


class FrameShimTests(unittest.TestCase):
    """The script the player frame runs first, inlined by the player backend (backend/player/)."""

    def test_the_shim_is_current_and_was_not_edited_by_hand(self):
        text = FRAME_SHIM.read_text(encoding="utf-8")
        banner = BANNER.match(text)
        self.assertIsNotNone(banner, f"player/frame-shim.js has no build banner; {REBUILD}")
        self.assertEqual(
            sha256(text[banner.end() :].encode("utf-8")), banner.group(3), f"edit page/frame/ instead, then {REBUILD}"
        )
        self.assertEqual(
            sources_hash("player/frame-shim.js"), banner.group(2), f"player/frame-shim.js is stale; {REBUILD}"
        )

    def test_the_shim_imports_nothing(self):
        self.assertEqual(IMPORT.findall(FRAME_SHIM.read_text(encoding="utf-8")), [])


class SourcesHashTests(unittest.TestCase):
    """Each output's banner hashes only what it bundles."""

    def test_a_page_edit_restamps_only_the_desktop_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in ("page/pages/home", "page/frame", "page/shared", "tools/bundle"):
                (root / folder).mkdir(parents=True)
            for name in ("page/index.js", "page/pages/home/home-page.js", "page/frame/index.js", "page/shared/a.js"):
                (root / name).write_text("// one\n")
            (root / "tools/bundle/bundle.mjs").write_text("// tool\n")
            before = {output: sources_hash(output, root) for output in SOURCES}
            (root / "page/pages/home/home-page.js").write_text("// two\n")
            changed = [output for output in SOURCES if sources_hash(output, root) != before[output]]
            self.assertEqual(changed, ["desktop/plugin.js"])
            (root / "page/shared/a.js").write_text("// two\n")
            changed = [output for output in SOURCES if sources_hash(output, root) != before[output]]
            self.assertEqual(changed, ["desktop/plugin.js", "player/frame-shim.js"])


if __name__ == "__main__":
    unittest.main()

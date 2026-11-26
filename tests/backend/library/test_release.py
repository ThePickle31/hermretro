"""What a publish of a game holds and records (backend/library/release.py): the files, the release's
version and changelog, the publish and install records, and changes since a publish.

Run alone: python -m unittest tests.backend.library.test_release
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.library import game_card, layout, release  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home, make_project  # noqa: E402 - the repository root goes on sys.path first

REPO = "https://example.invalid/space-game"


class Release(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        self.root = make_project(self.home.base, "Release Game")
        layout.ensure(self.root)

    def test_files_lists_the_game_alone_or_with_its_source(self):
        (self.root / "assets" / "sprites").mkdir(parents=True)
        (self.root / "assets" / "sprites" / "hero.png").write_bytes(b"png")
        (self.root / "assets" / ".DS_Store").write_bytes(b"")
        (self.root / "assets" / "link.png").symlink_to(self.root / "assets" / "sprites" / "hero.png")
        outside = self.home.base / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("key")
        (self.root / "art").symlink_to(outside)
        (self.root / "docs" / "game").mkdir(parents=True)
        (self.root / "docs" / "game" / "GAME-BRIEF.md").write_text("brief")
        (self.root / "captures").mkdir()
        (self.root / "captures" / "shot.png").write_bytes(b"png")
        game = [".gitignore", "CHANGELOG.md", "README.md", "build/game.gbc", "cover.png", "game.json"]
        self.assertEqual(release.files(self.root, source=False), game)
        self.assertEqual(
            release.files(self.root, source=True),
            sorted(game + ["release-game.gbsproj", "project/scene.gbsres", "assets/sprites/hero.png"]),
            "no hidden file, no link, nothing through a linked folder, and not the agent's plans in docs/",
        )

    def test_a_release_is_prepared_once_and_recorded_after_the_push(self):
        self.assertIsNone(release.unpublished_changes(self.root))
        for _attempt in range(2):  # a failed push is retried: one changelog entry
            release.prepare_release(self.root, "0.2.0", "First levels.")
        changelog = (self.root / "CHANGELOG.md").read_text()
        self.assertRegex(changelog, r"^# Changelog\n\n## 0\.2\.0 \(\d{4}-\d{2}-\d{2}\)\n\nFirst levels\.\n$")
        self.assertEqual(game_card.load(self.root)["gameVersion"], "0.2.0")
        self.assertIn("- Version: 0.2.0", (self.root / "README.md").read_text())
        self.assertIsNone(release.published(self.root), "nothing is recorded before the push succeeds")
        record = release.record_publish(self.root, repo=REPO, commit="c" * 40, version="0.2.0", source=False)
        self.assertEqual(release.published(self.root), record)
        self.assertEqual(
            (record["source"], record["payload"]), (False, release.payload_digest(self.root, source=False))
        )
        self.assertFalse(release.unpublished_changes(self.root))
        (self.root / "project" / "scene.gbsres").write_text('{"changed": true}')
        self.assertFalse(release.unpublished_changes(self.root), "a source edit is not in a game-only publish")
        game_card.set_fields(self.root, {"tagline": "A new tagline for the shelf."})
        self.assertTrue(release.unpublished_changes(self.root), "the card is part of every publish")
        release.prepare_release(self.root, "0.3.0")
        self.assertRegex((self.root / "CHANGELOG.md").read_text(), r"^# Changelog\n\n## 0\.3\.0 .*\n\n## 0\.2\.0 ")
        with self.assertRaises(ValueError):
            release.record_publish(self.root, repo=REPO, commit="c", version="1.0", source=True)

    def test_an_install_records_where_it_came_from(self):
        self.assertIsNone(release.installed(self.root))
        source = {"canonical": REPO, "url": REPO + ".git", "ref": None, "subdir": None}
        record = release.record_install(
            self.root,
            source=source,
            commit="d" * 40,
            mode="game+source",
            rom={"path": "build/game.gbc", "sha256": "0" * 64},
        )
        self.assertEqual(release.installed(self.root), record)
        self.assertNotIn(".hermretro/install.json", release.files(self.root, source=True))
        self.assertIs(release.local_edits(self.root), False)
        (self.root / "README.md").write_text(layout.readme(self.root, {"title": "Renamed"}))  # hermretro's own file
        self.assertIs(release.local_edits(self.root), False)
        (self.root / "project" / "scene.gbsres").write_text('{"edited": true}')
        self.assertIs(release.local_edits(self.root), True)
        with self.assertRaises(ValueError):
            release.record_install(
                self.root,
                source=source,
                commit="d" * 40,
                mode="source",
                rom={"path": "build/game.gbc", "sha256": "0" * 64},
            )

    def test_next_version(self):
        self.assertEqual(
            [release.next_version("1.2.3", part) for part in ("patch", "minor", "major")], ["1.2.4", "1.3.0", "2.0.0"]
        )
        self.assertEqual(release.next_version("999999.0.9"), "999999.0.10")
        self.assertEqual(release.next_version("nonsense"), "0.1.0")
        with self.assertRaises(ValueError):
            release.next_version("1.0.0", "huge")


if __name__ == "__main__":
    unittest.main()

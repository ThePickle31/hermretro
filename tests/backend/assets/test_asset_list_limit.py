"""The assets RPC's list cap (backend/assets/rpcs.py ``ASSET_LIST_LIMIT``, 400 items, the cover included) and what its
``truncated`` means: true only when the list stopped at the cap with items left out; false at exactly the cap.

Run alone: python -m unittest tests.backend.assets.test_asset_list_limit
"""

import unittest
from pathlib import Path
from unittest import mock

from backend.assets import rpcs as assets_rpcs
from backend.hermes import host
from backend.library import Registry
from tests.support import add_images, isolated_home, make_library_game


class AssetListLimit(unittest.TestCase):
    def setUp(self):
        self.game, self.root = make_library_game(isolated_home(self), "Cap Field")  # its card brings the cover

    def listed(self, images):
        add_images(self.root, images)
        answer = assets_rpcs.rpc_assets(None)({"game": self.game})
        self.assertTrue(answer["ok"], answer)
        return answer

    def test_an_ordinary_game_lists_every_picture(self):
        answer = self.listed(4)
        self.assertEqual([item["name"] for item in answer["assets"]], ["Cover", *(f"image{n:03d}" for n in range(4))])
        self.assertIs(answer["truncated"], False)

    def test_one_below_the_cap_is_not_truncated(self):
        answer = self.listed(398)
        self.assertEqual(len(answer["assets"]), 399)
        self.assertIs(answer["truncated"], False)

    def test_exactly_the_cap_lists_all_and_is_not_truncated(self):
        answer = self.listed(399)  # the cover and 399 images: the list ends at the cap, nothing is left out
        self.assertEqual(len(answer["assets"]), 400)
        self.assertEqual(answer["assets"][-1]["name"], "image398")
        self.assertIs(answer["truncated"], False)

    def test_beyond_the_cap_stops_at_it(self):
        answer = self.listed(450)
        self.assertEqual(len(answer["assets"]), 400)
        self.assertEqual(answer["assets"][-1]["name"], "image398")
        self.assertIs(answer["truncated"], True)

    def test_the_walk_stops_before_the_next_subtree_and_loads_ownership_once(self):
        sprites = self.root / "assets" / "sprites"
        first, later = sprites / "000", sprites / "zzz"
        first.mkdir(parents=True)
        later.mkdir()
        (first / "nested.png").write_bytes(b"picture")
        (sprites / "000.png").write_bytes(b"picture")
        (later / "later.png").write_bytes(b"picture")
        with (
            mock.patch.object(assets_rpcs, "ASSET_LIST_LIMIT", 2),
            mock.patch.object(Registry, "load", autospec=True, side_effect=Registry.load) as load,
            mock.patch.object(Path, "iterdir", autospec=True, side_effect=Path.iterdir) as iterdir,
        ):
            answer = assets_rpcs.rpc_assets(None)({"game": self.game})
        self.assertTrue(answer["ok"], answer)
        self.assertEqual(
            [item["relative"] for item in answer["assets"]], ["cover.png", "assets/sprites/000/nested.png"]
        )
        self.assertIs(answer["truncated"], True)
        load.assert_called_once()
        walked = [call.args[0] for call in iterdir.call_args_list]
        self.assertIn(first, walked)
        self.assertNotIn(later, walked)

    def test_a_nested_games_art_cannot_fill_or_truncate_the_outer_list(self):
        add_images(self.root, 1)
        nested = self.root / "assets" / "sprites" / "Nested"
        add_images(nested, 2)
        self.assertIsNotNone(host._registry().upsert(str(nested)))
        with mock.patch.object(assets_rpcs, "ASSET_LIST_LIMIT", 2):
            answer = assets_rpcs.rpc_assets(None)({"root": str(self.root)})
        self.assertTrue(answer["ok"], answer)
        self.assertEqual([item["name"] for item in answer["assets"]], ["Cover", "image000"])
        self.assertIs(answer["truncated"], False)

    def test_listing_accepts_a_different_spelling_on_case_insensitive_filesystems(self):
        add_images(self.root, 1)
        alias = self.root.with_name(self.root.name.swapcase())
        if not alias.exists() or not alias.samefile(self.root):
            self.skipTest("the test filesystem is case-sensitive")
        answer = assets_rpcs.rpc_assets(None)({"root": str(alias)})
        self.assertTrue(answer["ok"], answer)
        self.assertEqual([item["relative"] for item in answer["assets"]], ["cover.png", "assets/sprites/image000.png"])


if __name__ == "__main__":
    unittest.main()

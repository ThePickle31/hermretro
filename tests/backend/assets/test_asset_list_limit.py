"""The assets RPC's list cap (backend/assets/rpcs.py ``ASSET_LIST_LIMIT``, 400 items, the cover included) and what its
``truncated`` means today: true once the list holds the cap, so also at exactly the cap with nothing left out; false
below it.

Run alone: python -m unittest tests.backend.assets.test_asset_list_limit
"""

import unittest

from backend.assets import rpcs as assets_rpcs
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

    def test_exactly_the_cap_lists_all_and_says_truncated(self):
        answer = self.listed(399)  # the cover and 399 images: nothing is left out, truncated is still true
        self.assertEqual(len(answer["assets"]), 400)
        self.assertEqual(answer["assets"][-1]["name"], "image398")
        self.assertIs(answer["truncated"], True)

    def test_beyond_the_cap_stops_at_it(self):
        answer = self.listed(450)
        self.assertEqual(len(answer["assets"]), 400)
        self.assertEqual(answer["assets"][-1]["name"], "image398")
        self.assertIs(answer["truncated"], True)


if __name__ == "__main__":
    unittest.main()

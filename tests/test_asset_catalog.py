"""Tests for local asset categorization and matching."""

import unittest

from blender_addon.cozyverse_builder.core.asset_catalog import categorize, match_assets, record_from_path


class AssetCatalogTests(unittest.TestCase):
    def test_categories_are_inferred_from_human_names(self):
        self.assertEqual(categorize("retro_lunar_rover"), "VEHICLE")
        self.assertEqual(categorize("tropical_palm_tree"), "VEGETATION")
        self.assertEqual(categorize("corner-coffee-shop"), "BUILDING")

    def test_matching_prefers_exact_prompt_terms_and_blend(self):
        records = [record_from_path("C:/assets/retro_lunar_rover.glb"), record_from_path("C:/assets/retro_lunar_rover.blend"), record_from_path("C:/assets/oak_tree.blend")]
        results = match_assets(records, "lunar rover", ("retro", "space"))
        self.assertEqual(results[0].extension, ".blend")
        self.assertEqual(len(results), 2)
        self.assertGreater(results[0].score, 0)

    def test_category_filter_is_respected(self):
        records = [record_from_path("C:/assets/city_car.glb"), record_from_path("C:/assets/city_house.blend")]
        results = match_assets(records, "city", (), "BUILDING")
        self.assertEqual([item.category for item in results], ["BUILDING"])


if __name__ == "__main__":
    unittest.main()

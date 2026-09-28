"""Unit tests for Style Studio presets and prompt enrichment."""

import unittest

from blender_addon.cozyverse_builder.core.style_spec import STYLE_PRESETS, style_items, styled_prompt


class StyleSpecTests(unittest.TestCase):
    def test_catalog_has_unique_complete_presets(self):
        items = style_items()
        self.assertGreaterEqual(len(items), 10)
        self.assertEqual(len(items), len({item[0] for item in items}))
        for preset in STYLE_PRESETS.values():
            self.assertEqual(len(preset.palette), 5)
            self.assertTrue(preset.directive and preset.avoid and preset.keywords)

    def test_retro_scifi_prompt_is_actionable(self):
        prompt = styled_prompt("Create a lunar cafe", "RETRO_SCIFI")
        self.assertIn("rounded modules", prompt)
        self.assertIn("Avoid:", prompt)
        self.assertIn("cyberpunk clutter", prompt)

    def test_unknown_style_falls_back_safely(self):
        self.assertIn("cozy handcrafted", styled_prompt("A village", "UNKNOWN"))


if __name__ == "__main__":
    unittest.main()

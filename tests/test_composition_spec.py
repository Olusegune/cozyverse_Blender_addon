"""Tests for deterministic procedural composition families."""

import unittest

from blender_addon.cozyverse_builder.core.composition_spec import PROFILES, layout_points, profile_for, prompt_seed


class CompositionSpecTests(unittest.TestCase):
    def test_all_scene_plan_families_have_distinct_profiles(self):
        self.assertEqual(len(PROFILES), 8)
        self.assertEqual(len({profile.architecture_form for profile in PROFILES.values()}), 8)

    def test_layout_is_deterministic_but_prompt_dependent(self):
        first = layout_points("lunar station", "SPACE_OUTPOST", 5, "PROPS")
        self.assertEqual(first, layout_points("lunar station", "SPACE_OUTPOST", 5, "PROPS"))
        self.assertNotEqual(first, layout_points("martian repair base", "SPACE_OUTPOST", 5, "PROPS"))

    def test_seed_and_fallback_are_stable(self):
        self.assertEqual(prompt_seed("Cafe", "CAFE"), prompt_seed("Cafe", "CAFE"))
        self.assertEqual(profile_for("UNKNOWN"), PROFILES["VILLAGE"])


if __name__ == "__main__":
    unittest.main()

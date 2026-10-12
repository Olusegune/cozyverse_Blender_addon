from __future__ import annotations

import unittest

from blender_addon.cozyverse_builder.core.story_spec import PRESETS, build_story_plan


class StorySpecTests(unittest.TestCase):
    def test_plan_is_deterministic_and_counts_keyframes(self):
        plan = build_story_plan("BUSY_MARKET", "CV_WORLD", 1, 120, 2, 4, 0, 2, 1)
        self.assertEqual(plan.midpoint, 60)
        self.assertEqual(plan.target_count, 8)
        self.assertEqual(plan.keyframe_count, 24)
        self.assertEqual(plan.fingerprint(), build_story_plan("BUSY_MARKET", "CV_WORLD", 1, 120, 2, 4, 0, 2, 1).fingerprint())

    def test_presets_have_distinct_motion_profiles(self):
        self.assertGreater(PRESETS["BUSY_MARKET"].character_motion, PRESETS["QUIET_MORNING"].character_motion)
        self.assertGreater(PRESETS["RAINY_EVENING"].precipitation_travel, 0.0)

    def test_invalid_range_and_preset_are_rejected(self):
        with self.assertRaises(ValueError):
            build_story_plan("UNKNOWN", "CV_WORLD", 1, 120, 0, 0, 0, 0)
        with self.assertRaises(ValueError):
            build_story_plan("QUIET_MORNING", "CV_WORLD", 120, 1, 0, 0, 0, 0)


if __name__ == "__main__":
    unittest.main()

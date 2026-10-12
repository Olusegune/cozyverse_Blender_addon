"""Tests for the renderer-independent CozyVerse scene plan."""

import json
import unittest

from blender_addon.cozyverse_builder.core.scene_plan import parse_plan, proposed_plan


class ScenePlanTests(unittest.TestCase):
    def test_space_prompt_creates_editable_outpost_plan(self):
        plan = proposed_plan("A retro sci-fi lunar service station", "RETRO_SCIFI")
        self.assertEqual(plan.world_type, "SPACE_OUTPOST")
        self.assertEqual(plan.architecture_count, 3)
        self.assertTrue(plan.include_road)
        self.assertEqual(parse_plan(plan.canonical_json()), plan)

    def test_nature_plan_avoids_forcing_a_road(self):
        plan = proposed_plan("A quiet forest and winding river", "STORYBOOK")
        self.assertEqual(plan.world_type, "NATURE")
        self.assertFalse(plan.include_road)
        self.assertGreater(plan.vegetation_count, plan.architecture_count)

    def test_invalid_counts_are_rejected(self):
        payload = json.loads(proposed_plan("Village", "COZY_VILLAGE").canonical_json())
        payload["prop_count"] = 1000
        with self.assertRaises(ValueError):
            parse_plan(json.dumps(payload))


if __name__ == "__main__":
    unittest.main()

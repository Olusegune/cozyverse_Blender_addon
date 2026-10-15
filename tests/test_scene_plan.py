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

    def test_water_and_hills_are_read_from_the_description(self):
        lake = proposed_plan("A cozy cafe beside a quiet lake in the hills", "COZY_VILLAGE")
        self.assertEqual((lake.water, lake.terrain, lake.base_shape), ("LAKE", "HILLS", "ROUNDED_RECT"))
        sea = proposed_plan("A harbor village on a little island in the sea", "STORYBOOK")
        self.assertEqual((sea.water, sea.world_type, sea.base_shape), ("SEA", "VILLAGE", "ISLAND"))
        dry = proposed_plan("A sunny market square", "COZY_VILLAGE")
        self.assertEqual((dry.water, dry.terrain), ("NONE", "FLAT"))
        self.assertEqual(parse_plan(sea.canonical_json()), sea)

    def test_island_alone_is_scenery_but_with_a_village_it_is_a_place(self):
        self.assertEqual(proposed_plan("A tiny island", "STORYBOOK").world_type, "NATURE")
        self.assertEqual(proposed_plan("A fishing village on an island", "STORYBOOK").world_type, "VILLAGE")

    def test_older_plans_without_water_still_load(self):
        payload = json.loads(proposed_plan("Village", "COZY_VILLAGE").canonical_json())
        del payload["water"], payload["terrain"]
        plan = parse_plan(json.dumps(payload))
        self.assertEqual((plan.water, plan.terrain), ("NONE", "FLAT"))

    def test_unknown_water_is_rejected(self):
        payload = json.loads(proposed_plan("Village", "COZY_VILLAGE").canonical_json())
        payload["water"] = "LAVA"
        with self.assertRaises(ValueError):
            parse_plan(json.dumps(payload))


if __name__ == "__main__":
    unittest.main()

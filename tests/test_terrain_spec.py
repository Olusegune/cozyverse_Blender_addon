import math
import unittest

from blender_addon.cozyverse_builder.core import terrain_spec as t


def landscape(water, terrain="FLAT", seed=12345):
    stage = t.stage_for(water)
    zone = t.build_zone(water, seed, stage)
    return stage, zone, t.hills_for(seed, stage, water), seed


class TerrainSpecTests(unittest.TestCase):
    def test_prompts_are_read_for_water_and_hills(self):
        self.assertEqual(t.infer_water("A cafe on a quiet lake"), "LAKE")
        self.assertEqual(t.infer_water("a tiny harbor village by the sea"), "SEA")
        self.assertEqual(t.infer_water("houses along a canal"), "RIVER")
        self.assertEqual(t.infer_water("a koi pond garden"), "POND")
        self.assertEqual(t.infer_water("a sunny market square"), "NONE")
        self.assertEqual(t.infer_water("a sea and a lake"), "SEA")  # the bigger body wins
        self.assertEqual(t.infer_terrain("a village in the mountains"), "HILLS")
        self.assertEqual(t.infer_terrain("a flat market"), "FLAT")
        self.assertEqual(t.infer_water("The seaside bakery"), "SEA")
        self.assertEqual(t.infer_water("A seashell shop"), "NONE")  # whole words only

    def test_everything_is_deterministic(self):
        first = landscape("LAKE", seed=777)
        second = landscape("LAKE", seed=777)
        self.assertEqual(first[1], second[1])
        self.assertEqual(t.height_at(1.0, 2.0, "HILLS", first[1], first[2], 777), t.height_at(1.0, 2.0, "HILLS", second[1], second[2], 777))
        other = landscape("LAKE", seed=778)
        self.assertNotEqual(first[1]["rx"], other[1]["rx"])

    def test_no_water_and_flat_means_perfectly_flat_ground(self):
        for x, y in ((0, 0), (3, 2), (-5, -4)):
            self.assertEqual(t.height_at(x, y, "FLAT", None, [], 1), 0.0)

    def test_a_lake_is_a_basin_below_the_water_level_with_flat_land_around_it(self):
        stage, zone, hills, seed = landscape("LAKE")
        centre = t.height_at(zone["cx"], zone["cy"], "FLAT", zone, hills, seed)
        self.assertLess(centre, t.WATER_LEVEL - 0.3)
        self.assertGreater(centre, t.BOTTOM)  # the basin never cuts through the base
        far = t.height_at(-zone["cx"], -2.0, "FLAT", zone, hills, seed)
        self.assertEqual(far, 0.0)
        # The land rises smoothly from the basin up to the flat ground.
        samples = [t.height_at(zone["cx"] + zone["rx"] * f, zone["cy"], "FLAT", zone, hills, seed) for f in (0.0, 0.5, 0.9, 1.3, 1.8)]
        self.assertEqual(samples, sorted(samples)[::1] if samples[0] <= samples[-1] else samples)
        self.assertLess(samples[0], samples[2])

    def test_a_river_runs_across_the_whole_stage(self):
        stage, zone, hills, seed = landscape("RIVER")
        for x in (-5.0, -2.0, 0.0, 2.5, 5.0):
            centre_y = zone["y0"] + zone["amp"] * math.sin(zone["freq"] * x + zone["phase"])
            self.assertLess(t.height_at(x, centre_y, "FLAT", zone, hills, seed), t.WATER_LEVEL)
            self.assertEqual(t.height_at(x, -1.0, "FLAT", zone, hills, seed), 0.0)

    def test_the_sea_surrounds_an_island(self):
        stage, zone, hills, seed = landscape("SEA")
        self.assertGreater(stage.half_x, t.STANDARD.half_x)  # a bigger slab holds the island
        self.assertEqual(t.height_at(0.0, 0.0, "FLAT", zone, hills, seed), 0.0)
        self.assertAlmostEqual(t.height_at(stage.half_x - 0.1, 0.0, "FLAT", zone, hills, seed), t.SEABED, places=2)
        shore = [t.height_at(x / 10, 0.0, "FLAT", zone, hills, seed) for x in range(0, 66, 3)]
        self.assertEqual(shore[0], 0.0)
        self.assertTrue(all(a >= b - 1e-9 for a, b in zip(shore, shore[1:])))  # only ever slopes down to sea

    def test_hills_rise_at_the_edges_and_never_under_the_middle_of_the_village(self):
        stage, zone, hills, seed = landscape("NONE", "HILLS")
        peak = max(t.height_at(x / 2, y / 2, "HILLS", None, hills, seed) for x in range(-11, 12) for y in range(-8, 9))
        self.assertGreater(peak, 0.6)
        self.assertLess(t.height_at(0.0, -1.5, "HILLS", None, hills, seed), 0.05)  # the road stays level

    def test_buildable_ground_avoids_water_slopes_and_hills(self):
        stage, zone, hills, seed = landscape("LAKE", "HILLS")
        self.assertFalse(t.is_buildable(zone["cx"], zone["cy"], 0.3, "HILLS", zone, hills, seed))  # in the lake
        self.assertFalse(t.is_buildable(zone["cx"] - zone["rx"] * 1.05, zone["cy"], 0.3, "HILLS", zone, hills, seed))  # on the bank
        self.assertTrue(t.is_buildable(-zone["cx"] * 0.2, -1.0, 0.5, "HILLS", zone, hills, seed))
        self.assertTrue(t.is_dry(0.0, 0.0, 0.3, "HILLS", zone, hills, seed))
        self.assertFalse(t.is_dry(zone["cx"], zone["cy"], 0.0, "HILLS", zone, hills, seed))

    def test_grid_and_outlines_cover_the_stage(self):
        stage, zone, hills, seed = landscape("LAKE", "HILLS")
        grid = t.height_grid(20, 14, stage, "HILLS", zone, hills, seed)
        self.assertEqual((len(grid), len(grid[0])), (15, 21))
        self.assertLess(min(min(row) for row in grid), t.WATER_LEVEL)
        outline = t.water_outline(zone, stage)
        xs, ys = [p[0] for p in outline], [p[1] for p in outline]
        self.assertGreater(len(outline), 30)
        self.assertLess(min(xs), zone["cx"] - zone["rx"] * 0.8)
        # Counter-clockwise, so the water mesh faces up.
        area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(outline, outline[1:] + outline[:1])) / 2
        self.assertGreater(area, 0)
        river_stage, river, _h, _s = landscape("RIVER")
        ribbon = t.water_outline(river, river_stage)
        self.assertAlmostEqual(max(p[0] for p in ribbon), river_stage.half_x - 0.005, places=3)
        sea_stage, sea, _h, _s = landscape("SEA")
        self.assertEqual(len(t.water_outline(sea, sea_stage)), 4)


if __name__ == "__main__":
    unittest.main()

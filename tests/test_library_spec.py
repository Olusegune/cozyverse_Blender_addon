import json
import math
import unittest

from blender_addon.cozyverse_builder.core import library_spec as spec


class LibrarySpecTests(unittest.TestCase):
    def test_roles_are_guessed_from_names(self):
        self.assertEqual(spec.guess_role("tq Car Fiat 500"), "CAR")
        self.assertEqual(spec.guess_role("Palm tree 03"), "TREE")
        self.assertEqual(spec.guess_role("Street Lamp Classic"), "LAMP")
        self.assertEqual(spec.guess_role("old stone cottage"), "BUILDING")
        self.assertEqual(spec.guess_role("mystery object", "misc"), "UNTAGGED")

    def test_state_round_trip_and_repair(self):
        state = spec.new_state()
        state["sources"].append({"id": "s1", "label": "Mine", "path": "C:/models", "license": "OWNED", "enabled": True})
        state["overrides"]["a.blend"] = {"role": "CAR"}
        state["index"].append({"key": "a.blend", "path": "a.blend", "name": "a"})
        self.assertEqual(spec.load_state(spec.dump_state(state)), state)
        for bad in ("", "not json", "[]", json.dumps({"sources": "oops", "index": [1, 2], "overrides": 5})):
            repaired = spec.load_state(bad)
            self.assertEqual((repaired["sources"], repaired["index"], repaired["overrides"]), ([], [], {}))
        weird = spec.load_state(json.dumps({"sources": [{"path": "x", "license": "NOPE"}, {"label": "no path"}]}))
        self.assertEqual([item["license"] for item in weird["sources"]], ["UNKNOWN"])

    def test_effective_applies_overrides_and_source_license(self):
        record = {"key": "k", "path": "p", "name": "n", "role_guess": "TREE", "source": "s1"}
        sources = {"s1": {"license": "EDITORIAL", "label": "Pack"}}
        plain = spec.effective(record, {}, sources)
        self.assertEqual((plain["role"], plain["license"], plain["forward"], plain["stylize"]), ("TREE", "EDITORIAL", "AUTO", False))
        tuned = spec.effective(record, {"k": {"role": "CAR", "license": "OWNED", "stylize": True}}, sources)
        self.assertEqual((tuned["role"], tuned["license"], tuned["stylize"]), ("CAR", "OWNED", True))

    def test_filter_and_paging(self):
        records = [{"key": str(i), "name": name, "role": role, "tags": [], "source_label": "Pack"} for i, (name, role) in enumerate((("Red car", "CAR"), ("Blue car", "CAR"), ("Oak tree", "TREE"), ("Lamp", "LAMP")))]
        self.assertEqual([r["name"] for r in spec.filter_records(records, role="CAR")], ["Blue car", "Red car"])
        self.assertEqual([r["name"] for r in spec.filter_records(records, query="oak")], ["Oak tree"])
        self.assertEqual(len(spec.filter_records(records, query="pack")), 4)  # the source name is searchable
        page, number, total = spec.page_of(list(range(25)), 9, 10)
        self.assertEqual((page, number, total), ([20, 21, 22, 23, 24], 2, 3))
        self.assertEqual(spec.page_of([], 0, 10), ([], 0, 1))

    def test_car_fit_scales_orients_and_grounds_each_forward(self):
        # A 4.2 x 1.8 x 1.4 car centred away from the origin and floating at z=3.
        lo, hi = (10.0, 5.0, 3.0), (14.2, 6.8, 4.4)
        fit = spec.fit_transform(lo, hi, "CAR", "+X")
        self.assertAlmostEqual(fit["scale"], 0.9 / 4.2)
        self.assertEqual(fit["yaw"], 0.0)
        # The model's centre-bottom lands on the origin after the transform.
        centre = ((12.1), 5.9, 3.0)
        placed = [c * fit["scale"] + o for c, o in zip(centre, fit["offset"])]
        self.assertTrue(all(abs(v) < 1e-9 for v in placed))
        # A -Y facing model (long in Y) is turned so its front points along +X.
        fit_y = spec.fit_transform((0, 0, 0), (1.8, 4.2, 1.4), "CAR", "-Y")
        self.assertAlmostEqual(fit_y["yaw"], math.pi / 2)
        self.assertAlmostEqual(fit_y["scale"], 0.9 / 4.2)
        front = (0.9, 0.0)  # the -Y face centre (x=0.9, y=0) relative to the model centre (0.9, 2.1) is (0, -2.1)
        rotated_x = 0.0 * math.cos(fit_y["yaw"]) - (-2.1) * math.sin(fit_y["yaw"])
        self.assertGreater(rotated_x, 0.0)  # the front ends up on +X
        self.assertEqual(spec.fit_transform((0, 0, 0), (4.2, 1.8, 1.4), "CAR")["forward"], "+X")
        self.assertEqual(spec.fit_transform((0, 0, 0), (1.8, 4.2, 1.4), "CAR")["forward"], "-Y")

    def test_other_roles_fit_by_height_or_footprint(self):
        tree = spec.fit_transform((0, 0, 0), (2, 2, 8), "TREE")
        self.assertAlmostEqual(tree["scale"], 1.7 / 8)
        house = spec.fit_transform((0, 0, 0), (10, 6, 7), "BUILDING")
        self.assertAlmostEqual(house["scale"], 2.0 / 10)
        with self.assertRaises(ValueError):
            spec.fit_transform((0, 0, 0), (0, 0, 0), "CAR")

    def test_license_note_reports_the_strictest(self):
        self.assertIsNone(spec.license_note(["OWNED", "OWNED"]))
        self.assertEqual(spec.license_note(["OWNED", "UNKNOWN"]).level, "INFO")
        self.assertEqual(spec.license_note(["UNKNOWN", "EDITORIAL"]).level, "WARNING")

    def test_inner_names(self):
        self.assertEqual(spec.split_inner("Collection:Car"), ("Collection", "Car"))
        self.assertEqual(spec.split_inner(""), ("", ""))
        self.assertEqual(spec.asset_key("a.blend", "Object:Car"), "a.blend|Object:Car")


if __name__ == "__main__":
    unittest.main()

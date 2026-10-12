"""Tests for local reference-image and asset indexing helpers."""

import tempfile
import unittest
from pathlib import Path

from blender_addon.cozyverse_builder.core import reference_spec as reference


class ReferenceSpecTests(unittest.TestCase):
    def test_palette_is_bounded_and_deterministic(self):
        pixels = [1.0, 0.0, 0.0, 1.0] * 10 + [0.0, 1.0, 0.0, 1.0] * 4
        self.assertEqual(reference.dominant_palette(pixels, count=2), [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0)])

    def test_asset_scan_filters_supported_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "house.blend").touch()
            (root / "character.glb").touch()
            (root / "notes.txt").touch()
            found = reference.scan_asset_files([directory])
            self.assertEqual(len(found), 2)
            self.assertTrue(found[0].endswith("character.glb"))

    def test_reference_validation_rejects_non_image(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset.blend"
            path.touch()
            with self.assertRaises(ValueError):
                reference.validate_reference_path(str(path))

    def test_composition_extracts_bounded_cues_and_plan_quality(self):
        pixels = []
        for y in range(4):
            for x in range(8):
                pixels.extend((0.9 if x > 5 else 0.15, 0.2, 0.05, 1.0))
        result = reference.analyze_composition(pixels, 8, 4)
        self.assertEqual(result.aspect, "WIDE")
        self.assertGreater(result.focal_x, 0.5)
        self.assertIn(result.suggested_time, {"DAY", "DUSK", "NIGHT"})
        self.assertLess(reference.reference_plan(result, "BLOCKOUT")["architecture_count"], reference.reference_plan(result, "DETAILED")["architecture_count"])

    def test_composition_rejects_mismatched_pixels(self):
        with self.assertRaises(ValueError):
            reference.analyze_composition([1.0, 0.0, 0.0, 1.0], 2, 2)


if __name__ == "__main__":
    unittest.main()

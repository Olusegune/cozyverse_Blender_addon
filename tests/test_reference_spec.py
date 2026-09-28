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


if __name__ == "__main__":
    unittest.main()

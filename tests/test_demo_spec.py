from __future__ import annotations

import unittest

from blender_addon.cozyverse_builder.core.demo_spec import (
    DEFAULT_PROMPT,
    DEMO_ITEMS,
    DemoItem,
    normalized_prompt,
    validate_demo_spec,
)


class DemoSpecTests(unittest.TestCase):
    def test_bundled_spec_is_valid(self) -> None:
        validate_demo_spec()

    def test_prompt_defaults_and_is_bounded(self) -> None:
        self.assertEqual(normalized_prompt("  "), DEFAULT_PROMPT)
        self.assertEqual(normalized_prompt("  hello  "), "hello")
        self.assertEqual(len(normalized_prompt("x" * 5000)), 4000)

    def test_duplicate_names_are_rejected(self) -> None:
        item = DEMO_ITEMS[0]
        with self.assertRaisesRegex(ValueError, "unique"):
            validate_demo_spec((item, item))

    def test_unknown_kind_is_rejected(self) -> None:
        invalid = DemoItem("bad", "python", (0, 0, 0), (1, 1, 1))
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            validate_demo_spec((invalid,))

    def test_nonpositive_scale_is_rejected(self) -> None:
        invalid = DemoItem("bad", "cube", (0, 0, 0), (1, 0, 1))
        with self.assertRaisesRegex(ValueError, "positive"):
            validate_demo_spec((invalid,))


if __name__ == "__main__":
    unittest.main()


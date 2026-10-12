from __future__ import annotations

import json
import unittest

from blender_addon.cozyverse_builder.core.revision_spec import make_revision_preview, plan_fingerprint, redact_log_message


class RevisionSpecTests(unittest.TestCase):
    def test_preview_reports_non_destructive_revision(self) -> None:
        old = {"title": "Village", "world_type": "VILLAGE", "architecture_count": 2, "prop_count": 2, "vegetation_count": 2, "character_count": 1, "include_road": True}
        new = {**old, "world_type": "CITY", "architecture_count": 4}
        preview = make_revision_preview(old, new, "CV_WORLD", 42, 3, 2)
        self.assertEqual(preview.deleted_objects, 0)
        self.assertEqual(preview.skipped_objects, 42)
        self.assertEqual(preview.protected_objects, 3)
        self.assertEqual(preview.manually_edited_objects, 2)
        self.assertEqual(preview.changed_fields, ("world_type", "architecture_count"))

    def test_fingerprint_ignores_json_formatting(self) -> None:
        self.assertEqual(plan_fingerprint('{"a":1,"b":2}'), plan_fingerprint(json.dumps({"b": 2, "a": 1}, indent=2)))

    def test_log_redaction_removes_patterns_and_known_values(self) -> None:
        secret = "sk-test-123"
        message = redact_log_message(f"api_key={secret} authorization BearerValue token:abc {secret}", (secret,))
        self.assertNotIn(secret, message)
        self.assertNotIn("BearerValue", message)
        self.assertNotIn("abc", message)
        self.assertGreaterEqual(message.count("[REDACTED]"), 3)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from blender_addon.cozyverse_builder.providers.contracts import (
    build_plan,
    parse_status_response,
    parse_submit_response,
    validate_download_url,
)


class ProviderContractTests(unittest.TestCase):
    def test_tripo_plan_is_pinned_and_fingerprinted(self) -> None:
        plan = build_plan("TRIPO", "low-poly market stall")
        self.assertEqual(plan.model, "v3.1-20260211")
        self.assertEqual(len(plan.fingerprint()), 64)
        self.assertTrue(plan.submit_url.startswith("https://"))

    def test_meshy_plan_requests_preview_glb(self) -> None:
        plan = build_plan("MESHY", "stylized jeepney")
        self.assertEqual(plan.payload["mode"], "preview")
        self.assertEqual(plan.payload["target_formats"], ["glb"])

    def test_submit_and_status_normalization(self) -> None:
        self.assertEqual(parse_submit_response("TRIPO", {"data": {"task_id": "t1"}}), "t1")
        self.assertEqual(parse_submit_response("MESHY", {"result": "m1"}), "m1")
        status = parse_status_response("TRIPO", {"data": {"status": "running", "progress": 40}})
        self.assertEqual(status["status"], "IN_PROGRESS")
        self.assertEqual(status["progress"], 40)

    def test_download_allowlist_rejects_arbitrary_hosts(self) -> None:
        self.assertEqual(validate_download_url("TRIPO", "https://cdn.tripo3d.ai/out/model.glb"), "https://cdn.tripo3d.ai/out/model.glb")
        with self.assertRaisesRegex(ValueError, "host"):
            validate_download_url("MESHY", "https://example.com/model.glb")
        with self.assertRaisesRegex(ValueError, "GLB"):
            validate_download_url("MESHY", "https://assets.meshy.ai/model.zip")


if __name__ == "__main__":
    unittest.main()


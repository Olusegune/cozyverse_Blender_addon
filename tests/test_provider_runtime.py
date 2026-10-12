from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from blender_addon.cozyverse_builder.providers.contracts import build_plan
from blender_addon.cozyverse_builder.providers.runtime import download, poll, submit


class FakeResponse:
    def __init__(self, data: bytes, headers=None):
        self._data = data
        self.headers = headers or {}

    def read(self, size=-1):
        return self._data[:size] if size >= 0 else self._data

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class ProviderRuntimeTests(unittest.TestCase):
    def test_submit_and_poll_use_injected_transport(self) -> None:
        plan = build_plan("MESHY", "a miniature cart")
        submit_opener = lambda request, timeout: FakeResponse(b'{"result":"job-1"}')
        poll_opener = lambda request, timeout: FakeResponse(b'{"status":"SUCCEEDED","progress":100,"model_urls":{"glb":"https://assets.meshy.ai/job/model.glb"},"consumed_credits":20}')
        self.assertEqual(submit(plan, "session-secret", submit_opener), "job-1")
        result = poll(plan, "job-1", "session-secret", poll_opener)
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(result["consumed_credits"], 20)

    def test_download_accepts_glb_magic_and_rejects_other_content(self) -> None:
        glb = b"glTF" + b"\x02\x00\x00\x00" + b"\x0c\x00\x00\x00"
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "model.glb"
            result = download("MESHY", "https://assets.meshy.ai/job/model.glb", target, lambda request, timeout: FakeResponse(glb, {"Content-Length": str(len(glb))}))
            self.assertEqual(result.read_bytes(), glb)
            with self.assertRaisesRegex(RuntimeError, "valid binary GLB"):
                download("MESHY", "https://assets.meshy.ai/job/model.glb", target, lambda request, timeout: FakeResponse(b"not-a-model"))


if __name__ == "__main__":
    unittest.main()

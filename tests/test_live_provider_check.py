import contextlib
import importlib.util
import io
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("live_check", ROOT / "tools" / "live_provider_check.py")
live = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(live)

KEY = "sk-live-SECRET-0123456789"


class FakeResponse:
    def __init__(self, payload, headers=None):
        self.payload = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, limit=-1):
        return self.payload if limit < 0 else self.payload[:limit]


def run(argv, env, opener, answer="YES"):
    out = io.StringIO()
    asked = []
    with contextlib.redirect_stdout(out):
        try:
            code = live.main(argv, env, opener, lambda prompt: asked.append(prompt) or answer)
        except SystemExit as exit_:
            code = exit_.code if isinstance(exit_.code, int) else 1
            out.write(str(exit_.code))
    return code, out.getvalue(), asked


def plan_opener(requests):
    def opener(request, timeout=0):
        requests.append(request)
        return FakeResponse({"content": [{"type": "text", "text": json.dumps({"title": "Harbor", "world": {"type": "VILLAGE", "water": "SEA"}, "assets": [{"description": "a striped lighthouse", "role": "BUILDING"}]})}]})

    return opener


class CheckerTests(unittest.TestCase):
    def test_a_missing_key_explains_what_to_do_and_sends_nothing(self):
        requests = []
        code, out, asked = run(["plan"], {}, plan_opener(requests))
        self.assertNotEqual(code, 0)
        self.assertIn("ANTHROPIC_API_KEY", out)
        self.assertIn("Never paste keys into chat", out)
        self.assertEqual((requests, asked), ([], []))

    def test_dry_run_shows_the_request_and_sends_nothing(self):
        requests = []
        code, out, asked = run(["plan", "--dry-run"], {"ANTHROPIC_API_KEY": KEY}, plan_opener(requests))
        self.assertEqual(code, 0)
        self.assertIn("api.anthropic.com", out)
        self.assertNotIn(KEY, out)
        self.assertEqual(requests, [])

    def test_anything_but_yes_cancels(self):
        requests = []
        code, out, asked = run(["plan"], {"ANTHROPIC_API_KEY": KEY}, plan_opener(requests), answer="y")
        self.assertNotEqual(code, 0)
        self.assertEqual(requests, [])
        self.assertIn("Cancelled", out)

    def test_a_confirmed_plan_call_passes_and_never_prints_the_key(self):
        requests = []
        code, out, asked = run(["plan"], {"ANTHROPIC_API_KEY": KEY}, plan_opener(requests))
        self.assertEqual(code, 0)
        self.assertIn("PASS", out)
        self.assertIn("lighthouse", out)
        self.assertNotIn(KEY, out)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].get_header("X-api-key"), KEY)  # the key travels only in the header

    def test_the_key_is_never_accepted_on_the_command_line(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                live.main(["plan", "--api-key", KEY], {}, None, None)

    def test_a_bad_reply_fails_clearly(self):
        code, out, _ = run(["plan", "--yes"], {"ANTHROPIC_API_KEY": KEY}, lambda request, timeout=0: FakeResponse({"content": [{"type": "text", "text": "no plan"}]}))
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)
        self.assertNotIn(KEY, out)

    def test_followups_are_validated_too(self):
        reply = {"content": [{"type": "text", "text": json.dumps({"commands": [{"verb": "SET_WARMTH", "args": {"delta": 10}}, {"verb": "EXEC", "args": {}}]})}]}
        code, out, _ = run(["followup", "--yes"], {"ANTHROPIC_API_KEY": KEY}, lambda request, timeout=0: FakeResponse(reply))
        self.assertEqual(code, 0)
        self.assertIn("warmer", out)
        self.assertIn("dropped", out)

    def test_generation_is_capped_and_confirmed_and_only_downloads_a_valid_glb(self):
        calls = []

        def opener(request, timeout=0):
            url = request.full_url
            calls.append((request.get_method(), url))
            if url.endswith("/task") and request.get_method() == "POST":
                return FakeResponse({"code": 0, "data": {"task_id": "task-123456789"}})
            if "/task/" in url:
                return FakeResponse({"code": 0, "data": {"status": "success", "progress": 100, "output": {"model_url": "https://cdn.tripo3d.ai/x/model.glb"}, "credits_consumed": 20}})
            return FakeResponse(b"glTF" + b"\x02\x00\x00\x00" + b"0" * 64, {"Content-Length": "72"})

        env = {"TRIPO_API_KEY": KEY}
        code, out, _ = run(["generate", "--provider", "tripo", "--max-credits", "5"], env, opener)
        self.assertEqual(code, 1)  # below the estimated cost: refused before anything is sent
        self.assertEqual(calls, [])
        self.assertIn("at least", out)
        code, out, _ = run(["generate", "--provider", "tripo", "--max-credits", "20", "--interval", "0"], env, opener)
        self.assertEqual(code, 0, out)
        self.assertIn("PASS", out)
        self.assertNotIn(KEY, out)
        self.assertEqual(calls[0][0], "POST")
        self.assertTrue(any(url.startswith("https://cdn.tripo3d.ai") for _m, url in calls))

        def evil(request, timeout=0):
            if request.full_url.endswith("/task") and request.get_method() == "POST":
                return FakeResponse({"code": 0, "data": {"task_id": "t-1"}})
            return FakeResponse({"code": 0, "data": {"status": "success", "progress": 100, "output": {"model_url": "https://evil.example/model.glb"}}})

        code, out, _ = run(["generate", "--provider", "tripo", "--yes", "--interval", "0"], env, evil)
        self.assertEqual(code, 1)  # a download from an unapproved host is refused


if __name__ == "__main__":
    unittest.main()

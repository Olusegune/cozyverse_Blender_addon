"""Check CozyVerse against the real AI and 3D services, safely, outside Blender.

Nothing is sent unless you type YES after seeing exactly what would be sent. Keys are read only
from environment variables (never from the command line, so they stay out of your shell history),
are never printed, and spending is capped.

  python tools/live_provider_check.py plan --provider anthropic
  python tools/live_provider_check.py followup --provider openai --model <model name>
  python tools/live_provider_check.py generate --provider tripo --max-credits 20

Add --dry-run to see the request without sending anything.

Keys:  ANTHROPIC_API_KEY, OPENAI_API_KEY, CUSTOM_LLM_API_KEY, TRIPO_API_KEY, MESHY_API_KEY
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "blender_addon"))

from cozyverse_builder.core import blueprint_spec as spec  # noqa: E402
from cozyverse_builder.core import director_llm as llm  # noqa: E402
from cozyverse_builder.providers import contracts, runtime  # noqa: E402

KEY_NAMES = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "custom": "CUSTOM_LLM_API_KEY", "tripo": "TRIPO_API_KEY", "meshy": "MESHY_API_KEY"}
SAMPLE_PROMPT = "A small rainy harbor village on an island at dusk with a striped lighthouse, a fishing boat and warm lanterns"
SAMPLE_REQUEST = "more flowers, less clutter, warmer light"


def _key(provider: str, env) -> str:
    name = KEY_NAMES[provider]
    value = (env.get(name) or "").strip()
    if not value:
        raise SystemExit(f"No key found. Set {name} in this terminal first, for example in PowerShell:\n  $env:{name} = '...'\nThen run this again. (Never paste keys into chat.)")
    return value


def _confirm(lines: list[str], args, input_fn) -> None:
    print("\nThis would be sent:")
    for line in lines:
        print("  -", line)
    if args.dry_run:
        print("\n--dry-run: nothing was sent.")
        raise SystemExit(0)
    if not args.yes and input_fn("\nType YES to send it, anything else to cancel: ").strip() != "YES":
        raise SystemExit("Cancelled. Nothing was sent.")


def _config(args) -> llm.ProviderConfig:
    return llm.ProviderConfig(args.provider.upper(), args.model or "", args.base_url or "")


def run_plan(args, env, opener, input_fn) -> int:
    config = _config(args)
    key = _key(args.provider, env)
    request = llm.build_plan_request(config, key, args.prompt, args.style)
    _confirm(llm.describe_outbound(config, "PLAN", args.prompt, False), args, input_fn)
    started = time.time()
    response = llm.send(request, opener)
    blueprint = llm.parse_plan_response(config.kind, response, args.prompt, args.style, llm.model_for(config))
    print(f"\nReply in {time.time() - started:.1f}s. The plan passed validation:")
    for line in spec.describe_blueprint(blueprint):
        print("  ", line)
    for asset in blueprint.assets:
        print(f"   asset: {asset.role:9} {asset.description}")
    for warning in blueprint.warnings:
        print("   note:", warning)
    print("\nPASS: a live model returned a valid Scene Blueprint.")
    return 0


def run_followup(args, env, opener, input_fn) -> int:
    config = _config(args)
    key = _key(args.provider, env)
    summary = {"title": "Village", "style": "Cozy Village", "water": "NONE", "terrain": "FLAT", "items": {"building": 3, "tree": 6, "prop": 6, "character": 2}}
    request = llm.build_followup_request(config, key, args.prompt, summary)
    _confirm(llm.describe_outbound(config, "FOLLOWUP", args.prompt, False), args, input_fn)
    commands, problems = llm.parse_followup_response(config.kind, llm.send(request, opener))
    print("\nThe model's commands, after validation:")
    for command in commands:
        print("  ", spec.describe_command(command))
    for problem in problems:
        print("   dropped:", problem)
    print("\nPASS: a live model returned allowlisted follow-up commands.")
    return 0


def run_generate(args, env, opener, input_fn) -> int:
    key = _key(args.provider, env)
    plan = contracts.build_plan(args.provider.upper(), args.prompt)
    contracts.validate_budget(plan, args.max_credits, plan.fingerprint())
    lines = [f"To: {plan.provider} ({plan.submit_url})", f"Prompt: {plan.prompt}", f"Model: {plan.model}", f"Estimated cost: about {plan.estimated_credits} credits (your cap: {args.max_credits})", plan.cancellation_note, "Your key goes in a header and is never shown"]
    _confirm(lines, args, input_fn)
    task = runtime.submit(plan, key, opener)
    print(f"\nSubmitted. Task {task[:12]}... (the provider may still charge if you stop now)")
    deadline = time.time() + args.timeout
    status = {}
    while time.time() < deadline:
        status = runtime.poll(plan, task, key, opener)
        print(f"  {status['status']:12} {status['progress']:3d}%")
        if status["status"] in {"SUCCEEDED", "FAILED", "CANCELED"}:
            break
        time.sleep(args.interval)
    if status.get("status") != "SUCCEEDED":
        print(f"\nFAIL: the job ended as {status.get('status', 'TIMEOUT')}. Credits used: {status.get('consumed_credits')}")
        return 1
    folder = ROOT / "work" / "live_check"
    path = runtime.download(plan.provider, contracts.validate_download_url(plan.provider, status["download_url"]), folder / f"{plan.provider.lower()}_{task[:8]}.glb", opener)
    print(f"\nDownloaded a valid GLB ({path.stat().st_size / 1024:.0f} KB): {path}")
    print(f"Credits reported by the provider: {status.get('consumed_credits')}")
    print("\nPASS: a live provider generated a model that CozyVerse accepts. Import it from the Assets tab (3D asset factory) to inspect it.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safely check CozyVerse against the real AI and 3D services.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "followup"):
        p = sub.add_parser(name)
        p.add_argument("--provider", choices=("anthropic", "openai", "custom"), default="anthropic")
        p.add_argument("--model", default="", help="required for openai and custom; defaults for anthropic")
        p.add_argument("--base-url", default="", help="custom servers only")
        p.add_argument("--prompt", default=SAMPLE_PROMPT if name == "plan" else SAMPLE_REQUEST)
        p.add_argument("--style", default="COZY_VILLAGE")
    gen = sub.add_parser("generate")
    gen.add_argument("--provider", choices=("tripo", "meshy"), required=True)
    gen.add_argument("--prompt", default="A stylized low-poly striped lighthouse, single object")
    gen.add_argument("--max-credits", type=int, default=20)
    gen.add_argument("--timeout", type=int, default=600)
    gen.add_argument("--interval", type=float, default=5.0)
    for p in sub.choices.values():
        p.add_argument("--dry-run", action="store_true", help="show what would be sent and stop")
        p.add_argument("--yes", action="store_true", help="skip the YES prompt (you are confirming by passing this)")
    return parser


def main(argv=None, env=None, opener=urlopen, input_fn=input) -> int:
    args = build_parser().parse_args(argv)
    env = os.environ if env is None else env
    try:
        return {"plan": run_plan, "followup": run_followup, "generate": run_generate}[args.command](args, env, opener, input_fn)
    except (spec.BlueprintError, RuntimeError, ValueError) as exc:
        print(f"\nFAIL: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

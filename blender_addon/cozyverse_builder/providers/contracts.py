"""Validated request/response contracts for Tripo and Meshy."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class GenerationPlan:
    provider: str
    prompt: str
    model: str
    submit_url: str
    status_url_template: str
    payload: dict
    cost_note: str

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def build_plan(provider: str, prompt: str) -> GenerationPlan:
    clean_prompt = prompt.strip()
    if not clean_prompt:
        raise ValueError("Generation prompt is required")
    normalized = provider.upper()
    if normalized == "TRIPO":
        if len(clean_prompt) > 1024:
            raise ValueError("Tripo prompts must be 1024 characters or fewer")
        return GenerationPlan(
            provider="TRIPO",
            prompt=clean_prompt,
            model="v3.1-20260211",
            submit_url="https://openapi.tripo3d.ai/v3/generation/text-to-model",
            status_url_template="https://openapi.tripo3d.ai/v3/tasks/{task_id}",
            payload={
                "prompt": clean_prompt,
                "model": "v3.1-20260211",
                "texture": True,
                "pbr": True,
                "texture_quality": "standard",
                "smart_low_poly": True,
                "face_limit": 20000,
                "auto_size": True,
            },
            cost_note="Tripo freezes provider credits when the task is created; exact credits depend on provider pricing.",
        )
    if normalized == "MESHY":
        return GenerationPlan(
            provider="MESHY",
            prompt=clean_prompt,
            model="latest",
            submit_url="https://api.meshy.ai/openapi/v2/text-to-3d",
            status_url_template="https://api.meshy.ai/openapi/v2/text-to-3d/{task_id}",
            payload={
                "mode": "preview",
                "prompt": clean_prompt,
                "ai_model": "latest",
                "should_remesh": True,
                "target_polycount": 20000,
                "target_formats": ["glb"],
            },
            cost_note="Meshy charges provider credits when the preview task is created; exact credits are reported by the task.",
        )
    raise ValueError(f"Unsupported generation provider: {provider}")


def parse_submit_response(provider: str, response: dict) -> str:
    if provider == "TRIPO":
        task_id = response.get("data", {}).get("task_id")
    elif provider == "MESHY":
        task_id = response.get("result")
    else:
        raise ValueError("Unsupported provider response")
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("Provider response did not contain a task ID")
    return task_id


def parse_status_response(provider: str, response: dict) -> dict:
    if provider == "TRIPO":
        data = response.get("data", {})
        status_map = {"queued": "PENDING", "running": "IN_PROGRESS", "success": "SUCCEEDED", "failed": "FAILED", "cancelled": "CANCELED", "banned": "FAILED"}
        output = data.get("output") or {}
        return {
            "status": status_map.get(str(data.get("status", "")).lower(), "UNKNOWN"),
            "progress": int(data.get("progress") or 0),
            "download_url": output.get("model_url", ""),
            "consumed_credits": data.get("credits_consumed"),
        }
    if provider == "MESHY":
        urls = response.get("model_urls") or {}
        return {
            "status": str(response.get("status", "UNKNOWN")).upper(),
            "progress": int(response.get("progress") or 0),
            "download_url": urls.get("glb", ""),
            "consumed_credits": response.get("consumed_credits"),
        }
    raise ValueError("Unsupported provider response")


def validate_download_url(provider: str, url: str) -> str:
    parsed = urlparse(url)
    allowed = {
        "TRIPO": {"cdn.tripo3d.ai"},
        "MESHY": {"assets.meshy.ai", "cdn.meshy.ai"},
    }.get(provider, set())
    if parsed.scheme != "https" or parsed.hostname not in allowed:
        raise ValueError("Download URL host is not approved")
    if not parsed.path.lower().endswith((".glb", ".gltf")):
        raise ValueError("Only GLB or GLTF model downloads are supported")
    return url


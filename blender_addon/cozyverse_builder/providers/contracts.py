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
    cancel_url_template: str
    payload: dict
    cost_note: str
    estimated_credits: int
    cancellation_note: str

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
            submit_url="https://api.tripo3d.ai/v2/openapi/task",
            status_url_template="https://api.tripo3d.ai/v2/openapi/task/{task_id}",
            cancel_url_template="",
            payload={
                "type": "text_to_model",
                "prompt": clean_prompt,
                "model_version": "v3.1-20260211",
                "texture": True,
                "pbr": True,
                "texture_quality": "standard",
                "face_limit": 20000,
                "auto_size": True,
            },
            cost_note="Estimated 20 Tripo API credits for v3.1 Text-to-3D with standard texture; provider pricing can change.",
            estimated_credits=20,
            cancellation_note="The verified Tripo v2 schema does not publish a cancellation endpoint; submission may not be cancellable.",
        )
    if normalized == "MESHY":
        return GenerationPlan(
            provider="MESHY",
            prompt=clean_prompt,
            model="latest",
            submit_url="https://api.meshy.ai/openapi/v2/text-to-3d",
            status_url_template="https://api.meshy.ai/openapi/v2/text-to-3d/{task_id}",
            cancel_url_template="https://api.meshy.ai/openapi/v2/text-to-3d/{task_id}",
            payload={
                "mode": "preview",
                "prompt": clean_prompt,
                "ai_model": "latest",
                "should_remesh": True,
                "target_polycount": 20000,
                "target_formats": ["glb"],
            },
            cost_note="Estimated 20 Meshy API credits for a latest standard preview mesh; provider pricing can change.",
            estimated_credits=20,
            cancellation_note="Meshy can delete and refund a PENDING task; an IN_PROGRESS task cannot be deleted or refunded.",
        )
    raise ValueError(f"Unsupported generation provider: {provider}")


def parse_submit_response(provider: str, response: dict) -> str:
    if provider == "TRIPO":
        if response.get("code") not in {None, 0}:
            raise ValueError(str(response.get("message") or "Tripo rejected the request"))
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
        "TRIPO": {"cdn.tripo3d.ai", "tripo-data.cdn.bcebos.com"},
        "MESHY": {"assets.meshy.ai", "cdn.meshy.ai"},
    }.get(provider, set())
    if parsed.scheme != "https" or parsed.hostname not in allowed:
        raise ValueError("Download URL host is not approved")
    if not parsed.path.lower().endswith((".glb", ".gltf")):
        raise ValueError("Only GLB or GLTF model downloads are supported")
    return url


def validate_budget(plan: GenerationPlan, credit_limit: int, approved_fingerprint: str) -> None:
    if approved_fingerprint != plan.fingerprint():
        raise ValueError("The approved request no longer matches the preview")
    if credit_limit < plan.estimated_credits:
        raise ValueError(f"Credit limit must be at least {plan.estimated_credits}")
    if credit_limit > 1000:
        raise ValueError("Credit limit exceeds the CozyVerse safety maximum")

"""Network-thread helpers for approved provider jobs; this module never imports bpy."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .contracts import GenerationPlan, parse_status_response, parse_submit_response, validate_download_url


MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_MODEL_BYTES = 100 * 1024 * 1024


def _json_request(url: str, api_key: str, method: str = "GET", payload: dict | None = None, opener=urlopen) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=body,
        method=method,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with opener(request, timeout=30) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        detail = exc.read(2048).decode("utf-8", "replace")
        raise RuntimeError(f"Provider HTTP {exc.code}: {detail[:300]}") from exc
    except (OSError, URLError) as exc:
        raise RuntimeError(f"Provider connection failed: {exc}") from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("Provider response exceeded the safety limit")
    try:
        return json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Provider returned invalid JSON") from exc


def submit(plan: GenerationPlan, api_key: str, opener=urlopen) -> str:
    return parse_submit_response(plan.provider, _json_request(plan.submit_url, api_key, "POST", plan.payload, opener))


def poll(plan: GenerationPlan, task_id: str, api_key: str, opener=urlopen) -> dict:
    url = plan.status_url_template.format(task_id=task_id)
    return parse_status_response(plan.provider, _json_request(url, api_key, opener=opener))


def cancel(plan: GenerationPlan, task_id: str, api_key: str, opener=urlopen) -> None:
    if not plan.cancel_url_template:
        raise RuntimeError(plan.cancellation_note)
    _json_request(plan.cancel_url_template.format(task_id=task_id), api_key, "DELETE", opener=opener)


def download(provider: str, url: str, destination: Path, opener=urlopen) -> Path:
    validate_download_url(provider, url)
    request = Request(url, method="GET", headers={"User-Agent": "CozyVerse-Builder/0.14"})
    try:
        with opener(request, timeout=60) as response:
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > MAX_MODEL_BYTES:
                raise RuntimeError("Model download exceeds 100 MB")
            data = response.read(MAX_MODEL_BYTES + 1)
    except (HTTPError, OSError, URLError) as exc:
        raise RuntimeError(f"Model download failed: {exc}") from exc
    if len(data) > MAX_MODEL_BYTES:
        raise RuntimeError("Model download exceeds 100 MB")
    if len(data) < 12 or data[:4] != b"glTF":
        raise RuntimeError("Downloaded file is not a valid binary GLB")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return destination

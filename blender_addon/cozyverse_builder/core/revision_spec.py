"""Pure planning and redaction helpers for safe CozyVerse revisions."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass


PLAN_FIELDS = (
    "title",
    "world_type",
    "style_id",
    "base_shape",
    "architecture_count",
    "prop_count",
    "vegetation_count",
    "character_count",
    "include_road",
    "camera_type",
    "water",
    "terrain",
    "prompt",
)


@dataclass(frozen=True)
class RevisionPreview:
    schema_version: str
    source_world: str
    changed_fields: tuple[str, ...]
    created_objects: int
    deleted_objects: int
    skipped_objects: int
    protected_objects: int
    manually_edited_objects: int
    plan_fingerprint: str

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


def plan_fingerprint(plan_json: str) -> str:
    parsed = json.loads(plan_json)
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def estimated_object_count(plan: dict) -> int:
    """Conservative count for native objects the local builder will create."""
    content = sum(max(0, int(plan.get(name, 0))) for name in (
        "architecture_count", "prop_count", "vegetation_count", "character_count"
    ))
    infrastructure = 7 + (2 if plan.get("include_road", True) else 0)
    return content + infrastructure


def make_revision_preview(
    old_plan: dict | None,
    new_plan: dict,
    source_world: str,
    existing_objects: int,
    protected_objects: int,
    manually_edited_objects: int,
) -> RevisionPreview:
    old_plan = old_plan or {}
    changed = tuple(field for field in PLAN_FIELDS if old_plan.get(field) != new_plan.get(field))
    return RevisionPreview(
        "1.0",
        source_world,
        changed,
        estimated_object_count(new_plan),
        0,
        max(0, int(existing_objects)),
        max(0, int(protected_objects)),
        max(0, int(manually_edited_objects)),
        plan_fingerprint(json.dumps(new_plan)),
    )


_SECRET_PATTERN = re.compile(
    r"(?i)(api[_ -]?key|authorization|bearer|token|secret|password)(\s*[:=]\s*|\s+)([^\s,;]+)"
)


def redact_log_message(message: str, known_secrets: tuple[str, ...] = ()) -> str:
    value = _SECRET_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", str(message))
    for secret in known_secrets:
        if secret:
            value = value.replace(secret, "[REDACTED]")
    return value[:500]

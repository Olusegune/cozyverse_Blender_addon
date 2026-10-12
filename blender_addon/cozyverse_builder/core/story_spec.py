"""Deterministic, Blender-independent Story Moment planning."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json


@dataclass(frozen=True)
class StoryPreset:
    label: str
    description: str
    character_motion: float
    foliage_sway_degrees: float
    precipitation_travel: float
    light_pulse: float


PRESETS = {
    "QUIET_MORNING": StoryPreset("Quiet Morning", "Gentle idle motion and subtle foliage sway", 0.04, 2.0, 0.0, 0.025),
    "BUSY_MARKET": StoryPreset("Busy Market", "Livelier character staging with a breezy environment", 0.12, 4.0, 0.0, 0.045),
    "RAINY_EVENING": StoryPreset("Rainy Evening", "Sheltered character motion, rain travel and warm light pulse", 0.07, 5.0, 1.8, 0.08),
}


@dataclass(frozen=True)
class StoryPlan:
    schema_version: str
    preset: str
    world_name: str
    start_frame: int
    end_frame: int
    character_count: int
    foliage_count: int
    precipitation_count: int
    light_count: int
    skipped_count: int

    @property
    def midpoint(self) -> int:
        return self.start_frame + (self.end_frame - self.start_frame) // 2

    @property
    def target_count(self) -> int:
        return self.character_count + self.foliage_count + self.precipitation_count + self.light_count

    @property
    def keyframe_count(self) -> int:
        return self.target_count * 3

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def build_story_plan(
    preset: str,
    world_name: str,
    start_frame: int,
    end_frame: int,
    character_count: int,
    foliage_count: int,
    precipitation_count: int,
    light_count: int,
    skipped_count: int = 0,
) -> StoryPlan:
    if preset not in PRESETS:
        raise ValueError("Unsupported Story Moment preset")
    start, end = int(start_frame), int(end_frame)
    if start < 0 or end <= start or end - start > 10000:
        raise ValueError("Story frame range must be increasing and at most 10,000 frames")
    counts = [character_count, foliage_count, precipitation_count, light_count, skipped_count]
    if any(int(value) < 0 for value in counts):
        raise ValueError("Story target counts cannot be negative")
    return StoryPlan("1.0", preset, world_name, start, end, *(int(value) for value in counts))

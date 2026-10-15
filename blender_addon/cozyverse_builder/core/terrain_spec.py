"""Pure terrain and water planning: where lakes, rivers and seas go, and how tall the land is.

Everything is deterministic from a seed so a prompt always makes the same landscape. The central
idea is one height function: buildings only go where the ground is flat and dry (height ~ 0),
trees may climb hills, and water sits wherever the land dips below the water level.
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass

WATER_KINDS = ("NONE", "LAKE", "POND", "RIVER", "SEA")
TERRAIN_KINDS = ("FLAT", "HILLS")
WATER_LEVEL = -0.10
SEABED = -0.55
BASIN_DEPTH = 0.62
BOTTOM = -0.80
FLAT_TOLERANCE = 0.045


@dataclass(frozen=True)
class Stage:
    half_x: float
    half_y: float
    scale_x: float  # how much a standard layout shrinks to fit the land
    scale_y: float
    road_half: float
    ortho: float
    camera_scale: float


STANDARD = Stage(5.7, 4.2, 1.0, 1.0, 5.15, 13.5, 1.0)
SEA_STAGE = Stage(6.6, 5.2, 0.66, 0.70, 3.5, 17.0, 1.22)

_WATER_WORDS = (
    ("SEA", {"sea", "ocean", "island", "harbor", "harbour", "beach", "coast", "coastal", "bay", "lagoon", "archipelago", "seaside", "waterfront", "pier", "dock", "shore"}),
    ("LAKE", {"lake", "lakeside", "reservoir", "lakeshore"}),
    ("RIVER", {"river", "stream", "creek", "canal", "brook", "riverside"}),
    ("POND", {"pond", "pool", "koi"}),
)
_HILL_WORDS = {"hill", "hills", "hillside", "mountain", "mountains", "valley", "cliff", "cliffs", "highland", "highlands", "alpine", "peak", "peaks", "mesa", "slope"}


def _words(prompt: str) -> set[str]:
    return set(re.split(r"[^a-z0-9]+", prompt.casefold()))


def infer_water(prompt: str) -> str:
    words = _words(prompt)
    return next((kind for kind, vocabulary in _WATER_WORDS if words & vocabulary), "NONE")


def infer_terrain(prompt: str) -> str:
    return "HILLS" if _words(prompt) & _HILL_WORDS else "FLAT"


def stage_for(water: str) -> Stage:
    return SEA_STAGE if water == "SEA" else STANDARD


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def smoothstep(edge0: float, edge1: float, value: float) -> float:
    t = _clamp((value - edge0) / (edge1 - edge0))
    return t * t * (3.0 - 2.0 * t)


def build_zone(water: str, seed: int, stage: Stage) -> dict | None:
    """Where the water goes. Lakes and ponds take a back corner, rivers run behind the village."""
    if water == "NONE":
        return None
    rng = random.Random(seed ^ 0x5EA5)
    side = 1.0 if rng.random() < 0.5 else -1.0
    phase = rng.uniform(0.0, math.tau)
    if water == "LAKE":
        return {"kind": "LAKE", "cx": side * 3.0, "cy": 2.55, "rx": 2.2 + rng.uniform(0.0, 0.3), "ry": 1.45 + rng.uniform(0.0, 0.2), "phase": phase}
    if water == "POND":
        return {"kind": "POND", "cx": side * 3.7, "cy": 1.9, "rx": 0.95, "ry": 0.72, "phase": phase}
    if water == "RIVER":
        return {"kind": "RIVER", "y0": 0.75, "amp": 0.22, "freq": 0.55 + rng.uniform(0.0, 0.25), "phase": phase, "half_width": 0.58}
    return {"kind": "SEA", "ax": stage.half_x * 0.76, "ay": stage.half_y * 0.74, "p": 2.6, "phase": phase, "phase2": rng.uniform(0.0, math.tau)}


def _wobble(angle: float, phase: float) -> float:
    return 1.0 + 0.12 * math.sin(3.0 * angle + phase) + 0.06 * math.sin(5.0 * angle + 2.0 * phase)


def _bank_distance(x: float, y: float, zone: dict) -> float:
    """Normalised distance from the water's middle: below 1 is inside the water body."""
    if zone["kind"] in {"LAKE", "POND"}:
        u, v = (x - zone["cx"]) / zone["rx"], (y - zone["cy"]) / zone["ry"]
        return math.hypot(u, v) / _wobble(math.atan2(v, u), zone["phase"])
    center = zone["y0"] + zone["amp"] * math.sin(zone["freq"] * x + zone["phase"])
    return abs(y - center) / zone["half_width"]


def _island_metric(x: float, y: float, zone: dict) -> float:
    angle = math.atan2(y / zone["ay"], x / zone["ax"])
    base = (abs(x / zone["ax"]) ** zone["p"] + abs(y / zone["ay"]) ** zone["p"]) ** (1.0 / zone["p"])
    return base / (1.0 + 0.09 * math.sin(3.0 * angle + zone["phase"]) + 0.05 * math.sin(5.0 * angle + zone["phase2"]))


def hills_for(seed: int, stage: Stage, water: str) -> list[tuple[float, float, float, float, float]]:
    rng = random.Random(seed ^ 0x1D115)
    inland = water == "SEA"
    reach_y = stage.half_y * (0.42 if inland else 0.82)
    spread_x = stage.half_x * (0.5 if inland else 0.9)
    hills = [(rng.uniform(-1.0, 1.0) * spread_x, reach_y + rng.uniform(-0.2, 0.2), rng.uniform(0.9, 1.6), rng.uniform(1.4, 2.0), rng.uniform(1.0, 1.3)) for _ in range(3)]
    for side in (-1.0, 1.0):
        hills.append((side * stage.half_x * (0.5 if inland else 0.88), rng.uniform(0.2, 2.2) * stage.scale_y, rng.uniform(0.6, 1.1), 1.2, 1.4))
    return hills


def _noise(x: float, y: float, seed: int) -> float:
    """Smooth value noise in [0, 1]."""
    def corner(ix: int, iy: int) -> float:
        return random.Random((ix * 73856093) ^ (iy * 19349663) ^ seed).random()

    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    top = corner(ix, iy) * (1 - fx) + corner(ix + 1, iy) * fx
    bottom = corner(ix, iy + 1) * (1 - fx) + corner(ix + 1, iy + 1) * fx
    return top * (1 - fy) + bottom * fy


def height_at(x: float, y: float, terrain: str, zone: dict | None, hills: list, seed: int) -> float:
    land = 0.0
    if terrain == "HILLS":
        land = sum(amp * math.exp(-0.5 * (((x - cx) / sx) ** 2 + ((y - cy) / sy) ** 2)) for cx, cy, amp, sx, sy in hills)
        land += 0.05 * _noise(x * 1.3, y * 1.3, seed & 0xFFFF) * min(1.0, land * 2.0)
    if zone is None:
        return land
    if zone["kind"] == "SEA":
        radius = _island_metric(x, y, zone)
        land *= 1.0 - smoothstep(0.55, 0.85, radius)
        return land + SEABED * smoothstep(0.8, 1.05, radius)
    bank = _bank_distance(x, y, zone)
    land *= smoothstep(1.0, 2.8, bank)  # hills ease away from water instead of walling it in
    return land - BASIN_DEPTH * smoothstep(0.0, 0.5, _clamp(1.0 - bank))


def _samples(x: float, y: float, margin: float):
    yield x, y
    if margin > 0.0:
        yield from ((x + margin, y), (x - margin, y), (x, y + margin), (x, y - margin))


def is_buildable(x: float, y: float, margin: float, terrain: str, zone: dict | None, hills: list, seed: int) -> bool:
    """Flat, dry ground with room around it."""
    return all(-0.002 <= height_at(sx, sy, terrain, zone, hills, seed) <= FLAT_TOLERANCE for sx, sy in _samples(x, y, margin))


def is_dry(x: float, y: float, margin: float, terrain: str, zone: dict | None, hills: list, seed: int) -> bool:
    """Land of any height (trees can climb hills) but never in or right at the water."""
    return all(height_at(sx, sy, terrain, zone, hills, seed) >= -0.03 for sx, sy in _samples(x, y, margin))


def height_grid(nx: int, ny: int, stage: Stage, terrain: str, zone: dict | None, hills: list, seed: int) -> list[list[float]]:
    return [
        [height_at(-stage.half_x + stage.half_x * 2 * i / nx, -stage.half_y + stage.half_y * 2 * j / ny, terrain, zone, hills, seed) for i in range(nx + 1)]
        for j in range(ny + 1)
    ]


def water_outline(zone: dict, stage: Stage, samples: int = 72) -> list[tuple[float, float]]:
    """The water surface polygon, listed counter-clockwise."""
    inset = 0.005  # keeps the water's sides off the terrain's own sides
    if zone["kind"] == "SEA":
        hx, hy = stage.half_x - inset, stage.half_y - inset
        return [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
    if zone["kind"] in {"LAKE", "POND"}:
        points = []
        for step in range(samples):
            angle = math.tau * step / samples
            wobble = _wobble(angle, zone["phase"])
            points.append((zone["cx"] + zone["rx"] * wobble * math.cos(angle), zone["cy"] + zone["ry"] * wobble * math.sin(angle)))
        return points
    half = stage.half_x - inset
    xs = [-half + 2 * half * step / 60 for step in range(61)]
    centre = lambda x: zone["y0"] + zone["amp"] * math.sin(zone["freq"] * x + zone["phase"])  # noqa: E731
    return [(x, centre(x) - zone["half_width"]) for x in xs] + [(x, centre(x) + zone["half_width"]) for x in reversed(xs)]

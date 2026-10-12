"""Deterministic composition families for varied editable miniature worlds."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class CompositionProfile:
    label: str
    hero: str
    architecture_form: str
    prop_form: str
    vegetation_form: str
    camera_location: tuple[float, float, float]
    camera_target: tuple[float, float, float]


PROFILES = {
    "VILLAGE": CompositionProfile("Village", "Town Hall", "PITCHED_HOUSE", "CRATE", "TREE", (10.8, -13.2, 10.2), (0, 0.5, 0.8)),
    "CITY": CompositionProfile("Urban Street", "Corner Tower", "TOWER", "STREET_PROP", "TREE", (11.5, -14.0, 8.0), (0, 0.5, 1.2)),
    "CAFE": CompositionProfile("Cafe", "Hero Cafe", "CAFE", "TABLE", "PLANTER", (9.2, -12.0, 7.0), (0, 0.7, 1.0)),
    "NATURE": CompositionProfile("Landscape", "Hero Tree", "ROCK", "ROCK", "TREE", (10.0, -12.0, 9.5), (0, 0, 0.4)),
    "SPACE_OUTPOST": CompositionProfile("Space Outpost", "Command Module", "MODULE", "TECH", "ALIEN_PLANT", (12.5, -14.0, 8.5), (0, 0.4, 1.0)),
    "MARKET": CompositionProfile("Market", "Market Pavilion", "STALL", "STALL_PROP", "PLANTER", (10.4, -13.0, 8.0), (0, 0.3, 0.9)),
    "FARM": CompositionProfile("Farm", "Main Barn", "BARN", "FARM_PROP", "TREE", (12.0, -14.5, 9.0), (0, 0.8, 0.8)),
    "FANTASY": CompositionProfile("Fantasy", "Wizard Tower", "TURRET", "MAGIC_PROP", "FANTASY_TREE", (10.0, -12.5, 10.5), (0, 0.5, 1.2)),
}


def prompt_seed(prompt: str, world_type: str) -> int:
    digest = hashlib.sha256(f"{world_type}\0{prompt.strip().casefold()}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def layout_points(prompt: str, world_type: str, count: int, zone: str) -> tuple[tuple[float, float, float], ...]:
    """Create stable non-grid points within a named scene zone."""
    rng = random.Random(prompt_seed(prompt + zone, world_type))
    bounds = {
        "ARCHITECTURE": (-4.2, 4.2, 0.7, 3.0),
        "PROPS": (-4.7, 4.7, -3.0, 1.0),
        "VEGETATION": (-4.8, 4.8, -3.2, 3.2),
        "CHARACTERS": (-3.8, 3.8, -2.6, 0.5),
    }[zone]
    x_min, x_max, y_min, y_max = bounds
    points = []
    for index in range(max(0, count)):
        lane = index % 4
        x = x_min + (x_max - x_min) * ((lane + 0.5) / 4.0) + rng.uniform(-0.35, 0.35)
        y = rng.uniform(y_min, y_max)
        points.append((round(x, 3), round(y, 3), 0.0))
    return tuple(points)


def profile_for(world_type: str) -> CompositionProfile:
    return PROFILES.get(world_type, PROFILES["VILLAGE"])

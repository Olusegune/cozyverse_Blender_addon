"""Renderer-independent scene plans for the Create -> Review -> Build workflow."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .terrain_spec import TERRAIN_KINDS, WATER_KINDS, infer_terrain, infer_water


WORLD_TYPES = {"VILLAGE", "CITY", "CAFE", "NATURE", "SPACE_OUTPOST", "MARKET", "FARM", "FANTASY"}
BASE_SHAPES = {"ROUNDED_RECT", "CIRCLE", "ISLAND"}
CAMERA_TYPES = {"ORTHO", "PERSPECTIVE"}


@dataclass(frozen=True)
class ScenePlan:
    schema_version: str
    title: str
    world_type: str
    style_id: str
    base_shape: str
    architecture_count: int
    prop_count: int
    vegetation_count: int
    character_count: int
    include_road: bool
    camera_type: str
    prompt: str
    water: str = "NONE"
    terrain: str = "FLAT"

    def validate(self) -> None:
        if self.schema_version != "1.0":
            raise ValueError("Unsupported scene-plan schema")
        if not self.title.strip() or not self.prompt.strip():
            raise ValueError("Scene plan requires a title and prompt")
        if self.world_type not in WORLD_TYPES:
            raise ValueError("Unsupported world type")
        if self.water not in WATER_KINDS or self.terrain not in TERRAIN_KINDS:
            raise ValueError("Unsupported water or terrain")
        if self.base_shape not in BASE_SHAPES or self.camera_type not in CAMERA_TYPES:
            raise ValueError("Unsupported base or camera configuration")
        for value in (self.architecture_count, self.prop_count, self.vegetation_count, self.character_count):
            if not 0 <= value <= 50:
                raise ValueError("Scene-plan counts must be between 0 and 50")

    def canonical_json(self) -> str:
        self.validate()
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


def infer_world_type(prompt: str) -> str:
    value = prompt.casefold()
    rules = (
        ("SPACE_OUTPOST", ("space", "lunar", "moon", "planet", "sci-fi")),
        ("CAFE", ("cafe", "coffee", "restaurant")),
        ("MARKET", ("market", "bazaar", "stall")),
        ("FARM", ("farm", "barn", "field")),
        ("CITY", ("city", "urban", "street", "neighborhood")),
        ("FANTASY", ("fantasy", "wizard", "magic", "castle")),
        ("NATURE", ("forest", "nature", "landscape")),
    )
    found = next((kind for kind, words in rules if any(word in value for word in words)), None)
    if found:
        return found
    # A river or island on its own is scenery; with a settlement it is a place to live.
    settlement = ("village", "town", "harbor", "harbour", "port", "house", "home", "cottage", "inn", "hamlet", "settlement", "bakery", "shop", "lighthouse")
    if any(word in value for word in ("river", "island", "lake", "pond", "stream", "creek", "mountain", "hill")) and not any(word in value for word in settlement):
        return "NATURE"
    return "VILLAGE"


def proposed_plan(prompt: str, style_id: str) -> ScenePlan:
    world_type = infer_world_type(prompt)
    title = world_type.replace("_", " ").title()
    counts = {
        "NATURE": (1, 3, 10, 0, False),
        "SPACE_OUTPOST": (3, 7, 1, 2, True),
        "CITY": (4, 8, 4, 2, True),
        "CAFE": (2, 8, 5, 2, True),
        "MARKET": (3, 10, 4, 3, True),
        "FARM": (2, 7, 8, 2, True),
    }.get(world_type, (3, 6, 6, 2, True))
    architecture, props, vegetation, characters, road = counts
    water = infer_water(prompt)
    return ScenePlan("1.0", title, world_type, style_id, "ISLAND" if water == "SEA" else "ROUNDED_RECT", architecture, props, vegetation, characters, road, "ORTHO", prompt.strip(), water, infer_terrain(prompt))


def parse_plan(payload: str) -> ScenePlan:
    try:
        plan = ScenePlan(**json.loads(payload))
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Scene plan is not valid JSON") from exc
    plan.validate()
    return plan

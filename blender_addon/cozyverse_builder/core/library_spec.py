"""Pure library logic: roles, licences, filtering, persistence shape and auto-fit maths.

Nothing here imports Blender, so it is fully unit-tested outside of it.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

from .asset_catalog import tokenize

SCHEMA_VERSION = 1
MODEL_EXTENSIONS = (".blend", ".glb", ".gltf", ".fbx", ".obj")

ROLES = (
    ("CAR", "Car", "Drives the road in Cars and traffic"),
    ("TREE", "Tree", "Plants and trees"),
    ("LAMP", "Street lamp", "Lamps and lanterns"),
    ("BUILDING", "Building", "Houses and shops"),
    ("CHARACTER", "Person", "People and animals"),
    ("PROP", "Prop", "Anything else that decorates"),
    ("UNTAGGED", "Untagged", "Not sorted yet"),
)
ROLE_WORDS = {
    "CAR": {"car", "sedan", "taxi", "hatchback", "suv", "van", "truck", "pickup", "coupe", "jeep", "lorry", "bus", "vehicle", "cab", "wagon", "cars"},
    "TREE": {"tree", "palm", "pine", "oak", "bush", "shrub", "plant", "birch", "willow", "trees", "forest"},
    "LAMP": {"lamp", "lantern", "streetlight", "lamppost", "lamp-post", "lights", "torch"},
    "BUILDING": {"house", "building", "shop", "cafe", "tower", "cottage", "hut", "store", "barn", "church", "castle", "station", "hall"},
    "CHARACTER": {"character", "person", "human", "man", "woman", "boy", "girl", "npc", "people", "dog", "cat", "animal", "avatar"},
    "PROP": {"prop", "crate", "barrel", "bench", "sign", "cone", "bin", "hydrant", "bollard", "chair", "table", "fence"},
}

LICENSES = (
    ("UNKNOWN", "Not sure", "You have not said what the licence allows"),
    ("OWNED", "Free to use", "Your own work, royalty free, or licensed for this use"),
    ("EDITORIAL", "Editorial only", "Restricted: renders may need extra clearance"),
)
FORWARDS = (
    ("AUTO", "Automatic", "Guess from the model's proportions"),
    ("-Y", "Faces -Y", "Blender's usual front view"),
    ("+Y", "Faces +Y", "Back-to-front models"),
    ("+X", "Faces +X", "Already pointing along X"),
    ("-X", "Faces -X", "Pointing the other way along X"),
)
# role -> (fit mode, target size in world units): LENGTH is the extent along the model's front.
FIT_TARGETS = {
    "CAR": ("LENGTH", 0.9),
    "TREE": ("HEIGHT", 1.7),
    "LAMP": ("HEIGHT", 1.1),
    "BUILDING": ("FOOTPRINT", 2.0),
    "CHARACTER": ("HEIGHT", 0.85),
    "PROP": ("FOOTPRINT", 0.5),
    "UNTAGGED": ("FOOTPRINT", 1.0),
}


def guess_role(*names: str) -> str:
    words = set(tokenize(" ".join(names)))
    ranked = sorted(((len(words & keywords), role) for role, keywords in ROLE_WORDS.items()), reverse=True)
    score, role = ranked[0]
    return role if score else "UNTAGGED"


def asset_key(path: str, inner: str = "") -> str:
    return f"{path}|{inner}" if inner else path


def split_inner(inner: str) -> tuple[str, str]:
    """('Collection', 'Name') from a stored ``Collection:Name`` string; ('', '') when empty."""
    kind, _, name = inner.partition(":")
    return (kind, name) if name else ("", "")


def new_state() -> dict:
    return {"version": SCHEMA_VERSION, "sources": [], "overrides": {}, "index": []}


def load_state(text: str) -> dict:
    """Parse stored JSON, repairing anything missing. Never raises on bad input."""
    state = new_state()
    try:
        raw = json.loads(text)
    except (TypeError, ValueError):
        return state
    if not isinstance(raw, dict):
        return state
    sources = raw.get("sources")
    if isinstance(sources, list):
        state["sources"] = [
            {"id": str(item.get("id", f"s{number}")), "label": str(item.get("label", "Library"))[:80], "path": str(item.get("path", "")), "license": item.get("license", "UNKNOWN") if item.get("license") in {entry[0] for entry in LICENSES} else "UNKNOWN", "enabled": bool(item.get("enabled", True))}
            for number, item in enumerate(sources)
            if isinstance(item, dict) and item.get("path")
        ]
    overrides = raw.get("overrides")
    if isinstance(overrides, dict):
        state["overrides"] = {str(key): dict(value) for key, value in overrides.items() if isinstance(value, dict)}
    index = raw.get("index")
    if isinstance(index, list):
        state["index"] = [item for item in index if isinstance(item, dict) and item.get("path") and item.get("key")]
    return state


def dump_state(state: dict) -> str:
    return json.dumps(state, sort_keys=True, separators=(",", ":"))


def effective(record: dict, overrides: dict, sources: dict) -> dict:
    """The record with the user's overrides and the source's default licence applied."""
    override = overrides.get(record["key"], {})
    source = sources.get(record.get("source"), {})
    return {
        **record,
        "role": override.get("role") or record.get("role_guess") or "UNTAGGED",
        "license": override.get("license") or source.get("license") or "UNKNOWN",
        "forward": override.get("forward") or "AUTO",
        "stylize": bool(override.get("stylize", False)),
        "source_label": source.get("label", ""),
    }


def filter_records(records: list[dict], query: str = "", role: str = "ALL") -> list[dict]:
    words = set(tokenize(query))
    kept = []
    for record in records:
        if role != "ALL" and record["role"] != role:
            continue
        if words:
            haystack = set(tokenize(f"{record['name']} {' '.join(record.get('tags', ()))} {record.get('source_label', '')}"))
            if not words <= haystack and not all(any(word in token for token in haystack) for word in words):
                continue
        kept.append(record)
    return sorted(kept, key=lambda item: (item["name"].casefold(), item["key"].casefold()))


def page_of(records: list, page: int, size: int) -> tuple[list, int, int]:
    """(items on the page, clamped page number, total pages)."""
    total = max(1, math.ceil(len(records) / max(1, size)))
    page = max(0, min(page, total - 1))
    return records[page * size : (page + 1) * size], page, total


def default_forward(size_x: float, size_y: float) -> str:
    """Models longer in Y usually follow Blender's front view (-Y); otherwise assume +X."""
    return "-Y" if size_y > size_x * 1.1 else "+X"


def _rotation_for(forward: str) -> float:
    return {"+X": 0.0, "-X": math.pi, "+Y": -math.pi / 2, "-Y": math.pi / 2}[forward]


def fit_transform(minimum: tuple[float, float, float], maximum: tuple[float, float, float], role: str, forward: str = "AUTO") -> dict:
    """Uniform scale, yaw and offset that stand a model on the ground, facing +X, sized for its role.

    The returned transform maps a model point ``p`` to ``R(yaw) * scale * (p - (cx, cy, min_z))``.
    """
    sx, sy, sz = (maximum[0] - minimum[0], maximum[1] - minimum[1], maximum[2] - minimum[2])
    if min(sx, sy, sz) <= 0.0 and max(sx, sy, sz) <= 0.0:
        raise ValueError("The model has no size")
    if forward == "AUTO":
        forward = default_forward(sx, sy)
    mode, target = FIT_TARGETS.get(role, FIT_TARGETS["UNTAGGED"])
    if mode == "LENGTH":
        size = sx if forward in {"+X", "-X"} else sy
    elif mode == "HEIGHT":
        size = sz
    else:
        size = max(sx, sy)
    if size <= 1e-9:
        raise ValueError("The model has no size along the fitting axis")
    scale = target / size
    yaw = _rotation_for(forward)
    center = ((minimum[0] + maximum[0]) / 2, (minimum[1] + maximum[1]) / 2, minimum[2])
    cos, sin = math.cos(yaw), math.sin(yaw)
    rotated = (center[0] * cos - center[1] * sin, center[0] * sin + center[1] * cos, center[2])
    return {"scale": scale, "yaw": yaw, "offset": (-rotated[0] * scale, -rotated[1] * scale, -rotated[2] * scale), "forward": forward}


@dataclass(frozen=True)
class LicenseNote:
    level: str
    text: str


def license_note(licenses: list[str]) -> LicenseNote | None:
    """A human note about the strictest licence among the given ones, or None when all is clear."""
    if "EDITORIAL" in licenses:
        return LicenseNote("WARNING", "This world uses editorial-only assets. Check their licence before publishing renders.")
    if "UNKNOWN" in licenses:
        return LicenseNote("INFO", "Some assets have no licence noted. Set it in the Library so you remember what is allowed.")
    return None

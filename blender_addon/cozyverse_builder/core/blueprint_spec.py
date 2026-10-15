"""The Director's contract: a validated Scene Blueprint and an allowlist of follow-up commands.

A blueprint describes a world in plain data. It can come from the offline planner or from an AI
model, and either way it is *only data*: every field is checked, clamped and sanitised here, text
that looks like code is rejected, and nothing in this module can run anything. Follow-up edits are
a short list of allowlisted commands, never scripts.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, replace

from .atmosphere_spec import PRESETS
from .scene_plan import WORLD_TYPES, ScenePlan, proposed_plan
from .style_spec import STYLE_PRESETS
from .terrain_spec import TERRAIN_KINDS, WATER_KINDS, infer_terrain, infer_water

SCHEMA_VERSION = "1.0"
LOOKS = tuple(PRESETS)
WEATHERS = ("CLEAR", "RAIN", "FOG", "SNOW")
SEASONS = ("SPRING", "SUMMER", "AUTUMN", "WINTER")
ASSET_ROLES = ("BUILDING", "TREE", "PROP", "CHARACTER", "CAR", "LAMP")
ASSET_SOURCES = ("AUTO", "LIBRARY", "PROCEDURAL", "GENERATE")
COUNT_LIMITS = {"architecture": (0, 8), "props": (0, 20), "vegetation": (0, 16), "characters": (0, 12)}
MAX_ASSETS = 12
MAX_COMMANDS = 16
SHOTS = ("WIDE", "HERO", "DETAIL")

_TOP_LEVEL = {"schema_version", "title", "summary", "world", "counts", "atmosphere", "motion", "assets", "warnings"}
_FORBIDDEN_KEYS = {"python", "script", "code", "exec", "eval", "shell", "command_line", "subprocess", "bpy", "import", "__import__"}
_CODE_PATTERN = re.compile(
    r"(?i)(\bimport\s+\w|\bexec\s*\(|\beval\s*\(|__\w+__|\bos\.\w|\bsubprocess|\bbpy\.|<\s*script|\bsystem\s*\(|\brm\s+-rf|\$\(|`|;\s*\w+\s*\(|\bopen\s*\(|\bcompile\s*\()"
)
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


class BlueprintError(ValueError):
    """The plan or command list was rejected. The message is safe to show to the user."""


def clean_text(value, limit: int) -> str:
    """A bounded single-line string, rejecting anything that looks like code."""
    text = _CONTROL.sub("", str(value if value is not None else "")).replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if _CODE_PATTERN.search(text):
        raise BlueprintError("The plan contained something that looks like code, so it was rejected")
    return text[:limit]


def _number(value, low: float, high: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:  # NaN
        return default
    return max(low, min(high, number))


def _choice(value, allowed, default):
    return value if isinstance(value, str) and value in allowed else default


@dataclass(frozen=True)
class AssetNeed:
    id: str
    role: str
    description: str
    source: str = "AUTO"
    library_key: str = ""
    provider: str = ""
    estimated_credits: int = 0
    hero: bool = False


@dataclass(frozen=True)
class Blueprint:
    schema_version: str
    title: str
    summary: str
    prompt: str
    style_id: str
    world_type: str
    water: str
    terrain: str
    camera_type: str
    include_road: bool
    counts: dict
    atmosphere: dict
    motion: dict
    assets: tuple[AssetNeed, ...] = ()
    warnings: tuple[str, ...] = ()
    source: str = "OFFLINE"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["assets"] = [asdict(asset) for asset in self.assets]
        data["warnings"] = list(self.warnings)
        return data

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def _walk_strings(value, depth: int = 0):
    if depth > 6:
        raise BlueprintError("The plan is nested too deeply")
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _walk_strings(item, depth + 1)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_strings(item, depth + 1)


def reject_executable_content(raw) -> None:
    """Refuse the whole payload if any key or text is a code vector."""
    if isinstance(raw, dict):
        stack = [raw]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if {str(key).lower() for key in node} & _FORBIDDEN_KEYS:
                    raise BlueprintError("The plan contained executable content, so it was rejected")
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    for text in _walk_strings(raw):
        if _CODE_PATTERN.search(text):
            raise BlueprintError("The plan contained something that looks like code, so it was rejected")


def validate_blueprint(raw, prompt: str = "", style_id: str = "COZY_VILLAGE", source: str = "AI") -> Blueprint:
    """Turn untrusted data into a Blueprint, repairing small problems and rejecting dangerous ones."""
    if not isinstance(raw, dict):
        raise BlueprintError("The plan was not a JSON object")
    reject_executable_content(raw)
    warnings: list[str] = []
    ignored = sorted(str(key) for key in raw if key not in _TOP_LEVEL)
    if ignored:
        warnings.append(f"Ignored unknown fields: {', '.join(ignored[:5])}")
    if raw.get("schema_version") not in {None, SCHEMA_VERSION}:
        raise BlueprintError("This plan uses a newer format than this add-on understands")
    base = proposed_plan(prompt or str(raw.get("title") or "A cozy world"), style_id)
    world = raw.get("world") if isinstance(raw.get("world"), dict) else {}
    title = clean_text(raw.get("title") or base.title, 80) or base.title
    world_type = _choice(world.get("type"), WORLD_TYPES, None)
    if world_type is None:
        world_type = base.world_type
        if world.get("type"):
            warnings.append(f"Unknown world type {clean_text(world.get('type'), 30)!r}; used {world_type}")
    style = _choice(world.get("style"), set(STYLE_PRESETS), None)
    if style is None:
        style = style_id if style_id in STYLE_PRESETS else "COZY_VILLAGE"
        if world.get("style"):
            warnings.append("Unknown style; kept your chosen style")
    water = _choice(world.get("water"), WATER_KINDS, base.water)
    terrain = _choice(world.get("terrain"), TERRAIN_KINDS, base.terrain)
    camera = _choice(world.get("camera"), ("ORTHO", "PERSPECTIVE"), base.camera_type)
    include_road = bool(world.get("include_road", base.include_road))
    defaults = {"architecture": base.architecture_count, "props": base.prop_count, "vegetation": base.vegetation_count, "characters": base.character_count}
    given = raw.get("counts") if isinstance(raw.get("counts"), dict) else {}
    counts = {}
    for name, (low, high) in COUNT_LIMITS.items():
        number = int(_number(given.get(name, defaults[name]), low, high, defaults[name]))
        if name in given and int(_number(given[name], -10**6, 10**6, number)) != number:
            warnings.append(f"Limited {name} to {number}")
        counts[name] = number

    mood = raw.get("atmosphere") if isinstance(raw.get("atmosphere"), dict) else {}
    atmosphere: dict = {}
    if mood.get("look") is not None:
        look = _choice(mood.get("look"), LOOKS, None)
        if look is None:
            warnings.append("Unknown look ignored")
        else:
            atmosphere["look"] = look
    for key, low, high in (("time_hour", 0.0, 24.0), ("clouds", 0.0, 100.0), ("stars", 0.0, 100.0), ("fog", 0.0, 100.0), ("rain", 0.0, 100.0), ("warmth", 0.0, 100.0)):
        if mood.get(key) is not None:
            atmosphere[key] = round(_number(mood[key], low, high, low), 2)
    if mood.get("weather") is not None:
        atmosphere["weather"] = _choice(mood["weather"], WEATHERS, "CLEAR")
    if mood.get("season") is not None:
        atmosphere["season"] = _choice(mood["season"], SEASONS, "SUMMER")

    movement = raw.get("motion") if isinstance(raw.get("motion"), dict) else {}
    motion = {
        "life": bool(movement.get("life", True)),
        "cars": int(_number(movement.get("cars", 0), 0, 4, 0)),
        "train": bool(movement.get("train", False)),
        "build_up": bool(movement.get("build_up", False)),
    }
    if water == "SEA" and motion["train"]:
        motion["train"] = False
        warnings.append("A train needs solid ground, so it was left out of the sea island")
    if not include_road and motion["cars"]:
        motion["cars"] = 0
        warnings.append("Cars need a road, so they were left out")

    assets: list[AssetNeed] = []
    for index, item in enumerate(raw.get("assets") if isinstance(raw.get("assets"), list) else []):
        if len(assets) >= MAX_ASSETS:
            warnings.append(f"Kept the first {MAX_ASSETS} assets")
            break
        if not isinstance(item, dict):
            continue
        description = clean_text(item.get("description"), 120)
        if not description:
            continue
        provider = _choice(str(item.get("provider", "")).upper(), ("TRIPO", "MESHY"), "")
        assets.append(
            AssetNeed(
                id=re.sub(r"[^a-z0-9_]+", "_", clean_text(item.get("id") or f"asset_{index + 1}", 40).lower()) or f"asset_{index + 1}",
                role=_choice(str(item.get("role", "")).upper(), ASSET_ROLES, "PROP"),
                description=description,
                source=_choice(str(item.get("source", "")).upper(), ASSET_SOURCES, "AUTO"),
                library_key="",  # an AI never gets to name files on your machine; matching happens locally
                provider=provider,
                hero=bool(item.get("hero", False)),
            )
        )
    return Blueprint(
        SCHEMA_VERSION,
        title,
        clean_text(raw.get("summary") or "", 400),
        re.sub(r"\s+", " ", _CONTROL.sub("", prompt or "")).strip()[:4000] or title,  # the user's own words are kept as written
        style,
        world_type,
        water,
        terrain,
        camera,
        include_road,
        counts,
        atmosphere,
        motion,
        tuple(assets),
        tuple(warnings[:8]),
        source,
    )


def to_schema(bp: Blueprint) -> dict:
    """The blueprint in the same shape validate_blueprint reads, so it can be stored and reloaded."""
    return {
        "schema_version": SCHEMA_VERSION,
        "title": bp.title,
        "summary": bp.summary,
        "world": {"type": bp.world_type, "style": bp.style_id, "water": bp.water, "terrain": bp.terrain, "camera": bp.camera_type, "include_road": bp.include_road},
        "counts": dict(bp.counts),
        "atmosphere": dict(bp.atmosphere),
        "motion": dict(bp.motion),
        "assets": [{"id": a.id, "role": a.role, "description": a.description, "source": a.source, "provider": a.provider, "hero": a.hero} for a in bp.assets],
    }


def blueprint_to_plan(bp: Blueprint) -> ScenePlan:
    plan = ScenePlan(
        "1.0",
        bp.title,
        bp.world_type,
        bp.style_id,
        "ISLAND" if bp.water == "SEA" else "ROUNDED_RECT",
        bp.counts["architecture"],
        bp.counts["props"],
        bp.counts["vegetation"],
        bp.counts["characters"],
        bp.include_road,
        bp.camera_type,
        bp.prompt,
        bp.water,
        bp.terrain,
    )
    plan.validate()
    return plan


# ----------------------------------------------------------------------------- the offline planner

_LOOK_RULES = (
    ("STARRY_NIGHT", {"starry", "stars", "starlit", "starlight"}),
    ("MOONLIT", {"moonlit", "moonlight", "midnight", "night", "nighttime"}),
    ("FIRST_SNOW", {"snow", "snowy", "snowfall", "snowing", "winter"}),
    ("RAINY_CAFE", {"rain", "rainy", "raining", "drizzle", "storm", "stormy", "monsoon", "wet"}),
    ("SUNSET_GLOW", {"sunset", "dusk", "sundown"}),
    ("BLUE_HOUR", {"twilight", "bluehour"}),
    ("MISTY_DAWN", {"dawn", "misty", "morning", "sunrise", "foggy"}),
    ("OVERCAST", {"overcast", "cloudy", "grey", "gray"}),
    ("BRIGHT_DAY", {"sunny", "noon", "midday", "bright", "daytime"}),
    ("GOLDEN_HOUR", {"golden", "evening", "afternoon"}),
)
_SEASON_WORDS = {"SPRING": {"spring", "blossom", "blossoms"}, "SUMMER": {"summer"}, "AUTUMN": {"autumn", "fall", "harvest"}, "WINTER": {"winter", "snow", "snowy", "christmas"}}
_ROLE_NOUNS = {
    "BUILDING": {"store", "shop", "cafe", "bakery", "lighthouse", "windmill", "temple", "church", "tower", "barn", "cabin", "cottage", "house", "inn", "pavilion", "mill", "castle", "station", "hut", "restaurant", "market", "school", "library"},
    "TREE": {"tree", "trees", "palm", "palms", "pine", "oak", "willow", "bamboo", "flower", "flowers", "garden", "hedge", "bush", "bushes", "plants"},
    "PROP": {"lamp", "lantern", "lanterns", "bench", "fountain", "sign", "cart", "crate", "crates", "barrel", "barrels", "boat", "boats", "bridge", "well", "fence", "stall", "umbrella", "umbrellas", "bicycle", "bike"},
    "CAR": {"car", "cars", "jeepney", "taxi", "truck", "bus", "tricycle", "van", "scooter", "scooters"},
    "CHARACTER": {"villager", "villagers", "fisherman", "cat", "cats", "dog", "dogs", "person", "people", "child", "children", "vendor", "vendors", "customers", "baker"},
}
_STOP = {"a", "an", "the", "and", "with", "of", "in", "on", "at", "by", "to", "small", "tiny", "little", "cozy", "quiet", "beautiful", "some", "few", "many", "near", "next", "from", "beside", "behind", "under", "over", "around", "along", "across", "through", "between", "above", "below", "front", "inside", "outside", "that", "this", "for", "as"}


def _tokens(text: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", text.casefold()) if token]


def infer_atmosphere(prompt: str) -> dict:
    words = set(_tokens(prompt))
    atmosphere: dict = {}
    look = next((name for name, vocabulary in _LOOK_RULES if words & vocabulary), None)
    if look:
        atmosphere["look"] = look
    season = next((name for name, vocabulary in _SEASON_WORDS.items() if words & vocabulary), None)
    if season:
        atmosphere["season"] = season
    if words & {"fog", "foggy", "mist", "misty"}:
        atmosphere["fog"] = 45.0
    if words & {"cloudy", "overcast", "clouds"}:
        atmosphere["clouds"] = 80.0
    if words & {"stars", "starry", "starlit"}:
        atmosphere["stars"] = 90.0
    if words & {"windy", "breezy"}:
        atmosphere["wind"] = 60.0
    return atmosphere


def infer_motion(prompt: str, include_road: bool, water: str) -> dict:
    words = set(_tokens(prompt))
    cars = 2 if include_road and words & (_ROLE_NOUNS["CAR"] | {"traffic", "street"}) else 0
    train = bool(words & {"train", "railway", "railroad", "trains", "railway"}) and water != "SEA"
    return {"life": True, "cars": cars, "train": train, "build_up": bool(words & {"animated", "assembling", "buildup"})}


def extract_assets(prompt: str) -> tuple[AssetNeed, ...]:
    """Name the things the description asks for, with the adjectives that make each one specific."""
    every_noun = set().union(*_ROLE_NOUNS.values())
    found: list[AssetNeed] = []
    seen: set[str] = set()
    for clause in re.split(r"[;,.:()]|\band\b|\bwith\b|\bplus\b", prompt, flags=re.IGNORECASE):
        tokens = _tokens(clause)
        for index, token in enumerate(tokens):
            role = next((name for name, nouns in _ROLE_NOUNS.items() if token in nouns), None)
            if role is None or token in seen:
                continue
            seen.add(token)
            before: list[str] = []
            for other in reversed(tokens[max(0, index - 3):index]):
                if other in _STOP or other in every_noun:
                    break
                before.insert(0, other)
            found.append(AssetNeed(f"{role.lower()}_{len(found) + 1}", role, " ".join([*before, token])[:120], "AUTO", hero=not any(a.hero for a in found) and role == "BUILDING"))
            if len(found) >= 8:
                return tuple(found)
    return tuple(found)


def plan_offline(prompt: str, style_id: str = "COZY_VILLAGE") -> Blueprint:
    """A deterministic plan from keywords alone. Used with no key, no network, and as the fallback."""
    prompt = re.sub(r"\s+", " ", _CONTROL.sub("", prompt or "")).strip() or "a cozy world"
    base = proposed_plan(prompt, style_id)
    include_road = base.include_road
    return validate_blueprint(
        {
            "title": base.title,
            "summary": f"{base.title} in the {STYLE_PRESETS.get(style_id, STYLE_PRESETS['COZY_VILLAGE']).label} style.",
            "world": {"type": base.world_type, "style": style_id, "water": base.water, "terrain": base.terrain, "camera": base.camera_type, "include_road": include_road},
            "counts": {"architecture": base.architecture_count, "props": base.prop_count, "vegetation": base.vegetation_count, "characters": base.character_count},
            "atmosphere": infer_atmosphere(prompt),
            "motion": infer_motion(prompt, include_road, base.water),
            "assets": [asdict(asset) for asset in extract_assets(prompt)],
        },
        prompt,
        style_id,
        source="OFFLINE",
    )


def blueprint_atmosphere_patch(bp: Blueprint) -> dict:
    """Settings values for the Mood tab, only for what the plan actually specified."""
    patch: dict = {}
    values = bp.atmosphere
    if "look" in values:
        patch["atmosphere_preset"] = values["look"]
    mapping = {"time_hour": "time_hour", "clouds": "clouds_amount", "stars": "stars_amount", "fog": "fog_amount", "rain": "rain_amount", "warmth": "warmth", "wind": "wind_amount"}
    patch.update({target: values[source] for source, target in mapping.items() if source in values})
    if "weather" in values:
        patch["weather"] = values["weather"]
    if "season" in values:
        patch["season"] = values["season"]
    return patch


def describe_blueprint(bp: Blueprint) -> list[str]:
    """Short lines for the Review panel."""
    lines = [f"{bp.world_type.replace('_', ' ').title()} · {bp.style_id.replace('_', ' ').title()}"]
    scenery = [name for name, kind in (("lake", "LAKE"), ("pond", "POND"), ("river", "RIVER"), ("sea", "SEA")) if bp.water == kind] + (["hills"] if bp.terrain == "HILLS" else [])
    if scenery:
        lines.append("Landscape: " + ", ".join(scenery))
    c = bp.counts
    lines.append(f"{c['architecture']} buildings · {c['props']} props · {c['vegetation']} plants · {c['characters']} people")
    if bp.atmosphere:
        lines.append("Mood: " + ", ".join(f"{key.replace('_', ' ')} {value}" for key, value in sorted(bp.atmosphere.items())))
    extras = [label for label, on in (("ambient life", bp.motion["life"]), (f"{bp.motion['cars']} cars", bp.motion["cars"]), ("a train", bp.motion["train"]), ("build-up animation", bp.motion["build_up"])) if on]
    if extras:
        lines.append("Motion: " + ", ".join(extras))
    return lines


def diff_blueprints(old: Blueprint, new: Blueprint) -> list[str]:
    """What changed between two plans, in plain words."""
    changes = []
    for label, a, b in (("World", old.world_type, new.world_type), ("Style", old.style_id, new.style_id), ("Water", old.water, new.water), ("Land", old.terrain, new.terrain)):
        if a != b:
            changes.append(f"{label}: {a.title()} → {b.title()}")
    for name in COUNT_LIMITS:
        if old.counts[name] != new.counts[name]:
            changes.append(f"{name.title()}: {old.counts[name]} → {new.counts[name]}")
    for key in sorted(set(old.atmosphere) | set(new.atmosphere)):
        if old.atmosphere.get(key) != new.atmosphere.get(key):
            changes.append(f"Mood {key}: {old.atmosphere.get(key, 'unset')} → {new.atmosphere.get(key, 'unset')}")
    for key in sorted(new.motion):
        if old.motion.get(key) != new.motion.get(key):
            changes.append(f"Motion {key}: {old.motion.get(key)} → {new.motion.get(key)}")
    added = {a.description for a in new.assets} - {a.description for a in old.assets}
    removed = {a.description for a in old.assets} - {a.description for a in new.assets}
    changes.extend(f"Adds: {text}" for text in sorted(added))
    changes.extend(f"Drops: {text}" for text in sorted(removed))
    return changes


# ----------------------------------------------------------------------------- follow-up commands


@dataclass(frozen=True)
class Command:
    verb: str
    args: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"verb": self.verb, "args": dict(self.args)}


_TARGET_ROLES = ("BUILDING", "TREE", "PROP", "CHARACTER")
VERBS = ("SET_LOOK", "SET_TIME", "SET_WEATHER", "SET_SEASON", "SET_CLOUDS", "SET_STARS", "SET_FOG", "SET_WARMTH", "ADD", "REMOVE", "MOVE", "SCALE", "SHOT", "MOTION", "NEW_VERSION")
_FEATURES = ("LIFE", "CARS", "TRAIN", "BUILDUP", "DAYCYCLE")


def _target(value) -> dict:
    if not isinstance(value, dict):
        return {"role": "BUILDING", "index": 0}
    if value.get("name"):
        name = clean_text(value["name"], 80)
        if not re.fullmatch(r"[A-Za-z0-9_.\- ]+", name):
            raise BlueprintError("A command named an object in an unsafe way")
        return {"name": name}
    return {"role": _choice(str(value.get("role", "")).upper(), _TARGET_ROLES, "BUILDING"), "index": int(_number(value.get("index", 0), 0, 50, 0))}


def validate_command(raw) -> Command:
    if not isinstance(raw, dict):
        raise BlueprintError("A command was not an object")
    reject_executable_content(raw)
    verb = str(raw.get("verb", "")).upper()
    if verb not in VERBS:
        raise BlueprintError(f"{clean_text(verb, 30)!r} is not an allowed command")
    args = raw.get("args") if isinstance(raw.get("args"), dict) else {}
    if verb == "SET_LOOK":
        look = _choice(str(args.get("look", "")).upper(), LOOKS, None)
        if look is None:
            raise BlueprintError("SET_LOOK needs one of the known looks")
        return Command(verb, {"look": look})
    if verb == "SET_TIME":
        return Command(verb, {"hour": round(_number(args.get("hour"), 0.0, 24.0, 12.0), 2)})
    if verb == "SET_WEATHER":
        out = {"weather": _choice(str(args.get("weather", "")).upper(), WEATHERS, "CLEAR")}
        if args.get("amount") is not None:
            out["amount"] = round(_number(args["amount"], 0.0, 100.0, 50.0), 1)
        return Command(verb, out)
    if verb == "SET_SEASON":
        return Command(verb, {"season": _choice(str(args.get("season", "")).upper(), SEASONS, "SUMMER")})
    if verb in {"SET_CLOUDS", "SET_STARS", "SET_FOG"}:
        return Command(verb, {"amount": round(_number(args.get("amount"), 0.0, 100.0, 50.0), 1)})
    if verb == "SET_WARMTH":
        if args.get("value") is not None:
            return Command(verb, {"value": round(_number(args["value"], 0.0, 100.0, 50.0), 1)})
        return Command(verb, {"delta": round(_number(args.get("delta"), -50.0, 50.0, 0.0), 1)})
    if verb in {"ADD", "REMOVE"}:
        out = {"role": _choice(str(args.get("role", "")).upper(), _TARGET_ROLES, "PROP"), "count": int(_number(args.get("count", 1), 1, 8, 1))}
        if verb == "ADD":
            out["description"] = clean_text(args.get("description", ""), 80)
        return Command(verb, out)
    if verb == "MOVE":
        return Command(verb, {"target": _target(args.get("target")), "dx": round(_number(args.get("dx"), -6.0, 6.0, 0.0), 2), "dy": round(_number(args.get("dy"), -6.0, 6.0, 0.0), 2)})
    if verb == "SCALE":
        return Command(verb, {"target": _target(args.get("target")), "factor": round(_number(args.get("factor"), 0.5, 2.0, 1.0), 2)})
    if verb == "SHOT":
        return Command(verb, {"shot": _choice(str(args.get("shot", "")).upper(), SHOTS, "WIDE")})
    if verb == "MOTION":
        feature = _choice(str(args.get("feature", "")).upper(), _FEATURES, None)
        if feature is None:
            raise BlueprintError("MOTION needs a known feature")
        return Command(verb, {"feature": feature, "on": bool(args.get("on", True)), "count": int(_number(args.get("count", 2), 1, 4, 2))})
    out = {}
    if args.get("water") is not None:
        out["water"] = _choice(str(args["water"]).upper(), WATER_KINDS, "NONE")
    if args.get("terrain") is not None:
        out["terrain"] = _choice(str(args["terrain"]).upper(), TERRAIN_KINDS, "FLAT")
    if args.get("style") is not None:
        out["style"] = _choice(str(args["style"]).upper(), set(STYLE_PRESETS), "COZY_VILLAGE")
    return Command("NEW_VERSION", out)


def validate_commands(raw) -> tuple[tuple[Command, ...], list[str]]:
    """(valid commands, problems). Bad commands are dropped one by one; a bad list is rejected."""
    if not isinstance(raw, list):
        raise BlueprintError("The commands were not a list")
    commands: list[Command] = []
    problems: list[str] = []
    for item in raw[:MAX_COMMANDS]:
        try:
            commands.append(validate_command(item))
        except BlueprintError as exc:
            problems.append(str(exc))
    if len(raw) > MAX_COMMANDS:
        problems.append(f"Kept the first {MAX_COMMANDS} commands")
    if raw and not commands:
        raise BlueprintError("None of the commands were allowed: " + "; ".join(problems[:3]))
    return tuple(commands), problems


def describe_command(command: Command) -> str:
    a = command.args
    verb = command.verb
    if verb == "SET_LOOK":
        return f"Switch to the {a['look'].replace('_', ' ').title()} look"
    if verb == "SET_TIME":
        return f"Set the time to {int(a['hour']):02d}:{int((a['hour'] % 1) * 60):02d}"
    if verb == "SET_WEATHER":
        return f"Make the weather {a['weather'].lower()}" + (f" ({a['amount']:.0f}%)" if "amount" in a else "")
    if verb == "SET_SEASON":
        return f"Set the season to {a['season'].lower()}"
    if verb in {"SET_CLOUDS", "SET_STARS", "SET_FOG"}:
        return f"Set {verb.split('_')[1].lower()} to {a['amount']:.0f}%"
    if verb == "SET_WARMTH":
        return f"Set warmth to {a['value']:.0f}%" if "value" in a else f"Make the light {'warmer' if a['delta'] >= 0 else 'cooler'} by {abs(a['delta']):.0f}"
    if verb == "ADD":
        return f"Add {a['count']} x {(a.get('description') or a['role'].lower())}"
    if verb == "REMOVE":
        return f"Archive up to {a['count']} {a['role'].lower()} (hidden, kept)"
    if verb == "MOVE":
        return f"Move {_target_text(a['target'])} by ({a['dx']:+.1f}, {a['dy']:+.1f})"
    if verb == "SCALE":
        return f"Scale {_target_text(a['target'])} by {a['factor']:.2f}x"
    if verb == "SHOT":
        return f"Switch to the {a['shot'].lower()} camera"
    if verb == "MOTION":
        return f"Turn {a['feature'].lower()} {'on' if a['on'] else 'off'}" + (f" ({a['count']})" if a["feature"] == "CARS" and a["on"] else "")
    changes = ", ".join(f"{key} {value}" for key, value in a.items())
    return f"Build a new version with {changes}" if changes else "Build a new version"


def _target_text(target: dict) -> str:
    return target["name"] if "name" in target else f"the {target['role'].lower()}" + (f" #{target['index'] + 1}" if target.get("index") else "")


_DIRECTIONS = {"left": (-1.5, 0.0), "right": (1.5, 0.0), "forward": (0.0, -1.5), "closer": (0.0, -1.5), "back": (0.0, 1.5), "backward": (0.0, 1.5), "up": (0.0, 1.5), "down": (0.0, -1.5)}


def commands_from_text(text: str) -> tuple[tuple[Command, ...], list[str]]:
    """Understand a short follow-up without an AI. Returns (commands, phrases it could not use).

    "More flowers; less clutter; warmer" is three small requests, so each clause is read on its own.
    """
    commands: list[Command] = []
    ignored: list[str] = []
    for clause in re.split(r"[;,.\n]|\band\b|\bbut\b|\bthen\b", text or "", flags=re.IGNORECASE):
        if clause.strip():
            found, left = _commands_from_clause(clause)
            commands.extend(found)
            ignored.extend(left)
    merged = {}
    for command in [c for c in commands if c.verb == "NEW_VERSION"]:  # one rebuild, however many clauses asked for it
        merged.update(command.args)
    commands = [c for c in commands if c.verb != "NEW_VERSION"] + ([Command("NEW_VERSION", merged)] if merged else [])
    unique, seen_commands = [], set()
    for command in commands:  # Commands hold a dict, so compare them by their JSON
        key = json.dumps(command.to_dict(), sort_keys=True)
        if key not in seen_commands:
            seen_commands.add(key)
            unique.append(command)
    return tuple(unique[:MAX_COMMANDS]), list(dict.fromkeys(ignored))[:6]


def _commands_from_clause(text: str) -> tuple[list[Command], list[str]]:
    words = _tokens(text)
    word_set = set(words)
    commands: list[Command] = []
    used: set[str] = set()

    def add(verb: str, **args):
        commands.append(validate_command({"verb": verb, "args": args}))

    def has(*vocabulary) -> bool:
        hit = word_set & set(vocabulary)
        used.update(hit)
        return bool(hit)

    more = has("more", "add", "plant", "extra")
    fewer = has("less", "fewer", "remove", "reduce", "declutter", "clutter")
    if has("flowers", "flower", "plants", "greenery", "garden", "trees", "tree", "bushes", "hedge") and not fewer:
        add("ADD", role="TREE", count=3, description="flowers and plants" if word_set & {"flowers", "flower", "garden"} else "trees and plants")
    if fewer:
        role = "TREE" if word_set & {"trees", "tree", "plants", "flowers"} else "CHARACTER" if word_set & {"people", "characters", "villagers"} else "PROP"
        add("REMOVE", role=role, count=3)
    if more and has("people", "villagers", "characters", "customers", "cat", "dog", "cats", "dogs"):
        add("ADD", role="CHARACTER", count=2, description="villagers")
    if more and has("bench", "benches", "lamp", "lamps", "lantern", "lanterns", "fountain", "crates", "barrels", "umbrellas"):
        add("ADD", role="PROP", count=2, description=next(w for w in words if w in {"bench", "benches", "lamp", "lamps", "lantern", "lanterns", "fountain", "crates", "barrels", "umbrellas"}))
    if more and has("house", "houses", "shop", "cafe", "store", "building", "buildings", "bakery"):
        add("ADD", role="BUILDING", count=1, description="a building")
    if has("warmer", "warm", "cozier"):
        add("SET_WARMTH", delta=15)
    if has("cooler", "colder", "cool"):
        add("SET_WARMTH", delta=-15)
    if has("rain", "rainy", "raining", "drizzle"):
        add("SET_WEATHER", weather="RAIN", amount=60)
    if has("snow", "snowy", "snowing"):
        add("SET_WEATHER", weather="SNOW", amount=60)
        add("SET_SEASON", season="WINTER")
    if has("fog", "foggy", "mist", "misty"):
        add("SET_FOG", amount=45)
    if has("sunny", "clear") and not word_set & {"night"}:
        add("SET_WEATHER", weather="CLEAR")
    if has("night", "midnight"):
        add("SET_LOOK", look="STARRY_NIGHT" if word_set & {"stars", "starry"} else "MOONLIT")
    elif has("sunset", "dusk"):
        add("SET_LOOK", look="SUNSET_GLOW")
    elif has("dawn", "sunrise", "morning"):
        add("SET_LOOK", look="MISTY_DAWN")
    elif has("noon", "midday", "daytime"):
        add("SET_LOOK", look="BRIGHT_DAY")
    elif has("evening", "golden"):
        add("SET_LOOK", look="GOLDEN_HOUR")
    if has("stars", "starry"):
        add("SET_STARS", amount=90)
    if has("cloudier", "cloudy", "overcast", "clouds"):
        add("SET_CLOUDS", amount=80)
    for season in ("spring", "summer", "autumn", "fall", "winter"):
        if has(season) and season != "winter":
            add("SET_SEASON", season="AUTUMN" if season == "fall" else season.upper())
    if has("wide", "overview"):
        add("SHOT", shot="WIDE")
    if has("closeup", "close", "detail"):
        add("SHOT", shot="DETAIL")
    if has("hero"):
        add("SHOT", shot="HERO")
    if has("traffic", "cars", "car"):
        add("MOTION", feature="CARS", on=not fewer, count=2)
    if has("train", "railway"):
        add("MOTION", feature="TRAIN", on=not fewer)
    if has("animate", "buildup", "assemble"):
        add("MOTION", feature="BUILDUP", on=True)
    water = infer_water(text)
    terrain = infer_terrain(text)
    if (water != "NONE" or terrain != "FLAT") and (more or word_set & {"lake", "pond", "river", "sea", "hills", "island"}):
        change = {}
        if water != "NONE":
            change["water"] = water
        if terrain != "FLAT":
            change["terrain"] = terrain
        add("NEW_VERSION", **change)
        used.update(word_set & {"lake", "pond", "river", "sea", "hills", "island", "mountain", "mountains"})
    for direction, (dx, dy) in _DIRECTIONS.items():
        if direction in word_set and word_set & {"move", "shift", "push"}:
            role = "TREE" if word_set & {"tree", "trees"} else "BUILDING"
            commands.append(Command("MOVE", {"target": {"role": role, "index": 0}, "dx": dx, "dy": dy}))
            used.update({direction, "move", "shift", "push"})
    if word_set & {"bigger", "larger", "taller"}:
        commands.append(Command("SCALE", {"target": {"role": "BUILDING", "index": 0}, "factor": 1.25}))
        used.update({"bigger", "larger", "taller"})
    if word_set & {"smaller", "shorter"}:
        commands.append(Command("SCALE", {"target": {"role": "BUILDING", "index": 0}, "factor": 0.8}))
        used.update({"smaller", "shorter"})
    ignored = [word for word in words if word not in used and word not in _STOP and len(word) > 3 and word not in {"make", "please", "this", "that", "with", "some", "more", "much", "very", "like", "want", "scene", "world", "into"}]
    return commands, ignored


def with_counts(bp: Blueprint, **changes: int) -> Blueprint:
    counts = dict(bp.counts)
    for name, value in changes.items():
        low, high = COUNT_LIMITS[name]
        counts[name] = max(low, min(high, int(value)))
    return replace(bp, counts=counts)

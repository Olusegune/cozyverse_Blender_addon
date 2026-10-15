"""The Director: turns a description (and optionally a reference image) into a plan, then keeps editing the world.

Planning works fully offline. An AI model is optional and only used after you confirm exactly what
will be sent. Whatever the source, a plan is validated data, and every follow-up is a short list of
allowlisted commands: the Director never runs generated code, never moves anything you locked, and
archives instead of deleting, so Blender's Undo (or "Bring back") restores everything.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import queue
import random
import re
import threading

import bpy
from bpy.props import StringProperty

from . import library
from .core import blueprint_spec as spec
from .core import director_llm as llm
from .core import library_spec as lib_spec
from .core import terrain_spec
from .core.blueprint_spec import Blueprint, BlueprintError, Command
from .materials import create_material
from .motion import PART_SUFFIX
from .operators import _log_activity, _prompt_from_settings
from .vehicles import _ball, _box, _cyl, road_for
from .world_builder import _build_architecture, _build_character, _new_collection, _plant

AI_RESULTS: queue.SimpleQueue = queue.SimpleQueue()
DIRECTOR = "CV_DIRECTOR"
ARCHIVE = "CV_ARCHIVE"
USER_ASSETS = "CV_USER_ASSETS"
_ROLE_COLLECTION = {"BUILDING": "CV_ARCHITECTURE", "TREE": "CV_VEGETATION", "PROP": "CV_PROPS", "CHARACTER": "CV_CHARACTERS"}
_STRIP_INDEX = re.compile(r"\.\d+$")
_FLOWER_WORDS = {"flower", "flowers", "garden", "blossom", "blossoms", "tulips", "roses"}


# ----------------------------------------------------------------------------- settings and keys


def preferences(context: bpy.types.Context):
    entry = context.preferences.addons.get(__package__)
    return entry.preferences if entry else None


def provider_config(context: bpy.types.Context) -> llm.ProviderConfig | None:
    prefs = preferences(context)
    if prefs is None or prefs.provider == "NONE":
        return None
    return llm.ProviderConfig(prefs.provider, prefs.model_name.strip(), prefs.director_base_url.strip())


def api_key(context: bpy.types.Context) -> str:
    key = context.window_manager.cozyverse_secrets.api_key.strip()
    prefs = preferences(context)
    if not key and prefs is not None and prefs.api_key_environment_variable.strip():
        key = os.environ.get(prefs.api_key_environment_variable.strip(), "").strip()
    return key


def ai_ready(context: bpy.types.Context) -> tuple[bool, str]:
    """(ready, a short reason when not). Nothing is sent by asking."""
    config = provider_config(context)
    if config is None:
        return False, "Choose an AI provider in Settings"
    if not api_key(context):
        return False, "Add your key for this session in Settings"
    try:
        llm.endpoint_for(config)
        llm.model_for(config)
    except BlueprintError as exc:
        return False, str(exc)
    return True, f"{config.label()} · {llm.model_for(config)}"


# ----------------------------------------------------------------------------- the plan


def plan_key(settings) -> str:
    return hashlib.sha1(f"{_prompt_from_settings(settings)}|{settings.preset}".encode("utf-8")).hexdigest()[:16]


def store_blueprint(settings, blueprint: Blueprint, key: str | None = None) -> None:
    settings.director_blueprint_json = json.dumps(spec.to_schema(blueprint), sort_keys=True)
    settings.director_source = blueprint.source
    settings.director_plan_key = key or plan_key(settings)
    settings.director_pending = True


def stored_blueprint(settings) -> Blueprint | None:
    """The plan kept for the current description and style, or None when it is out of date."""
    if not settings.director_blueprint_json or settings.director_plan_key != plan_key(settings):
        return None
    try:
        return spec.validate_blueprint(json.loads(settings.director_blueprint_json), _prompt_from_settings(settings), settings.preset, source=settings.director_source or "OFFLINE")
    except (ValueError, BlueprintError):
        return None


def plan_for(context: bpy.types.Context) -> Blueprint:
    """The plan for what is typed now: an AI plan you already approved the request for, else the offline one."""
    settings = context.scene.cozyverse
    blueprint = stored_blueprint(settings)
    if blueprint is None:
        blueprint = spec.plan_offline(_prompt_from_settings(settings), settings.preset)
        store_blueprint(settings, blueprint)
    return blueprint


def _head_noun(text: str) -> str:
    words = [w for w in re.split(r"[^a-z0-9]+", text.casefold()) if w]
    return words[-1] if words else ""


def best_library_match(records: list[dict], role: str, description: str) -> dict | None:
    """The best of your own models for a described need: same role, sharing the main noun or two words."""
    wanted = set(re.split(r"[^a-z0-9]+", description.casefold())) - {""}
    head = _head_noun(description)
    best, best_score = None, 0
    for record in records:
        if record["role"] != role:
            continue
        have = set(record.get("tags", ())) | set(re.split(r"[^a-z0-9]+", record["name"].casefold()))
        score = len(wanted & have) + (2 if head and head in have else 0)
        if score < 2:
            continue
        if record["license"] == "EDITORIAL":
            score -= 0.5  # prefer something you are free to publish
        if score > best_score:
            best, best_score = record, score
    return best


def resolve_assets(context: bpy.types.Context, blueprint: Blueprint) -> list[dict]:
    """Where each needed thing would come from: your library, a procedural stand-in, or generation."""
    records = library.effective_records() if library.state()["index"] else []
    prefs = preferences(context)
    provider = prefs.generation_provider if prefs is not None and prefs.generation_provider in {"TRIPO", "MESHY"} else "TRIPO"
    rows = []
    taken: set[str] = set()
    for asset in blueprint.assets:
        row = {"id": asset.id, "role": asset.role, "description": asset.description, "resolution": "PROCEDURAL", "name": "", "key": "", "license": "", "credits": 0, "provider": provider}
        match = best_library_match([r for r in records if r["key"] not in taken], asset.role, asset.description)
        if match is not None:
            taken.add(match["key"])
            row.update(resolution="LIBRARY", name=match["name"], key=match["key"], license=match["license"])
        elif asset.source == "GENERATE" or (len(asset.description.split()) >= 3 and asset.role in {"BUILDING", "PROP", "CHARACTER"} and (asset.hero or asset.source == "AUTO")):
            from .providers.contracts import build_plan

            row.update(resolution="GENERATE", credits=build_plan(provider, asset.description).estimated_credits)
        rows.append(row)
    return rows


def fill_settings_from_blueprint(settings, blueprint: Blueprint) -> None:
    """Load the plan into the Review fields."""
    plan = spec.blueprint_to_plan(blueprint)
    settings.plan_title = plan.title
    settings.plan_world_type = plan.world_type
    settings.plan_base_shape = plan.base_shape
    settings.plan_camera_type = plan.camera_type
    settings.plan_architecture_count = plan.architecture_count
    settings.plan_prop_count = plan.prop_count
    settings.plan_vegetation_count = plan.vegetation_count
    settings.plan_character_count = plan.character_count
    settings.plan_include_road = plan.include_road
    settings.plan_water = plan.water
    settings.plan_terrain = plan.terrain


# ----------------------------------------------------------------------------- space on the land


class Ground:
    """Free, level, dry places in a built world, so new things never land on water or on each other."""

    def __init__(self, world: bpy.types.Collection):
        self.world = world
        self.water = world.get("cv_water", "NONE")
        self.terrain = world.get("cv_terrain", "FLAT")
        self.seed = int(world.get("cv_layout_seed", "0") or 0) & 0xFFFFFFFF
        self.stage = terrain_spec.stage_for(self.water)
        self.zone = terrain_spec.build_zone(self.water, self.seed, self.stage)
        self.hills = terrain_spec.hills_for(self.seed, self.stage, self.water) if self.terrain == "HILLS" else []
        self.road = road_for(world)
        self.has_railway = any(child.name.startswith("CV_RAILWAY") for child in world.children)
        self.occupied: list[tuple[float, float, float]] = []
        for obj in world.all_objects:
            holder = obj.users_collection[0].name if obj.users_collection else ""
            if obj.type == "MESH" and obj.parent is None and holder.startswith(tuple(_ROLE_COLLECTION.values()) + (DIRECTOR, USER_ASSETS)):
                self.occupied.append((obj.location.x, obj.location.y, max(0.2, 0.45 * max(obj.dimensions.x, obj.dimensions.y))))
            elif obj.type == "EMPTY" and holder.startswith((DIRECTOR, USER_ASSETS)) and obj.parent is None:
                self.occupied.append((obj.location.x, obj.location.y, 0.7))

    def height(self, x: float, y: float) -> float:
        return terrain_spec.height_at(x, y, self.terrain, self.zone, self.hills, self.seed)

    def free(self, x: float, y: float, role: str, radius: float) -> bool:
        margin = {"BUILDING": 0.8, "PROP": 0.3, "CHARACTER": 0.3, "TREE": 0.2}.get(role, 0.3)
        land = terrain_spec.is_dry if role == "TREE" else terrain_spec.is_buildable
        if not land(x, y, margin, self.terrain, self.zone, self.hills, self.seed):
            return False
        if self.road is not None and abs(y - self.road.location.y) < self.road.scale.y + 0.35 and abs(x) < self.road.scale.x:
            return False
        if self.has_railway and y < -3.0:
            return False
        return all(math.hypot(x - ox, y - oy) >= radius + r + 0.12 for ox, oy, r in self.occupied)

    def find(self, rng: random.Random, role: str, radius: float):
        for _ in range(300):
            x = rng.uniform(-0.82, 0.82) * self.stage.half_x
            y = rng.uniform(-0.8, 0.8) * self.stage.half_y
            if self.free(x, y, role, radius):
                z = max(0.0, self.height(x, y)) if role == "TREE" else 0.0
                return x, y, z
        return None


def _collection(world: bpy.types.Collection, name: str) -> bpy.types.Collection:
    existing = next((child for child in world.children if child.name.startswith(name)), None)
    return existing or _new_collection(name, world)


def _world_material(world: bpy.types.Collection, prefix: str, fallback):
    for obj in world.all_objects:
        for material in getattr(obj.data, "materials", ()) if getattr(obj, "data", None) is not None else ():
            if material is not None and material.name.startswith(prefix):
                return material
    return create_material(f"{prefix}_Director", fallback)


def _stamp(world: bpy.types.Collection, objects) -> None:
    for obj in objects:
        obj["cv_managed"] = True
        obj["cv_locked"] = bool(obj.get("cv_locked", False))
        obj["cv_world_root"] = world.name
        obj["cv_director"] = True


def _next_name(holder: bpy.types.Collection, stem: str) -> str:
    return f"{stem}_{sum(1 for o in holder.all_objects if o.name.startswith(stem)) + 1}"


def _empty_root(name: str, location, holder: bpy.types.Collection, role: str) -> bpy.types.Object:
    root = bpy.data.objects.new(name, None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.2
    root.location = location
    holder.objects.link(root)
    root["cv_role"] = role
    return root


# ----------------------------------------------------------------------------- creating things


def _make_flowers(world, holder, location, index):
    root = _empty_root(_next_name(holder, "CV_Director_Flowers"), location, holder, "TREE")
    palette = [(0.95, 0.35, 0.45, 1.0), (0.98, 0.78, 0.25, 1.0), (0.75, 0.45, 0.9, 1.0), (0.98, 0.98, 0.95, 1.0)]
    stem = _world_material(world, "CV_Mat_Leaves", (0.1, 0.38, 0.12, 1.0))
    bloom = create_material(f"CV_Mat_Bloom{index % 4 + 1}", palette[index % 4], 0.0, 0.6)
    for number, (dx, dy, h) in enumerate(((0.0, 0.0, 0.32), (0.16, 0.08, 0.26), (-0.14, 0.1, 0.3), (0.05, -0.16, 0.24), (-0.1, -0.12, 0.28)), start=1):
        _cyl(f"{root.name}_Stem{number}", root, (dx, dy, h / 2), 0.014, h, holder, stem)
        _ball(f"{root.name}_Bloom{number}", root, (dx, dy, h + 0.03), 0.07, holder, bloom)
    return root


def _make_bench(world, holder, location):
    root = _empty_root(_next_name(holder, "CV_Director_Bench"), location, holder, "PROP")
    wood = _world_material(world, "CV_Mat_Wood", (0.28, 0.1, 0.035, 1.0))
    trim = _world_material(world, "CV_Mat_Trim", (0.6, 0.45, 0.2, 1.0))
    _box(f"{root.name}_Seat", root, (0.0, 0.0, 0.2), (0.4, 0.14, 0.03), holder, wood, 0.01)
    _box(f"{root.name}_Back", root, (0.0, 0.12, 0.34), (0.4, 0.02, 0.1), holder, wood, 0.01)
    for number, dx in enumerate((-0.32, 0.32), start=1):
        _box(f"{root.name}_Leg{number}", root, (dx, 0.0, 0.1), (0.03, 0.12, 0.1), holder, trim, 0.0)
    return root


def _make_lamp(world, holder, location):
    root = _empty_root(_next_name(holder, "CV_Director_Lamp"), location, holder, "PROP")
    trim = _world_material(world, "CV_Mat_Trim", (0.15, 0.15, 0.18, 1.0))
    glow = _world_material(world, "CV_Mat_Window", (1.0, 0.8, 0.45, 1.0))
    _cyl(f"{root.name}_Post", root, (0.0, 0.0, 0.5), 0.03, 1.0, holder, trim)
    _ball(f"{root.name}_Lamp", root, (0.0, 0.0, 1.05), 0.09, holder, glow)
    return root


def _make_crate(world, holder, location):
    root = _empty_root(_next_name(holder, "CV_Director_Crate"), location, holder, "PROP")
    wood = _world_material(world, "CV_Mat_Wood", (0.28, 0.1, 0.035, 1.0))
    _box(f"{root.name}_Box", root, (0.0, 0.0, 0.18), (0.2, 0.2, 0.18), holder, wood, 0.02)
    return root


def _make_one(world, holder, ground: Ground, role: str, description: str, spot, index: int):
    x, y, z = spot
    words = set(re.split(r"[^a-z0-9]+", description.casefold()))
    if role == "TREE":
        if words & _FLOWER_WORDS:
            return _make_flowers(world, holder, (x, y, z), index)
        _plant(_next_name(holder, "CV_Director_Tree"), (x, y, z), 0.6 + (index % 4) * 0.1, holder, _world_material(world, "CV_Mat_Wood", (0.28, 0.1, 0.035, 1.0)), _world_material(world, "CV_Mat_Leaves", (0.1, 0.38, 0.12, 1.0)))
        return None
    if role == "CHARACTER":
        _build_character(_next_name(holder, "CV_Director_Character"), (x, y, 0.0), 0.75, holder, _world_material(world, "CV_Mat_Trim", (0.6, 0.3, 0.2, 1.0)), _world_material(world, "CV_Mat_Character_Skin", (0.56, 0.3, 0.18, 1.0)))
        return None
    if role == "BUILDING":
        form = world.get("cv_architecture_treatment", "PITCHED_HOUSE")
        _build_architecture(
            form,
            _next_name(holder, "CV_Director_Building"),
            (x, y, 0.0),
            0.85,
            holder,
            _world_material(world, "CV_Mat_Shop", (0.15, 0.52, 0.62, 1.0)),
            _world_material(world, "CV_Mat_Roof", (0.62, 0.11, 0.08, 1.0)),
            _world_material(world, "CV_Mat_Trim", (0.95, 0.55, 0.08, 1.0)),
            _world_material(world, "CV_Mat_Window", (0.08, 0.28, 0.42, 1.0)),
        )
        return None
    if words & {"bench", "benches", "seat"}:
        return _make_bench(world, holder, (x, y, 0.0))
    if words & {"lamp", "lamps", "lantern", "lanterns", "light", "lights"}:
        return _make_lamp(world, holder, (x, y, 0.0))
    return _make_crate(world, holder, (x, y, 0.0))


def add_things(context: bpy.types.Context, world: bpy.types.Collection, role: str, count: int, description: str, index: int) -> tuple[int, str]:
    """Add up to ``count`` new things on free ground. Prefers your own library, then simple procedural ones."""
    ground = Ground(world)
    rng = random.Random(f"{world.name}|{index}|{role}|{description}")
    holder = _collection(world, DIRECTOR)
    records = library.effective_records() if library.state()["index"] else []
    match = best_library_match(records, role, description) if description else None
    radius = {"TREE": 0.5, "BUILDING": 1.2, "PROP": 0.4, "CHARACTER": 0.3}.get(role, 0.4)
    before = set(holder.all_objects)
    made, from_library = 0, False
    for number in range(count):
        spot = ground.find(rng, role, radius)
        if spot is None:
            break
        if match is not None:
            try:
                library.place_asset(match, _collection(world, USER_ASSETS), role, location=spot)
                from_library = True
            except (ValueError, RuntimeError):
                match = None
                _make_one(world, holder, ground, role, description, spot, index + number)
        else:
            _make_one(world, holder, ground, role, description, spot, index + number)
        ground.occupied.append((spot[0], spot[1], radius))
        made += 1
    _stamp(world, [o for o in holder.all_objects if o not in before])
    for obj in holder.all_objects:
        if obj not in before and obj.type != "EMPTY" and obj.parent is None:
            obj["cv_generated_transform"] = json.dumps([round(v, 6) for v in (*obj.location, *obj.rotation_euler, *obj.scale)])
    return made, ("from your library" if from_library else "built procedurally")


# ----------------------------------------------------------------------------- groups: move, scale, archive


def _stem(obj) -> str:
    return PART_SUFFIX.sub("", _STRIP_INDEX.sub("", obj.name))


def role_groups(world: bpy.types.Collection, role: str) -> list[list[bpy.types.Object]]:
    """Whole things (a building with its roof and windows) of one role, in a stable order."""
    groups: dict[tuple[str, str], list] = {}
    holder_name = _ROLE_COLLECTION[role]
    for child in world.children:
        if child.name.startswith(holder_name):
            for obj in child.objects:
                if obj.type == "MESH":
                    groups.setdefault((child.name, _stem(obj)), []).append(obj)
    ordered = sorted(groups.values(), key=lambda items: (not _stem(items[0]).startswith("CV_Hero"), _stem(items[0])))
    extras = []
    for child in world.children:
        if child.name.startswith((DIRECTOR, USER_ASSETS)):
            for obj in child.objects:
                if obj.parent is None and obj.get("cv_role", obj.get("cv_asset_role", "")) == role:
                    extras.append([obj, *obj.children_recursive])
                elif obj.parent is None and obj.type == "MESH" and role == {"CV_Director_Tree": "TREE", "CV_Director_Character": "CHARACTER", "CV_Director_Building": "BUILDING"}.get(_STRIP_INDEX.sub("", PART_SUFFIX.sub("", obj.name)).rsplit("_", 1)[0], ""):
                    extras.append([o for o in child.objects if _stem(o) == _stem(obj)])
    return ordered + extras


def _group_locked(group) -> bool:
    return any(obj.get("cv_locked") for obj in group)


def find_group(world: bpy.types.Collection, target: dict):
    if "name" in target:
        wanted = _STRIP_INDEX.sub("", target["name"])
        for role in _ROLE_COLLECTION:
            for group in role_groups(world, role):
                if any(_STRIP_INDEX.sub("", o.name) == wanted or _stem(o) == _STRIP_INDEX.sub("", wanted) for o in group):
                    return group
        return None
    groups = role_groups(world, target["role"])
    return groups[target["index"]] if target["index"] < len(groups) else None


def archive_group(world: bpy.types.Collection, group) -> None:
    archive = _collection(world, ARCHIVE)
    archive.hide_viewport = archive.hide_render = True
    for obj in group:
        if obj.users_collection:
            obj["cv_archived_from"] = obj.users_collection[0].name
        for owner in list(obj.users_collection):
            owner.objects.unlink(obj)
        archive.objects.link(obj)


def restore_archive(world: bpy.types.Collection) -> int:
    archive = next((child for child in world.children if child.name.startswith(ARCHIVE)), None)
    if archive is None:
        return 0
    restored = 0
    for obj in list(archive.objects):
        home = next((c for c in world.children if c.name == obj.get("cv_archived_from")), world)
        archive.objects.unlink(obj)
        home.objects.link(obj)
        del obj["cv_archived_from"]
        restored += 1
    return restored


# ----------------------------------------------------------------------------- applying commands


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def apply_commands(context: bpy.types.Context, commands) -> list[str]:
    """Run allowlisted commands against the active world. Returns one plain line per command."""
    settings = context.scene.cozyverse
    world = bpy.data.collections.get(settings.active_world_name) if settings.active_world_name else None
    if world is None:
        return ["There is no world to change yet"]
    report: list[str] = []
    for index, command in enumerate(commands):
        a = command.args
        text = spec.describe_command(command)
        try:
            verb = command.verb
            if verb == "SET_LOOK":
                settings.atmosphere_preset = a["look"]
            elif verb == "SET_TIME":
                settings.atmosphere_preset = "CUSTOM"
                settings.time_hour = a["hour"]
            elif verb == "SET_WEATHER":
                settings.weather = a["weather"]
                if "amount" in a and a["weather"] == "RAIN":
                    settings.rain_amount = a["amount"]
                if "amount" in a and a["weather"] == "SNOW":
                    settings.snow_amount = a["amount"]
            elif verb == "SET_SEASON":
                settings.season = a["season"]
            elif verb == "SET_CLOUDS":
                settings.clouds_amount = a["amount"]
            elif verb == "SET_STARS":
                settings.stars_amount = a["amount"]
            elif verb == "SET_FOG":
                settings.fog_amount = a["amount"]
            elif verb == "SET_WARMTH":
                settings.atmosphere_preset = "CUSTOM"
                settings.warmth = _clamp(a["value"] if "value" in a else settings.warmth + a["delta"])
            elif verb == "SHOT":
                if bpy.ops.cozyverse.frame_shot(shot=a["shot"]) != {"FINISHED"}:
                    text += " (no camera was available)"
            elif verb == "MOTION":
                text = _apply_motion(context, a, text)
            elif verb == "ADD":
                made, source = add_things(context, world, a["role"], a["count"], a.get("description", ""), index)
                text = f"Added {made} of {a['count']} {a.get('description') or a['role'].lower()} ({source})" if made else f"There was no free space for {a.get('description') or a['role'].lower()}"
            elif verb == "REMOVE":
                text = _apply_remove(world, a)
            elif verb in {"MOVE", "SCALE"}:
                text = _apply_transform(world, command)
            elif verb == "NEW_VERSION":
                text = _apply_new_version(context, a)
            report.append(("Done: " if not text.startswith(("Skipped", "There was no", "Nothing")) else "") + text)
        except (BlueprintError, RuntimeError, ValueError, KeyError) as exc:
            report.append(f"Skipped: {text} ({exc})")
    return report


def _apply_motion(context, a: dict, text: str) -> str:
    settings = context.scene.cozyverse
    feature, on = a["feature"], a["on"]
    world = bpy.data.collections.get(settings.active_world_name)
    if feature == "LIFE":
        settings.life_enabled = on
    elif feature == "CARS":
        if on:
            settings.traffic_cars = a["count"]
            if bpy.ops.cozyverse.traffic_add() != {"FINISHED"}:
                return "Skipped: this world has no road for cars"
        else:
            bpy.ops.cozyverse.traffic_remove()
    elif feature == "TRAIN":
        if on:
            if bpy.ops.cozyverse.railway_add() != {"FINISHED"}:
                return "Skipped: a train needs solid ground along the edge"
        else:
            bpy.ops.cozyverse.railway_remove()
    elif feature == "BUILDUP":
        bpy.ops.cozyverse.buildup_add(play=False) if on else bpy.ops.cozyverse.buildup_remove()
    elif feature == "DAYCYCLE":
        bpy.ops.cozyverse.daycycle_add() if on else bpy.ops.cozyverse.daycycle_remove()
    return text


def _apply_remove(world: bpy.types.Collection, a: dict) -> str:
    groups = role_groups(world, a["role"])
    # Things the Director added go first, then the rest from the back of the list.
    ordered = sorted(groups, key=lambda g: (not g[0].get("cv_director", False), g[0].name), reverse=False)
    ordered = [g for g in ordered if g[0].get("cv_director", False)][::-1] + [g for g in ordered if not g[0].get("cv_director", False)][::-1]
    removed, locked = 0, 0
    for group in ordered:
        if removed >= a["count"]:
            break
        if _group_locked(group):
            locked += 1
            continue
        archive_group(world, group)
        removed += 1
    if not removed:
        return f"Nothing to archive: {'everything is locked' if locked else 'there were none'}"
    return f"Archived {removed} {a['role'].lower()} (hidden, not deleted)" + (f"; kept {locked} locked" if locked else "")


def _apply_transform(world: bpy.types.Collection, command: Command) -> str:
    a = command.args
    group = find_group(world, a["target"])
    label = spec.describe_command(command)
    if group is None:
        return f"Skipped: could not find that object ({label})"
    if _group_locked(group):
        return f"Skipped: it is locked, so it stays where you put it ({label})"
    roots = [obj for obj in group if obj.parent is None or obj.parent not in group]
    if command.verb == "MOVE":
        ground = Ground(world)
        probe = roots[0]
        target_x, target_y = probe.location.x + a["dx"], probe.location.y + a["dy"]
        if not terrain_spec.is_buildable(target_x, target_y, 0.3, ground.terrain, ground.zone, ground.hills, ground.seed) and abs(a["dx"]) + abs(a["dy"]) > 0:
            return f"Skipped: that spot is water, a slope or the road ({label})"
        for obj in roots:
            obj.location.x += a["dx"]
            obj.location.y += a["dy"]
        return label
    factor = a["factor"]
    pivot = roots[0].location.copy()
    for obj in roots:
        if obj is not roots[0]:
            obj.location = pivot + (obj.location - pivot) * factor
        obj.scale = tuple(v * factor for v in obj.scale)
    return label


def _apply_new_version(context, a: dict) -> str:
    settings = context.scene.cozyverse
    if "water" in a:
        settings.water_choice = a["water"]
    if "terrain" in a:
        settings.terrain_choice = a["terrain"]
    if "style" in a:
        settings.preset = a["style"]
    if bpy.ops.cozyverse.conjure() != {"FINISHED"}:
        raise RuntimeError("the new version could not be built")
    return "Built a new version; the previous one is hidden and keeps your locks and hand edits"


# ----------------------------------------------------------------------------- after a build


def finish_world(context: bpy.types.Context) -> None:
    """Carry out the rest of the plan once the world exists: mood, motion and your own models."""
    settings = context.scene.cozyverse
    if not settings.director_pending:
        return
    settings.director_pending = False
    blueprint = stored_blueprint(settings)
    world = bpy.data.collections.get(settings.active_world_name)
    if blueprint is None or world is None:
        return
    patch = spec.blueprint_atmosphere_patch(blueprint)
    if "atmosphere_preset" in patch:
        settings.atmosphere_preset = patch.pop("atmosphere_preset")
    for name, value in patch.items():
        setattr(settings, name, value)
    settings.life_enabled = blueprint.motion["life"]
    rows = resolve_assets(context, blueprint)
    notes: list[str] = []
    car = next((row for row in rows if row["resolution"] == "LIBRARY" and row["role"] == "CAR"), None)
    if car is not None and not settings.slot_car_enabled:
        settings.slot_car_asset, settings.slot_car_enabled = car["key"], True
        notes.append(f"Cars use {car['name']} from your library")
    if blueprint.motion["cars"] and road_for(world) is not None:
        settings.traffic_cars = blueprint.motion["cars"]
        bpy.ops.cozyverse.traffic_add()
    if blueprint.motion["train"] and world.get("cv_water") != "SEA":
        bpy.ops.cozyverse.railway_add()
    if blueprint.motion["build_up"]:
        bpy.ops.cozyverse.buildup_add(play=False)
    ground = Ground(world)
    rng = random.Random(f"{world.name}|plan")
    for row in rows:
        if row["resolution"] != "LIBRARY" or row["role"] not in _ROLE_COLLECTION:
            continue
        record = library.record_for(row["key"])
        spot = ground.find(rng, row["role"], 0.8)
        if record is None or spot is None:
            continue
        try:
            wrapper = library.place_asset(record, _collection(world, USER_ASSETS), row["role"], location=spot)
            for obj in (wrapper, *wrapper.children_recursive):
                obj["cv_world_root"] = world.name
            ground.occupied.append((spot[0], spot[1], 0.8))
            notes.append(f"Placed {row['name']} from your library")
        except (ValueError, RuntimeError):
            continue
    summary = {
        "library": [row["name"] for row in rows if row["resolution"] == "LIBRARY"],
        "procedural": [row["description"] for row in rows if row["resolution"] == "PROCEDURAL"],
        "generate": [{"id": r["id"], "description": r["description"], "credits": r["credits"], "provider": r["provider"]} for r in rows if r["resolution"] == "GENERATE"],
        "notes": notes,
    }
    settings.director_report_json = json.dumps(summary)
    _log_activity(context, "DIRECTOR", f"Applied {blueprint.source} plan: {len(summary['library'])} from library, {len(summary['procedural'])} procedural, {len(summary['generate'])} could be generated")


# ----------------------------------------------------------------------------- the model, in the background


def reference_png(settings, max_side: int = 768) -> bytes | None:
    """A reduced copy of the reference image, only when you asked for it to be sent."""
    image = settings.reference_image
    if image is None or not settings.director_send_image:
        return None
    path = os.path.join(bpy.app.tempdir, "cozyverse_reference_small.png")
    copy = image.copy()
    try:
        width, height = copy.size
        scale = min(1.0, max_side / max(width, height, 1))
        if scale < 1.0:
            copy.scale(max(1, int(width * scale)), max(1, int(height * scale)))
        copy.file_format = "PNG"
        copy.filepath_raw = path
        copy.save()
        with open(path, "rb") as handle:
            return handle.read()
    except (RuntimeError, OSError):
        return None
    finally:
        bpy.data.images.remove(copy)
        try:
            os.remove(path)
        except OSError:
            pass


def _worker(scene_name: str, kind: str, request: dict, extra: dict) -> None:
    try:
        response = llm.send(request)
        if kind == "PLAN":
            blueprint = llm.parse_plan_response(request["kind"], response, extra["prompt"], extra["style"], extra["model"])
            AI_RESULTS.put((scene_name, kind, True, blueprint, extra))
        else:
            commands, problems = llm.parse_followup_response(request["kind"], response)
            AI_RESULTS.put((scene_name, kind, True, (commands, problems), extra))
    except (BlueprintError, RuntimeError) as exc:
        AI_RESULTS.put((scene_name, kind, False, str(exc)[:300], extra))


def _drain() -> float | None:
    while True:
        try:
            scene_name, kind, ok, payload, extra = AI_RESULTS.get_nowait()
        except queue.Empty:
            break
        scene = bpy.data.scenes.get(scene_name)
        if scene is None or not hasattr(scene, "cozyverse"):
            continue
        settings = scene.cozyverse
        settings.director_busy = False
        if kind == "PLAN":
            _plan_arrived(scene, settings, ok, payload, extra)
        else:
            _followup_arrived(scene, settings, ok, payload, extra)
    return 0.25 if any(t.name.startswith("CozyVerseDirector") and t.is_alive() for t in threading.enumerate()) or not AI_RESULTS.empty() else None


def _plan_arrived(scene, settings, ok: bool, payload, extra: dict) -> None:
    if not ok:
        settings.director_status = f"The AI plan did not work: {payload}. Using the offline plan instead."
        settings.status = settings.director_status
        blueprint = spec.plan_offline(extra["prompt"], extra["style"])
        store_blueprint(settings, blueprint, extra["key"])
    else:
        blueprint = payload
        if plan_key(settings) != extra["key"]:
            settings.director_status = "You changed the description while the AI was thinking, so its plan was set aside."
            return
        store_blueprint(settings, blueprint, extra["key"])
        settings.director_status = f"The AI drafted a plan ({blueprint.source.partition(':')[2] or 'model'}). Review it before building."
        settings.status = settings.director_status
    with bpy.context.temp_override(scene=scene):
        bpy.ops.cozyverse.prepare_scene_plan()


def _followup_arrived(scene, settings, ok: bool, payload, extra: dict) -> None:
    if not ok:
        settings.director_status = f"The AI could not help: {payload}. Trying the built-in reader."
        commands, problems = spec.commands_from_text(extra["text"])
    else:
        commands, problems = payload
    set_preview(settings, commands, problems, extra["text"], "AI" if ok else "OFFLINE")


def set_preview(settings, commands, problems, text: str, source: str) -> None:
    settings.director_commands_json = json.dumps([c.to_dict() for c in commands])
    settings.director_preview_json = json.dumps({"source": source, "text": text, "lines": [spec.describe_command(c) for c in commands], "notes": list(problems)[:5]})
    settings.director_status = f"{len(commands)} change(s) ready to review" if commands else "I could not turn that into changes. Try describing it differently."
    settings.status = settings.director_status


def _start(context: bpy.types.Context, kind: str, request: dict, extra: dict) -> None:
    settings = context.scene.cozyverse
    settings.director_busy = True
    settings.director_status = "Waiting for the AI..."
    threading.Thread(target=_worker, args=(context.scene.name, kind, request, extra), name=f"CozyVerseDirector-{kind}", daemon=True).start()
    if not bpy.app.timers.is_registered(_drain):
        bpy.app.timers.register(_drain, first_interval=0.25)


def world_summary(world: bpy.types.Collection) -> dict:
    """What a model is told about the world: counts and mood only. No file names, no paths."""
    counts = {role.lower(): len(role_groups(world, role)) for role in _ROLE_COLLECTION}
    return {"title": world.get("cv_composition_label", "World"), "style": world.get("cv_style_label", ""), "water": world.get("cv_water", "NONE"), "terrain": world.get("cv_terrain", "FLAT"), "items": counts}


# ----------------------------------------------------------------------------- operators


class CV_OT_DirectorAsk(bpy.types.Operator):
    bl_idname = "cozyverse.director_ask"
    bl_label = "Plan With AI"
    bl_description = "Ask your AI model to draft the plan. You see exactly what will be sent and confirm first"

    def invoke(self, context: bpy.types.Context, _event):
        ready, reason = ai_ready(context)
        if not ready:
            self.report({"WARNING"}, reason)
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self, width=520, confirm_text="Send and Plan")

    def _outbound(self, context):
        settings = context.scene.cozyverse
        has_image = settings.director_send_image and settings.reference_image is not None
        return llm.describe_outbound(provider_config(context), "PLAN", _prompt_from_settings(settings), has_image)

    def draw(self, context: bpy.types.Context) -> None:
        box = self.layout.box()
        box.label(text="This will be sent over the internet:", icon="URL")
        for line in self._outbound(context):
            box.label(text=line)
        self.layout.label(text="Nothing is built until you review the plan.", icon="CHECKMARK")

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        config = provider_config(context)
        prompt = _prompt_from_settings(settings)
        if config is None or not prompt:
            return {"CANCELLED"}
        try:
            request = llm.build_plan_request(config, api_key(context), prompt, settings.preset, reference_png(settings))
        except BlueprintError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        _start(context, "PLAN", request, {"prompt": prompt, "style": settings.preset, "model": llm.model_for(config), "key": plan_key(settings)})
        _log_activity(context, "DIRECTOR", f"Asked {config.label()} for a plan (key not logged)")
        return {"FINISHED"}


class CV_OT_DirectorPreview(bpy.types.Operator):
    bl_idname = "cozyverse.director_preview"
    bl_label = "Preview Changes"
    bl_description = "Work out what your request would change, without changing anything yet"

    def invoke(self, context: bpy.types.Context, _event):
        settings = context.scene.cozyverse
        if not settings.director_text.strip():
            self.report({"WARNING"}, "Type what you would like to change first")
            return {"CANCELLED"}
        if settings.director_use_ai and ai_ready(context)[0]:
            return context.window_manager.invoke_props_dialog(self, width=520, confirm_text="Send and Preview")
        return self.execute(context)

    def draw(self, context: bpy.types.Context) -> None:
        box = self.layout.box()
        box.label(text="This will be sent over the internet:", icon="URL")
        for line in llm.describe_outbound(provider_config(context), "FOLLOWUP", context.scene.cozyverse.director_text, False):
            box.label(text=line)
        self.layout.label(text="Nothing changes until you press Apply.", icon="CHECKMARK")

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        text = settings.director_text.strip()
        world = bpy.data.collections.get(settings.active_world_name) if settings.active_world_name else None
        if not text or world is None:
            self.report({"WARNING"}, "Conjure or select a world first")
            return {"CANCELLED"}
        if settings.director_use_ai and ai_ready(context)[0]:
            try:
                request = llm.build_followup_request(provider_config(context), api_key(context), text, world_summary(world))
            except BlueprintError as exc:
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            _start(context, "FOLLOWUP", request, {"text": text})
            return {"FINISHED"}
        commands, ignored = spec.commands_from_text(text)
        set_preview(settings, commands, [f"Did not understand: {', '.join(ignored)}"] if ignored else [], text, "OFFLINE")
        return {"FINISHED"}


class CV_OT_DirectorApply(bpy.types.Operator):
    bl_idname = "cozyverse.director_apply"
    bl_label = "Apply Changes"
    bl_description = "Make the previewed changes. Locked objects are never touched, and Undo (Ctrl+Z) reverses everything"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        try:
            commands, _problems = spec.validate_commands(json.loads(settings.director_commands_json or "[]"))
        except (ValueError, BlueprintError):
            self.report({"WARNING"}, "There is nothing to apply. Preview a change first")
            return {"CANCELLED"}
        report = apply_commands(context, commands)
        settings.director_result_json = json.dumps(report)
        settings.director_commands_json = ""
        settings.director_preview_json = ""
        settings.director_text = ""
        settings.director_status = f"Applied {sum(1 for line in report if line.startswith('Done'))} of {len(report)} change(s)"
        settings.status = settings.director_status
        _log_activity(context, "DIRECTOR", settings.director_status)
        return {"FINISHED"}


class CV_OT_DirectorDiscard(bpy.types.Operator):
    bl_idname = "cozyverse.director_discard"
    bl_label = "Discard"
    bl_description = "Forget the previewed changes"

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        settings.director_commands_json = settings.director_preview_json = settings.director_result_json = ""
        return {"FINISHED"}


class CV_OT_DirectorExample(bpy.types.Operator):
    bl_idname = "cozyverse.director_example"
    bl_label = "Use Example"
    bl_description = "Fill in an example request"

    text: StringProperty()

    def execute(self, context: bpy.types.Context):
        context.scene.cozyverse.director_text = self.text
        return {"FINISHED"}


class CV_OT_DirectorRestore(bpy.types.Operator):
    bl_idname = "cozyverse.director_restore"
    bl_label = "Bring Back Archived Items"
    bl_description = "Put back everything the Director archived in this world"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        world = bpy.data.collections.get(context.scene.cozyverse.active_world_name)
        count = restore_archive(world) if world is not None else 0
        if not count:
            return {"CANCELLED"}
        context.scene.cozyverse.status = f"Brought back {count} object(s)"
        return {"FINISHED"}


class CV_OT_DirectorPrepareGeneration(bpy.types.Operator):
    bl_idname = "cozyverse.director_prepare_generation"
    bl_label = "Prepare Generation"
    bl_description = "Fill in the 3D Asset Factory with this item. Nothing is sent or charged until you review the cost and confirm there"

    description: StringProperty()

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        style = settings.preset.replace("_", " ").lower()
        settings.generation_prompt = f"A stylized {self.description}, {style} style, simple clean low-poly miniature, single object"[:1000]
        settings.active_tab = "GENERATE"
        if bpy.ops.cozyverse.preview_generation() != {"FINISHED"}:
            settings.status = settings.generation_status or "Choose Tripo or Meshy in Settings, then preview the request"
            return {"FINISHED"}  # the prompt is filled in; only the provider is missing
        settings.status = "Review the cost in the 3D asset factory. Nothing has been sent"
        return {"FINISHED"}


_CLASSES = (
    CV_OT_DirectorAsk,
    CV_OT_DirectorPreview,
    CV_OT_DirectorApply,
    CV_OT_DirectorDiscard,
    CV_OT_DirectorExample,
    CV_OT_DirectorRestore,
    CV_OT_DirectorPrepareGeneration,
)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    if bpy.app.timers.is_registered(_drain):
        bpy.app.timers.unregister(_drain)
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

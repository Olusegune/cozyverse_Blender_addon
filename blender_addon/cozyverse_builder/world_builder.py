"""Deterministic offline miniature-world construction for recovery milestone R1."""

from __future__ import annotations

import math
import random
import json

import bpy
from mathutils import Vector

from .atmosphere import RAIN_NAME, SNOW_NAME, SUN_NAME, WIND_NAME, apply_atmosphere
from .core.style_spec import STYLE_PRESETS
from .core.composition_spec import layout_points, profile_for, prompt_seed
from .life import apply_life
from .materials import create_material


WORLD_ROOT = "CV_WORLD"


def _next_world_name() -> str:
    if bpy.data.collections.get(WORLD_ROOT) is None:
        return WORLD_ROOT
    index = 2
    while bpy.data.collections.get(f"{WORLD_ROOT}_{index:03d}") is not None:
        index += 1
    return f"{WORLD_ROOT}_{index:03d}"


def _new_collection(name: str, parent: bpy.types.Collection) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name)
    parent.children.link(collection)
    collection["cv_managed"] = True
    collection["cv_demo"] = True
    return collection


def _material(name: str, color: tuple[float, float, float, float], metallic: float = 0.0, emissive: bool = False) -> bpy.types.Material:
    # Every world version owns its materials so later styles never recolor earlier worlds.
    return create_material(name, color, metallic, emissive=emissive)


def _mark(obj: bpy.types.Object, identifier: str) -> None:
    obj.name = identifier
    obj["cv_id"] = identifier.lower()
    obj["cv_managed"] = True
    obj["cv_demo"] = True
    obj["cv_locked"] = False
    obj["cv_provenance"] = "offline_procedural_r1"


def _move(obj: bpy.types.Object, collection: bpy.types.Collection) -> None:
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    collection.objects.link(obj)


def _finish_mesh(
    obj: bpy.types.Object,
    name: str,
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    bevel: float = 0.08,
) -> bpy.types.Object:
    _mark(obj, name)
    _move(obj, collection)
    obj.data.materials.append(material)
    if bevel > 0.0:
        modifier = obj.modifiers.new("CV Soft Edges", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
    return obj


def _cube(name, location, scale, collection, material, bevel=0.08):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.scale = scale
    return _finish_mesh(obj, name, collection, material, bevel)


def _cylinder(name, location, radius, depth, collection, material):
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=radius, depth=depth, location=location)
    return _finish_mesh(bpy.context.object, name, collection, material, 0.04)


def _plant(name: str, location, scale: float, collection, trunk_mat, leaf_mat) -> None:
    x, y, z = location
    _cylinder(f"{name}_Trunk", (x, y, z + 0.65 * scale), 0.12 * scale, 1.3 * scale, collection, trunk_mat)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.72 * scale, location=(x, y, z + 1.55 * scale))
    crown = bpy.context.object
    crown.scale.z = 1.18
    _finish_mesh(crown, f"{name}_Leaves", collection, leaf_mat, 0.0)


def _sphere(name, location, radius, collection, material, scale=(1.0, 1.0, 1.0)):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=radius, location=location)
    obj = bpy.context.object
    obj.scale = scale
    return _finish_mesh(obj, name, collection, material, 0.0)


def _windows(name, x, y, front_y, rows, columns, scale, collection, glass, width=0.17, height=0.2):
    """Small emissive panes on a building's front face; they glow with the practical lights."""
    for row, z in enumerate(rows):
        for column, offset in enumerate(columns):
            _cube(
                f"{name}_Window{row * len(columns) + column + 1}",
                (x + offset * scale, front_y, z * scale),
                (width * scale, 0.04, height * scale),
                collection,
                glass,
                0.015,
            )


def _build_architecture(form, name, location, scale, collection, wall, roof, trim, glass):
    x, y, _ = location
    if form == "MODULE":
        body = _cylinder(name, (x, y, 0.9 * scale), 0.95 * scale, 1.8 * scale, collection, wall)
        _sphere(f"{name}_Dome", (x, y, 1.8 * scale), 0.8 * scale, collection, glass, (1.0, 1.0, 0.45))
        _cylinder(f"{name}_Antenna", (x, y, 2.7 * scale), 0.06 * scale, 1.4 * scale, collection, trim)
        _windows(name, x, y, y - 0.92 * scale, (0.95,), (-0.3, 0.0, 0.3), scale, collection, glass, 0.12, 0.17)
        return body
    if form == "ROCK":
        return _sphere(name, (x, y, 0.65 * scale), 0.9 * scale, collection, wall, (1.3, 0.9, 0.7))
    if form in {"TURRET", "STALL"}:
        body = _cylinder(name, (x, y, 0.9 * scale), 0.75 * scale, 1.8 * scale, collection, wall) if form == "TURRET" else _cube(name, (x, y, 0.75 * scale), (0.9 * scale, 0.65 * scale, 0.75 * scale), collection, wall, 0.07)
        bpy.ops.mesh.primitive_cone_add(vertices=8 if form == "TURRET" else 4, radius1=1.05 * scale, depth=0.9 * scale, location=(x, y, 2.05 * scale))
        _finish_mesh(bpy.context.object, f"{name}_Roof", collection, roof, 0.04)
        if form == "TURRET":
            _windows(name, x, y, y - 0.76 * scale, (0.7, 1.35), (0.0,), scale, collection, glass, 0.1, 0.16)
        else:
            # A hanging lantern keeps market stalls glowing after dark.
            _sphere(f"{name}_Lantern", (x + 0.35 * scale, y - 0.7 * scale, 1.35 * scale), 0.14 * scale, collection, glass)
        return body
    height = 1.5 if form == "TOWER" else 1.0
    body = _cube(name, (x, y, height * scale), (0.9 * scale, 0.72 * scale, height * scale), collection, wall, 0.1)
    if form in {"PITCHED_HOUSE", "BARN", "CAFE"}:
        bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=1.15 * scale, depth=0.8 * scale, location=(x, y, (2.25 if height == 1.0 else 3.2) * scale))
        roof_obj = bpy.context.object
        roof_obj.rotation_euler.z = math.radians(45)
        _finish_mesh(roof_obj, f"{name}_Roof", collection, roof, 0.05)
    if form in {"PITCHED_HOUSE", "BARN", "TOWER"}:
        rows = (0.7, 1.6, 2.5) if form == "TOWER" else (0.75,)
        _windows(name, x, y, y - 0.73 * scale, rows, (-0.4, 0.4), scale, collection, glass)
    if form == "CAFE":
        _cube(f"{name}_Window", (x, y - 0.73 * scale, 1.05 * scale), (0.48 * scale, 0.04, 0.52 * scale), collection, glass, 0.02)
        _cube(f"{name}_Awning", (x, y - 1.0 * scale, 1.75 * scale), (0.75 * scale, 0.34 * scale, 0.06), collection, trim, 0.03)
    return body


def _build_character(name, location, scale, collection, body_mat, skin_mat):
    x, y, _ = location
    _cylinder(f"{name}_Body", (x, y, 0.72 * scale), 0.2 * scale, 0.9 * scale, collection, body_mat)
    _sphere(f"{name}_Head", (x, y, 1.38 * scale), 0.25 * scale, collection, skin_mat)


def _create_rain(collection: bpy.types.Collection, material: bpy.types.Material) -> bpy.types.Object:
    rng = random.Random(42)
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []
    for _ in range(160):
        x = rng.uniform(-5.2, 5.2)
        y = rng.uniform(-3.7, 3.7)
        z = rng.uniform(0.5, 7.5)
        width = 0.018
        length = rng.uniform(0.28, 0.7)
        start = len(vertices)
        vertices.extend(
            (
                (x - width, y, z),
                (x + width, y, z),
                (x + width - 0.11, y, z - length),
                (x - width - 0.11, y, z - length),
            )
        )
        faces.append((start, start + 1, start + 2, start + 3))
    mesh = bpy.data.meshes.new("CV_Rain_Preview_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    rain = bpy.data.objects.new(RAIN_NAME, mesh)
    collection.objects.link(rain)
    mesh.materials.append(material)
    _mark(rain, RAIN_NAME)
    rain["cv_weather"] = "RAIN"
    return rain


def _create_snow(collection: bpy.types.Collection, material: bpy.types.Material) -> bpy.types.Object:
    rng = random.Random(84)
    vertices = []
    faces = []
    for _ in range(240):
        x, y, z = rng.uniform(-5.2, 5.2), rng.uniform(-3.7, 3.7), rng.uniform(0.5, 7.5)
        size = rng.uniform(0.025, 0.065)
        start = len(vertices)
        vertices.extend(((x - size, y, z), (x + size, y, z), (x + size, y, z + size * 2), (x - size, y, z + size * 2)))
        faces.append((start, start + 1, start + 2, start + 3))
    mesh = bpy.data.meshes.new("CV_Snow_Preview_Mesh")
    mesh.from_pydata(vertices, [], faces)
    snow = bpy.data.objects.new(SNOW_NAME, mesh)
    collection.objects.link(snow)
    mesh.materials.append(material)
    _mark(snow, SNOW_NAME)
    snow["cv_weather"] = "SNOW"
    snow.display_type = "SOLID"
    snow.show_in_front = True
    return snow


def _create_wind(collection: bpy.types.Collection) -> bpy.types.Object:
    wind = bpy.data.objects.new(WIND_NAME, None)
    collection.objects.link(wind)
    _mark(wind, WIND_NAME)
    wind.empty_display_type = "ARROWS"
    wind.empty_display_size = 1.4
    wind.rotation_euler = (0.0, math.radians(70.0), math.radians(-25.0))
    wind["cv_weather"] = "WIND"
    wind["cv_wind_strength"] = 0.0
    return wind


def _point_camera(camera: bpy.types.Object, target=(0.0, 0.0, 0.8)) -> None:
    direction = Vector(target) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _tag_world_members(collection: bpy.types.Collection, world_name: str) -> None:
    for obj in collection.objects:
        obj["cv_world_root"] = world_name
        obj["cv_generated_transform"] = json.dumps(
            [round(value, 6) for value in (*obj.location, *obj.rotation_euler, *obj.scale)]
        )
    for child in collection.children:
        _tag_world_members(child, world_name)


def build_offline_world(scene: bpy.types.Scene, settings, prompt: str, plan: dict | None = None, variation: int = 0) -> bpy.types.Collection:
    """Create a new editable world without altering earlier worlds or user objects.

    ``variation`` re-rolls the deterministic layout (the Remix button) without changing the prompt.
    """
    seed_prompt = prompt if not variation else f"{prompt} #remix{int(variation)}"
    root = _new_collection(_next_world_name(), scene.collection)
    root["cv_schema_version"] = "2.0"
    root["cv_prompt"] = prompt
    root["cv_preset"] = settings.preset
    plan = plan or {}
    root["cv_scene_plan"] = json.dumps(plan, sort_keys=True) if plan else ""
    root["cv_version_state"] = "editable"
    style = STYLE_PRESETS.get(settings.preset, STYLE_PRESETS["COZY_VILLAGE"])
    root["cv_style_label"] = style.label
    root["cv_asset_keywords"] = ", ".join(style.keywords)

    base_collection = _new_collection("CV_BASE", root)
    architecture = _new_collection("CV_ARCHITECTURE", root)
    props = _new_collection("CV_PROPS", root)
    vegetation = _new_collection("CV_VEGETATION", root)
    characters = _new_collection("CV_CHARACTERS", root)
    lights = _new_collection("CV_LIGHTS", root)
    cameras = _new_collection("CV_CAMERAS", root)
    atmosphere_collection = _new_collection("CV_ATMOSPHERE", root)
    rain_collection = _new_collection("CV_RAIN", atmosphere_collection)
    snow_collection = _new_collection("CV_SNOW", atmosphere_collection)
    wind_collection = _new_collection("CV_WIND", atmosphere_collection)

    earth_color, shop_color, roof_color, trim_color, leaf_color = style.palette
    earth = _material("CV_Mat_Earth", earth_color)
    road = _material("CV_Mat_Road", (0.055, 0.065, 0.08, 1.0))
    plaster = _material("CV_Mat_Shop", shop_color, style.metallic * 0.25)
    roof = _material("CV_Mat_Roof", roof_color, max(0.15, style.metallic))
    wood = _material("CV_Mat_Wood", (0.28, 0.10, 0.035, 1.0))
    trim = _material("CV_Mat_Trim", trim_color, style.metallic)
    green = _material("CV_Mat_Leaves", leaf_color)
    glass = _material("CV_Mat_Window", (0.08, 0.28, 0.42, 1.0), 0.0, emissive=True)
    rain_material = _material("CV_Mat_Rain", (0.08, 0.48, 1.0, 1.0), 0.1, emissive=True)
    snow_material = _material("CV_Mat_Snow", (0.9, 0.96, 1.0, 1.0), 0.0, emissive=True)
    skin = _material("CV_Mat_Character_Skin", (0.56, 0.30, 0.18, 1.0))

    world_type = plan.get("world_type", "VILLAGE")
    profile = profile_for(world_type)
    style_form_overrides = {"RETRO_SCIFI": "MODULE", "GOTHIC": "TURRET", "ART_DECO": "TOWER", "COZY_FANTASY": "TURRET"}
    architecture_form = style_form_overrides.get(settings.preset, profile.architecture_form)
    root["cv_composition_family"] = world_type
    root["cv_composition_label"] = profile.label
    root["cv_architecture_treatment"] = architecture_form
    root["cv_layout_seed"] = str(prompt_seed(seed_prompt, world_type))
    root["cv_variation"] = int(variation)

    base_shape = plan.get("base_shape", "ROUNDED_RECT")
    if base_shape == "CIRCLE":
        _cylinder("CV_Diorama_Base", (0.0, 0.0, -0.4), 5.2, 0.8, base_collection, earth)
    else:
        base = _cube("CV_Diorama_Base", (0.0, 0.0, -0.4), (5.7, 4.2, 0.4), base_collection, earth, 0.18)
        if base_shape == "ISLAND":
            base.scale.y = 0.82
            base.rotation_euler.z = math.radians(4)
    if plan.get("include_road", True):
        if world_type == "SPACE_OUTPOST":
            _cylinder("CV_Landing_Pad", (0.0, -1.4, 0.08), 2.0, 0.12, base_collection, road)
        elif world_type == "NATURE":
            _cube("CV_Path", (0.0, -1.2, 0.06), (4.8, 0.48, 0.06), base_collection, wood, 0.12)
        else:
            _cube("CV_Road", (0.0, -1.45, 0.06), (5.15, 1.05, 0.08), base_collection, road, 0.04)
            _cube("CV_Sidewalk", (0.0, -0.15, 0.13), (5.15, 0.22, 0.14), base_collection, trim, 0.035)

    architecture_count = max(1, min(int(plan.get("architecture_count", 1)), 8))
    architecture_points = layout_points(seed_prompt, world_type, architecture_count, "ARCHITECTURE")
    hero_slug = profile.hero.replace(" ", "_")
    for index, location in enumerate(architecture_points):
        name = f"CV_Hero_{hero_slug}" if index == 0 else f"CV_{architecture_form.title()}_{index + 1}"
        scale = 1.35 if index == 0 else 0.75 + (index % 3) * 0.12
        _build_architecture(architecture_form, name, location, scale, architecture, plaster, roof, trim, glass)

    prop_count = max(0, min(int(plan.get("prop_count", 3)), 20))
    for index, (x, y, _) in enumerate(layout_points(seed_prompt, world_type, prop_count, "PROPS")):
        if profile.prop_form in {"TECH", "MAGIC_PROP"}:
            _cylinder(f"CV_{profile.prop_form.title()}_{index + 1}", (x, y, 0.38), 0.18 + (index % 2) * 0.08, 0.76, props, trim)
            _sphere(f"CV_{profile.prop_form.title()}_{index + 1}_Beacon", (x, y, 0.86), 0.1, props, glass)
        elif profile.prop_form in {"TABLE", "STALL_PROP"}:
            _cube(f"CV_{profile.prop_form.title()}_{index + 1}", (x, y, 0.38), (0.4, 0.32, 0.12), props, wood, 0.04)
        else:
            _cube(f"CV_{profile.prop_form.title()}_{index + 1}", (x, y, 0.3), (0.22 + (index % 3) * 0.06, 0.22, 0.3), props, trim if index % 2 else wood, 0.035)

    vegetation_count = max(0, min(int(plan.get("vegetation_count", 4)), 16))
    for index, location in enumerate(layout_points(seed_prompt, world_type, vegetation_count, "VEGETATION")):
        if profile.vegetation_form == "ALIEN_PLANT":
            _sphere(f"CV_Alien_Plant_{index + 1}", (location[0], location[1], 0.55), 0.5, vegetation, green, (0.55, 0.55, 1.4))
        else:
            _plant(f"CV_{profile.vegetation_form.title()}_{index + 1}", location, 0.62 + (index % 4) * 0.1, vegetation, wood, green)

    character_count = max(0, min(int(plan.get("character_count", 0)), 12))
    for index, location in enumerate(layout_points(seed_prompt, world_type, character_count, "CHARACTERS")):
        _build_character(f"CV_Character_{index + 1}", location, 0.72 + (index % 3) * 0.06, characters, trim if index % 2 else plaster, skin)

    sun_data = bpy.data.lights.new(SUN_NAME, "SUN")
    sun = bpy.data.objects.new(SUN_NAME, sun_data)
    lights.objects.link(sun)
    _mark(sun, SUN_NAME)

    for suffix, location in (("Shop", (-0.8, -0.05, 1.65)), ("Porch", (-0.8, -0.9, 2.15))):
        light_data = bpy.data.lights.new(f"CV_Interior_{suffix}", "POINT")
        light_data.shadow_soft_size = 1.0
        light = bpy.data.objects.new(f"CV_Interior_{suffix}", light_data)
        light.location = location
        lights.objects.link(light)
        _mark(light, f"CV_Interior_{suffix}")

    camera_data = bpy.data.cameras.new("CV_Camera")
    camera_data.type = "PERSP" if plan.get("camera_type") == "PERSPECTIVE" else "ORTHO"
    camera_data.ortho_scale = 13.5
    camera = bpy.data.objects.new("CV_Camera", camera_data)
    camera.location = profile.camera_location
    if camera_data.type == "PERSP":
        camera_data.lens = 52.0 if world_type in {"CAFE", "MARKET"} else 44.0
    _point_camera(camera, profile.camera_target)
    cameras.objects.link(camera)
    _mark(camera, "CV_Camera")
    scene.camera = camera

    _create_rain(rain_collection, rain_material)
    _create_snow(snow_collection, snow_material)
    _create_wind(wind_collection)
    scene["cv_active_world"] = root.name
    # Tag first so the atmosphere pass can find this world's objects, then snapshot the
    # transforms it adjusts so they never read as manual edits.
    _tag_world_members(root, root.name)
    apply_atmosphere(scene, settings)
    _tag_world_members(root, root.name)
    if settings.life_enabled:
        apply_life(scene, root)
    return root

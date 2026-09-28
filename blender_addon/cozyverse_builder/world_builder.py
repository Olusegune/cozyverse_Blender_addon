"""Deterministic offline miniature-world construction for recovery milestone R1."""

from __future__ import annotations

import math
import random

import bpy
from mathutils import Vector

from .atmosphere import RAIN_NAME, SUN_NAME, apply_atmosphere
from .core.style_spec import STYLE_PRESETS


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


def _material(name: str, color: tuple[float, float, float, float], metallic: float = 0.0) -> bpy.types.Material:
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.diffuse_color = color
    material.metallic = metallic
    material.roughness = 0.72
    return material


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


def _point_camera(camera: bpy.types.Object, target=(0.0, 0.0, 0.8)) -> None:
    direction = Vector(target) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _tag_world_members(collection: bpy.types.Collection, world_name: str) -> None:
    for obj in collection.objects:
        obj["cv_world_root"] = world_name
    for child in collection.children:
        _tag_world_members(child, world_name)


def build_offline_world(scene: bpy.types.Scene, settings, prompt: str) -> bpy.types.Collection:
    """Create a new editable world without altering earlier worlds or user objects."""
    root = _new_collection(_next_world_name(), scene.collection)
    root["cv_schema_version"] = "2.0"
    root["cv_prompt"] = prompt
    root["cv_preset"] = settings.preset
    style = STYLE_PRESETS.get(settings.preset, STYLE_PRESETS["COZY_VILLAGE"])
    root["cv_style_label"] = style.label
    root["cv_asset_keywords"] = ", ".join(style.keywords)

    base_collection = _new_collection("CV_BASE", root)
    architecture = _new_collection("CV_ARCHITECTURE", root)
    props = _new_collection("CV_PROPS", root)
    vegetation = _new_collection("CV_VEGETATION", root)
    lights = _new_collection("CV_LIGHTS", root)
    cameras = _new_collection("CV_CAMERAS", root)
    atmosphere_collection = _new_collection("CV_ATMOSPHERE", root)
    rain_collection = _new_collection("CV_RAIN", atmosphere_collection)

    earth_color, shop_color, roof_color, trim_color, leaf_color = style.palette
    earth = _material("CV_Mat_Earth", earth_color)
    road = _material("CV_Mat_Road", (0.055, 0.065, 0.08, 1.0))
    plaster = _material("CV_Mat_Shop", shop_color, style.metallic * 0.25)
    roof = _material("CV_Mat_Roof", roof_color, max(0.15, style.metallic))
    wood = _material("CV_Mat_Wood", (0.28, 0.10, 0.035, 1.0))
    trim = _material("CV_Mat_Trim", trim_color, style.metallic)
    green = _material("CV_Mat_Leaves", leaf_color)
    glass = _material("CV_Mat_Window", (0.08, 0.28, 0.42, 1.0), 0.25)
    rain_material = _material("CV_Mat_Rain", (0.08, 0.48, 1.0, 1.0), 0.1)

    _cube("CV_Diorama_Base", (0.0, 0.0, -0.4), (5.7, 4.2, 0.4), base_collection, earth, 0.18)
    _cube("CV_Road", (0.0, -1.45, 0.06), (5.15, 1.05, 0.08), base_collection, road, 0.04)
    _cube("CV_Sidewalk", (0.0, -0.15, 0.13), (5.15, 0.22, 0.14), base_collection, trim, 0.035)

    _cube("CV_SariSari_Store", (-0.8, 1.2, 1.25), (2.0, 1.35, 1.25), architecture, plaster, 0.12)
    bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=2.35, radius2=0.0, depth=1.25, location=(-0.8, 1.2, 3.05))
    roof_obj = bpy.context.object
    roof_obj.scale.y = 0.72
    roof_obj.rotation_euler.z = math.radians(45)
    _finish_mesh(roof_obj, "CV_SariSari_Roof", architecture, roof, 0.06)
    _cube("CV_Service_Window", (-0.8, -0.17, 1.45), (0.95, 0.05, 0.62), architecture, glass, 0.02)
    _cube("CV_Awning", (-0.8, -0.62, 2.12), (1.35, 0.52, 0.07), architecture, trim, 0.04).rotation_euler.x = math.radians(-10)
    _cube("CV_Counter", (-0.8, -0.42, 0.78), (1.08, 0.3, 0.12), props, wood, 0.04)
    _cube("CV_Store_Sign", (-0.8, -0.24, 2.45), (1.15, 0.06, 0.28), props, trim, 0.04)
    _cube("CV_Crate_A", (-2.75, 0.1, 0.45), (0.42, 0.42, 0.42), props, wood, 0.05)
    _cube("CV_Crate_B", (-2.75, 0.95, 0.34), (0.34, 0.34, 0.34), props, trim, 0.05)
    _cube("CV_Bench", (2.4, 0.25, 0.5), (1.0, 0.32, 0.16), props, wood, 0.05)

    for index, location in enumerate(((-4.0, 2.3, 0.0), (3.9, 2.25, 0.0), (3.65, -2.7, 0.0), (-3.8, -2.8, 0.0))):
        _plant(f"CV_Tropical_Plant_{index + 1}", location, 0.72 + index * 0.08, vegetation, wood, green)

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
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 13.5
    camera = bpy.data.objects.new("CV_Camera", camera_data)
    camera.location = (10.8, -13.2, 10.2)
    _point_camera(camera)
    cameras.objects.link(camera)
    _mark(camera, "CV_Camera")
    scene.camera = camera

    _create_rain(rain_collection, rain_material)
    _tag_world_members(root, root.name)
    scene["cv_active_world"] = root.name
    apply_atmosphere(scene, settings)
    return root

"""Procedural traffic and railway: low-poly cars on the road and a train that stops at a station.

Everything is plain, editable Blender geometry. Motion is a handful of simple-expression drivers on
each vehicle's root empty, so it loops forever on any frame range, needs no add-on to play back,
and can be retimed from the root's custom properties (``cv_period`` frames per trip, ``cv_phase``
frame offset). Cars pop in and out at the road ends; the train leaves and enters tunnel portals.
"""

from __future__ import annotations

import json
import math

import bpy

from .atmosphere import apply_atmosphere
from .core.style_spec import STYLE_PRESETS
from .life import add_driver
from .materials import create_material
from .operators import _log_activity
from .world_builder import _cube, _cylinder, _new_collection, _sphere

TRAFFIC = "CV_TRAFFIC"
RAILWAY = "CV_RAILWAY"
TRACK_Y = -3.7
RAIL_TOP = 0.16
LOCO_LENGTH = 0.9
CARRIAGE_LENGTH = 0.8
COUPLING = 0.08
BASE_EDGE_X = 5.7
OWN_MATERIALS = ("CV_Mat_Veh", "CV_Mat_WindowLamp")


def _child_collection(world, prefix):
    return next((child for child in world.children if child.name.startswith(prefix)), None) if world is not None else None


def traffic_for(world):
    return _child_collection(world, TRAFFIC)


def railway_for(world):
    return _child_collection(world, RAILWAY)


def road_for(world):
    return next((obj for obj in world.all_objects if obj.name.startswith("CV_Road") and obj.type == "MESH"), None) if world is not None else None


def _dispose(collection) -> None:
    """Delete a vehicle collection with its objects, orphaned actions and materials."""
    if collection is None:
        return
    for obj in list(collection.all_objects):
        bpy.data.objects.remove(obj)
    for child in list(collection.children):
        bpy.data.collections.remove(child)
    bpy.data.collections.remove(collection)
    for material in list(bpy.data.materials):
        if material.name.startswith(OWN_MATERIALS) and material.users == 0:
            bpy.data.materials.remove(material)


def _paints(world) -> list[tuple[float, float, float, float]]:
    style = STYLE_PRESETS.get(world.get("cv_preset", ""), STYLE_PRESETS["COZY_VILLAGE"])
    palette = style.palette
    return [palette[2], palette[1], palette[3], (0.9, 0.87, 0.78, 1.0)]


def _box(name, parent, local, half, collection, material, bevel=0.02):
    obj = _cube(name, (0.0, 0.0, 0.0), half, collection, material, bevel)
    obj.parent = parent
    obj.location = local
    return obj


def _cyl(name, parent, local, radius, depth, collection, material, rotation=None):
    obj = _cylinder(name, (0.0, 0.0, 0.0), radius, depth, collection, material)
    obj.parent = parent
    obj.location = local
    if rotation is not None:
        obj.rotation_euler = rotation
    return obj


def _ball(name, parent, local, radius, collection, material):
    obj = _sphere(name, (0.0, 0.0, 0.0), radius, collection, material)
    obj.parent = parent
    obj.location = local
    return obj


def _root(name, collection, world, location, period, phase):
    root = bpy.data.objects.new(name, None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.25
    root.location = location
    collection.objects.link(root)
    root["cv_managed"] = True
    root["cv_demo"] = True
    root["cv_locked"] = False
    root["cv_world_root"] = world.name
    root["cv_period"] = float(period)
    root["cv_phase"] = float(phase)
    root["cv_u"] = 0.0
    return root


def _u_driver(root) -> None:
    add_driver(
        root,
        '["cv_u"]',
        -1,
        "((frame+o)-T*floor((frame+o)/T))/T",
        (("o", "OBJECT", root, '["cv_phase"]'), ("T", "OBJECT", root, '["cv_period"]')),
    )


def _snapshot(collection, world) -> None:
    """Mark world membership and record rest transforms for parts (roots are animated, so skipped)."""
    for obj in collection.all_objects:
        obj["cv_world_root"] = world.name
        if obj.type != "EMPTY":
            obj["cv_generated_transform"] = json.dumps([round(v, 6) for v in (*obj.location, *obj.rotation_euler, *obj.scale)])


# ----------------------------------------------------------------------------- cars


def _build_car(index, root, collection, paint, tire, glass, lamp, tail, hub):
    name = root.name
    body = _box(f"{name}_Body", root, (0.0, 0.0, 0.15), (0.44, 0.2, 0.08), collection, paint, 0.035)
    _box(f"{name}_Cabin", root, (-0.04, 0.0, 0.305), (0.21, 0.17, 0.075), collection, glass, 0.02)
    _box(f"{name}_Roof", root, (-0.04, 0.0, 0.385), (0.23, 0.185, 0.014), collection, paint, 0.01)
    for number, (x, y) in enumerate(((0.28, 0.2), (0.28, -0.2), (-0.26, 0.2), (-0.26, -0.2)), start=1):
        wheel = _cyl(f"{name}_Wheel{number}", root, (x, y, 0.085), 0.085, 0.07, collection, tire, rotation=(math.pi / 2, 0.0, 0.0))
        outward = -1.0 if y > 0 else 1.0  # the wheel's axis points along -Y after the tilt
        _box(f"{name}_Hub{number}", wheel, (0.0, 0.0, outward * 0.037), (0.055, 0.012, 0.004), collection, hub, 0.0)
    for number, y in enumerate((0.12, -0.12), start=1):
        _ball(f"{name}_Headlight{number}", root, (0.45, y, 0.155), 0.04, collection, lamp)
        _ball(f"{name}_Taillight{number}", root, (-0.45, y, 0.155), 0.03, collection, tail)
    return body


def build_traffic(scene, world, count: int, seconds: float):
    """Replace the world's traffic with ``count`` cars driving both lanes of its road."""
    road = road_for(world)
    if road is None:
        return None
    _dispose(traffic_for(world))
    collection = _new_collection(TRAFFIC, world)
    fps = max(1, scene.render.fps)
    road_top = road.location.z + road.scale.z
    lane = max(0.3, road.scale.y * 0.46)
    half_length = road.scale.x - 0.35
    tire = create_material("CV_Mat_Veh_Tire", (0.04, 0.04, 0.05, 1.0))
    hub = create_material("CV_Mat_Veh_Hub", (0.72, 0.72, 0.7, 1.0), 0.3)
    glass = create_material("CV_Mat_Veh_Glass", (0.1, 0.3, 0.42, 1.0), 0.2)
    lamp = create_material("CV_Mat_WindowLamp", (1.0, 0.85, 0.5, 1.0), 0.0, emissive=True)
    tail = create_material("CV_Mat_Veh_Tail", (0.75, 0.05, 0.05, 1.0))
    paints = _paints(world)
    for index in range(count):
        east = index % 2 == 0
        period = max(24.0, seconds * fps * (1.0 + 0.18 * math.sin(index * 1.7)))
        phase = (index // 2) * period * 0.5 + index * period / max(1, count) * 0.37
        y = road.location.y + (-lane if east else lane)
        root = _root(f"CV_Car_{index + 1}", collection, world, (0.0, y, road_top), period, phase)
        root.rotation_euler = (0.0, 0.0, 0.0 if east else math.pi)
        paint = create_material(f"CV_Mat_Veh_Paint{index + 1}", paints[index % len(paints)], 0.15)
        _build_car(index, root, collection, paint, tire, glass, lamp, tail, hub)
        _u_driver(root)
        start, end = (-half_length, half_length) if east else (half_length, -half_length)
        var_u = (("u", "OBJECT", root, '["cv_u"]'),)
        add_driver(root, "location", 0, f"{start:.4f}+({end - start:.4f})*u", var_u)
        for axis in range(3):  # pop in and out at the ends of the road
            add_driver(root, "delta_scale", axis, "max(0.0001,min(1,u*14)*min(1,(1-u)*14))", var_u)
    _snapshot(collection, world)
    return collection


# ----------------------------------------------------------------------------- train


def train_length(cars: int) -> float:
    return LOCO_LENGTH + cars * (CARRIAGE_LENGTH + COUPLING)


def _build_locomotive(root, collection, paint, trim, dark, glass, lamp, wheel_mat):
    name = f"{root.name}_Loco"
    _box(f"{name}_Body", root, (-0.34, 0.0, 0.14), (0.2, 0.2, 0.05), collection, dark, 0.02)
    _box(f"{name}_Cab", root, (-0.28, 0.0, 0.31), (0.17, 0.215, 0.2), collection, paint, 0.03)
    _box(f"{name}_Roof", root, (-0.28, 0.0, 0.525), (0.2, 0.235, 0.018), collection, trim, 0.012)
    for side in (1, -1):
        _box(f"{name}_Window{'L' if side > 0 else 'R'}", root, (-0.28, side * 0.2, 0.34), (0.07, 0.016, 0.07), collection, glass, 0.01)
    _cyl(f"{name}_Boiler", root, (0.1, 0.0, 0.27), 0.16, 0.62, collection, paint, rotation=(0.0, math.pi / 2, 0.0))
    _cyl(f"{name}_Chimney", root, (0.3, 0.0, 0.52), 0.05, 0.2, collection, dark)
    _ball(f"{name}_Lamp", root, (0.42, 0.0, 0.28), 0.045, collection, lamp)
    for number, x in enumerate((-0.28, 0.0, 0.28), start=1):
        for side in (1, -1):
            _cyl(f"{name}_Wheel{number}{'L' if side > 0 else 'R'}", root, (x, side * 0.2, 0.07), 0.07, 0.04, collection, wheel_mat, rotation=(math.pi / 2, 0.0, 0.0))


def _build_carriage(index, root, collection, x, paint, trim, glass, wheel_mat):
    name = f"{root.name}_Car{index}"
    _box(f"{name}_Body", root, (x, 0.0, 0.27), (CARRIAGE_LENGTH / 2, 0.215, 0.15), collection, paint, 0.03)
    _box(f"{name}_Roof", root, (x, 0.0, 0.435), (CARRIAGE_LENGTH / 2 + 0.01, 0.23, 0.02), collection, trim, 0.012)
    for number, offset in enumerate((-0.24, 0.0, 0.24), start=1):
        for side in (1, -1):
            _box(f"{name}_Window{number}{'L' if side > 0 else 'R'}", root, (x + offset, side * 0.213, 0.3), (0.075, 0.012, 0.065), collection, glass, 0.008)
    for number, offset in enumerate((-0.25, 0.25), start=1):
        for side in (1, -1):
            _cyl(f"{name}_Wheel{number}{'L' if side > 0 else 'R'}", root, (x + offset, side * 0.2, 0.07), 0.07, 0.04, collection, wheel_mat, rotation=(math.pi / 2, 0.0, 0.0))
    _box(f"{name}_Coupling", root, (x + CARRIAGE_LENGTH / 2 + COUPLING / 2, 0.0, 0.14), (COUPLING / 2 + 0.01, 0.02, 0.02), collection, wheel_mat, 0.0)


def build_railway(scene, world, cars: int, seconds: float):
    """Replace the world's railway: front-edge track, station, tunnel portals and a train."""
    _dispose(railway_for(world))
    collection = _new_collection(RAILWAY, world)
    fps = max(1, scene.render.fps)
    length = train_length(cars)
    hump_half = length / 2 + 0.2
    hump_x = BASE_EDGE_X - hump_half
    style = STYLE_PRESETS.get(world.get("cv_preset", ""), STYLE_PRESETS["COZY_VILLAGE"])
    earth, shop, roof, trim, leaf = style.palette
    ballast = create_material("CV_Mat_Veh_Ballast", (0.2, 0.19, 0.18, 1.0))
    sleeper = create_material("CV_Mat_Veh_Sleeper", (0.28, 0.14, 0.07, 1.0))
    steel = create_material("CV_Mat_Veh_Steel", (0.62, 0.63, 0.66, 1.0), 0.7)
    rock = create_material("CV_Mat_Veh_Rock", (0.52, 0.48, 0.4, 1.0))
    mouth = create_material("CV_Mat_Veh_Tunnel", (0.01, 0.01, 0.015, 1.0))
    platform_mat = create_material("CV_Mat_Veh_Platform", (0.62, 0.58, 0.52, 1.0))
    canopy_mat = create_material("CV_Mat_Veh_Canopy", roof)
    dark = create_material("CV_Mat_Veh_Dark", (0.08, 0.08, 0.1, 1.0), 0.3)
    paint = create_material("CV_Mat_Veh_TrainPaint", shop, 0.2)
    coach = create_material("CV_Mat_Veh_CoachPaint", roof, 0.2)
    glass = create_material("CV_Mat_WindowLamp", (1.0, 0.8, 0.45, 1.0), 0.0, emissive=True)
    wheel_mat = create_material("CV_Mat_Veh_TrainWheel", (0.05, 0.05, 0.06, 1.0), 0.4)

    # Track: ballast bed, sleepers and two rails run between the tunnel portals.
    track_half = BASE_EDGE_X - 0.1
    _cube("CV_Rail_Bed", (0.0, TRACK_Y, 0.05), (track_half, 0.27, 0.05), collection, ballast, 0.02)
    count = int(track_half * 2 / 0.32)
    for number in range(count):
        x = -track_half + 0.16 + number * 0.32
        _cube(f"CV_Rail_Sleeper{number + 1}", (x, TRACK_Y, 0.108), (0.05, 0.22, 0.014), collection, sleeper, 0.0)
    for number, side in enumerate((1, -1), start=1):
        _cube(f"CV_Rail_Rail{number}", (0.0, TRACK_Y + side * 0.15, 0.135), (track_half, 0.014, 0.022), collection, steel, 0.0)

    # Station: platform, shelter and a lamp that glows at night.
    _cube("CV_Rail_Platform", (0.0, TRACK_Y + 0.55, 0.09), (1.25, 0.28, 0.09), collection, platform_mat, 0.02)
    for number, x in enumerate((-0.95, 0.95), start=1):
        _cylinder(f"CV_Rail_Post{number}", (x, TRACK_Y + 0.7, 0.45), 0.03, 0.55, collection, dark)
    _cube("CV_Rail_Canopy", (0.0, TRACK_Y + 0.62, 0.74), (1.2, 0.34, 0.025), collection, canopy_mat, 0.015)
    _sphere("CV_Rail_Lamp", (0.0, TRACK_Y + 0.4, 0.66), 0.05, collection, glass)

    # Tunnel portals the train disappears into at either end.
    for number, side in enumerate((-1, 1), start=1):
        _cube(f"CV_Rail_Hill{number}", (side * hump_x, TRACK_Y, 0.55), (hump_half, 0.62, 0.55), collection, rock, 0.28)
        _cube(f"CV_Rail_Mouth{number}", (side * (hump_x - hump_half - 0.005), TRACK_Y, 0.34), (0.012, 0.3, 0.3), collection, mouth, 0.0)

    root = _root("CV_Train", collection, world, (-hump_x, TRACK_Y, RAIL_TOP), seconds * fps, 0.0)
    _build_locomotive(root, collection, paint, steel, dark, glass, glass, wheel_mat)
    # The locomotive faces +X, so carriages trail behind it (toward -X).
    for index in range(1, cars + 1):
        x = -0.45 - COUPLING - CARRIAGE_LENGTH / 2 - (index - 1) * (CARRIAGE_LENGTH + COUPLING)
        _build_carriage(index, root, collection, x, coach, steel, glass, wheel_mat)
    # Shift the consist so its middle sits on the root and the whole train hides inside a portal.
    for child in root.children:
        child.location.x += length / 2 - LOCO_LENGTH / 2

    _u_driver(root)
    root["cv_leg1"] = 0.0
    root["cv_leg2"] = 0.0
    var_u = (("u", "OBJECT", root, '["cv_u"]'),)
    first = "min(1,max(0,u/0.4))"
    second = "min(1,max(0,(u-0.6)/0.4))"
    add_driver(root, '["cv_leg1"]', -1, f"{first}*{first}*(3-2*{first})", var_u)
    add_driver(root, '["cv_leg2"]', -1, f"{second}*{second}*(3-2*{second})", var_u)
    add_driver(
        root,
        "location",
        0,
        f"-{hump_x:.4f}+{hump_x:.4f}*(a+b)",
        (("a", "OBJECT", root, '["cv_leg1"]'), ("b", "OBJECT", root, '["cv_leg2"]')),
    )
    _snapshot(collection, world)
    return collection


# ----------------------------------------------------------------------------- operators


def _refresh_lights(context) -> None:
    apply_atmosphere(context.scene, context.scene.cozyverse)  # lamps and headlights join the glow


class CV_OT_TrafficAdd(bpy.types.Operator):
    bl_idname = "cozyverse.traffic_add"
    bl_label = "Add Cars"
    bl_description = "Cars drive both lanes of this world's road, looping forever. Rebuilding replaces them; Remove clears them"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        world = bpy.data.collections.get(settings.active_world_name)
        if world is None:
            self.report({"WARNING"}, "Conjure or select a world first")
            return {"CANCELLED"}
        if road_for(world) is None:
            self.report({"WARNING"}, "This world has no road. Cars need one; try a village, city, cafe, market or farm")
            return {"CANCELLED"}
        build_traffic(context.scene, world, settings.traffic_cars, settings.traffic_seconds)
        _refresh_lights(context)
        settings.status = f"{settings.traffic_cars} car(s) on the road. Press Space to watch"
        _log_activity(context, "TRAFFIC", f"Added {settings.traffic_cars} car(s) to {world.name}")
        return {"FINISHED"}


class CV_OT_TrafficRemove(bpy.types.Operator):
    bl_idname = "cozyverse.traffic_remove"
    bl_label = "Remove Cars"
    bl_description = "Remove the cars and everything that belongs to them"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        world = bpy.data.collections.get(context.scene.cozyverse.active_world_name)
        if traffic_for(world) is None:
            return {"CANCELLED"}
        _dispose(traffic_for(world))
        context.scene.cozyverse.status = "Cars removed"
        return {"FINISHED"}


class CV_OT_RailwayAdd(bpy.types.Operator):
    bl_idname = "cozyverse.railway_add"
    bl_label = "Add Train"
    bl_description = "A train rolls out of a tunnel, stops at a small station, then leaves through the other tunnel, looping forever"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        world = bpy.data.collections.get(settings.active_world_name)
        if world is None:
            self.report({"WARNING"}, "Conjure or select a world first")
            return {"CANCELLED"}
        build_railway(context.scene, world, settings.train_cars, settings.train_seconds)
        _refresh_lights(context)
        settings.status = "A train serves the station. Press Space to watch"
        _log_activity(context, "RAILWAY", f"Added a {settings.train_cars}-carriage train and station to {world.name}")
        return {"FINISHED"}


class CV_OT_RailwayRemove(bpy.types.Operator):
    bl_idname = "cozyverse.railway_remove"
    bl_label = "Remove Railway"
    bl_description = "Remove the train, track, station and tunnels"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        world = bpy.data.collections.get(context.scene.cozyverse.active_world_name)
        if railway_for(world) is None:
            return {"CANCELLED"}
        _dispose(railway_for(world))
        context.scene.cozyverse.status = "Railway removed"
        return {"FINISHED"}


_CLASSES = (CV_OT_TrafficAdd, CV_OT_TrafficRemove, CV_OT_RailwayAdd, CV_OT_RailwayRemove)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

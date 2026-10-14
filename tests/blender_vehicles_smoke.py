"""Blender background acceptance test for procedural cars and the train."""

from __future__ import annotations

import importlib
import pathlib
import sys

import bpy
from mathutils import Vector


repo_root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "blender_addon"))
addon = importlib.import_module("cozyverse_builder")
addon.register()


def evaluated(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    return obj.evaluated_get(depsgraph)


def at(frame):
    bpy.context.scene.frame_set(int(round(frame)))
    bpy.context.view_layer.update()


def world_x(obj):
    return evaluated(obj).matrix_world.translation.x


def drivers(owner):
    animation = getattr(owner, "animation_data", None)
    return list(animation.drivers) if animation else []


def check_drivers(collection):
    for obj in collection.all_objects:
        for fcurve in drivers(obj):
            assert fcurve.driver.is_simple_expression and fcurve.driver.is_valid, fcurve.driver.expression


try:
    scene = bpy.context.scene
    settings = scene.cozyverse
    settings.prompt = "A cozy village with a town hall and trees"
    assert bpy.ops.cozyverse.conjure() == {"FINISHED"}
    world = bpy.data.collections[settings.active_world_name]
    baseline_objects = len(bpy.data.objects)

    # ---- cars ---------------------------------------------------------------
    settings.traffic_cars = 3
    settings.traffic_seconds = 6.0
    assert bpy.ops.cozyverse.traffic_add() == {"FINISHED"}
    traffic = next(c for c in world.children if c.name.startswith("CV_TRAFFIC"))
    roots = sorted((o for o in traffic.objects if o.name.startswith("CV_Car_") and o.type == "EMPTY"), key=lambda o: o.name)
    assert len(roots) == 3
    check_drivers(traffic)
    road = next(o for o in world.all_objects if o.name.startswith("CV_Road"))
    lanes = {round(r.location.y - road.location.y, 2) for r in roots}
    assert len(lanes) == 2, lanes  # both lanes are used
    directions = {round(r.rotation_euler.z, 2) for r in roots}
    assert directions == {0.0, 3.14}, directions

    car = roots[0]
    period, phase = car["cv_period"], car["cv_phase"]
    at(period / 2 - phase)  # halfway through its trip
    assert abs(world_x(car)) < 0.05
    assert max(evaluated(car).matrix_world.to_scale()) > 0.99
    at(-phase + 1)  # just started: still popping in
    assert max(evaluated(car).matrix_world.to_scale()) < 0.3
    first = world_x(car)
    at(-phase + 1 + period)
    assert abs(world_x(car) - first) < 1e-3  # it loops forever
    at(500)
    assert abs(world_x(car)) < road.scale.x  # still on the road far past the timeline end
    wheel = next(o for o in traffic.all_objects if o.name.startswith("CV_Car_1_Wheel"))
    assert wheel.parent is car
    for frame in (1, 40, 133):
        at(frame)
        assert bpy.ops.cozyverse.inspect_manual_edits() == {"FINISHED"} and "0 changed" in settings.status

    # Headlights share the practical-light glow.
    lamp = next(m for m in bpy.data.materials if m.name.startswith("CV_Mat_WindowLamp"))
    bsdf = next(n for n in lamp.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    assert bsdf.inputs["Emission Strength"].default_value > 0.5

    assert bpy.ops.cozyverse.traffic_add() == {"FINISHED"}  # rebuilding replaces, never duplicates
    assert len([c for c in world.children if c.name.startswith("CV_TRAFFIC")]) == 1
    assert len([o for o in bpy.data.objects if o.name.startswith("CV_Car_") and o.type == "EMPTY"]) == 3
    traffic = next(c for c in world.children if c.name.startswith("CV_TRAFFIC"))  # the rebuild replaced it

    # ---- train --------------------------------------------------------------
    settings.train_cars = 2
    settings.train_seconds = 10.0
    assert bpy.ops.cozyverse.railway_add() == {"FINISHED"}
    railway = next(c for c in world.children if c.name.startswith("CV_RAILWAY"))
    train = next(o for o in railway.objects if o.name.startswith("CV_Train") and o.type == "EMPTY")
    check_drivers(railway)
    period = train["cv_period"]
    parts = [o for o in railway.all_objects if o.parent is train and o.type == "MESH"]
    assert len(parts) > 20
    left, right = sorted((o for o in railway.all_objects if o.name.startswith("CV_Rail_Hill")), key=lambda o: o.location.x)
    left_span = (left.location.x - left.scale.x, left.location.x + left.scale.x)
    right_span = (right.location.x - right.scale.x, right.location.x + right.scale.x)

    def train_extent():
        xs = []
        for part in parts:
            ev = evaluated(part)
            xs.extend((ev.matrix_world @ Vector(corner)).x for corner in ev.bound_box)
        return min(xs), max(xs)

    at(1)  # departs the left tunnel: the whole train is hidden inside the hill
    lo, hi = train_extent()
    assert lo >= left_span[0] - 0.01 and hi <= left_span[1] + 0.01, (lo, hi, left_span)
    for fraction in (0.42, 0.5, 0.58):  # it stops at the station for a while
        at(fraction * period + 1)
        assert abs(world_x(train)) < 0.05, (fraction, world_x(train))
    at(0.2 * period + 1)  # on its way in, between the tunnel and the station
    assert -4.5 < world_x(train) < -0.2
    at(period - 1)  # arrived in the right tunnel, hidden again
    lo, hi = train_extent()
    assert lo >= right_span[0] - 0.01 and hi <= right_span[1] + 0.01, (lo, hi, right_span)
    at(1 + period)
    assert abs(world_x(train) - left.location.x) < 0.05  # and the loop restarts in the left tunnel
    for frame in (1, 30, 77):
        at(frame)
        assert bpy.ops.cozyverse.inspect_manual_edits() == {"FINISHED"} and "0 changed" in settings.status

    # ---- coexistence with the other motion features --------------------------
    settings.story_preset = "QUIET_MORNING"
    assert bpy.ops.cozyverse.preview_story() == {"FINISHED"}
    assert settings.story_target_count > 0
    assert bpy.ops.cozyverse.buildup_add() == {"FINISHED"}
    finish = int(next(o for o in world.objects if o.get("cv_buildup_controller"))["cv_finish_frame"])
    at(1)
    vehicle_meshes = [o for o in (*traffic.all_objects, *railway.all_objects) if o.type == "MESH"]
    assert all(max(evaluated(o).delta_scale) < 0.05 for o in vehicle_meshes)
    at(finish)
    assert all(min(evaluated(o).delta_scale) > 0.99 for o in vehicle_meshes)
    assert bpy.ops.cozyverse.buildup_remove() == {"FINISHED"}

    # ---- save and reopen -------------------------------------------------------
    path = repo_root / "work" / "cozyverse_vehicles_smoke.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    bpy.ops.wm.open_mainfile(filepath=str(path))
    scene = bpy.context.scene
    settings = scene.cozyverse
    world = bpy.data.collections[settings.active_world_name]
    kept = [f for o in world.all_objects for f in drivers(o)]
    assert kept and all(f.driver.is_simple_expression and f.driver.is_valid for f in kept)

    # ---- removal leaves nothing behind -------------------------------------------
    assert bpy.ops.cozyverse.traffic_remove() == {"FINISHED"}
    assert bpy.ops.cozyverse.railway_remove() == {"FINISHED"}
    assert bpy.ops.cozyverse.traffic_remove() == {"CANCELLED"}
    assert not [c for c in world.children if c.name.startswith(("CV_TRAFFIC", "CV_RAILWAY"))]
    assert len(bpy.data.objects) == baseline_objects, (len(bpy.data.objects), baseline_objects)
    assert not [m for m in bpy.data.materials if m.name.startswith(("CV_Mat_Veh", "CV_Mat_WindowLamp")) and m.users == 0]

    # A world without a road gets a friendly refusal for cars but can still have a railway.
    settings.prompt = "a quiet forest landscape with a river"
    assert bpy.ops.cozyverse.conjure() == {"FINISHED"}
    assert bpy.ops.cozyverse.traffic_add() == {"CANCELLED"}
    assert bpy.ops.cozyverse.railway_add() == {"FINISHED"}
finally:
    addon.unregister()
print("COZYVERSE_VEHICLES_SMOKE_OK")

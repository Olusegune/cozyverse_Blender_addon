"""Blender background acceptance test for ambient life (wind, flicker) and the build-up animation."""

from __future__ import annotations

import importlib
import pathlib
import sys

import bpy


repo_root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "blender_addon"))
addon = importlib.import_module("cozyverse_builder")
addon.register()


def evaluated(obj):
    return obj.evaluated_get(bpy.context.evaluated_depsgraph_get())


def at(frame: int):
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()


def drivers_of(owner):
    animation = getattr(owner, "animation_data", None)
    return list(animation.drivers) if animation else []


def mesh_objects(world):
    return [obj for obj in world.all_objects if obj.type == "MESH" and not obj.get("cv_weather") and not obj.get("cv_buildup_controller")]


def size(obj):
    return min(evaluated(obj).matrix_world.to_scale())  # the thinnest axis: RISE grows flat sheets first


def min_z(obj):
    ev = evaluated(obj)
    return min((ev.matrix_world @ __import__("mathutils").Vector(corner)).z for corner in ev.bound_box)


try:
    scene = bpy.context.scene
    settings = scene.cozyverse
    settings.prompt = "A rainy cafe corner with warm glowing windows and tropical plants"
    assert bpy.ops.cozyverse.conjure() == {"FINISHED"}
    world = bpy.data.collections[settings.active_world_name]

    # ---- ambient life -----------------------------------------------------
    plants = [obj for obj in world.all_objects if obj.get("cv_life")]
    lamps = [obj for obj in world.all_objects if obj.type == "LIGHT" and obj.data.get("cv_life_light")]
    assert plants and lamps
    for owner in [*plants, *(lamp.data for lamp in lamps)]:
        for fcurve in drivers_of(owner):
            assert fcurve.driver.is_simple_expression, fcurve.driver.expression  # no Python is ever evaluated
            assert fcurve.driver.is_valid, fcurve.driver.expression

    plant = plants[0]

    def sway_range(wind: float) -> float:
        settings.wind_amount = wind
        values = []
        for frame in range(1, 90, 3):
            at(frame)
            values.append(evaluated(plant).delta_rotation_euler[0])
        return max(values) - min(values)

    calm = sway_range(0.0)
    assert calm > 0.01, calm  # it moves even without wind
    assert sway_range(100.0) > calm * 2.0  # and the Wind slider drives it harder
    settings.wind_amount = 0.0
    settings.life_sway = 0.0
    assert 0.0 < sway_range(0.0) < calm  # the sway slider is live, no rebuild needed
    settings.life_sway = 50.0

    lamp = lamps[0]
    base = float(lamp.data["cv_base_energy"])
    assert base > 0.0
    readings = []
    for frame in range(1, 60):
        at(frame)
        readings.append(evaluated(lamp).data.energy)
    assert max(readings) - min(readings) > base * 0.05, "lamps should flicker"
    settings.life_flicker = 0.0
    at(5)
    assert abs(evaluated(lamp).data.energy - base) < 1e-3  # flicker 0 means steady light
    settings.life_flicker = 35.0

    # Moving plants and lamps are never mistaken for hand edits.
    for frame in (1, 17, 53):
        at(frame)
        assert bpy.ops.cozyverse.inspect_manual_edits() == {"FINISHED"} and "0 changed" in settings.status

    # Story still animates plants that have ambient drivers.
    settings.story_preset = "QUIET_MORNING"
    assert bpy.ops.cozyverse.preview_story() == {"FINISHED"}
    assert settings.story_target_count > 0
    assert settings.story_skipped_count == len(lamps)  # only the flickering lamps are left to Ambient life

    # Toggling off removes every driver and restores the plants exactly.
    settings.life_enabled = False
    assert not [obj for obj in world.all_objects if obj.get("cv_life")]
    assert not drivers_of(plant) and tuple(plant.delta_rotation_euler) == (0.0, 0.0, 0.0)
    assert abs(lamp.data.energy - base) < 1e-6
    settings.life_enabled = True
    assert [obj for obj in world.all_objects if obj.get("cv_life")]

    # ---- build-up ---------------------------------------------------------
    rest = {obj.name: (tuple(obj.scale), min_z(obj)) for obj in mesh_objects(world)}
    settings.buildup_seconds = 3.0
    original_range = (scene.frame_start, scene.frame_end)
    for style in ("POP", "RISE", "DROP"):
        settings.buildup_style = style
        assert bpy.ops.cozyverse.buildup_add() == {"FINISHED"}
        controller = next(obj for obj in world.objects if obj.get("cv_buildup_controller"))
        finish = int(controller["cv_finish_frame"])
        assert scene.frame_end > finish and scene.frame_current == 1
        for fcurve in [f for obj in mesh_objects(world) for f in drivers_of(obj)]:
            assert fcurve.driver.is_simple_expression and fcurve.driver.is_valid, fcurve.driver.expression

        at(1)  # nothing has appeared yet
        assert all(size(obj) < 0.01 for obj in mesh_objects(world)), style
        at(finish // 2 + 1)  # partway: some pieces are in, some are not
        sizes = [size(obj) for obj in mesh_objects(world)]
        assert min(sizes) < 0.01 and max(sizes) > 0.5, (style, min(sizes), max(sizes))
        if style == "POP":
            for obj in mesh_objects(world):
                if size(obj) > 0.2:
                    assert abs(min_z(obj) - rest[obj.name][1]) < 0.02, obj.name  # grows from the ground
        if style == "DROP":
            assert any(min_z(obj) > rest[obj.name][1] + 0.3 for obj in mesh_objects(world) if size(obj) > 0.5)
        at(finish)  # finished: every piece is exactly where the builder put it
        for obj in mesh_objects(world):
            ev = evaluated(obj)
            assert tuple(round(v, 4) for v in ev.matrix_world.to_scale()) == tuple(round(v, 4) for v in rest[obj.name][0]), (style, obj.name)
            assert abs(min_z(obj) - rest[obj.name][1]) < (0.08 if obj.get("cv_life") else 1e-3), (style, obj.name)  # swaying plants tilt a touch
        assert bpy.ops.cozyverse.inspect_manual_edits() == {"FINISHED"} and "0 changed" in settings.status

    # Build-up coexists with Story and with a finished-world postcard.
    assert bpy.ops.cozyverse.preview_story() == {"FINISHED"} and settings.story_skipped_count == len(lamps)
    at(1)
    assert bpy.ops.cozyverse.render_postcard() == {"FINISHED"} and scene.frame_current >= finish
    assert bpy.ops.cozyverse.buildup_finish() == {"FINISHED"} and scene.frame_current == finish

    # It survives save and reopen, still pure simple expressions.
    path = repo_root / "work" / "cozyverse_motion_smoke.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    bpy.ops.wm.open_mainfile(filepath=str(path))
    reopened = bpy.data.collections[bpy.context.scene.cozyverse.active_world_name]
    kept = [f for obj in reopened.all_objects for f in drivers_of(obj)] + [f for obj in reopened.all_objects if obj.type == "LIGHT" for f in drivers_of(obj.data)]
    assert kept and all(f.driver.is_simple_expression and f.driver.is_valid for f in kept)
    scene = bpy.context.scene
    settings = scene.cozyverse

    # Remove puts everything back.
    assert bpy.ops.cozyverse.buildup_remove() == {"FINISHED"}
    assert not [obj for obj in reopened.all_objects if obj.get("cv_buildup") or obj.get("cv_buildup_controller")]
    assert (scene.frame_start, scene.frame_end) == original_range
    for obj in [o for o in reopened.all_objects if o.type == "MESH" and not o.get("cv_weather")]:
        assert tuple(obj.delta_scale) == (1.0, 1.0, 1.0) and obj.delta_location[2] == 0.0
        assert not [f for f in drivers_of(obj) if "cv_p" in f.data_path or f.data_path.startswith("delta_scale")]
    assert not [action for action in bpy.data.actions if action.name.startswith("CV_BUILDUP")]
    assert bpy.ops.cozyverse.buildup_remove() == {"CANCELLED"}
finally:
    addon.unregister()
print("COZYVERSE_MOTION_SMOKE_OK")

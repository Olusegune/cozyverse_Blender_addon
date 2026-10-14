"""Blender background acceptance test for the one-click clip renderer."""

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
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    return obj.evaluated_get(depsgraph)


try:
    scene = bpy.context.scene
    settings = scene.cozyverse
    assert bpy.ops.cozyverse.render_clip() == {"CANCELLED"}  # nothing to film yet
    settings.prompt = "A cozy village with a town hall and trees"
    assert bpy.ops.cozyverse.conjure() == {"FINISHED"}
    world = bpy.data.collections[settings.active_world_name]

    # Build-up + orbit: one timeline that covers both, with the orbit spanning the whole clip.
    settings.clip_buildup, settings.clip_orbit, settings.clip_quality = True, True, "HD720"
    settings.buildup_seconds = 3.0
    assert bpy.ops.cozyverse.render_clip() == {"FINISHED"}
    controller = next(o for o in world.objects if o.get("cv_buildup_controller"))
    rig = next(o for o in bpy.data.objects if o.get("cv_turntable"))
    total = scene.frame_end
    assert scene.frame_start == 1 and total == int(controller["cv_finish_frame"]) - 1 + int(round(1.5 * scene.render.fps)) + 1 or total > int(controller["cv_finish_frame"])
    assert settings.turntable_frames == total
    assert (scene.render.resolution_x, scene.render.resolution_y) == (1280, 720)
    assert scene.render.image_settings.file_format == "FFMPEG" and scene.render.ffmpeg.codec == "H264"
    assert scene.render.filepath.endswith("cozyverse_clip_")
    assert scene.render.engine in {"BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"}

    camera = scene.camera
    scene.frame_set(1)
    first = evaluated(camera).matrix_world.translation.copy()
    meshes = [o for o in world.all_objects if o.type == "MESH" and not o.get("cv_weather") and not o.get("cv_buildup_controller")]
    assert all(max(evaluated(o).delta_scale) < 0.05 for o in meshes)  # the clip opens on an empty stage
    scene.frame_set(total // 2)
    assert (evaluated(camera).matrix_world.translation - first).length > 1.0  # the camera is sweeping
    scene.frame_set(total)
    assert all(min(evaluated(o).delta_scale) > 0.99 for o in meshes)  # and ends on the finished world
    scene.frame_set(total + 1)
    assert (evaluated(camera).matrix_world.translation - first).length < 0.5  # one full turn: it loops

    # Rendering again rebuilds cleanly instead of stacking rigs.
    assert bpy.ops.cozyverse.render_clip() == {"FINISHED"}
    assert len([o for o in bpy.data.objects if o.get("cv_turntable")]) == 1
    assert len([o for o in world.objects if o.get("cv_buildup_controller")]) == 1

    # Orbit only, 1080p, no build-up: a plain turntable clip.
    assert bpy.ops.cozyverse.buildup_remove() == {"FINISHED"}
    settings.clip_buildup, settings.clip_orbit, settings.clip_quality = False, True, "HD1080"
    settings.turntable_frames = 60
    assert bpy.ops.cozyverse.render_clip() == {"FINISHED"}
    assert (scene.render.resolution_x, scene.render.resolution_y) == (1920, 1080)
    assert scene.frame_end == 60 and not [o for o in world.objects if o.get("cv_buildup_controller")]
finally:
    addon.unregister()
print("COZYVERSE_CLIP_SMOKE_OK")

"""Foreground Blender undo acceptance test for an approved CozyVerse revision."""

from __future__ import annotations

import importlib
import pathlib
import sys

import bpy


repo_root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "blender_addon"))
addon = importlib.import_module("cozyverse_builder")
addon.register()

settings = bpy.context.scene.cozyverse
settings.prompt = "Create an editable miniature village for revision undo verification"
settings.prompt_text = None
window = bpy.context.window_manager.windows[0]
area = next(area for area in window.screen.areas if area.type == "VIEW_3D")
region = next(region for region in area.regions if region.type == "WINDOW")
with bpy.context.temp_override(window=window, area=area, region=region):
    bpy.context.preferences.edit.use_global_undo = True
    assert bpy.ops.ed.undo_push(message="Before CozyVerse revision") == {"FINISHED"}
    assert bpy.ops.cozyverse.prepare_scene_plan() == {"FINISHED"}
    settings.plan_approved = True
    assert bpy.ops.cozyverse.build_approved_plan() == {"FINISHED"}
    assert bpy.data.collections.get("CV_WORLD") is not None
    assert bpy.ops.ed.undo() == {"FINISHED"}
assert bpy.data.collections.get("CV_WORLD") is None

addon.unregister()
print("COZYVERSE_M5_FOREGROUND_UNDO_OK")
bpy.ops.wm.quit_blender()

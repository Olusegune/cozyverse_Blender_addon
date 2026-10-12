"""Foreground Blender undo acceptance test for M8.1 Story application."""

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
settings.prompt = "Create a lively miniature market with characters and trees"
window = bpy.context.window_manager.windows[0]
area = next(area for area in window.screen.areas if area.type == "VIEW_3D")
region = next(region for region in area.regions if region.type == "WINDOW")
with bpy.context.temp_override(window=window, area=area, region=region):
    bpy.context.preferences.edit.use_global_undo = True
    assert bpy.ops.cozyverse.prepare_scene_plan() == {"FINISHED"}
    settings.plan_approved = True
    assert bpy.ops.cozyverse.build_approved_plan() == {"FINISHED"}
    character = next(obj for obj in bpy.data.collections[settings.active_world_name].all_objects if obj.name.startswith("CV_Character_") and obj.name.endswith("_Body"))
    character_name = character.name
    original = tuple(character.location)
    assert bpy.ops.ed.undo_push(message="Before CozyVerse Story") == {"FINISHED"}
    settings.story_preset = "BUSY_MARKET"
    assert bpy.ops.cozyverse.preview_story() == {"FINISHED"}
    settings.story_approved = True
    assert bpy.ops.cozyverse.apply_story() == {"FINISHED"}
    story_id = settings.story_active_id
    assert story_id and character.animation_data and character.animation_data.action
    assert bpy.ops.ed.undo() == {"FINISHED"}
    assert bpy.data.collections.get(f"CV_STORY_{story_id}") is None
    restored = bpy.data.objects.get(character_name)
    assert restored is not None
    assert all(abs(a - b) < 1e-6 for a, b in zip(restored.location, original)), (tuple(restored.location), original)
    assert restored.animation_data is None or restored.animation_data.action is None

addon.unregister()
print("COZYVERSE_M8_STORY_UNDO_OK")
bpy.ops.wm.quit_blender()

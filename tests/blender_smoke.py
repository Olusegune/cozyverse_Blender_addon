"""Run with Blender background mode to verify registration and demo creation."""

from __future__ import annotations

import importlib
import pathlib
import sys

import bpy


repo_root = pathlib.Path(__file__).resolve().parents[1]
addon_parent = repo_root / "blender_addon"
sys.path.insert(0, str(addon_parent))

addon = importlib.import_module("cozyverse_builder")
addon.register()
try:
    assert hasattr(bpy.types.Scene, "cozyverse")
    result = bpy.ops.cozyverse.create_local_demo()
    assert result == {"FINISHED"}, result
    collection = bpy.data.collections.get("CV_DEMO")
    assert collection is not None
    assert len(collection.objects) >= 10
    assert all(obj.get("cv_demo") is True for obj in collection.objects)
    assert bpy.context.scene.camera is not None

    first_demo_count = len(collection.objects)
    bpy.ops.mesh.primitive_cube_add()
    user_object = bpy.context.object
    user_object.name = "User_Object_Must_Survive"
    for owner in list(user_object.users_collection):
        owner.objects.unlink(user_object)
    collection.objects.link(user_object)
    result = bpy.ops.cozyverse.create_local_demo()
    assert result == {"FINISHED"}, result
    assert bpy.data.objects.get("User_Object_Must_Survive") is user_object
    assert len([obj for obj in collection.objects if obj.get("cv_demo") is True]) == first_demo_count
    assert bpy.data.collections.get("CV_DEMO.001") is None

    output_path = repo_root / "work" / "cozyverse_foundation_smoke.blend"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    bpy.ops.wm.open_mainfile(filepath=str(output_path))
    assert bpy.data.collections.get("CV_DEMO") is not None
    assert bpy.context.scene.cozyverse.last_demo_prompt
finally:
    addon.unregister()

assert not hasattr(bpy.types.Scene, "cozyverse")
addon.register()
assert hasattr(bpy.types.Scene, "cozyverse")
addon.unregister()
assert not hasattr(bpy.types.Scene, "cozyverse")
print("COZYVERSE_BLENDER_SMOKE_OK")

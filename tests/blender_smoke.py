"""Blender background acceptance test for recovery milestone R1."""

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
    assert hasattr(bpy.types.WindowManager, "cozyverse_secrets")
    settings = bpy.context.scene.cozyverse

    bpy.ops.mesh.primitive_cube_add(location=(20.0, 20.0, 20.0))
    preexisting = bpy.context.object
    preexisting.name = "Preexisting_User_Object"

    secret_sentinel = "cv-secret-must-never-enter-blend-file"
    bpy.context.window_manager.cozyverse_secrets.api_key = secret_sentinel
    settings.prompt = "Create a tiny Manila sari-sari store with a road, tropical plants and warm sunset."
    result = bpy.ops.cozyverse.create_local_demo()
    assert result == {"FINISHED"}, result

    world = bpy.data.collections.get("CV_WORLD")
    assert world is not None
    child_names = {child.name for child in world.children}
    assert {"CV_BASE", "CV_ARCHITECTURE", "CV_PROPS", "CV_VEGETATION", "CV_LIGHTS", "CV_CAMERAS", "CV_ATMOSPHERE"} <= child_names
    for object_name in ("CV_Diorama_Base", "CV_Road", "CV_SariSari_Store", "CV_Sun", "CV_Camera", "CV_Rain_Preview"):
        assert bpy.data.objects.get(object_name) is not None, object_name
    assert bpy.context.scene.camera is bpy.data.objects["CV_Camera"]

    sun = bpy.data.objects["CV_Sun"]
    settings.time_hour = 12.0
    noon_rotation = tuple(sun.rotation_euler)
    noon_energy = sun.data.energy
    settings.time_hour = 18.0
    assert tuple(sun.rotation_euler) != noon_rotation
    assert sun.data.energy != noon_energy

    interior = bpy.data.objects["CV_Interior_Shop"]
    settings.interior_intensity = 15.0
    low_interior_energy = interior.data.energy
    settings.interior_intensity = 90.0
    assert interior.data.energy > low_interior_energy

    rain = bpy.data.objects["CV_Rain_Preview"]
    settings.weather = "RAIN"
    settings.rain_amount = 65.0
    assert not rain.hide_viewport
    assert not rain.hide_render
    assert len(rain.data.vertices) >= 400
    settings.weather = "CLEAR"
    assert rain.hide_viewport and rain.hide_render

    settings.weather = "RAIN"
    settings.rain_amount = 45.0
    assert bpy.ops.cozyverse.save_atmosphere_preset() == {"FINISHED"}
    assert "cv_custom_atmosphere_preset" in bpy.context.scene

    store = bpy.data.objects["CV_SariSari_Store"]
    store.location.x += 0.75
    edited_x = store.location.x
    assert bpy.ops.cozyverse.create_local_demo() == {"FINISHED"}
    assert bpy.data.collections.get("CV_WORLD_002") is not None
    assert bpy.data.objects.get("CV_SariSari_Store") is store
    assert store.location.x == edited_x
    assert bpy.data.objects.get("Preexisting_User_Object") is preexisting

    settings.prompt = ""
    settings.prompt_text = None
    assert bpy.ops.cozyverse.create_local_demo() == {"CANCELLED"}
    assert bpy.data.collections.get("CV_WORLD_003") is None

    output_path = repo_root / "work" / "cozyverse_r1_smoke.blend"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    assert secret_sentinel.encode("utf-8") not in output_path.read_bytes()
    bpy.ops.wm.open_mainfile(filepath=str(output_path))
    assert bpy.data.collections.get("CV_WORLD") is not None
    assert bpy.data.collections.get("CV_WORLD_002") is not None
    assert bpy.data.objects.get("Preexisting_User_Object") is not None
    assert bpy.data.objects["CV_SariSari_Store"].location.x == edited_x
    assert bpy.context.scene.cozyverse.weather == "RAIN"
    assert bpy.context.scene.cozyverse.rain_amount == 45.0
finally:
    addon.unregister()

assert not hasattr(bpy.types.Scene, "cozyverse")
assert not hasattr(bpy.types.WindowManager, "cozyverse_secrets")
addon.register()
assert hasattr(bpy.types.Scene, "cozyverse")
assert hasattr(bpy.types.WindowManager, "cozyverse_secrets")
addon.unregister()
assert not hasattr(bpy.types.Scene, "cozyverse")
assert not hasattr(bpy.types.WindowManager, "cozyverse_secrets")
print("COZYVERSE_R1_BLENDER_SMOKE_OK")


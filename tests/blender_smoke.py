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
from cozyverse_builder.providers.contracts import build_plan
from cozyverse_builder.operators import _compose_prompt

addon.register()
try:
    assert hasattr(bpy.types.Scene, "cozyverse")
    assert hasattr(bpy.types.WindowManager, "cozyverse_secrets")
    settings = bpy.context.scene.cozyverse

    composed = _compose_prompt("a tiny harbor", "a lighthouse", "misty dawn", "boats", "modern cars")
    assert composed.startswith("Create a tiny harbor") and composed.endswith(".")
    assert bpy.ops.cozyverse.apply_prompt_template(template="CAFE") == {"FINISHED"}
    assert "cafe" in settings.prompt.lower()
    assert bpy.ops.cozyverse.apply_prompt_template(template="RETRO_SCIFI") == {"FINISHED"}
    assert settings.preset == "RETRO_SCIFI"
    assert "rounded modules" in settings.prompt
    # Headless Blender does not expose a system clipboard; verify its safe empty-state path.
    bpy.context.window_manager.clipboard = ""
    assert bpy.ops.cozyverse.paste_prompt() == {"CANCELLED"}

    bpy.ops.mesh.primitive_cube_add(location=(20.0, 20.0, 20.0))
    preexisting = bpy.context.object
    preexisting.name = "Preexisting_User_Object"

    secret_sentinel = "cv-secret-must-never-enter-blend-file"
    bpy.context.window_manager.cozyverse_secrets.api_key = secret_sentinel
    bpy.context.window_manager.cozyverse_secrets.tripo_api_key = secret_sentinel + "-tripo"
    bpy.context.window_manager.cozyverse_secrets.meshy_api_key = secret_sentinel + "-meshy"
    settings.prompt = "Create a tiny Manila sari-sari store with a road, tropical plants and warm sunset."
    assert bpy.ops.cozyverse.edit_multiline_prompt() == {"FINISHED"}
    settings.prompt_text.write("\nInclude a welcoming storefront and evening atmosphere.")
    assert bpy.ops.cozyverse.use_multiline_prompt() == {"FINISHED"}
    assert "\n" in settings.prompt
    result = bpy.ops.cozyverse.create_local_demo()
    assert result == {"FINISHED"}, result

    world = bpy.data.collections.get("CV_WORLD")
    assert world is not None
    child_names = {child.name for child in world.children}
    assert {"CV_BASE", "CV_ARCHITECTURE", "CV_PROPS", "CV_VEGETATION", "CV_LIGHTS", "CV_CAMERAS", "CV_ATMOSPHERE"} <= child_names
    for object_name in ("CV_Diorama_Base", "CV_Road", "CV_SariSari_Store", "CV_Sun", "CV_Camera", "CV_Rain_Preview"):
        assert bpy.data.objects.get(object_name) is not None, object_name
    assert bpy.context.scene.camera is bpy.data.objects["CV_Camera"]
    assert world.get("cv_style_label") == "Retro Sci-Fi"
    assert "space" in world.get("cv_asset_keywords")

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

    generation_plan = build_plan("TRIPO", "a stylized low-poly street food cart")
    settings.generation_prompt = generation_plan.prompt
    settings.generation_plan_json = generation_plan.canonical_json()
    settings.generation_fingerprint = generation_plan.fingerprint()
    settings.generation_approved = True
    assert bpy.ops.cozyverse.run_mock_generation() == {"FINISHED"}
    mock_asset = bpy.data.objects.get("CV_Mock_Generated_Asset")
    assert mock_asset is not None and mock_asset.get("cv_provider_mock") is True
    assert settings.generation_approved is False

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

    reference = bpy.data.images.new("CV_Test_Diorama_Reference", width=2, height=2)
    reference.pixels = [0.8, 0.2, 0.1, 1.0] * 4
    settings.reference_image = reference
    settings.reference_image_path = "C:/local/test-reference.png"
    assert bpy.ops.cozyverse.analyze_reference_locally() == {"FINISHED"}
    assert settings.reference_palette_json != "[]"
    assert bpy.ops.cozyverse.recreate_reference_mock() == {"FINISHED"}
    reference_world = bpy.data.collections.get("CV_WORLD_003")
    assert reference_world is not None
    assert reference_world.get("cv_reference_mode") == "local_palette_interpretation"

    output_path = repo_root / "work" / "cozyverse_r1_smoke.blend"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    assert secret_sentinel.encode("utf-8") not in output_path.read_bytes()
    assert (secret_sentinel + "-tripo").encode("utf-8") not in output_path.read_bytes()
    assert (secret_sentinel + "-meshy").encode("utf-8") not in output_path.read_bytes()
    bpy.ops.wm.open_mainfile(filepath=str(output_path))
    assert bpy.data.collections.get("CV_WORLD") is not None
    assert bpy.data.collections.get("CV_WORLD_002") is not None
    assert bpy.data.collections.get("CV_WORLD_003").get("cv_reference_mode") == "local_palette_interpretation"
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

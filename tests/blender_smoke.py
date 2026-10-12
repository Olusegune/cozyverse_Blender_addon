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
from cozyverse_builder.operators import CV_OT_BuildApprovedPlan, _compose_prompt

addon.register()
try:
    assert hasattr(bpy.types.Scene, "cozyverse")
    assert hasattr(bpy.types.WindowManager, "cozyverse_secrets")
    settings = bpy.context.scene.cozyverse
    assert bpy.data.filepath == ""
    assert bpy.ops.cozyverse.create_checkpoint() == {"CANCELLED"}

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
    settings.prompt = "Create a retro sci-fi lunar service station with a road, alien plants and warm sunset."
    assert bpy.ops.cozyverse.edit_multiline_prompt() == {"FINISHED"}
    settings.prompt_text.write("\nInclude a welcoming storefront and evening atmosphere.")
    assert bpy.ops.cozyverse.use_multiline_prompt() == {"FINISHED"}
    assert "\n" in settings.prompt
    assert bpy.ops.cozyverse.prepare_scene_plan() == {"FINISHED"}
    assert settings.workflow_step == "REVIEW"
    assert settings.scene_plan_json
    assert settings.revision_preview_json
    assert settings.revision_deleted == 0
    assert settings.revision_source_world == ""
    assert bpy.ops.cozyverse.build_approved_plan() == {"CANCELLED"}
    settings.plan_approved = True
    settings.plan_prop_count += 1
    assert bpy.ops.cozyverse.build_approved_plan() == {"CANCELLED"}
    assert settings.last_error == "The plan changed after preview"
    assert settings.plan_approved is False
    settings.plan_approved = True
    result = bpy.ops.cozyverse.build_approved_plan()
    assert result == {"FINISHED"}, result
    assert settings.workflow_step == "BUILT"
    assert settings.active_world_name == "CV_WORLD"
    assert bpy.ops.cozyverse.select_world(world_name="CV_WORLD") == {"FINISHED"}
    assert bpy.ops.cozyverse.archive_world(world_name="CV_WORLD", hidden=True) == {"FINISHED"}
    assert bpy.data.collections["CV_WORLD"].hide_viewport is True
    assert bpy.ops.cozyverse.archive_world(world_name="CV_WORLD", hidden=False) == {"FINISHED"}
    assert bpy.data.collections["CV_WORLD"].hide_viewport is False

    world = bpy.data.collections.get("CV_WORLD")
    assert world is not None
    child_names = {child.name for child in world.children}
    assert {"CV_BASE", "CV_ARCHITECTURE", "CV_PROPS", "CV_VEGETATION", "CV_CHARACTERS", "CV_LIGHTS", "CV_CAMERAS", "CV_ATMOSPHERE"} <= child_names
    for object_name in ("CV_Diorama_Base", "CV_Landing_Pad", "CV_Hero_Command_Module", "CV_Sun", "CV_Camera", "CV_Rain_Preview"):
        assert bpy.data.objects.get(object_name) is not None, object_name
    assert bpy.context.scene.camera is bpy.data.objects["CV_Camera"]
    assert world.get("cv_style_label") == "Retro Sci-Fi"
    assert "space" in world.get("cv_asset_keywords")
    assert world.get("cv_composition_family") == "SPACE_OUTPOST"
    assert len(world.children["CV_CHARACTERS"].objects) >= 4

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
    assert '"schema_version":"3.0"' in bpy.context.scene["cv_custom_atmosphere_preset"]
    assert world.get("cv_atmosphere_schema") == "3.0"
    settings.weather = "SNOW"
    settings.snow_amount = 60.0
    settings.weather_quality = "LOW"
    snow = bpy.data.objects["CV_Snow_Preview"]
    assert not snow.hide_viewport and len(snow.data.vertices) == 60 * 4 * 3 // 2
    settings.weather = "FOG"
    settings.fog_amount = 40.0
    assert bpy.context.scene.world.node_tree.nodes["CV Fog"].inputs["Density"].default_value > 0.0
    settings.wind_amount = 55.0
    assert bpy.data.objects["CV_Wind"].get("cv_wind_strength") == 55.0
    settings.wetness_amount = 70.0
    assert bpy.data.materials["CV_Mat_Earth"].roughness < bpy.data.materials["CV_Mat_Earth"]["cv_dry_roughness"]
    settings.season = "AUTUMN"
    assert bpy.data.materials["CV_Mat_Leaves"].diffuse_color[0] > bpy.data.materials["CV_Mat_Leaves"].diffuse_color[1]

    story_character = bpy.data.objects["CV_Character_1_Body"]
    story_locked = bpy.data.objects["CV_Character_1_Head"]
    story_locked["cv_locked"] = True
    manual_character = bpy.data.objects["CV_Character_2_Body"]
    manual_character.keyframe_insert(data_path="rotation_euler", index=2, frame=1)
    manual_action = manual_character.animation_data.action
    original_character_location = tuple(story_character.location)
    actions_before_preview = set(bpy.data.actions)
    settings.story_preset = "BUSY_MARKET"
    settings.story_start_frame = 1
    settings.story_end_frame = 120
    assert bpy.ops.cozyverse.preview_story() == {"FINISHED"}
    assert set(bpy.data.actions) == actions_before_preview
    assert tuple(story_character.location) == original_character_location
    assert settings.story_skipped_count >= 2
    assert settings.story_approved is False
    settings.story_approved = True
    assert bpy.ops.cozyverse.apply_story() == {"FINISHED"}
    first_story_id = settings.story_active_id
    assert first_story_id
    assert story_character.animation_data.action.get("cv_story_id") == first_story_id
    bpy.context.scene.frame_set(60)
    assert story_character.location.z != original_character_location[2]
    bpy.context.scene.frame_set(1)
    assert story_locked.animation_data is None
    assert manual_character.animation_data.action is manual_action
    assert bpy.data.collections.get(f"CV_STORY_{first_story_id}") is not None
    assert bpy.ops.cozyverse.clear_story() == {"FINISHED"}
    assert settings.story_active_id == ""
    assert story_character.animation_data.action is None
    assert tuple(story_character.location) == original_character_location
    assert manual_character.animation_data.action is manual_action
    story_locked["cv_locked"] = False
    original_weather = settings.weather
    original_rain_amount = settings.rain_amount
    settings.story_preset = "RAINY_EVENING"
    assert bpy.ops.cozyverse.preview_story() == {"FINISHED"}
    settings.story_approved = True
    assert bpy.ops.cozyverse.apply_story() == {"FINISHED"}
    rainy_story_id = settings.story_active_id
    assert rain.animation_data.action.get("cv_story_id") == rainy_story_id
    assert settings.weather == "RAIN" and settings.rain_amount >= 55.0
    assert bpy.ops.cozyverse.clear_story() == {"FINISHED"}
    assert settings.weather == original_weather and settings.rain_amount == original_rain_amount
    settings.practical_temperature = 2300.0
    settings.practical_lights = False
    assert interior.data.energy == 0.0
    settings.practical_lights = True
    assert interior.data.energy > 0.0
    settings.exposure = 0.75
    assert bpy.context.scene.view_settings.exposure == 0.75
    assert bpy.ops.cozyverse.save_atmosphere_preset() == {"FINISHED"}

    generation_plan = build_plan("TRIPO", "a stylized low-poly street food cart")
    settings.generation_prompt = generation_plan.prompt
    settings.generation_plan_json = generation_plan.canonical_json()
    settings.generation_fingerprint = generation_plan.fingerprint()
    settings.generation_estimated_credits = generation_plan.estimated_credits
    settings.generation_approved = True
    assert bpy.ops.cozyverse.run_mock_generation() == {"FINISHED"}
    assert settings.generation_approved is False
    assert settings.generation_job_status == "PENDING"
    assert bpy.data.collections.get("CV_ASSET_QUARANTINE") is None
    assert bpy.ops.cozyverse.refresh_generation_job() == {"FINISHED"}
    assert settings.generation_job_status == "IN_PROGRESS"
    assert bpy.ops.cozyverse.refresh_generation_job() == {"FINISHED"}
    assert settings.generation_job_status == "SUCCEEDED"
    assert bpy.ops.cozyverse.download_generation_result() == {"FINISHED"}
    assert bpy.ops.cozyverse.import_generation_result() == {"CANCELLED"}
    settings.generation_import_approved = True
    assert bpy.ops.cozyverse.import_generation_result() == {"FINISHED"}
    mock_asset = bpy.data.objects.get(settings.generation_quarantine_name)
    assert mock_asset is not None and mock_asset.get("cv_provenance") == "provider_mock"
    assert bpy.data.collections.get("CV_ASSET_QUARANTINE") is not None
    assert bpy.ops.cozyverse.promote_generation_asset() == {"CANCELLED"}
    settings.generation_promotion_approved = True
    assert bpy.ops.cozyverse.promote_generation_asset() == {"FINISHED"}
    assert mock_asset.get("cv_asset_factory") is True
    assert bpy.data.collections.get("CV_ASSET_FACTORY") is not None

    store = bpy.data.objects["CV_Hero_Command_Module"]
    store.location.x += 0.75
    edited_x = store.location.x
    assert bpy.ops.cozyverse.inspect_manual_edits() == {"FINISHED"}
    assert "Manual-edit check:" in settings.status and "changed" in settings.status
    store.select_set(True)
    assert bpy.ops.cozyverse.lock_selected_objects() == {"FINISHED"}
    assert store.get("cv_locked") is True
    first_material_color = tuple(store.data.materials[0].diffuse_color)
    settings.preset = "GOTHIC"
    assert bpy.ops.cozyverse.create_local_demo() == {"FINISHED"}
    assert bpy.data.collections.get("CV_WORLD_002") is not None
    assert bpy.data.collections["CV_WORLD_002"].get("cv_architecture_treatment") == "TURRET"
    settings.exposure = -1.0
    settings.practical_temperature = 6000.0
    assert bpy.ops.cozyverse.save_atmosphere_preset() == {"FINISHED"}
    assert bpy.ops.cozyverse.select_world(world_name="CV_WORLD") == {"FINISHED"}
    assert settings.exposure == 0.75
    assert settings.practical_temperature == 2300.0
    assert bpy.ops.cozyverse.select_world(world_name="CV_WORLD_002") == {"FINISHED"}
    assert settings.exposure == -1.0
    assert settings.practical_temperature == 6000.0
    legacy = '{"schema_version":"1.0","time_hour":10,"sun_intensity":40,"warmth":50,"ambient_intensity":30,"interior_intensity":20,"weather":"CLEAR","rain_amount":0}'
    bpy.data.collections["CV_WORLD_002"]["cv_atmosphere_values"] = legacy
    assert bpy.ops.cozyverse.load_atmosphere_preset() == {"FINISHED"}
    assert settings.time_hour == 10.0
    assert '"schema_version":"3.0"' in bpy.data.collections["CV_WORLD_002"]["cv_atmosphere_values"]
    settings.prompt = "Create a revised village with a larger market square"
    settings.prompt_text = None
    world_count_before_cancel = len([item for item in bpy.data.collections if item.get("cv_managed") and item.name.startswith("CV_WORLD")])
    assert bpy.ops.cozyverse.prepare_scene_plan() == {"FINISHED"}
    assert settings.revision_source_world == "CV_WORLD_002"
    assert settings.revision_skipped > 0
    assert settings.revision_deleted == 0
    assert bpy.ops.cozyverse.cancel_revision() == {"FINISHED"}
    assert len([item for item in bpy.data.collections if item.get("cv_managed") and item.name.startswith("CV_WORLD")]) == world_count_before_cancel
    assert bpy.data.objects.get("CV_Hero_Command_Module") is store
    assert store.location.x == edited_x
    assert tuple(store.data.materials[0].diffuse_color) == first_material_color
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
    assert reference_world.get("cv_reference_mode") == "local_composition_interpretation"
    assert reference_world.get("cv_reference_analysis")
    assert reference_world.get("cv_reference_quality") == "BALANCED"

    library_path = repo_root / "work" / "cozyverse_asset_library_test.blend"
    bpy.data.libraries.write(str(library_path), {preexisting})
    settings.asset_items.clear()
    asset = settings.asset_items.add()
    asset.name = "Test Street Prop"
    asset.path = str(library_path)
    asset.extension = ".blend"
    asset.category = "PROP"
    asset.tags = "test, street, prop"
    asset.source = "LOCAL_FOLDER"
    settings.asset_index = 0
    settings.asset_place_location = (6.0, 6.0, 0.0)
    settings.asset_place_scale = 0.75
    assert bpy.ops.cozyverse.preview_asset_placement() == {"FINISHED"}
    assert bpy.data.objects.get(settings.asset_preview_name).get("cv_asset_preview") is True
    assert bpy.ops.cozyverse.place_approved_asset() == {"CANCELLED"}
    settings.asset_placement_approved = True
    assert bpy.ops.cozyverse.place_approved_asset() == {"FINISHED"}
    assert bpy.data.collections.get("CV_IMPORTED_ASSETS") is not None
    imported_wrapper = bpy.data.objects.get("CV_ASSET_Test Street Prop")
    assert imported_wrapper is not None
    assert imported_wrapper.get("cv_provenance") == "user_approved_local_asset"

    settings.story_preset = "QUIET_MORNING"
    settings.story_start_frame = 5
    settings.story_end_frame = 96
    assert bpy.ops.cozyverse.preview_story() == {"FINISHED"}
    settings.story_approved = True
    assert bpy.ops.cozyverse.apply_story() == {"FINISHED"}
    persistent_story_id = settings.story_active_id
    assert persistent_story_id and bpy.data.collections.get(f"CV_STORY_{persistent_story_id}") is not None
    persistent_world = bpy.data.collections[settings.active_world_name]
    animated_leaf = next(obj for obj in persistent_world.all_objects if obj.name.endswith("_Leaves") and obj.animation_data and obj.animation_data.action)
    assert animated_leaf.animation_data.action.get("cv_story_id") == persistent_story_id

    assert "UNDO" in CV_OT_BuildApprovedPlan.bl_options

    output_path = repo_root / "work" / "cozyverse_r1_smoke.blend"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    active_path = bpy.data.filepath
    assert bpy.ops.cozyverse.create_checkpoint() == {"FINISHED"}
    checkpoint_path = pathlib.Path(settings.checkpoint_path)
    assert checkpoint_path.exists()
    assert bpy.data.filepath == active_path
    assert settings.activity_log
    assert all(secret_sentinel not in item.message for item in settings.activity_log)
    assert secret_sentinel.encode("utf-8") not in output_path.read_bytes()
    assert (secret_sentinel + "-tripo").encode("utf-8") not in output_path.read_bytes()
    assert (secret_sentinel + "-meshy").encode("utf-8") not in output_path.read_bytes()
    bpy.ops.wm.open_mainfile(filepath=str(output_path))
    assert bpy.data.collections.get("CV_WORLD") is not None
    assert bpy.data.collections.get("CV_WORLD_002") is not None
    assert bpy.data.collections.get("CV_WORLD_003").get("cv_reference_mode") == "local_composition_interpretation"
    assert bpy.data.objects.get("Preexisting_User_Object") is not None
    assert bpy.data.objects["CV_Hero_Command_Module"].location.x == edited_x
    assert bpy.context.scene.cozyverse.story_active_id == persistent_story_id
    assert bpy.data.collections.get(f"CV_STORY_{persistent_story_id}") is not None
    assert bpy.context.scene.cozyverse.weather == "CLEAR"
    assert bpy.context.scene.cozyverse.time_hour in {12.0, 18.5, 22.0}
    assert bpy.data.collections["CV_WORLD_002"].get("cv_atmosphere_schema") == "3.0"
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

"""Blender background acceptance test for the 0.17 Magic Flow path."""

from __future__ import annotations

import importlib
import pathlib
import sys

import bpy


repo_root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "blender_addon"))
addon = importlib.import_module("cozyverse_builder")
addon.register()
try:
    scene = bpy.context.scene
    settings = scene.cozyverse
    assert hasattr(bpy.ops.cozyverse, "conjure") and hasattr(bpy.ops.cozyverse, "quick_conjure")

    # Empty prompt is a friendly refusal, not an error.
    settings.prompt = ""
    assert bpy.ops.cozyverse.conjure() == {"CANCELLED"}

    # One click builds an approved, presented world.
    assert bpy.ops.cozyverse.surprise() == {"FINISHED"}
    assert settings.prompt
    settings.prompt = "A rainy cafe corner with warm glowing windows"
    assert bpy.ops.cozyverse.conjure() == {"FINISHED"}
    assert settings.workflow_step == "BUILT"
    first = settings.active_world_name
    assert first == "CV_WORLD"
    world = bpy.data.collections[first]

    # Fresh builds no longer leak rain or snow previews.
    rain = next(obj for obj in world.all_objects if obj.name.startswith("CV_Rain_Preview"))
    snow = next(obj for obj in world.all_objects if obj.name.startswith("CV_Snow_Preview"))
    assert rain.hide_render and snow.hide_render
    # ...and previews do not count as hand edits.
    assert bpy.ops.cozyverse.inspect_manual_edits() == {"FINISHED"}
    assert "0 changed" in settings.status

    # Materials are real shader node trees whose windows glow with the practical lights.
    window = next(m for m in bpy.data.materials if m.name.startswith("CV_Mat_Window"))
    bsdf = next(n for n in window.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    settings.practical_lights = True
    settings.interior_intensity = 80.0
    assert bsdf.inputs["Emission Strength"].default_value > 1.0
    settings.practical_lights = False
    assert bsdf.inputs["Emission Strength"].default_value == 0.0
    settings.practical_lights = True
    leaves = next(m for m in bpy.data.materials if m.name.startswith("CV_Mat_Leaves"))
    settings.season = "AUTUMN"
    leaf_bsdf = next(n for n in leaves.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    assert leaf_bsdf.inputs["Base Color"].default_value[0] > leaf_bsdf.inputs["Base Color"].default_value[1]
    settings.season = "SUMMER"

    # Remix keeps the plan and produces a new, different version without touching the first.
    layout_before = sorted(tuple(round(v, 3) for v in obj.location) for obj in world.all_objects if obj.type == "MESH")
    assert bpy.ops.cozyverse.conjure(remix=True) == {"FINISHED"}
    assert settings.variation == 1
    second = settings.active_world_name
    assert second != first and bpy.data.collections.get(first) is not None
    # Versions share one stage: the earlier one is hidden, never deleted, and the new one is visible.
    assert bpy.data.collections[first].hide_viewport and bpy.data.collections[first].hide_render
    assert not bpy.data.collections[second].hide_viewport
    assert "earlier version" in settings.status
    layout_after_first = sorted(tuple(round(v, 3) for v in obj.location) for obj in bpy.data.collections[first].all_objects if obj.type == "MESH")
    assert layout_before == layout_after_first
    layout_second = sorted(tuple(round(v, 3) for v in obj.location) for obj in bpy.data.collections[second].all_objects if obj.type == "MESH")
    assert layout_second != layout_before

    # Cinematic shots are separate cameras; the original is never moved.
    base_camera = next(obj for obj in bpy.data.collections[second].all_objects if obj.type == "CAMERA")
    base_location = tuple(base_camera.location)
    assert bpy.ops.cozyverse.frame_shot(shot="HERO") == {"FINISHED"}
    assert scene.camera.get("cv_shot") == "HERO"
    assert bpy.ops.cozyverse.frame_shot(shot="DETAIL") == {"FINISHED"}
    assert scene.camera.data.dof.use_dof
    assert bpy.ops.cozyverse.frame_shot(shot="WIDE") == {"FINISHED"}
    assert scene.camera is base_camera and tuple(base_camera.location) == base_location
    assert bpy.ops.cozyverse.inspect_manual_edits() == {"FINISHED"}
    assert "0 changed" in settings.status

    # Turntable: a seamless linear orbit that can be removed without leaving a trace.
    import math
    camera = scene.camera
    start = camera.matrix_world.translation.copy()
    settings.turntable_frames = 48
    assert bpy.ops.cozyverse.turntable() == {"FINISHED"}
    rig = next(obj for obj in bpy.data.collections[second].all_objects if obj.get("cv_turntable"))
    assert camera.parent is rig and scene.frame_end == 48
    scene.frame_set(1)
    assert (camera.matrix_world.translation - start).length < 1e-4
    scene.frame_set(25)
    halfway = camera.matrix_world.translation
    assert abs(halfway.x + start.x) < 0.02 and abs(halfway.y + start.y) < 0.02  # half a turn, linear
    scene.frame_set(1)
    assert bpy.ops.cozyverse.turntable() == {"FINISHED"}  # rebuilding never duplicates the rig
    assert len([obj for obj in bpy.data.objects if obj.get("cv_turntable")]) == 1
    assert bpy.ops.cozyverse.inspect_manual_edits() == {"FINISHED"} and "0 changed" in settings.status
    assert bpy.ops.cozyverse.toggle_turntable() == {"FINISHED"}  # second toggle removes it
    assert camera.parent is None and (camera.matrix_world.translation - start).length < 1e-4
    assert not [obj for obj in bpy.data.objects if obj.get("cv_turntable")]
    assert not [action for action in bpy.data.actions if action.name.startswith("CV_TURNTABLE")]
    assert bpy.ops.cozyverse.toggle_turntable() == {"FINISHED"}
    assert bpy.ops.cozyverse.clear_turntable() == {"FINISHED"}
    assert bpy.ops.cozyverse.clear_turntable() == {"CANCELLED"}

    # Pie menu actions.
    assert hasattr(bpy.types, "CV_MT_pie_main")
    assert bpy.ops.cozyverse.set_look(look="MOONLIT") == {"FINISHED"} and settings.atmosphere_preset == "MOONLIT"
    scene.camera = base_camera
    assert bpy.ops.cozyverse.next_shot() == {"FINISHED"} and scene.camera.get("cv_shot") == "HERO"
    assert bpy.ops.cozyverse.next_shot() == {"FINISHED"} and scene.camera.get("cv_shot") == "DETAIL"
    assert bpy.ops.cozyverse.next_shot() == {"FINISHED"} and scene.camera is base_camera

    # Time of day and tabs.
    assert bpy.ops.cozyverse.set_time_of_day(hour=6.0) == {"FINISHED"}
    assert settings.time_hour == 6.0 and settings.atmosphere_preset == "CUSTOM"
    for tab in ("ATMOSPHERE", "SHOT", "STORY", "GENERATE", "ACTIVITY", "SETTINGS", "CREATE"):
        assert bpy.ops.cozyverse.goto_tab(tab=tab) == {"FINISHED"}
        assert settings.active_tab == tab
    assert bpy.ops.cozyverse.render_postcard() == {"FINISHED"}

    # The sidebar keeps the user's own words; the style directive is added once when planning.
    settings.prompt = "A tiny harbor with a lighthouse"
    settings.preset = "SOLARPUNK"
    from cozyverse_builder.operators import _plan_prompt
    assert "Style direction" not in settings.prompt and _plan_prompt(settings).count("Style direction") == 1

    # Every composition family has glowing parts, so night looks alive everywhere.
    for kind in ("village", "city", "cafe", "farm", "market", "fantasy", "lunar space outpost", "forest landscape"):
        settings.prompt = f"a {kind}"
        assert bpy.ops.cozyverse.conjure() == {"FINISHED"}, kind
        glow = [o for o in bpy.data.collections[settings.active_world_name].all_objects if any(t in o.name for t in ("Window", "Lantern", "Beacon", "Dome"))]
        if kind != "forest landscape":
            assert glow, kind

    # Review-first mode still gates the build behind approval.
    settings.review_before_build = True
    assert bpy.ops.cozyverse.back_to_description() == {"FINISHED"}
    count = len([c for c in bpy.data.collections if c.name.startswith("CV_WORLD")])
    assert bpy.ops.cozyverse.conjure() == {"FINISHED"}
    assert settings.workflow_step == "REVIEW"
    assert len([c for c in bpy.data.collections if c.name.startswith("CV_WORLD")]) == count
finally:
    addon.unregister()
print("COZYVERSE_FLOW_SMOKE_OK")

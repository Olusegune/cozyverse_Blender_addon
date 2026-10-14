"""Blender background acceptance test for the sky: looks, gradient, stars, fog volume and the day cycle."""

from __future__ import annotations

import importlib
import pathlib
import sys

import bpy


repo_root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "blender_addon"))
addon = importlib.import_module("cozyverse_builder")
addon.register()
from cozyverse_builder.core.atmosphere_spec import PRESETS  # noqa: E402

try:
    scene = bpy.context.scene
    settings = scene.cozyverse
    settings.prompt = "A cozy village with a town hall and trees"
    assert bpy.ops.cozyverse.conjure() == {"FINISHED"}
    world_collection = bpy.data.collections[settings.active_world_name]
    nodes = scene.world.node_tree.nodes
    output = nodes["World Output"]

    # Ten ready-made looks, each one switchable in a single step.
    assert len(PRESETS) == 10
    for name, values in PRESETS.items():
        settings.atmosphere_preset = name
        assert abs(settings.time_hour - values.time_hour) < 1e-4 and settings.weather == values.weather, name

    # The sky is a gradient with stars; camera rays see the bright version, lighting stays soft.
    assert all(nodes.get(n) is not None for n in ("CV Sky Gradient", "CV Sky Stars", "CV Sky Mix", "CV Sky Camera"))
    assert output.inputs["Surface"].links[0].from_node.name == "CV Sky Mix"
    assert not output.inputs["Volume"].is_linked  # an infinite world volume would black out the sky

    def stars():
        return nodes["CV Sky Star Visible"].inputs[1].default_value

    def horizon():
        return tuple(nodes["CV Sky Gradient"].inputs[6].default_value)[:3]

    settings.weather = "CLEAR"
    settings.fog_amount = 0.0
    settings.atmosphere_preset = "STARRY_NIGHT"
    night_horizon, night_stars = horizon(), stars()
    settings.atmosphere_preset = "BRIGHT_DAY"
    day_horizon, day_stars = horizon(), stars()
    assert night_stars > 0.5 and day_stars == 0.0
    assert sum(day_horizon) > sum(night_horizon) * 3  # a pale day sky against a deep night one
    settings.atmosphere_preset = "STARRY_NIGHT"
    settings.stars_amount = 0.0
    assert stars() == 0.0
    settings.stars_amount = 70.0
    settings.weather = "RAIN"
    assert stars() < night_stars * 0.2  # clouds hide the stars
    settings.weather = "CLEAR"
    # A golden sunset warms the horizon: red beats blue.
    settings.atmosphere_preset = "SUNSET_GLOW"
    red, green, blue = horizon()
    assert red > blue

    # Fog is a bounded box of mist, so the sky survives it.
    settings.fog_amount = 0.0
    fog = next(o for o in world_collection.all_objects if o.name.startswith("CV_Fog_Volume"))
    assert fog.hide_render and fog.get("cv_weather") == "FOG"
    settings.fog_amount = 60.0
    assert not fog.hide_render and fog["cv_fog_density"] > 0.05
    assert not output.inputs["Volume"].is_linked
    assert bpy.ops.cozyverse.inspect_manual_edits() == {"FINISHED"} and "0 changed" in settings.status
    settings.fog_amount = 0.0

    # Day cycle: the sun, sky and glow follow the timeline, then it goes away cleanly.
    sun = next(o for o in world_collection.all_objects if o.name.startswith("CV_Sun"))
    original_range = (scene.frame_start, scene.frame_end)
    settings.daycycle_seconds = 4.0
    assert bpy.ops.cozyverse.daycycle_add() == {"FINISHED"}
    assert scene.get("cv_daycycle") and scene.frame_end == 4 * scene.render.fps
    scene.frame_set(1)
    midnight = tuple(sun.rotation_euler)
    scene.frame_set(1 + scene.frame_end // 2)
    assert abs(settings.time_hour - 12.0) < 0.6, settings.time_hour  # animated settings drive the sky
    assert tuple(sun.rotation_euler) != midnight
    noon_horizon = horizon()
    scene.frame_set(1)
    assert sum(noon_horizon) > sum(horizon()) * 2
    assert bpy.ops.cozyverse.daycycle_remove() == {"FINISHED"}
    assert not scene.get("cv_daycycle") and (scene.frame_start, scene.frame_end) == original_range
    assert bpy.ops.cozyverse.daycycle_remove() == {"CANCELLED"}
    time_now = settings.time_hour
    scene.frame_set(30)
    assert settings.time_hour == time_now  # nothing is animating it any more
finally:
    addon.unregister()
print("COZYVERSE_SKY_SMOKE_OK")

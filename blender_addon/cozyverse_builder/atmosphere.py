"""Apply Atmosphere Lab values to Blender-native scene data."""

from __future__ import annotations

import math

import bpy

from .core.atmosphere_spec import sun_azimuth_degrees, sun_elevation_degrees, warmth_rgb


SUN_NAME = "CV_Sun"
RAIN_NAME = "CV_Rain_Preview"
INTERIOR_LIGHT_PREFIX = "CV_Interior_"


def apply_atmosphere(scene: bpy.types.Scene, settings) -> bool:
    """Update existing CozyVerse lights, world nodes, and rain preview."""
    changed = False
    active_world = scene.get("cv_active_world", "")
    suns = [
        obj
        for obj in bpy.data.objects
        if obj.name.startswith(SUN_NAME)
        and obj.get("cv_demo") is True
        and (not active_world or obj.get("cv_world_root") == active_world)
    ]
    sun = suns[-1] if suns else None
    if sun is not None and isinstance(sun.data, bpy.types.Light):
        elevation = sun_elevation_degrees(settings.time_hour)
        azimuth = sun_azimuth_degrees(settings.time_hour)
        sun.rotation_euler = (
            math.radians(90.0 - elevation),
            0.0,
            math.radians(azimuth),
        )
        daylight = max(0.04, (elevation + 8.0) / 66.0)
        sun.data.energy = (settings.sun_intensity / 100.0) * 5.0 * daylight
        sun.data.color = warmth_rgb(settings.warmth)
        changed = True

    world = scene.world
    if world is None:
        world = bpy.data.worlds.new("CV_World")
        scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background") if world.node_tree else None
    if background is not None:
        ambient = settings.ambient_intensity / 100.0
        background.inputs["Strength"].default_value = 0.03 + ambient * 0.55
        warm = warmth_rgb(settings.warmth)
        night = 1.0 if 7.0 <= settings.time_hour <= 19.0 else 0.25
        background.inputs["Color"].default_value = (
            warm[0] * 0.12 * night,
            warm[1] * 0.16 * night,
            warm[2] * 0.24,
            1.0,
        )
        changed = True

    for obj in bpy.data.objects:
        if (
            obj.name.startswith(INTERIOR_LIGHT_PREFIX)
            and isinstance(obj.data, bpy.types.Light)
            and (not active_world or obj.get("cv_world_root") == active_world)
        ):
            obj.data.energy = (settings.interior_intensity / 100.0) * 900.0
            obj.data.color = (1.0, 0.42, 0.12)
            changed = True

    rain_objects = [
        obj
        for obj in bpy.data.objects
        if obj.name.startswith(RAIN_NAME)
        and obj.get("cv_demo") is True
        and (not active_world or obj.get("cv_world_root") == active_world)
    ]
    rain = rain_objects[-1] if rain_objects else None
    if rain is not None:
        enabled = settings.weather == "RAIN" and settings.rain_amount > 0.0
        rain.hide_viewport = not enabled
        rain.hide_render = not enabled
        rain["cv_rain_amount"] = float(settings.rain_amount)
        rain.scale.z = 0.6 + (settings.rain_amount / 100.0) * 0.8
        rain.color = (0.18, 0.55, 1.0, 1.0)
        changed = True

    return changed

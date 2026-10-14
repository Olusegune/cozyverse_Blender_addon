"""Apply Atmosphere Lab values to Blender-native scene data."""

from __future__ import annotations

import math
import random

import bpy

from .materials import sync_color, sync_glow, sync_roughness
from .core.atmosphere_spec import AtmosphereValues, kelvin_rgb, serialize_preset, sun_azimuth_degrees, sun_elevation_degrees, warmth_rgb


SUN_NAME = "CV_Sun"
RAIN_NAME = "CV_Rain_Preview"
SNOW_NAME = "CV_Snow_Preview"
WIND_NAME = "CV_Wind"
INTERIOR_LIGHT_PREFIX = "CV_Interior_"


def _set_precipitation_density(obj: bpy.types.Object, kind: str, quality: str) -> None:
    count = {"LOW": 60, "MEDIUM": 160, "HIGH": 320}.get(quality, 160)
    if kind == "SNOW":
        count = int(count * 1.5)
    if obj.get("cv_particle_count") == count:
        return
    rng = random.Random(42 if kind == "RAIN" else 84)
    vertices = []
    faces = []
    for _ in range(count):
        x, y, z = rng.uniform(-5.2, 5.2), rng.uniform(-3.7, 3.7), rng.uniform(0.5, 7.5)
        start = len(vertices)
        if kind == "RAIN":
            width, length = 0.018, rng.uniform(0.28, 0.7)
            vertices.extend(((x - width, y, z), (x + width, y, z), (x + width - 0.11, y, z - length), (x - width - 0.11, y, z - length)))
        else:
            size = rng.uniform(0.025, 0.065)
            vertices.extend(((x - size, y, z), (x + size, y, z), (x + size, y, z + size * 2), (x - size, y, z + size * 2)))
        faces.append((start, start + 1, start + 2, start + 3))
    obj.data.clear_geometry()
    obj.data.from_pydata(vertices, [], faces)
    obj.data.update()
    obj["cv_particle_count"] = count


def _mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def _sky_color(settings) -> tuple[float, float, float, float]:
    """Soft time-of-day backdrop: deep blue night, pale day, warm glow near the horizon."""
    elevation = sun_elevation_degrees(settings.time_hour)
    daylight = max(0.0, min(1.0, (elevation + 8.0) / 66.0)) ** 0.8
    sky = _mix((0.02, 0.035, 0.11), (0.46, 0.64, 0.90), daylight)
    glow = max(0.0, 1.0 - abs(elevation - 6.0) / 16.0) * (settings.warmth / 100.0)
    sky = _mix(sky, (0.95, 0.52, 0.30), glow * 0.55)
    return (*sky, 1.0)


def apply_atmosphere(scene: bpy.types.Scene, settings) -> bool:
    """Update existing CozyVerse lights, world nodes, and rain preview."""
    changed = False
    active_world = scene.get("cv_active_world", "")
    world_collection = bpy.data.collections.get(active_world) if active_world else None
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
        background.inputs["Color"].default_value = _sky_color(settings)
        changed = True

    if world.node_tree is not None:
        output = world.node_tree.nodes.get("World Output")
        fog = world.node_tree.nodes.get("CV Fog")
        if fog is None:
            fog = world.node_tree.nodes.new("ShaderNodeVolumePrincipled")
            fog.name = "CV Fog"
        density = settings.fog_amount / 100.0 * 0.045 if settings.weather == "FOG" or settings.fog_amount > 0.0 else 0.0
        fog.inputs["Density"].default_value = density
        if output is not None and not output.inputs["Volume"].is_linked:
            world.node_tree.links.new(fog.outputs["Volume"], output.inputs["Volume"])

    for obj in bpy.data.objects:
        if (
            obj.name.startswith(INTERIOR_LIGHT_PREFIX)
            and isinstance(obj.data, bpy.types.Light)
            and (not active_world or obj.get("cv_world_root") == active_world)
        ):
            target_energy = (settings.interior_intensity / 100.0) * 900.0 if settings.practical_lights else 0.0
            obj.data["cv_base_energy"] = target_energy  # the flicker driver multiplies this
            obj.data.energy = target_energy
            obj.data.color = kelvin_rgb(settings.practical_temperature)
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
        _set_precipitation_density(rain, "RAIN", settings.weather_quality)
        enabled = settings.weather == "RAIN" and settings.rain_amount > 0.0
        rain.hide_viewport = not enabled
        rain.hide_render = not enabled
        rain["cv_rain_amount"] = float(settings.rain_amount)
        rain.scale.z = 0.6 + (settings.rain_amount / 100.0) * 0.8
        rain.color = (0.18, 0.55, 1.0, 1.0)
        changed = True

    snow = next((obj for obj in bpy.data.objects if obj.name.startswith(SNOW_NAME) and (not active_world or obj.get("cv_world_root") == active_world)), None)
    if snow is not None:
        _set_precipitation_density(snow, "SNOW", settings.weather_quality)
        enabled = settings.weather == "SNOW" and settings.snow_amount > 0.0
        snow.hide_viewport = not enabled
        snow.hide_render = not enabled
        snow.scale = (1.0 + settings.snow_amount / 250.0,) * 3
        snow["cv_snow_amount"] = float(settings.snow_amount)
        snow["cv_preview_quality"] = settings.weather_quality
        changed = True

    wind = next((obj for obj in bpy.data.objects if obj.name.startswith(WIND_NAME) and (not active_world or obj.get("cv_world_root") == active_world)), None)
    if wind is not None:
        wind.hide_viewport = settings.wind_amount <= 0.0
        wind.hide_render = True
        wind["cv_wind_strength"] = float(settings.wind_amount)
        wind.empty_display_size = 0.6 + settings.wind_amount / 35.0

    season_colors = {"SPRING": (0.24, 0.62, 0.22, 1.0), "SUMMER": (0.10, 0.38, 0.12, 1.0), "AUTUMN": (0.72, 0.22, 0.035, 1.0), "WINTER": (0.58, 0.65, 0.55, 1.0)}
    if world_collection is not None:
        seen_materials = set()
        for obj in world_collection.all_objects:
            data = getattr(obj, "data", None)
            for material in getattr(data, "materials", ()) if data is not None else ():
                if material is None or material in seen_materials:
                    continue
                seen_materials.add(material)
                if "cv_dry_roughness" not in material:
                    material["cv_dry_roughness"] = material.roughness
                sync_roughness(material, max(0.08, float(material["cv_dry_roughness"]) * (1.0 - settings.wetness_amount / 125.0)))
                if material.name.startswith("CV_Mat_Leaves"):
                    sync_color(material, season_colors[settings.season])
                if material.get("cv_emissive"):
                    if material.name.startswith("CV_Mat_Window"):
                        glow = (settings.interior_intensity / 100.0) * 4.5 if settings.practical_lights else 0.0
                        sync_glow(material, glow, kelvin_rgb(settings.practical_temperature))
                    else:
                        sync_glow(material, 0.8, tuple(material.diffuse_color)[:3])

    scene.view_settings.exposure = settings.exposure
    if world_collection is not None and world_collection.get("cv_managed"):
        values = AtmosphereValues(
            settings.time_hour,
            settings.sun_intensity,
            settings.warmth,
            settings.ambient_intensity,
            settings.interior_intensity,
            settings.weather,
            settings.rain_amount,
            settings.exposure,
            settings.practical_temperature,
            settings.practical_lights,
            settings.fog_amount,
            settings.wind_amount,
            settings.wetness_amount,
            settings.snow_amount,
            settings.season,
            settings.weather_quality,
        )
        world_collection["cv_atmosphere_schema"] = "3.0"
        world_collection["cv_atmosphere_preset"] = settings.atmosphere_preset
        world_collection["cv_atmosphere_values"] = serialize_preset(values)

    return changed

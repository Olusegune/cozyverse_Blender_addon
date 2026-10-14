"""Apply Atmosphere Lab values to Blender-native scene data."""

from __future__ import annotations

import math
import random

import bpy

from .materials import sync_color, sync_glow, sync_roughness
from .core.atmosphere_spec import AtmosphereValues, cloud_color, cloud_cover, sky_colors, star_visibility, kelvin_rgb, serialize_preset, sun_azimuth_degrees, sun_elevation_degrees, warmth_rgb


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
            size = rng.uniform(0.025, 0.06)
            # An octagon, so flakes read as soft round dots instead of little squares.
            vertices.extend((x + math.cos(step * math.pi / 4) * size, y, z + math.sin(step * math.pi / 4) * size) for step in range(8))
        faces.append((start, start + 1, start + 2, start + 3) if kind == "RAIN" else tuple(range(start, start + 8)))
    obj.data.clear_geometry()
    obj.data.from_pydata(vertices, [], faces)
    obj.data.update()
    obj["cv_particle_count"] = count


def _ensure_sky_nodes(world: bpy.types.World, background) -> dict:
    """Build (once) the horizon-to-zenith gradient and procedural stars feeding the world's Background."""
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    if nodes.get("CV Sky Gradient") is None:
        coord = nodes.new("ShaderNodeTexCoord")
        coord.name = "CV Sky Coord"
        separate = nodes.new("ShaderNodeSeparateXYZ")
        separate.name = "CV Sky Separate"
        height = nodes.new("ShaderNodeMapRange")
        height.name = "CV Sky Height"
        height.inputs["From Min"].default_value = 0.0
        height.inputs["From Max"].default_value = 0.75
        gradient = nodes.new("ShaderNodeMix")
        gradient.name = "CV Sky Gradient"
        gradient.data_type = "RGBA"
        voronoi = nodes.new("ShaderNodeTexVoronoi")
        voronoi.name = "CV Sky Star Field"
        voronoi.voronoi_dimensions = "3D"
        voronoi.feature = "F1"
        voronoi.inputs["Scale"].default_value = 70.0
        mask = nodes.new("ShaderNodeMapRange")
        mask.name = "CV Sky Star Mask"
        mask.inputs["From Min"].default_value = 0.0
        mask.inputs["From Max"].default_value = 0.06
        mask.inputs["To Min"].default_value = 1.0
        mask.inputs["To Max"].default_value = 0.0
        visible = nodes.new("ShaderNodeMath")
        visible.name = "CV Sky Star Visible"
        visible.operation = "MULTIPLY"
        stars = nodes.new("ShaderNodeMix")
        stars.name = "CV Sky Stars"
        stars.data_type = "RGBA"
        stars.inputs[7].default_value = (6.0, 6.0, 7.0, 1.0)
        links.new(coord.outputs["Generated"], separate.inputs["Vector"])
        links.new(separate.outputs["Z"], height.inputs["Value"])
        links.new(height.outputs["Result"], gradient.inputs[0])
        links.new(coord.outputs["Generated"], voronoi.inputs["Vector"])
        links.new(voronoi.outputs["Distance"], mask.inputs["Value"])
        links.new(mask.outputs["Result"], visible.inputs[0])
        links.new(visible.outputs["Value"], stars.inputs[0])
        links.new(gradient.outputs[2], stars.inputs[6])
        links.new(stars.outputs[2], background.inputs["Color"])
        # Camera rays see a bright, saturated sky; everything else gets the softer ambient light.
        output = nodes.get("World Output")
        if output is not None:
            light_path = nodes.new("ShaderNodeLightPath")
            light_path.name = "CV Sky Light Path"
            seen = nodes.new("ShaderNodeBackground")
            seen.name = "CV Sky Camera"
            seen.inputs["Strength"].default_value = 1.0
            blend = nodes.new("ShaderNodeMixShader")
            blend.name = "CV Sky Mix"
            links.new(stars.outputs[2], seen.inputs["Color"])
            links.new(light_path.outputs["Is Camera Ray"], blend.inputs[0])
            links.new(background.outputs["Background"], blend.inputs[1])
            links.new(seen.outputs["Background"], blend.inputs[2])
            links.new(blend.outputs["Shader"], output.inputs["Surface"])
    return {"gradient": nodes["CV Sky Gradient"], "visible": nodes["CV Sky Star Visible"]}


FOG_NAME = "CV_Fog_Volume"


def _ensure_fog_volume(world_collection: bpy.types.Collection) -> bpy.types.Object:
    """A soft box of mist around the stage. Unlike a world volume it never swallows the sky."""
    existing = next((obj for obj in world_collection.all_objects if obj.name.startswith(FOG_NAME)), None)
    if existing is not None:
        return existing
    holder = next((child for child in world_collection.children if child.name.startswith("CV_ATMOSPHERE")), world_collection)
    mesh = bpy.data.meshes.new(f"{FOG_NAME}_Mesh")
    mesh.from_pydata(
        [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)],
        [],
        [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)],
    )
    mesh.update()
    material = bpy.data.materials.new("CV_Mat_Fog")
    material.use_nodes = True
    material.node_tree.nodes.clear()
    output = material.node_tree.nodes.new("ShaderNodeOutputMaterial")
    volume = material.node_tree.nodes.new("ShaderNodeVolumePrincipled")
    volume.name = "CV Fog Volume"
    material.node_tree.links.new(volume.outputs["Volume"], output.inputs["Volume"])
    mesh.materials.append(material)
    obj = bpy.data.objects.new(FOG_NAME, mesh)
    obj.scale = (9.0, 7.0, 4.0)
    obj.location = (0.0, 0.0, 3.0)
    obj.display_type = "WIRE"
    holder.objects.link(obj)
    obj["cv_managed"] = True
    obj["cv_demo"] = True
    obj["cv_locked"] = False
    obj["cv_weather"] = "FOG"
    obj["cv_world_root"] = world_collection.name
    return obj


def _apply_fog(world: bpy.types.World, world_collection, density: float) -> None:
    output = world.node_tree.nodes.get("World Output") if world.node_tree else None
    if output is not None:  # older worlds had an infinite fog volume that blacked out the sky
        for link in list(output.inputs["Volume"].links):
            world.node_tree.links.remove(link)
    if world_collection is None or not world_collection.get("cv_managed"):
        return
    fog = _ensure_fog_volume(world_collection)
    fog.hide_viewport = fog.hide_render = density <= 0.0
    for material in fog.data.materials:
        node = material.node_tree.nodes.get("CV Fog Volume") if material and material.node_tree else None
        if node is not None:
            node.inputs["Density"].default_value = density
    fog["cv_fog_density"] = density


def _ensure_cloud_nodes(scene: bpy.types.Scene, world: bpy.types.World, background) -> None:
    """Insert (once) a procedural cloud layer between the stars and both Background nodes."""
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    if nodes.get("CV Sky Cloud Mix") is not None or nodes.get("CV Sky Stars") is None:
        return
    separate = nodes["CV Sky Separate"]
    coord = nodes["CV Sky Coord"]
    # Project the view direction onto a flat cloud deck overhead so clouds shrink toward the horizon.
    floor = nodes.new("ShaderNodeMath")
    floor.name = "CV Sky Cloud Floor"
    floor.operation = "MAXIMUM"
    floor.inputs[1].default_value = 0.08
    divide_x = nodes.new("ShaderNodeMath")
    divide_x.name = "CV Sky Cloud X"
    divide_x.operation = "DIVIDE"
    divide_y = nodes.new("ShaderNodeMath")
    divide_y.name = "CV Sky Cloud Y"
    divide_y.operation = "DIVIDE"
    deck = nodes.new("ShaderNodeCombineXYZ")
    deck.name = "CV Sky Cloud Deck"
    drift = nodes.new("ShaderNodeMapping")
    drift.name = "CV Sky Cloud Map"
    noise = nodes.new("ShaderNodeTexNoise")
    noise.name = "CV Sky Cloud Noise"
    noise.noise_dimensions = "3D"
    noise.inputs["Scale"].default_value = 1.7
    noise.inputs["Detail"].default_value = 6.0
    noise.inputs["Roughness"].default_value = 0.55
    shape = nodes.new("ShaderNodeMapRange")
    shape.name = "CV Sky Cloud Mask"
    shape.inputs["From Min"].default_value = 0.8
    shape.inputs["From Max"].default_value = 1.05
    horizon = nodes.new("ShaderNodeMapRange")
    horizon.name = "CV Sky Cloud Horizon"
    horizon.inputs["From Min"].default_value = 0.0
    horizon.inputs["From Max"].default_value = 0.3
    fade = nodes.new("ShaderNodeMath")
    fade.name = "CV Sky Cloud Fade"
    fade.operation = "MULTIPLY"
    cloud_mix = nodes.new("ShaderNodeMix")
    cloud_mix.name = "CV Sky Cloud Mix"
    cloud_mix.data_type = "RGBA"
    links.new(separate.outputs["Z"], floor.inputs[0])
    links.new(separate.outputs["X"], divide_x.inputs[0])
    links.new(floor.outputs["Value"], divide_x.inputs[1])
    links.new(separate.outputs["Y"], divide_y.inputs[0])
    links.new(floor.outputs["Value"], divide_y.inputs[1])
    links.new(divide_x.outputs["Value"], deck.inputs["X"])
    links.new(divide_y.outputs["Value"], deck.inputs["Y"])
    links.new(deck.outputs["Vector"], drift.inputs["Vector"])
    links.new(drift.outputs["Vector"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], shape.inputs["Value"])
    links.new(separate.outputs["Z"], horizon.inputs["Value"])
    links.new(shape.outputs["Result"], fade.inputs[0])
    links.new(horizon.outputs["Result"], fade.inputs[1])
    links.new(fade.outputs["Value"], cloud_mix.inputs[0])
    stars = nodes["CV Sky Stars"]
    links.new(stars.outputs[2], cloud_mix.inputs[6])
    links.new(cloud_mix.outputs[2], background.inputs["Color"])
    seen = nodes.get("CV Sky Camera")
    if seen is not None:
        links.new(cloud_mix.outputs[2], seen.inputs["Color"])
    # The deck drifts with time, faster in wind; a simple-expression driver, so no Python runs.
    from .life import add_driver

    add_driver(
        world.node_tree,
        'nodes["CV Sky Cloud Map"].inputs["Location"].default_value',
        0,
        "frame*0.0025*(1+w/40)",
        (("w", "SCENE", scene, "cozyverse.wind_amount"),),
    )


def _apply_sky(scene: bpy.types.Scene, world: bpy.types.World, background, settings) -> None:
    sky = _ensure_sky_nodes(world, background)
    _ensure_cloud_nodes(scene, world, background)
    horizon, zenith = sky_colors(settings.time_hour, settings.warmth)
    sky["gradient"].inputs[6].default_value = (*horizon, 1.0)
    sky["gradient"].inputs[7].default_value = (*zenith, 1.0)
    sky["visible"].inputs[1].default_value = star_visibility(settings.time_hour, settings.stars_amount, settings.weather, settings.fog_amount)
    nodes = world.node_tree.nodes
    mask = nodes.get("CV Sky Cloud Mask")
    if mask is not None:
        cover = cloud_cover(settings.clouds_amount, settings.weather) / 100.0
        threshold = 0.78 - 0.62 * cover
        mask.inputs["From Min"].default_value = threshold
        mask.inputs["From Max"].default_value = threshold + 0.17
        nodes["CV Sky Cloud Mix"].inputs[7].default_value = (*cloud_color(settings.time_hour, settings.warmth), 1.0)


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
        _apply_sky(scene, world, background, settings)
        changed = True

    if world.node_tree is not None:
        density = settings.fog_amount / 100.0 * 0.30 if settings.weather == "FOG" or settings.fog_amount > 0.0 else 0.0
        _apply_fog(world, world_collection, density)

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
            settings.clouds_amount,
        )
        world_collection["cv_atmosphere_schema"] = "3.0"
        world_collection["cv_atmosphere_preset"] = settings.atmosphere_preset
        world_collection["cv_atmosphere_values"] = serialize_preset(values)

    return changed

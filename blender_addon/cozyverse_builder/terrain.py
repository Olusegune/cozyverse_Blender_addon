"""Blender side of terrain and water: a sculpted slab, glassy water bodies, and animated waves.

The land is one heightfield mesh (a slab with side walls, like a diorama cut from the ground), so
lakes, rivers, shores and hills are real geometry. Water is a separate prism whose top sits just
below the land, and its surface is a shader whose waves move with the timeline.
"""

from __future__ import annotations

import bpy

from .core import terrain_spec as spec
from .life import add_driver

GRID = (84, 64)
WATER_COLOR = (0.07, 0.38, 0.52, 1.0)
ICE_COLOR = (0.80, 0.91, 0.97, 1.0)


def _principled(material: bpy.types.Material):
    return next((n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)


def create_terrain_material(palette) -> bpy.types.Material:
    """Sand by the water, the style's earth on flat ground, grass on hills and rock on steep faces."""
    earth, _shop, _roof, _trim, leaf = palette
    material = bpy.data.materials.new("CV_Mat_Terrain")
    material.diffuse_color = earth
    material.roughness = 0.85
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    bsdf = _principled(material)
    geometry = nodes.new("ShaderNodeNewGeometry")
    separate = nodes.new("ShaderNodeSeparateXYZ")
    height = nodes.new("ShaderNodeMapRange")
    height.inputs["From Min"].default_value, height.inputs["From Max"].default_value = -0.7, 2.0
    ramp = nodes.new("ShaderNodeValToRGB")
    elements = ramp.color_ramp.elements
    sand_dark, sand = (0.46, 0.38, 0.24, 1.0), (0.78, 0.68, 0.46, 1.0)
    grass = (leaf[0] * 1.15 + 0.02, leaf[1] * 1.15 + 0.04, leaf[2] * 1.1 + 0.01, 1.0)
    stops = (
        (-0.62, sand_dark), (-0.10, sand), (-0.02, sand), (0.0, earth), (0.07, earth),
        (0.40, grass), (1.10, (grass[0] * 0.7, grass[1] * 0.75, grass[2] * 0.7, 1.0)), (1.60, (0.46, 0.43, 0.40, 1.0)),
    )
    elements[0].position, elements[0].color = (stops[0][0] + 0.7) / 2.7, stops[0][1]
    elements[1].position, elements[1].color = (stops[1][0] + 0.7) / 2.7, stops[1][1]
    for z, color in stops[2:]:
        element = elements.new((z + 0.7) / 2.7)
        element.color = color
    slope = nodes.new("ShaderNodeMapRange")
    slope.inputs["From Min"].default_value, slope.inputs["From Max"].default_value = 0.55, 0.80
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs[6].default_value = (0.40, 0.37, 0.34, 1.0)  # rock on steep faces and the cut sides
    links.new(geometry.outputs["Position"], separate.inputs["Vector"])
    links.new(separate.outputs["Z"], height.inputs["Value"])
    links.new(height.outputs["Result"], ramp.inputs["Fac"])
    links.new(geometry.outputs["Normal"], nodes.new("ShaderNodeSeparateXYZ").inputs["Vector"])
    normal_z = [n for n in nodes if n.bl_idname == "ShaderNodeSeparateXYZ"][-1]
    links.new(normal_z.outputs["Z"], slope.inputs["Value"])
    links.new(slope.outputs["Result"], mix.inputs[0])
    links.new(ramp.outputs["Color"], mix.inputs[7])
    links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    return material


def create_water_material(scene: bpy.types.Scene) -> bpy.types.Material:
    material = bpy.data.materials.new("CV_Mat_Water")
    material.diffuse_color = (*WATER_COLOR[:3], 0.7)
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    bsdf = _principled(material)
    bsdf.inputs["Base Color"].default_value = WATER_COLOR
    bsdf.inputs["Roughness"].default_value = 0.05
    bsdf.inputs["Alpha"].default_value = 0.78
    bsdf.inputs["IOR"].default_value = 1.33
    for attribute, value in (("surface_render_method", "BLENDED"), ("use_backface_culling", False)):
        try:
            setattr(material, attribute, value)
        except (AttributeError, TypeError):
            pass
    coordinates = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.name = "CV Water Noise"
    noise.noise_dimensions = "4D"
    noise.inputs["Scale"].default_value = 5.0
    noise.inputs["Detail"].default_value = 3.0
    noise.inputs["Roughness"].default_value = 0.5
    bump = nodes.new("ShaderNodeBump")
    bump.name = "CV Water Bump"
    bump.inputs["Strength"].default_value = 0.2
    bump.inputs["Distance"].default_value = 0.04
    links.new(coordinates.outputs["Object"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    # The ripples travel with the timeline, faster in wind and with the Waves slider.
    add_driver(
        material.node_tree,
        'nodes["CV Water Noise"].inputs["W"].default_value',
        -1,
        "frame*0.025*(1+w/50)*(1+s/100)",
        (("w", "SCENE", scene, "cozyverse.wind_amount"), ("s", "SCENE", scene, "cozyverse.water_waves")),
    )
    return material


def sync_water(material: bpy.types.Material, season: str, rain: float, waves: float) -> None:
    """Ice in winter, choppier water in rain and wind. Called whenever the atmosphere changes."""
    bsdf = _principled(material)
    bump = material.node_tree.nodes.get("CV Water Bump")
    noise = material.node_tree.nodes.get("CV Water Noise")
    if bsdf is None:
        return
    frozen = season == "WINTER"
    color = ICE_COLOR if frozen else WATER_COLOR
    material.diffuse_color = (*color[:3], 0.9 if frozen else 0.7)
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = 0.2 if frozen else 0.05
    bsdf.inputs["Alpha"].default_value = 0.96 if frozen else 0.78
    if bump is not None:
        bump.inputs["Strength"].default_value = 0.02 if frozen else 0.06 + 0.30 * waves / 100.0 + 0.25 * rain / 100.0
    if noise is not None:
        noise.inputs["Scale"].default_value = 5.0 + rain * 0.06


def build_terrain(collection, stage, terrain: str, zone, hills, seed: int, material) -> bpy.types.Object:
    """The land: a heightfield slab (top surface, cut sides and a flat bottom) as one editable mesh."""
    nx, ny = GRID
    heights = spec.height_grid(nx, ny, stage, terrain, zone, hills, seed)
    row = nx + 1
    vertices = [(-stage.half_x + stage.half_x * 2 * i / nx, -stage.half_y + stage.half_y * 2 * j / ny, heights[j][i]) for j in range(ny + 1) for i in range(row)]
    faces = [(j * row + i, j * row + i + 1, (j + 1) * row + i + 1, (j + 1) * row + i) for j in range(ny) for i in range(nx)]
    top_count = len(faces)
    ring = [(i, 0) for i in range(nx)] + [(nx, j) for j in range(ny)] + [(i, ny) for i in range(nx, 0, -1)] + [(0, j) for j in range(ny, 0, -1)]
    top_ring = [j * row + i for i, j in ring]
    base = len(vertices)
    vertices.extend((vertices[index][0], vertices[index][1], spec.BOTTOM) for index in top_ring)
    count = len(ring)
    for step in range(count):
        following = (step + 1) % count
        faces.append((top_ring[step], base + step, base + following, top_ring[following]))
    faces.append(tuple(base + step for step in reversed(range(count))))
    mesh = bpy.data.meshes.new("CV_Diorama_Base_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    for index, polygon in enumerate(mesh.polygons):
        polygon.use_smooth = index < top_count
    mesh.materials.append(material)
    obj = bpy.data.objects.new("CV_Diorama_Base", mesh)
    collection.objects.link(obj)
    bevel = obj.modifiers.new("CV Soft Edges", "BEVEL")
    bevel.width = 0.12
    bevel.segments = 2
    obj["cv_terrain"] = True
    return obj


def build_water(collection, zone, stage, material) -> bpy.types.Object:
    """A prism of water: its top just under the flat land, its bottom below the deepest basin."""
    outline = spec.water_outline(zone, stage)
    bottom = spec.SEABED + 0.05 if zone["kind"] == "SEA" else spec.BOTTOM + 0.12
    count = len(outline)
    vertices = [(x, y, spec.WATER_LEVEL) for x, y in outline] + [(x, y, bottom) for x, y in outline]
    faces = [tuple(range(count)), tuple(reversed(range(count, count * 2)))]
    faces.extend((step, (step + 1) % count, count + (step + 1) % count, count + step) for step in range(count))
    mesh = bpy.data.meshes.new("CV_Water_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.materials.append(material)
    obj = bpy.data.objects.new("CV_Water", mesh)
    collection.objects.link(obj)
    obj["cv_water"] = zone["kind"]
    return obj

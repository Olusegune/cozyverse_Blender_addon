"""Shader helpers: CozyVerse materials carry real nodes so renders match the viewport."""

from __future__ import annotations

import bpy


def _principled(material: bpy.types.Material):
    if material.node_tree is None:
        return None
    return next((node for node in material.node_tree.nodes if node.bl_idname == "ShaderNodeBsdfPrincipled"), None)


def _set_input(node, name: str, value) -> None:
    socket = node.inputs.get(name)
    if socket is not None:
        socket.default_value = value


def create_material(
    name: str,
    color: tuple[float, float, float, float],
    metallic: float = 0.0,
    roughness: float = 0.72,
    emissive: bool = False,
) -> bpy.types.Material:
    """Create a world-owned material with matching viewport color and Principled shader."""
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    material.metallic = metallic
    material.roughness = roughness
    material.use_nodes = True
    bsdf = _principled(material)
    if bsdf is not None:
        _set_input(bsdf, "Base Color", color)
        _set_input(bsdf, "Metallic", metallic)
        _set_input(bsdf, "Roughness", roughness)
        if emissive:
            material["cv_emissive"] = True
            _set_input(bsdf, "Emission Color", color)
            _set_input(bsdf, "Emission Strength", 0.0)
    return material


def sync_color(material: bpy.types.Material, color: tuple[float, float, float, float]) -> None:
    material.diffuse_color = color
    bsdf = _principled(material)
    if bsdf is not None:
        _set_input(bsdf, "Base Color", color)


def sync_roughness(material: bpy.types.Material, roughness: float) -> None:
    material.roughness = roughness
    bsdf = _principled(material)
    if bsdf is not None:
        _set_input(bsdf, "Roughness", roughness)


def sync_glow(material: bpy.types.Material, strength: float, color: tuple[float, float, float]) -> None:
    """Drive emissive windows from the practical-light settings."""
    bsdf = _principled(material)
    if bsdf is None:
        return
    _set_input(bsdf, "Emission Color", (*color, 1.0))
    _set_input(bsdf, "Emission Strength", strength)

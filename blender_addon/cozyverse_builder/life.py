"""Ambient life: foliage that sways with the wind and lamps that flicker, as native drivers.

Everything here is a Blender "simple expression" driver (no Python is ever evaluated), so it
renders, scrubs and survives save/reopen without the add-on. Sway uses the delta transforms so it
stacks on top of Story keyframes and never counts as a hand edit; amplitude is read live from the
scene's CozyVerse settings, so the sliders need no rebuild.
"""

from __future__ import annotations

import zlib

import bpy

SWAY_AXES = (("delta_rotation_euler", 0), ("delta_rotation_euler", 1), ("delta_location", 0), ("delta_location", 1))


def _phase(name: str) -> float:
    return (zlib.crc32(name.encode("utf-8")) % 6283) / 1000.0


def add_driver(owner, path: str, index: int, expression: str, variables) -> bpy.types.FCurve:
    """Add a simple-expression driver. ``variables`` is (name, id_type, id, data_path) tuples."""
    fcurve = owner.driver_add(path, index) if index >= 0 else owner.driver_add(path)
    driver = fcurve.driver
    driver.type = "SCRIPTED"
    driver.expression = expression
    for name, id_type, target_id, data_path in variables:
        variable = driver.variables.new()
        variable.name = name
        variable.type = "SINGLE_PROP"
        target = variable.targets[0]
        target.id_type = id_type
        target.id = target_id
        target.data_path = data_path
    for modifier in list(fcurve.modifiers):
        fcurve.modifiers.remove(modifier)
    return fcurve


def _remove_driver(owner, path: str, index: int = -1) -> None:
    try:
        owner.driver_remove(path, index)
    except (TypeError, RuntimeError):
        pass


def _is_foliage(obj: bpy.types.Object) -> bool:
    return obj.type == "MESH" and (obj.name.endswith("_Leaves") or obj.name.startswith("CV_Alien_Plant"))


def clear_life(world: bpy.types.Collection) -> int:
    """Remove ambient drivers from one world and restore its delta transforms. Returns objects cleared."""
    cleared = 0
    for obj in world.all_objects:
        if obj.get("cv_life"):
            for path, index in SWAY_AXES:
                _remove_driver(obj, path, index)
            obj.delta_rotation_euler = (0.0, 0.0, obj.delta_rotation_euler[2])
            obj.delta_location = (0.0, 0.0, obj.delta_location[2])
            del obj["cv_life"]
            cleared += 1
        data = obj.data if obj.type == "LIGHT" else None
        if data is not None and data.get("cv_life_light"):
            _remove_driver(data, "energy")
            data.energy = float(data.get("cv_base_energy", data.energy))
            del data["cv_life_light"]
            cleared += 1
    return cleared


def apply_life(scene: bpy.types.Scene, world: bpy.types.Collection) -> tuple[int, int]:
    """(Re)build the sway and flicker drivers for one world. Returns (foliage, lamps)."""
    clear_life(world)
    foliage = lamps = 0
    sway_amp = "(0.012+0.05*s/100+0.07*w/100)"
    speed = "(1+w/150)"
    for obj in world.all_objects:
        if _is_foliage(obj):
            phase = _phase(obj.name)
            variables = (("s", "SCENE", scene, "cozyverse.life_sway"), ("w", "SCENE", scene, "cozyverse.wind_amount"))
            add_driver(obj, "delta_rotation_euler", 0, f"{sway_amp}*sin(frame*0.13*{speed}+{phase:.3f})", variables)
            add_driver(obj, "delta_rotation_euler", 1, f"{sway_amp}*0.8*sin(frame*0.10*{speed}+{phase * 1.7:.3f}+1)", variables)
            add_driver(obj, "delta_location", 0, f"{sway_amp}*0.35*sin(frame*0.13*{speed}+{phase:.3f}+0.6)", variables)
            add_driver(obj, "delta_location", 1, f"{sway_amp}*0.25*sin(frame*0.10*{speed}+{phase * 1.7:.3f}+1.4)", variables)
            obj["cv_life"] = True
            foliage += 1
        elif obj.type == "LIGHT" and obj.name.startswith("CV_Interior_"):
            light = obj.data
            if "cv_base_energy" not in light:
                light["cv_base_energy"] = float(light.energy)
            phase = _phase(obj.name)
            wobble = f"(0.5*sin(frame*0.83+{phase:.3f})+0.3*sin(frame*2.1+{phase * 2.3:.3f})+0.2*sin(frame*5.3+{phase * 0.7:.3f}))"
            add_driver(
                light,
                "energy",
                -1,
                f"b*(1+f/100*0.45*{wobble})",
                (("b", "LIGHT", light, '["cv_base_energy"]'), ("f", "SCENE", scene, "cozyverse.life_flicker")),
            )
            light["cv_life_light"] = True
            lamps += 1
    return foliage, lamps

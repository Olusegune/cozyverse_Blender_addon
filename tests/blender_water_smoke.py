"""Blender background acceptance test for terrain and water: lakes, rivers, seas, hills."""

from __future__ import annotations

import importlib
import json
import pathlib
import re
import sys

import bpy


repo_root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "blender_addon"))
addon = importlib.import_module("cozyverse_builder")
addon.register()
from cozyverse_builder.core import terrain_spec as terrain  # noqa: E402


def evaluated(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    return obj.evaluated_get(depsgraph)


def conjure(prompt: str):
    settings.prompt = prompt
    assert bpy.ops.cozyverse.conjure() == {"FINISHED"}, prompt
    return bpy.data.collections[settings.active_world_name]


def landscape(world):
    plan = json.loads(world["cv_scene_plan"])
    seed = int(world["cv_layout_seed"]) & 0xFFFFFFFF
    stage = terrain.stage_for(plan["water"])
    zone = terrain.build_zone(plan["water"], seed, stage)
    hills = terrain.hills_for(seed, stage, plan["water"]) if plan["terrain"] == "HILLS" else []
    return plan, stage, zone, hills, seed


PART_SUFFIXES = ("_Roof", "_Dome", "_Antenna", "_Awning", "_Lantern", "_Beacon")


def buildings(world):
    """The main body of each building: everything in the architecture collection that is not a part."""
    holder = next(c for c in world.children if c.name.startswith("CV_ARCHITECTURE"))
    stripped = lambda o: re.sub(r"\.\d+$", "", o.name)  # noqa: E731  Blender adds .001 to repeated names
    return [o for o in holder.objects if o.type == "MESH" and not stripped(o).endswith(PART_SUFFIXES) and "_Window" not in o.name]


def water_material(world):
    water = next(o for o in world.all_objects if o.name.startswith("CV_Water"))
    return water, water.data.materials[0]


def bump_strength(material):
    return material.node_tree.nodes["CV Water Bump"].inputs["Strength"].default_value


try:
    scene = bpy.context.scene
    settings = scene.cozyverse

    # A dry, flat world is untouched: no terrain mesh, no water.
    flat = conjure("A sunny market square")
    assert flat["cv_water"] == "NONE" and flat["cv_terrain"] == "FLAT"
    assert not [o for o in flat.all_objects if o.name.startswith("CV_Water")]
    assert not flat.all_objects["CV_Diorama_Base"].get("cv_terrain") if "CV_Diorama_Base" in flat.all_objects else True

    # ---- the four kinds of water, read from the description ----------------------
    expected = {
        "a cozy village beside a quiet lake with tall trees": "LAKE",
        "a tiny town on a river with a market": "RIVER",
        "a harbor village on a little island in the sea": "SEA",
        "a village garden with a koi pond": "POND",
    }
    for prompt, kind in expected.items():
        world = conjure(prompt)
        plan, stage, zone, hills, seed = landscape(world)
        assert world["cv_water"] == kind and plan["water"] == kind, prompt
        base = world.all_objects["CV_Diorama_Base"] if "CV_Diorama_Base" in world.all_objects else next(o for o in world.all_objects if o.name.startswith("CV_Diorama_Base"))
        assert base.get("cv_terrain") and len(base.data.vertices) > 5000
        # The land really dips under the water and the water sits in the dip.
        top = max(v.co.z for v in base.data.vertices)
        bottom = min(v.co.z for v in base.data.vertices)
        assert top <= 0.01 and abs(bottom - terrain.BOTTOM) < 1e-5
        assert min(v.co.z for v in base.data.vertices if v.co.z > terrain.BOTTOM + 0.01) < terrain.WATER_LEVEL - 0.2
        water, material = water_material(world)
        assert water["cv_water"] == kind and abs(max(v.co.z for v in water.data.vertices) - terrain.WATER_LEVEL) < 1e-6
        # Everything built stands on level, dry ground; nothing floats over water.
        for obj in buildings(world):
            assert terrain.is_buildable(obj.location.x, obj.location.y, 0.3, plan["terrain"], zone, hills, seed), (prompt, obj.name, tuple(obj.location))
        for obj in world.all_objects:
            if obj.name.endswith("_Leaves"):
                assert terrain.is_dry(obj.location.x, obj.location.y, 0.0, plan["terrain"], zone, hills, seed), (prompt, obj.name)

    # ---- the island: a sea slab that is bigger than the usual stage ------------------
    sea = conjure("a harbor village on a little island in the sea")
    road = next(o for o in sea.all_objects if o.name.startswith("CV_Road"))
    assert road.scale.x == 3.5  # the road shrinks to fit the island
    assert len([b for b in buildings(sea)]) >= 2  # a village, not a lone hut
    assert bpy.ops.cozyverse.railway_add() == {"CANCELLED"}  # a train needs solid ground
    assert bpy.ops.cozyverse.traffic_add() == {"FINISHED"}
    assert bpy.ops.cozyverse.traffic_remove() == {"FINISHED"}
    assert scene.camera.data.ortho_scale > 15.0

    # ---- hills carry trees and the village stays level ---------------------------------
    hilly = conjure("a mountain village in the hills")
    plan, stage, zone, hills, seed = landscape(hilly)
    assert plan["terrain"] == "HILLS" and any(abs(h[2]) > 0.5 for h in hills)
    base = next(o for o in hilly.all_objects if o.name.startswith("CV_Diorama_Base"))
    assert max(v.co.z for v in base.data.vertices) > 0.5
    assert buildings(hilly) and all(terrain.is_buildable(o.location.x, o.location.y, 0.3, "HILLS", zone, hills, seed) for o in buildings(hilly))  # level ground only
    crowns = [o.location.z for o in hilly.all_objects if re.sub(r"\.\d+$", "", o.name).endswith("_Leaves")]
    assert crowns and max(crowns) > 1.5, "some trees should climb the hills (flat-ground crowns top out near 1.4)"

    # ---- you can override what the description says ---------------------------------------
    settings.water_choice, settings.terrain_choice = "LAKE", "HILLS"
    overridden = conjure("a sunny market square")
    assert overridden["cv_water"] == "LAKE" and overridden["cv_terrain"] == "HILLS"
    settings.water_choice = "NONE"
    assert conjure("a lake side cafe")["cv_water"] == "NONE"
    settings.water_choice, settings.terrain_choice = "AUTO", "AUTO"

    # The review step shows the same choices, and editing them invalidates the preview.
    settings.prompt = "a village by a lake"
    assert bpy.ops.cozyverse.prepare_scene_plan() == {"FINISHED"}
    assert settings.plan_water == "LAKE" and settings.plan_terrain == "FLAT"
    settings.plan_approved = True
    settings.plan_water = "RIVER"
    settings.plan_approved = True
    assert bpy.ops.cozyverse.build_approved_plan() == {"CANCELLED"}  # the plan changed after it was previewed
    assert bpy.ops.cozyverse.cancel_revision() == {"FINISHED"}

    # ---- the water moves, reacts to weather and freezes in winter --------------------------
    lake = conjure("a cozy village beside a quiet lake")
    water, material = water_material(lake)
    assert all(d.driver.is_simple_expression and d.driver.is_valid for d in material.node_tree.animation_data.drivers)
    settings.wind_amount = 0.0
    scene.frame_set(1)
    early = evaluated(material).node_tree.nodes["CV Water Noise"].inputs["W"].default_value
    scene.frame_set(120)
    assert evaluated(material).node_tree.nodes["CV Water Noise"].inputs["W"].default_value > early + 1.0  # the ripples drift
    scene.frame_set(1)
    settings.weather, settings.season, settings.water_waves = "CLEAR", "SUMMER", 0.0
    calm = bump_strength(material)
    settings.water_waves = 100.0
    assert bump_strength(material) > calm + 0.2
    settings.water_waves = 0.0
    settings.weather, settings.rain_amount = "RAIN", 80.0
    assert bump_strength(material) > calm + 0.1  # rain stirs the surface
    settings.weather = "CLEAR"
    settings.season = "WINTER"
    assert material.diffuse_color[0] > 0.7  # pale ice
    assert bump_strength(material) < 0.05  # ice is still
    settings.season = "SUMMER"
    assert material.diffuse_color[0] < 0.2

    # ---- it plays well with the rest of the add-on --------------------------------------------
    assert bpy.ops.cozyverse.inspect_manual_edits() == {"FINISHED"} and "0 changed" in settings.status
    settings.buildup_seconds = 2.0
    assert bpy.ops.cozyverse.buildup_add() == {"FINISHED"}
    controller = next(o for o in lake.objects if o.get("cv_buildup_controller"))
    finish = int(controller["cv_finish_frame"])
    scene.frame_set(1)
    assert max(evaluated(water).delta_scale) < 0.05  # the water builds up with the stage
    scene.frame_set(finish)
    assert min(evaluated(water).delta_scale) > 0.99
    assert bpy.ops.cozyverse.buildup_remove() == {"FINISHED"}

    # ---- save and reopen -------------------------------------------------------------------------
    path = repo_root / "work" / "cozyverse_water_smoke.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    bpy.ops.wm.open_mainfile(filepath=str(path))
    scene = bpy.context.scene
    reopened = bpy.data.collections[scene.cozyverse.active_world_name]
    assert reopened["cv_water"] == "LAKE"
    water, material = water_material(reopened)
    assert all(d.driver.is_simple_expression and d.driver.is_valid for d in material.node_tree.animation_data.drivers)
finally:
    addon.unregister()
print("COZYVERSE_WATER_SMOKE_OK")

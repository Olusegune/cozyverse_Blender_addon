"""Blender background acceptance test for the Library: indexing, persistence, auto-fit, car slot."""

from __future__ import annotations

import importlib
import os
import pathlib
import shutil
import sys

import bpy
from mathutils import Vector


repo_root = pathlib.Path(__file__).resolve().parents[1]
work = repo_root / "work" / "library_smoke"
shutil.rmtree(work, ignore_errors=True)
(work / "cars").mkdir(parents=True)
(work / "misc").mkdir(parents=True)
os.environ["COZYVERSE_LIBRARY_PATH"] = str(work / "store" / "library.json")
sys.path.insert(0, str(repo_root / "blender_addon"))
addon = importlib.import_module("cozyverse_builder")
addon.register()
from cozyverse_builder import library  # noqa: E402


def box(name, size, center, color=(0.8, 0.1, 0.1, 1.0)):
    half = [v / 2 for v in size]
    corners = [(sx * half[0], sy * half[1], sz * half[2]) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(corners, [], [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    mesh.update()
    material = bpy.data.materials.new(f"{name}_mat")
    material.use_nodes = True
    next(n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled").inputs["Base Color"].default_value = color
    mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    obj.location = center
    return obj


def write_blend(path, collection):
    bpy.data.libraries.write(str(path), {collection}, fake_user=True)


# A 4.2 m sedan facing -Y, floating and off-centre, with a "Front" marker at its -Y end.
sedan = bpy.data.collections.new("Sedan")
sedan.objects.link(box("Body", (1.8, 4.2, 1.2), (10.0, 5.0, 3.6)))
sedan.objects.link(box("Front", (0.4, 0.2, 0.2), (10.0, 5.0 - 2.0, 3.6), (1, 1, 0, 1)))
sedan.asset_mark()
write_blend(work / "cars" / "blue_sedan.blend", sedan)
house = bpy.data.collections.new("House")
house.objects.link(box("Walls", (6.0, 5.0, 4.0), (0.0, 0.0, 2.0), (0.7, 0.6, 0.5, 1)))
write_blend(work / "misc" / "old_stone_cottage.blend", house)  # not asset-marked: a whole-file entry
lamp_obj = box("Lamp", (0.3, 0.3, 3.0), (0, 0, 1.5), (0.9, 0.9, 0.6, 1))
bpy.context.scene.collection.objects.link(lamp_obj)
bpy.ops.object.select_all(action="DESELECT")
lamp_obj.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(work / "misc" / "street_lamp.glb"), use_selection=True)
bpy.data.objects.remove(lamp_obj)
crate = box("Crate", (1.0, 1.0, 1.0), (0, 0, 0.5))
bpy.context.scene.collection.objects.link(crate)
bpy.ops.object.select_all(action="DESELECT")
crate.select_set(True)
bpy.ops.wm.obj_export(filepath=str(work / "misc" / "wooden_crate.obj"), export_selected_objects=True)
bpy.data.objects.remove(crate)


def world_bounds(root):
    bpy.context.view_layer.update()
    points = [obj.matrix_world @ Vector(c) for obj in [root, *root.children_recursive] if obj.type == "MESH" for c in obj.bound_box]
    return Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points))), Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))


try:
    scene = bpy.context.scene
    settings = scene.cozyverse
    assert bpy.ops.cozyverse.library_place() == {"CANCELLED"}  # nothing selected yet

    # ---- adding folders and indexing ---------------------------------------
    assert bpy.ops.cozyverse.library_add_folder(directory=str(work / "nope")) == {"CANCELLED"}
    assert bpy.ops.cozyverse.library_add_folder(directory=str(work), label="Test pack") == {"FINISHED"}
    assert bpy.ops.cozyverse.library_add_folder(directory=str(work)) == {"CANCELLED"}  # no duplicates
    records = {r["name"]: r for r in library.effective_records()}
    assert set(records) == {"Sedan", "old stone cottage", "street lamp", "wooden crate"}, set(records)
    assert records["Sedan"]["role"] == "CAR" and records["Sedan"]["inner"] == "Collection:Sedan"
    assert records["old stone cottage"]["inner"] == "" and records["old stone cottage"]["role"] == "BUILDING"
    assert records["street lamp"]["role"] == "LAMP" and records["wooden crate"]["role"] == "PROP"
    assert all(isinstance(library.thumbnail_id(r), int) for r in records.values())  # icon ids exist only with a UI

    # ---- browsing ---------------------------------------------------------
    settings.library_query = "lamp"
    page, number, total, matches = library.view(settings)
    assert [r["name"] for r in page] == ["street lamp"] and matches == 1
    settings.library_query = ""
    settings.library_role = "CAR"
    assert [r["name"] for r in library.view(settings)[0]] == ["Sedan"]
    settings.library_role = "ALL"
    assert library.view(settings)[3] == 4

    # ---- choices persist between sessions --------------------------------------
    sedan_key = records["Sedan"]["key"]
    assert bpy.ops.cozyverse.library_select(key=sedan_key) == {"FINISHED"}
    assert settings.library_edit_role == "CAR" and settings.library_edit_license == "UNKNOWN"
    settings.library_edit_license = "EDITORIAL"
    settings.library_edit_forward = "-Y"
    library.reset_state()  # forget everything in memory; the file is the truth
    reloaded = library.record_for(sedan_key)
    assert reloaded["license"] == "EDITORIAL" and reloaded["forward"] == "-Y" and len(library.state()["index"]) == 4
    source_id = library.state()["sources"][0]["id"]
    assert bpy.ops.cozyverse.library_source_license(source=source_id, license="OWNED") == {"FINISHED"}
    assert library.record_for(records["street lamp"]["key"])["license"] == "OWNED"  # inherited from the folder
    assert library.record_for(sedan_key)["license"] == "EDITORIAL"  # a model's own choice wins

    # ---- placing: grounded, sized for its role, front on +X ----------------------
    assert bpy.ops.cozyverse.library_place() == {"FINISHED"}
    wrapper = bpy.data.objects[next(o.name for o in bpy.data.objects if o.name.startswith("CV_Asset_Sedan"))]
    low, high = world_bounds(wrapper)
    assert abs((high.x - low.x) - 0.9) < 0.01, (low, high)  # 4.2 m long becomes 0.9 along X
    assert abs(low.z) < 0.01 and abs((low.x + high.x) / 2) < 0.01 and abs((low.y + high.y) / 2) < 0.01
    marker = next(o for o in wrapper.children_recursive if o.name.startswith("Front"))
    assert marker.matrix_world.translation.x > (low.x + high.x) / 2 + 0.3  # the front faces +X
    assert wrapper["cv_license"] == "EDITORIAL" and all(o["cv_managed"] for o in wrapper.children_recursive)

    settings.library_edit_stylize = True
    assert bpy.ops.cozyverse.library_place() == {"FINISHED"}
    styled = [o for o in bpy.data.objects if o.name.startswith("Body") and o.get("cv_asset_source")]
    assert any(s.material and s.material.name.startswith("CV_Mat_Lib") for o in styled for s in o.material_slots)

    assert bpy.ops.cozyverse.library_select(key=records["street lamp"]["key"]) == {"FINISHED"}
    assert bpy.ops.cozyverse.library_place() == {"FINISHED"}  # glb, sized by height
    lamp = next(o for o in bpy.data.objects if o.name.startswith("CV_Asset_street lamp"))
    low, high = world_bounds(lamp)
    assert abs((high.z - low.z) - 1.1) < 0.02 and abs(low.z) < 0.02
    assert bpy.ops.cozyverse.library_select(key=records["wooden crate"]["key"]) == {"FINISHED"}
    assert bpy.ops.cozyverse.library_place() == {"FINISHED"}  # obj

    # ---- my car on the road ---------------------------------------------------
    settings.prompt = "A cozy village with a town hall and trees"
    assert bpy.ops.cozyverse.conjure() == {"FINISHED"}
    world = bpy.data.collections[settings.active_world_name]
    assert bpy.ops.cozyverse.library_select(key=sedan_key) == {"FINISHED"}
    settings.library_edit_stylize = False
    assert bpy.ops.cozyverse.library_use_as(role="CAR") == {"FINISHED"}
    assert settings.slot_car_enabled and settings.slot_car_asset == sedan_key
    settings.traffic_cars = 3
    assert bpy.ops.cozyverse.traffic_add() == {"FINISHED"}
    traffic = next(c for c in world.children if c.name.startswith("CV_TRAFFIC"))
    roots = [o for o in traffic.objects if o.name.startswith("CV_Car_") and o.type == "EMPTY"]
    assert len(roots) == 3
    for root in roots:
        wrappers = [c for c in root.children if c.name.startswith("CV_Asset_Sedan")]
        assert len(wrappers) == 1 and not [c for c in root.children if c.name.endswith("_Body")]
        assert wrappers[0].parent is root
    assert not [o for o in traffic.all_objects if o.name.startswith("CV_Car_1_Wheel")]  # no built-in parts
    scene.frame_set(int(roots[0]["cv_period"] / 2 - roots[0]["cv_phase"]))  # mid-trip, fully popped in
    low, high = world_bounds(roots[0])
    assert abs((high.x - low.x) - 0.9) < 0.01 or abs((high.y - low.y) - 0.9) < 0.01  # sized, whichever way it drives
    for fcurve in (f for o in traffic.all_objects if o.animation_data for f in o.animation_data.drivers):
        assert fcurve.driver.is_simple_expression and fcurve.driver.is_valid
    for frame in (1, 50):
        scene.frame_set(frame)
        assert bpy.ops.cozyverse.inspect_manual_edits() == {"FINISHED"} and "0 changed" in settings.status
    assert bpy.ops.cozyverse.render_postcard() == {"FINISHED"}  # editorial asset: a warning, not a failure

    # Clearing the slot swaps the built-in cars straight back in.
    assert bpy.ops.cozyverse.library_clear_slot() == {"FINISHED"}
    traffic = next(c for c in world.children if c.name.startswith("CV_TRAFFIC"))
    assert [o for o in traffic.all_objects if o.name.endswith("_Body")] and not [o for o in traffic.all_objects if o.name.startswith("CV_Asset_Sedan")]

    # A chosen model that has gone missing falls back quietly to the built-in car.
    assert bpy.ops.cozyverse.library_use_as(role="CAR") == {"FINISHED"}
    os.rename(work / "cars" / "blue_sedan.blend", work / "cars" / "moved.blend")
    assert bpy.ops.cozyverse.traffic_add() == {"FINISHED"}
    traffic = next(c for c in world.children if c.name.startswith("CV_TRAFFIC"))
    assert [o for o in traffic.all_objects if o.name.endswith("_Body")]

    # ---- rescan and removal ---------------------------------------------------
    assert bpy.ops.cozyverse.library_rescan() == {"FINISHED"}
    names = {r["name"] for r in library.effective_records()}
    moved = [r for r in library.effective_records() if r["name"] == "Sedan"]
    assert len(moved) == 1 and moved[0]["path"].endswith("moved.blend")  # the renamed file is still found, once
    assert bpy.ops.cozyverse.library_remove_source(source=source_id) == {"FINISHED"}
    assert not [r for r in library.state()["index"] if r["source"] == source_id]
    assert source_id not in {src["id"] for src in library.state()["sources"]}
    assert bpy.ops.cozyverse.library_browser.poll()
finally:
    addon.unregister()
print("COZYVERSE_LIBRARY_SMOKE_OK")

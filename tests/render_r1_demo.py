"""Render clear and rainy R1 demo frames for visual QA."""

from __future__ import annotations

import importlib
import pathlib
import sys

import bpy


repo_root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "blender_addon"))
addon = importlib.import_module("cozyverse_builder")
addon.register()

settings = bpy.context.scene.cozyverse
settings.prompt = "Create a tiny Manila sari-sari store with tropical plants and a warm sunset."
assert bpy.ops.cozyverse.create_local_demo() == {"FINISHED"}

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x = 800
scene.render.resolution_y = 600
scene.render.resolution_percentage = 100
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "MATERIAL"
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True
scene.display.shading.cavity_type = "WORLD"
scene.display.shading.show_specular_highlight = True
scene.render.image_settings.file_format = "PNG"

qa_dir = repo_root / "work" / "r1-visual-qa"
qa_dir.mkdir(parents=True, exist_ok=True)

settings.weather = "CLEAR"
scene.render.filepath = str(qa_dir / "clear-world.png")
bpy.ops.render.render(write_still=True)

settings.weather = "RAIN"
settings.rain_amount = 70.0
scene.render.filepath = str(qa_dir / "rain-world.png")
bpy.ops.render.render(write_still=True)

addon.unregister()
print("COZYVERSE_R1_RENDER_QA_OK")


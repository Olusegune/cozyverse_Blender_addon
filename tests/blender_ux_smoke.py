"""Blender background test for the three-step guided flow (0.18)."""

from __future__ import annotations

import importlib
import pathlib
import sys

import bpy

repo_root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "blender_addon"))
addon = importlib.import_module("cozyverse_builder")
addon.register()
try:
    settings = bpy.context.scene.cozyverse

    # Describe -> Review: nothing is built yet.
    settings.prompt = "A small harbor village at dusk with a lighthouse and fishing boats"
    assert bpy.ops.cozyverse.conjure(review=True) == {"FINISHED"}
    assert settings.workflow_step == "REVIEW" and not settings.plan_approved
    assert not [c for c in bpy.data.collections if c.name.startswith("CV_WORLD")]

    # Steps can be revisited; going to Create with no world is refused politely.
    assert bpy.ops.cozyverse.goto_step(step="DESCRIBE") == {"FINISHED"} and settings.workflow_step == "DESCRIBE"
    assert bpy.ops.cozyverse.goto_step(step="CREATE") == {"CANCELLED"}
    assert bpy.ops.cozyverse.goto_step(step="REVIEW") == {"FINISHED"} and settings.workflow_step == "REVIEW"

    # Review -> Build with one button (no separate approval tick).
    assert bpy.ops.cozyverse.build_reviewed() == {"FINISHED"}
    assert settings.workflow_step == "BUILT"
    assert [c for c in bpy.data.collections if c.name.startswith("CV_WORLD")]
    assert bpy.ops.cozyverse.goto_step(step="CREATE") == {"FINISHED"}

    # Styles are chosen from the gallery.
    assert bpy.ops.cozyverse.set_style(style="GOTHIC") == {"FINISHED"} and settings.preset == "GOTHIC"
    assert bpy.ops.cozyverse.set_style(style="NOPE") == {"CANCELLED"}

    # Prompt Studio: headless it still prepares the text; Done copies it into the prompt.
    assert bpy.ops.cozyverse.prompt_studio() == {"FINISHED"}
    text = settings.prompt_text
    assert text is not None and "harbor village" in text.as_string()
    text.clear()
    text.write("A mossy forest clearing with a tiny glowing cottage\nand a winding stream")
    assert bpy.ops.cozyverse.prompt_studio_done() == {"FINISHED"}
    assert "mossy forest" in settings.prompt and settings.workflow_step == "DESCRIBE"

    # Square previews ship for every gallery image.
    from cozyverse_builder import visual_assets

    for key in visual_assets.FILES:
        square = visual_assets._square_path(key)
        if square is not None:
            assert square.is_file(), key
finally:
    addon.unregister()
print("COZYVERSE_UX_SMOKE_OK")

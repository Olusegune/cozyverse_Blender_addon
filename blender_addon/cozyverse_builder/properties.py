"""CozyVerse settings stored with the Blender scene."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, PointerProperty, StringProperty

from .core.demo_spec import DEFAULT_PROMPT


class CV_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    local_demo_only: BoolProperty(
        name="Local Demonstration Mode",
        description="Keep CozyVerse offline and use only bundled deterministic demo logic",
        default=True,
    )

    def draw(self, _context: bpy.types.Context) -> None:
        layout = self.layout
        layout.prop(self, "local_demo_only")
        layout.label(text="Foundation build: no network or paid provider support.", icon="INFO")


class CV_SceneSettings(bpy.types.PropertyGroup):
    prompt: StringProperty(
        name="World Prompt",
        description="Describe the miniature world for the local demonstration",
        default=DEFAULT_PROMPT,
        maxlen=4000,
    )
    preset: EnumProperty(
        name="Preset",
        items=(
            ("COZY_VILLAGE", "Cozy Village", "Warm miniature village demonstration"),
            ("RAINY_CITY", "Rainy City", "Foundation placeholder for a rainy city prompt"),
            ("NATURE", "Nature", "Foundation placeholder for a nature prompt"),
        ),
        default="COZY_VILLAGE",
    )
    status: StringProperty(name="Status", default="Ready for a local demonstration")
    last_demo_prompt: StringProperty(name="Last Demo Prompt", default="", maxlen=4000)


_CLASSES = (CV_AddonPreferences, CV_SceneSettings)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.cozyverse = PointerProperty(type=CV_SceneSettings)


def unregister() -> None:
    if hasattr(bpy.types.Scene, "cozyverse"):
        del bpy.types.Scene.cozyverse
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)


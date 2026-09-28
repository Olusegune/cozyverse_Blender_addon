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
    provider: EnumProperty(
        name="AI Provider",
        description="Provider configuration for a future approved planner integration",
        items=(
            ("NONE", "Local Only", "Disable external AI providers"),
            ("OPENAI", "OpenAI", "Configure an OpenAI-compatible provider"),
            ("ANTHROPIC", "Anthropic", "Configure an Anthropic provider"),
            ("CUSTOM", "Custom", "Configure a future provider adapter"),
        ),
        default="NONE",
    )
    model_name: StringProperty(
        name="Model",
        description="Provider model identifier; no request is made in this foundation build",
        default="",
        maxlen=128,
    )
    api_key_environment_variable: StringProperty(
        name="Environment Variable",
        description="Optional environment variable name used by a future provider adapter",
        default="",
        maxlen=128,
    )

    def draw(self, _context: bpy.types.Context) -> None:
        layout = self.layout
        layout.prop(self, "local_demo_only")
        layout.prop(self, "provider")
        layout.prop(self, "model_name")
        layout.prop(self, "api_key_environment_variable")
        layout.label(text="API keys are entered only in the CozyVerse sidebar session.", icon="LOCKED")
        layout.label(text="Foundation build: no network or paid provider requests.", icon="INFO")


class CV_SessionSecrets(bpy.types.PropertyGroup):
    """Runtime-only secrets attached to WindowManager, never Scene data."""

    api_key: StringProperty(
        name="API Key",
        description="Session-only credential; never stored in the blend file or logs",
        default="",
        subtype="PASSWORD",
        options={"SKIP_SAVE"},
    )


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
    active_tab: EnumProperty(
        name="Workspace",
        items=(
            ("CREATE", "Create", "Create an editable local demonstration", "MOD_BUILD", 0),
            ("ACTIVITY", "Activity", "Review current status and local activity", "INFO", 1),
            ("SETTINGS", "Settings", "Configure local and future provider settings", "PREFERENCES", 2),
        ),
        default="CREATE",
    )


_CLASSES = (CV_AddonPreferences, CV_SessionSecrets, CV_SceneSettings)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.cozyverse = PointerProperty(type=CV_SceneSettings)
    bpy.types.WindowManager.cozyverse_secrets = PointerProperty(type=CV_SessionSecrets)


def unregister() -> None:
    if hasattr(bpy.types.Scene, "cozyverse"):
        del bpy.types.Scene.cozyverse
    if hasattr(bpy.types.WindowManager, "cozyverse_secrets"):
        del bpy.types.WindowManager.cozyverse_secrets
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

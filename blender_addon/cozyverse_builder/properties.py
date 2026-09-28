"""CozyVerse settings stored with the Blender scene."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty, StringProperty

from .core.demo_spec import DEFAULT_PROMPT


def _update_atmosphere(self, context: bpy.types.Context) -> None:
    from .atmosphere import apply_atmosphere

    scene = context.scene if context is not None else getattr(self, "id_data", None)
    if scene is not None:
        apply_atmosphere(scene, self)


def _update_atmosphere_preset(self, context: bpy.types.Context) -> None:
    if self.atmosphere_preset == "CUSTOM":
        return
    from .core.atmosphere_spec import PRESETS

    values = PRESETS[self.atmosphere_preset]
    self.time_hour = values.time_hour
    self.sun_intensity = values.sun_intensity
    self.warmth = values.warmth
    self.ambient_intensity = values.ambient_intensity
    self.interior_intensity = values.interior_intensity
    self.weather = values.weather
    self.rain_amount = values.rain_amount
    _update_atmosphere(self, context)


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
    generation_provider: EnumProperty(
        name="3D Generation Provider",
        description="Provider to configure for a future explicitly approved generation adapter",
        items=(
            ("NONE", "Disabled", "Disable external 3D generation"),
            ("TRIPO", "Tripo", "Configure Tripo credentials without sending a request"),
            ("MESHY", "Meshy", "Configure Meshy credentials without sending a request"),
        ),
        default="NONE",
    )

    def draw(self, _context: bpy.types.Context) -> None:
        layout = self.layout
        layout.prop(self, "local_demo_only")
        layout.prop(self, "provider")
        layout.prop(self, "model_name")
        layout.prop(self, "api_key_environment_variable")
        layout.prop(self, "generation_provider")
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
    tripo_api_key: StringProperty(
        name="Tripo API Key",
        description="Session-only Tripo credential; never stored in the blend file or logs",
        default="",
        subtype="PASSWORD",
        options={"SKIP_SAVE"},
    )
    meshy_api_key: StringProperty(
        name="Meshy API Key",
        description="Session-only Meshy credential; never stored in the blend file or logs",
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
    prompt_text: PointerProperty(
        name="Multiline Prompt",
        description="Optional Blender Text datablock used for a multiline world description",
        type=bpy.types.Text,
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
            ("ATMOSPHERE", "Atmosphere", "Control lighting, time, and rain", "LIGHT_SUN", 1),
            ("ACTIVITY", "Activity", "Review current status and local activity", "INFO", 2),
            ("SETTINGS", "Settings", "Configure local and future provider settings", "PREFERENCES", 3),
        ),
        default="CREATE",
    )
    atmosphere_preset: EnumProperty(
        name="Atmosphere Preset",
        items=(
            ("GOLDEN_HOUR", "Golden Hour", "Warm sunset lighting"),
            ("RAINY_CAFE", "Rainy Cafe", "Evening practical lights and visible rain"),
            ("MOONLIT", "Moonlit", "Cool low-light night"),
            ("MISTY_DAWN", "Misty Dawn", "Soft dawn lighting; fog remains unsupported"),
            ("CUSTOM", "Custom", "Current custom values"),
        ),
        default="GOLDEN_HOUR",
        update=_update_atmosphere_preset,
    )
    time_hour: FloatProperty(
        name="Time of Day",
        description="Artistic time of day in hours",
        default=18.0,
        min=0.0,
        max=24.0,
        precision=1,
        update=_update_atmosphere,
    )
    sun_intensity: FloatProperty(
        name="Sun Intensity",
        default=55.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_update_atmosphere,
    )
    warmth: FloatProperty(
        name="Warmth",
        default=88.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_update_atmosphere,
    )
    ambient_intensity: FloatProperty(
        name="Ambient Light",
        default=38.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_update_atmosphere,
    )
    interior_intensity: FloatProperty(
        name="Interior Lights",
        default=70.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_update_atmosphere,
    )
    weather: EnumProperty(
        name="Weather",
        items=(
            ("CLEAR", "Clear", "Hide the rain preview"),
            ("RAIN", "Rain", "Show the editable rain preview"),
        ),
        default="CLEAR",
        update=_update_atmosphere,
    )
    rain_amount: FloatProperty(
        name="Rain Amount",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_update_atmosphere,
    )
    fog_amount: FloatProperty(name="Fog", default=0.0, min=0.0, max=100.0, subtype="PERCENTAGE")
    wind_amount: FloatProperty(name="Wind", default=0.0, min=0.0, max=100.0, subtype="PERCENTAGE")
    wetness_amount: FloatProperty(name="Wetness", default=0.0, min=0.0, max=100.0, subtype="PERCENTAGE")


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

"""CozyVerse sidebar panels using Blender-native, theme-aware controls."""

from __future__ import annotations

import bpy


class _CVPanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CozyVerse"


def _addon_preferences(context: bpy.types.Context):
    entry = context.preferences.addons.get(__package__)
    return entry.preferences if entry else None


def _draw_header(layout: bpy.types.UILayout, settings) -> None:
    hero = layout.box()
    row = hero.row(align=True)
    row.scale_y = 1.15
    row.label(text="COZYVERSE", icon="WORLD_DATA")
    badge = row.row(align=True)
    badge.alignment = "RIGHT"
    badge.label(text="LOCAL", icon="LOCKED")
    hero.label(text="Editable miniature worlds", icon="MESH_ICOSPHERE")
    tabs = layout.row(align=True)
    tabs.scale_y = 1.15
    tabs.prop(settings, "active_tab", expand=True)


def _draw_create(layout: bpy.types.UILayout, settings) -> None:
    prompt = layout.box()
    prompt.label(text="DESCRIBE YOUR WORLD", icon="TEXT")
    prompt.prop(settings, "prompt", text="")
    prompt.prop(settings, "prompt_text", text="Long Prompt")
    prompt.operator("cozyverse.edit_multiline_prompt", text="Edit Multiline Prompt", icon="TEXT")
    prompt.prop(settings, "preset", text="Style")

    action = layout.column(align=True)
    action.scale_y = 1.4
    action.operator("cozyverse.create_local_demo", text="BUILD WORLD", icon="MOD_BUILD")
    reset = action.row(align=True)
    reset.scale_y = 0.9
    reset.operator("cozyverse.reset_prompt", text="Reset Prompt", icon="LOOP_BACK")

    safety = layout.box()
    safety.label(text="SAFE FOUNDATION MODE", icon="LOCKED")
    safety.label(text="Native editable objects")
    safety.label(text="No network or paid requests")
    status = layout.box()
    status.label(text="STATUS", icon="INFO")
    status.label(text=settings.status)


def _draw_atmosphere(layout: bpy.types.UILayout, settings) -> None:
    header = layout.box()
    header.label(text="ATMOSPHERE LAB", icon="LIGHT_SUN")
    header.label(text="Controls update the scene immediately")

    lighting = layout.box()
    lighting.prop(settings, "atmosphere_preset", text="Preset")
    lighting.prop(settings, "time_hour", slider=True)
    lighting.prop(settings, "sun_intensity", slider=True)
    lighting.prop(settings, "warmth", slider=True)
    lighting.prop(settings, "ambient_intensity", slider=True)
    lighting.prop(settings, "interior_intensity", slider=True)

    weather = layout.box()
    weather.label(text="WEATHER PREVIEW", icon="FORCE_WIND")
    weather.prop(settings, "weather", expand=True)
    rain_row = weather.row()
    rain_row.enabled = settings.weather == "RAIN"
    rain_row.prop(settings, "rain_amount", slider=True)

    advanced = weather.column(align=True)
    advanced.enabled = False
    advanced.label(text="Advanced weather arrives after R1", icon="LOCKED")
    advanced.prop(settings, "fog_amount", slider=True)
    advanced.prop(settings, "wind_amount", slider=True)
    advanced.prop(settings, "wetness_amount", slider=True)

    actions = layout.row(align=True)
    actions.operator("cozyverse.apply_atmosphere", text="Apply", icon="CHECKMARK")
    actions.operator("cozyverse.reset_atmosphere", text="Reset", icon="LOOP_BACK")
    layout.operator("cozyverse.save_atmosphere_preset", text="Save Custom Preset", icon="FILE_TICK")


def _draw_activity(layout: bpy.types.UILayout, settings) -> None:
    state = layout.box()
    state.label(text="SYSTEM STATUS", icon="INFO")
    state.label(text=settings.status)
    state.separator()
    state.label(text="Offline engine", icon="CHECKMARK")
    state.label(text="Blender-native output", icon="CHECKMARK")
    state.label(text="External requests disabled", icon="LOCKED")
    if settings.last_demo_prompt:
        history = layout.box()
        history.label(text="LATEST BUILD", icon="TIME")
        history.label(text=settings.last_demo_prompt[:72])


def _draw_settings(context: bpy.types.Context, layout: bpy.types.UILayout) -> None:
    preferences = _addon_preferences(context)
    secrets = context.window_manager.cozyverse_secrets

    mode = layout.box()
    mode.label(text="RUNTIME MODE", icon="OPTIONS")
    if preferences is None:
        mode.label(text="Local demonstration mode is enforced", icon="LOCKED")
        return
    mode.prop(preferences, "local_demo_only")

    provider = layout.box()
    provider.label(text="AI PROVIDER", icon="NETWORK_DRIVE")
    provider.prop(preferences, "provider", text="")
    provider.prop(preferences, "model_name")
    provider.prop(preferences, "api_key_environment_variable", text="Environment")
    key_row = provider.row(align=True)
    key_row.prop(secrets, "api_key", text="Session Key")
    key_row.operator("cozyverse.clear_api_key", text="", icon="X")
    configured = bool(secrets.api_key.strip())
    provider.label(
        text="Session key loaded" if configured else "No session key loaded",
        icon="KEY_HLT" if configured else "KEY_DEHLT",
    )
    provider.operator(
        "cozyverse.validate_provider_settings",
        text="Validate Locally",
        icon="CHECKMARK",
    )

    security = layout.box()
    security.label(text="CREDENTIAL SAFETY", icon="LOCKED")
    security.label(text="Keys are masked and session-only")
    security.label(text="Keys are never saved in .blend files")
    security.label(text="Validation sends no network request")

    about = layout.box()
    about.label(text="BUILD", icon="BLENDER")
    about.label(text=f"Blender {bpy.app.version_string}")
    about.label(text="CozyVerse 0.3.0 Recovery R1")


class CV_PT_Main(_CVPanel, bpy.types.Panel):
    bl_idname = "CV_PT_main"
    bl_label = "CozyVerse Builder"

    def draw(self, context: bpy.types.Context) -> None:
        settings = context.scene.cozyverse
        layout = self.layout
        _draw_header(layout, settings)
        layout.separator(factor=0.5)
        if settings.active_tab == "CREATE":
            _draw_create(layout, settings)
        elif settings.active_tab == "ATMOSPHERE":
            _draw_atmosphere(layout, settings)
        elif settings.active_tab == "ACTIVITY":
            _draw_activity(layout, settings)
        else:
            _draw_settings(context, layout)


_CLASSES = (CV_PT_Main,)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

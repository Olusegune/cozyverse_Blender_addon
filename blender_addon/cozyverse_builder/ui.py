"""CozyVerse sidebar panels using Blender-native, theme-aware controls."""

from __future__ import annotations

import bpy


class _CVPanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CozyVerse"


def _wrapped_lines(value: str, width: int = 34, limit: int = 5) -> list[str]:
    words = value.replace("\n", " ").split()
    if not words:
        return ["No world description yet"]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > width:
            lines.append(current)
            current = word
            if len(lines) == limit:
                break
        else:
            current = candidate
    if len(lines) < limit and current:
        lines.append(current)
    if len(lines) == limit and len(" ".join(words)) > len(" ".join(lines)):
        lines[-1] = lines[-1].rstrip(".") + "..."
    return lines


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
    title = prompt.row(align=True)
    title.label(text="1  DESCRIBE YOUR WORLD", icon="TEXT")
    prompt.prop(settings, "prompt", text="Quick Prompt")
    preview = prompt.box()
    preview.label(text="PROMPT PREVIEW")
    prompt_value = settings.prompt_text.as_string() if settings.prompt_text else settings.prompt
    for line in _wrapped_lines(prompt_value):
        preview.label(text=line)
    editor = prompt.column(align=True)
    editor.scale_y = 1.25
    editor.operator("cozyverse.edit_multiline_prompt", text="OPEN LARGE PROMPT EDITOR", icon="TEXT")
    prompt.prop(settings, "prompt_text", text="Prompt Document")
    prompt.prop(settings, "preset", text="Style")

    action = layout.column(align=True)
    action.label(text="2  BUILD AN EDITABLE WORLD", icon="OUTLINER_COLLECTION")
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
    provider.label(text="DIRECTOR AI", icon="NETWORK_DRIVE")
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

    generation = layout.box()
    generation.label(text="3D GENERATION", icon="MESH_ICOSPHERE")
    generation.prop(preferences, "generation_provider", text="")

    tripo = generation.box()
    tripo_header = tripo.row(align=True)
    tripo_header.label(text="TRIPO", icon="KEY_HLT" if secrets.tripo_api_key else "KEY_DEHLT")
    tripo_key = tripo.row(align=True)
    tripo_key.prop(secrets, "tripo_api_key", text="Session Key")
    clear_tripo = tripo_key.operator("cozyverse.clear_generation_key", text="", icon="X")
    clear_tripo.provider = "TRIPO"

    meshy = generation.box()
    meshy_header = meshy.row(align=True)
    meshy_header.label(text="MESHY", icon="KEY_HLT" if secrets.meshy_api_key else "KEY_DEHLT")
    meshy_key = meshy.row(align=True)
    meshy_key.prop(secrets, "meshy_api_key", text="Session Key")
    clear_meshy = meshy_key.operator("cozyverse.clear_generation_key", text="", icon="X")
    clear_meshy.provider = "MESHY"

    generation.operator("cozyverse.validate_generation_settings", text="Check Setup Locally", icon="CHECKMARK")
    note = generation.column(align=True)
    note.enabled = False
    note.label(text="Generation requests are not enabled in R1", icon="LOCKED")
    note.label(text="Each future job will require cost and consent review")

    security = layout.box()
    security.label(text="CREDENTIAL SAFETY", icon="LOCKED")
    security.label(text="Keys are masked and session-only")
    security.label(text="Keys are never saved in .blend files")
    security.label(text="Validation sends no network request")

    about = layout.box()
    about.label(text="BUILD", icon="BLENDER")
    about.label(text=f"Blender {bpy.app.version_string}")
    about.label(text="CozyVerse 0.4.0 Recovery R1")


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


class CV_TEXT_PT_Prompt(bpy.types.Panel):
    bl_idname = "CV_TEXT_PT_prompt"
    bl_label = "CozyVerse Prompt"
    bl_space_type = "TEXT_EDITOR"
    bl_region_type = "UI"
    bl_category = "CozyVerse"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.label(text="LARGE PROMPT EDITOR", icon="TEXT")
        layout.label(text="Write naturally across multiple lines.")
        layout.separator()
        column = layout.column(align=True)
        column.scale_y = 1.4
        column.operator("cozyverse.use_multiline_prompt", text="USE PROMPT AND RETURN", icon="CHECKMARK")
        layout.label(text="Then select Build World in CozyVerse.", icon="INFO")


_CLASSES = (CV_PT_Main, CV_TEXT_PT_Prompt)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

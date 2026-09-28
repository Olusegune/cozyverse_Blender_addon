"""CozyVerse sidebar panels using Blender-native, theme-aware controls."""

from __future__ import annotations

import bpy
import json

from .core.style_spec import STYLE_PRESETS


class _CVPanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CozyVerse"


def _wrapped_lines(value: str, width: int = 34, limit: int = 5) -> list[str]:
    words = value.replace("\n", " ").split()
    if not words:
        return ["No world description yet"]
    lines, current = [], ""
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
    badge.label(text="LOCAL SAFE", icon="LOCKED")
    hero.label(text="Editable miniature worlds", icon="MESH_ICOSPHERE")
    hero.label(text=settings.status, icon="INFO")


def _draw_create(layout: bpy.types.UILayout, settings) -> None:
    prompt = layout.box()
    prompt.label(text="DESCRIBE YOUR WORLD", icon="TEXT")
    preview = prompt.box()
    preview.label(text="CURRENT PROMPT", icon="PREVIEW_RANGE")
    prompt_value = settings.prompt_text.as_string() if settings.prompt_text else settings.prompt
    for line in _wrapped_lines(prompt_value, width=40, limit=4):
        preview.label(text=line)
    composer = prompt.column(align=True)
    composer.scale_y = 1.35
    composer.operator("cozyverse.prompt_composer", text="COMPOSE DETAILED PROMPT", icon="GREASEPENCIL")
    utilities = prompt.row(align=True)
    utilities.operator("cozyverse.paste_prompt", text="Paste", icon="PASTEDOWN")
    utilities.operator("cozyverse.reset_prompt", text="Reset", icon="LOOP_BACK")
    templates = prompt.box()
    templates.label(text="QUICK START", icon="BOOKMARKS")
    row = templates.row(align=True)
    for name, label, icon in (("VILLAGE", "Village", "HOME"), ("CITY", "City", "OUTLINER_OB_MESH"), ("CAFE", "Cafe", "LIGHT")):
        operator = row.operator("cozyverse.apply_prompt_template", text=label, icon=icon)
        operator.template = name
    row = templates.row(align=True)
    for name, label, icon in (("NATURE", "Nature", "WORLD"), ("FANTASY", "Fantasy", "SOLO_ON"), ("HISTORICAL", "History", "TIME")):
        operator = row.operator("cozyverse.apply_prompt_template", text=label, icon=icon)
        operator.template = name
    retro = templates.row(align=True)
    retro.scale_y = 1.2
    operator = retro.operator("cozyverse.apply_prompt_template", text="Retro Sci-Fi", icon="ORIENTATION_GIMBAL")
    operator.template = "RETRO_SCIFI"
    style = prompt.box()
    style.label(text="STYLE STUDIO", icon="BRUSH_DATA")
    style.prop(settings, "preset", text="")
    selected_style = STYLE_PRESETS.get(settings.preset)
    if selected_style:
        style.label(text=selected_style.description)
        style.label(text="Asset tags: " + ", ".join(selected_style.keywords), icon="TAG")
    action = layout.column(align=True)
    action.scale_y = 1.55
    action.operator("cozyverse.create_local_demo", text="BUILD EDITABLE WORLD", icon="MOD_BUILD")
    safety = layout.box()
    safety.label(text="LOCAL BUILD • NATIVE OBJECTS • NO COST", icon="LOCKED")
    advanced = layout.box()
    advanced.label(text="ADVANCED", icon="PREFERENCES")
    advanced.label(text="Use Blender's Text Editor for very long prompts.")
    advanced.operator("cozyverse.edit_multiline_prompt", text="Open Full Text Editor", icon="TEXT")


def _draw_atmosphere(layout: bpy.types.UILayout, settings) -> None:
    header = layout.box()
    header.label(text="ATMOSPHERE LAB", icon="LIGHT_SUN")
    header.label(text="Controls update the scene immediately")
    lighting = layout.box()
    for prop in ("atmosphere_preset", "time_hour", "sun_intensity", "warmth", "ambient_intensity", "interior_intensity"):
        lighting.prop(settings, prop, slider=prop != "atmosphere_preset")
    weather = layout.box()
    weather.label(text="WEATHER PREVIEW", icon="FORCE_WIND")
    weather.prop(settings, "weather", expand=True)
    rain = weather.row()
    rain.enabled = settings.weather == "RAIN"
    rain.prop(settings, "rain_amount", slider=True)
    advanced = weather.column(align=True)
    advanced.enabled = False
    advanced.label(text="Advanced weather arrives after R1", icon="LOCKED")
    for prop in ("fog_amount", "wind_amount", "wetness_amount"):
        advanced.prop(settings, prop, slider=True)
    actions = layout.row(align=True)
    actions.operator("cozyverse.apply_atmosphere", text="Apply", icon="CHECKMARK")
    actions.operator("cozyverse.reset_atmosphere", text="Reset", icon="LOOP_BACK")
    layout.operator("cozyverse.save_atmosphere_preset", text="Save Custom Preset", icon="FILE_TICK")


def _draw_image_to_world(layout: bpy.types.UILayout, settings) -> None:
    source = layout.box()
    source.label(text="DIORAMA REFERENCE", icon="IMAGE_DATA")
    source.label(text="Local-first • nothing is uploaded", icon="LOCKED")
    source.operator("cozyverse.select_reference_image", text="Choose Reference Image", icon="FILE_IMAGE")
    if settings.reference_image is not None:
        source.template_ID_preview(settings, "reference_image", rows=4, cols=5, hide_buttons=True)
        source.label(text=f"{settings.reference_image.size[0]} × {settings.reference_image.size[1]} pixels")
    analysis = layout.box()
    analysis.label(text="LOCAL INTERPRETATION", icon="EYEDROPPER")
    analysis.operator("cozyverse.analyze_reference_locally", text="Extract Color Palette", icon="COLOR")
    try:
        palette = json.loads(settings.reference_palette_json)
    except (TypeError, ValueError):
        palette = []
    if palette:
        analysis.label(text="Palette: " + "  ".join("#" + "".join(f"{round(channel * 255):02X}" for channel in color) for color in palette))
    analysis.label(text=settings.reference_status, icon="INFO")
    build = layout.column(align=True)
    build.enabled = settings.reference_image is not None
    build.scale_y = 1.5
    build.operator("cozyverse.recreate_reference_mock", text="CREATE EDITABLE INTERPRETATION", icon="MOD_BUILD")
    note = layout.box()
    note.label(text="Current scope", icon="INFO")
    note.label(text="Uses image palette + deterministic geometry")
    note.label(text="Exact AI vision reconstruction is not enabled")


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


def _draw_generate(context: bpy.types.Context, layout: bpy.types.UILayout, settings) -> None:
    preferences = _addon_preferences(context)
    provider_name = preferences.generation_provider if preferences else "NONE"
    hero = layout.box()
    hero.label(text="3D ASSET FACTORY", icon="MESH_ICOSPHERE")
    hero.label(text=f"Provider: {provider_name.title()}")
    hero.label(text="Check local assets before paid generation", icon="INFO")
    request = layout.box()
    request.label(text="DESCRIBE ONE MISSING ASSET", icon="TEXT")
    request.prop(settings, "generation_prompt", text="")
    request.operator("cozyverse.preview_generation", text="PREVIEW REQUEST", icon="PREVIEW_RANGE")
    review = layout.box()
    review.label(text="REVIEW IMPACT AND COST", icon="DOCUMENTS")
    review.label(text=settings.generation_status)
    for line in _wrapped_lines(settings.generation_cost_note, width=36, limit=4):
        review.label(text=line)
    if settings.generation_fingerprint:
        review.label(text=f"Plan: {settings.generation_fingerprint[:12]}", icon="CHECKMARK")
    review.prop(settings, "generation_approved")
    mock = review.column()
    mock.enabled = bool(settings.generation_plan_json and settings.generation_approved)
    mock.scale_y = 1.3
    mock.operator("cozyverse.run_mock_generation", text="RUN SAFE MOCK JOB", icon="PLAY")
    boundary = layout.box()
    boundary.label(text="LIVE PROVIDER BOUNDARY", icon="LOCKED")
    boundary.label(text="No Tripo or Meshy request is sent in this build")
    boundary.label(text="Live submission requires separate approval")


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
    provider.label(text="Session key loaded" if configured else "No session key loaded", icon="KEY_HLT" if configured else "KEY_DEHLT")
    provider.operator("cozyverse.validate_provider_settings", text="Validate Locally", icon="CHECKMARK")
    generation = layout.box()
    generation.label(text="3D GENERATION", icon="MESH_ICOSPHERE")
    generation.prop(preferences, "generation_provider", text="")
    for provider_id, label, attribute in (("TRIPO", "TRIPO", "tripo_api_key"), ("MESHY", "MESHY", "meshy_api_key")):
        box = generation.box()
        has_key = bool(getattr(secrets, attribute))
        box.label(text=label, icon="KEY_HLT" if has_key else "KEY_DEHLT")
        key = box.row(align=True)
        key.prop(secrets, attribute, text="Session Key")
        clear = key.operator("cozyverse.clear_generation_key", text="", icon="X")
        clear.provider = provider_id
    generation.operator("cozyverse.validate_generation_settings", text="Check Setup Locally", icon="CHECKMARK")
    note = generation.column(align=True)
    note.enabled = False
    note.label(text="Generation requests are not enabled in R1", icon="LOCKED")
    note.label(text="Future jobs require cost and consent review")
    assets = layout.box()
    assets.label(text="YOUR ASSET SOURCES", icon="ASSET_MANAGER")
    assets.prop(preferences, "include_blender_asset_libraries")
    assets.prop(preferences, "custom_asset_folder")
    assets.operator("cozyverse.index_local_assets", text="Index Local Assets", icon="VIEWZOOM")
    assets.label(text=f"Supported model files indexed: {context.scene.cozyverse.indexed_asset_count}", icon="CHECKMARK")
    assets.label(text="Indexing reads filenames only; importing comes next", icon="LOCKED")
    security = layout.box()
    security.label(text="CREDENTIAL SAFETY", icon="LOCKED")
    security.label(text="Keys are masked and session-only")
    security.label(text="Keys are never saved in .blend files")
    security.label(text="Validation sends no network request")
    about = layout.box()
    about.label(text="BUILD", icon="BLENDER")
    about.label(text=f"Blender {bpy.app.version_string}")
    about.label(text="CozyVerse 0.8.0 Style Studio")


class CV_PT_Main(_CVPanel, bpy.types.Panel):
    bl_idname = "CV_PT_main"
    bl_label = "CozyVerse Builder"

    def draw(self, context: bpy.types.Context) -> None:
        _draw_header(self.layout, context.scene.cozyverse)


class _CVChildPanel(_CVPanel):
    bl_parent_id = "CV_PT_main"


class CV_PT_Create(_CVChildPanel, bpy.types.Panel):
    bl_idname = "CV_PT_create"
    bl_label = "Create World"

    def draw(self, context: bpy.types.Context) -> None:
        _draw_create(self.layout, context.scene.cozyverse)


class CV_PT_Atmosphere(_CVChildPanel, bpy.types.Panel):
    bl_idname = "CV_PT_atmosphere"
    bl_label = "Atmosphere Lab"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        _draw_atmosphere(self.layout, context.scene.cozyverse)


class CV_PT_ImageToWorld(_CVChildPanel, bpy.types.Panel):
    bl_idname = "CV_PT_image_to_world"
    bl_label = "Image to World"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        _draw_image_to_world(self.layout, context.scene.cozyverse)


class CV_PT_Generate(_CVChildPanel, bpy.types.Panel):
    bl_idname = "CV_PT_generate"
    bl_label = "3D Asset Factory"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        _draw_generate(context, self.layout, context.scene.cozyverse)


class CV_PT_Activity(_CVChildPanel, bpy.types.Panel):
    bl_idname = "CV_PT_activity"
    bl_label = "Activity & Safety"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        _draw_activity(self.layout, context.scene.cozyverse)


class CV_PT_Settings(_CVChildPanel, bpy.types.Panel):
    bl_idname = "CV_PT_settings"
    bl_label = "Connections & Settings"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        _draw_settings(context, self.layout)


class CV_TEXT_PT_Prompt(bpy.types.Panel):
    bl_idname = "CV_TEXT_PT_prompt"
    bl_label = "CozyVerse Prompt"
    bl_space_type = "TEXT_EDITOR"
    bl_region_type = "UI"
    bl_category = "CozyVerse"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.label(text="ADVANCED PROMPT EDITOR", icon="TEXT")
        layout.label(text="Write naturally across multiple lines.")
        layout.label(text="Press Shift+F5 to return to the 3D View.", icon="INFO")
        layout.separator()
        column = layout.column(align=True)
        column.scale_y = 1.4
        column.operator("cozyverse.use_multiline_prompt", text="USE PROMPT AND RETURN", icon="CHECKMARK")
        layout.label(text="Then choose Build Editable World.", icon="INFO")


_CLASSES = (CV_PT_Main, CV_PT_Create, CV_PT_ImageToWorld, CV_PT_Atmosphere, CV_PT_Generate, CV_PT_Activity, CV_PT_Settings, CV_TEXT_PT_Prompt)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

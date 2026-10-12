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
    steps = layout.row(align=True)
    steps.enabled = False
    steps.prop(settings, "workflow_step", expand=True)

    if not settings.onboarding_complete:
        welcome = layout.box()
        welcome.label(text="WELCOME TO COZYVERSE", icon="FUND")
        welcome.label(text="Build your first editable miniature in three steps.")
        welcome.label(text="Nothing is uploaded and no credits are used.", icon="LOCKED")
        start = welcome.column(align=True)
        start.scale_y = 1.35
        start.operator("cozyverse.start_onboarding", text="START GUIDED EXAMPLE", icon="PLAY")
        start.operator("cozyverse.dismiss_onboarding", text="Use My Own Description", icon="FORWARD")

    if settings.workflow_step == "DESCRIBE":
        prompt = layout.box()
        prompt.label(text="STEP 1 — DESCRIBE", icon="TEXT")
        preview = prompt.box()
        preview.label(text="CURRENT PROMPT", icon="PREVIEW_RANGE")
        prompt_value = settings.prompt_text.as_string() if settings.prompt_text else settings.prompt
        for line in _wrapped_lines(prompt_value, width=40, limit=4):
            preview.label(text=line)
        composer = prompt.column(align=True)
        composer.scale_y = 1.25
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
        for name, label, icon in (("NATURE", "Nature", "WORLD"), ("FANTASY", "Fantasy", "SOLO_ON"), ("RETRO_SCIFI", "Retro Sci-Fi", "ORIENTATION_GIMBAL")):
            operator = row.operator("cozyverse.apply_prompt_template", text=label, icon=icon)
            operator.template = name
        style = prompt.box()
        style.label(text="STYLE STUDIO", icon="BRUSH_DATA")
        style.prop(settings, "preset", text="")
        selected_style = STYLE_PRESETS.get(settings.preset)
        if selected_style:
            style.label(text=selected_style.description)
        action = layout.column(align=True)
        action.scale_y = 1.5
        action.operator("cozyverse.prepare_scene_plan", text="REVIEW WORLD PLAN", icon="DOCUMENTS")
        advanced = layout.box()
        advanced.label(text="Long prompt?", icon="PREFERENCES")
        advanced.operator("cozyverse.edit_multiline_prompt", text="Open Advanced Text Editor", icon="TEXT")

    elif settings.workflow_step == "REVIEW":
        plan = layout.box()
        plan.label(text="STEP 2 — REVIEW PLAN", icon="DOCUMENTS")
        plan.label(text="Edit the proposal before anything is built.")
        plan.prop(settings, "plan_title")
        plan.prop(settings, "plan_world_type")
        plan.prop(settings, "plan_base_shape")
        plan.prop(settings, "plan_camera_type")
        contents = plan.box()
        contents.label(text="SCENE CONTENT", icon="OUTLINER_COLLECTION")
        grid = contents.grid_flow(row_major=True, columns=2, align=True)
        grid.prop(settings, "plan_architecture_count")
        grid.prop(settings, "plan_prop_count")
        grid.prop(settings, "plan_vegetation_count")
        grid.prop(settings, "plan_character_count")
        contents.prop(settings, "plan_include_road")
        style = plan.box()
        style.label(text="VISUAL DIRECTION", icon="BRUSH_DATA")
        style.prop(settings, "preset", text="")
        plan.prop(settings, "plan_approved", icon="CHECKMARK")
        actions = layout.row(align=True)
        actions.operator("cozyverse.back_to_description", text="Back", icon="BACK")
        build = actions.row(align=True)
        build.enabled = settings.plan_approved
        build.scale_y = 1.45
        build.operator("cozyverse.build_approved_plan", text="BUILD NEW VERSION", icon="MOD_BUILD")
        safety = layout.box()
        safety.label(text="Existing worlds and manual edits will not be overwritten.", icon="LOCKED")
        safety.label(text="LOCAL BUILD • NATIVE OBJECTS • NO COST")

    else:
        result = layout.box()
        result.label(text="STEP 3 — WORLD READY", icon="CHECKMARK")
        result.label(text=settings.active_world_name or "Generated world")
        primary = result.column(align=True)
        primary.scale_y = 1.35
        primary.operator("cozyverse.select_world", text="SELECT & FRAME WORLD", icon="VIEWZOOM")
        row = result.row(align=True)
        row.operator("cozyverse.lock_selected_objects", text="Protect Selected", icon="LOCKED")
        row.operator("cozyverse.inspect_manual_edits", text="Check Edits", icon="UV_SYNC_SELECT")
        next_version = layout.column(align=True)
        next_version.operator("cozyverse.back_to_description", text="CREATE ANOTHER VERSION", icon="DUPLICATE")

    if settings.operation_progress > 0:
        progress = layout.box()
        progress.label(text="PROGRESS", icon="SORTTIME")
        progress.prop(settings, "operation_progress", text="")
    if settings.last_error:
        error = layout.box()
        error.alert = True
        error.label(text=settings.last_error, icon="ERROR")
    if settings.recovery_hint:
        recovery = layout.box()
        recovery.label(text="NEXT STEP", icon="INFO")
        for line in _wrapped_lines(settings.recovery_hint, width=42, limit=3):
            recovery.label(text=line)


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


def _draw_asset_library(context: bpy.types.Context, layout: bpy.types.UILayout, settings) -> None:
    preferences = _addon_preferences(context)
    source = layout.box()
    source.label(text="LOCAL ASSET CATALOG", icon="ASSET_MANAGER")
    source.label(text="Your files are preferred before paid generation.", icon="LOCKED")
    if preferences is not None:
        source.prop(preferences, "include_blender_asset_libraries")
        source.prop(preferences, "custom_asset_folder")
    source.operator("cozyverse.index_local_assets", text="INDEX LOCAL SOURCES", icon="FILE_REFRESH")
    source.label(text=settings.asset_catalog_status, icon="INFO")

    search = layout.box()
    search.label(text="SEARCH & MATCH", icon="VIEWZOOM")
    search.prop(settings, "asset_search", text="")
    search.prop(settings, "asset_category", text="")
    search.operator("cozyverse.match_local_assets", text="FIND BEST MATCHES", icon="SORTSIZE")

    results = layout.box()
    results.label(text=f"RESULTS ({len(settings.asset_items)})", icon="PRESET")
    if not settings.asset_items:
        results.label(text="Index a folder or Blender Asset Library to begin.")
    for index, item in enumerate(settings.asset_items[:10]):
        row = results.row(align=True)
        icon = "RADIOBUT_ON" if settings.asset_index == index else "RADIOBUT_OFF"
        choose = row.operator("cozyverse.select_catalog_asset", text=item.name[:28], icon=icon)
        choose.index = index
        row.label(text=item.category.title())
        if item.match_score:
            row.label(text=f"{item.match_score:.1f}")

    if 0 <= settings.asset_index < len(settings.asset_items):
        item = settings.asset_items[settings.asset_index]
        detail = layout.box()
        detail.label(text="SELECTED ASSET", icon="FILE_3D")
        detail.label(text=item.name)
        detail.label(text=f"{item.category.title()} • {item.extension.upper().lstrip('.')} • {item.source.replace('_', ' ').title()}")
        for line in _wrapped_lines(item.tags, width=40, limit=2):
            detail.label(text=line, icon="TAG")
        placement = detail.box()
        placement.label(text="PLACEMENT", icon="ORIENTATION_LOCAL")
        placement.prop(settings, "asset_place_location")
        placement.prop(settings, "asset_place_rotation")
        placement.prop(settings, "asset_place_scale")
        placement.operator("cozyverse.preview_asset_placement", text="PREVIEW WITH PROXY", icon="CUBE")
        placement.prop(settings, "asset_placement_approved")
        place = placement.column(align=True)
        place.enabled = settings.asset_placement_approved and bool(settings.asset_preview_name)
        place.scale_y = 1.35
        place.operator("cozyverse.place_approved_asset", text="IMPORT APPROVED ASSET", icon="IMPORT")
        detail.label(text="Import destination: CV_IMPORTED_ASSETS", icon="OUTLINER_COLLECTION")


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
    versions = layout.box()
    versions.label(text="WORLD VERSIONS", icon="OUTLINER_COLLECTION")
    worlds = [collection for collection in bpy.data.collections if collection.get("cv_managed") and collection.name.startswith("CV_WORLD")]
    if not worlds:
        versions.label(text="No generated worlds yet")
    for world in sorted(worlds, key=lambda item: item.name, reverse=True)[:8]:
        row = versions.row(align=True)
        select = row.operator("cozyverse.select_world", text=world.name, icon="RADIOBUT_ON" if settings.active_world_name == world.name else "RADIOBUT_OFF")
        select.world_name = world.name
        visibility = row.operator("cozyverse.archive_world", text="", icon="HIDE_ON" if not world.hide_viewport else "HIDE_OFF")
        visibility.world_name = world.name
        visibility.hidden = not world.hide_viewport
    versions.label(text="Hide is reversible; versions are never deleted here.", icon="INFO")


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
    about.label(text="CozyVerse 0.11.0 Procedural Variety")


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


class CV_PT_AssetLibrary(_CVChildPanel, bpy.types.Panel):
    bl_idname = "CV_PT_asset_library"
    bl_label = "Asset Match & Placement"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        _draw_asset_library(context, self.layout, context.scene.cozyverse)


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


_CLASSES = (CV_PT_Main, CV_PT_Create, CV_PT_AssetLibrary, CV_PT_ImageToWorld, CV_PT_Atmosphere, CV_PT_Generate, CV_PT_Activity, CV_PT_Settings, CV_TEXT_PT_Prompt)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

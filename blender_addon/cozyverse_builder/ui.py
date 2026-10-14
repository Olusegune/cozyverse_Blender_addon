"""CozyVerse sidebar: one tabbed panel that always shows the next best action."""

from __future__ import annotations

import bpy
import json

from .core.composition_spec import profile_for
from .core.scene_plan import proposed_plan
from .core.style_spec import STYLE_PRESETS
from .flow import LOOKS, SHOTS, TABS, _turntable_for
from .motion import controller_for
from .vehicles import railway_for, road_for, traffic_for
from .visual_assets import icon_id

VERSION_LABEL = "0.17.0 Magic Flow"


def _ico(key: str, fallback: str) -> dict:
    """Icon kwargs: bundled artwork when present, otherwise a native Blender icon."""
    value = icon_id(key)
    return {"icon_value": value} if value else {"icon": fallback}


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


def _active_world(settings):
    world = bpy.data.collections.get(settings.active_world_name) if settings.active_world_name else None
    return world if world is not None and world.get("cv_managed") else None


def _clock(hour: float) -> str:
    hour = hour % 24.0
    whole = int(hour)
    return f"{whole:02d}:{int((hour - whole) * 60):02d}"


def _needs_world(layout: bpy.types.UILayout, settings, what: str) -> bool:
    """Friendly empty state. Returns True when there is no world to act on."""
    if _active_world(settings) is not None:
        return False
    box = layout.box()
    box.scale_y = 1.1
    if icon_id("empty_no_world"):
        box.template_icon(icon_value=icon_id("empty_no_world"), scale=5.0)
    box.label(text=f"Conjure a world to {what}", icon="WORLD_DATA")
    box.operator("cozyverse.goto_tab", text="Go to Create", icon="MOD_BUILD").tab = "CREATE"
    return True


def _draw_header(layout: bpy.types.UILayout, context: bpy.types.Context, settings) -> None:
    top = layout.row(align=True)
    top.label(text="CozyVerse", **_ico("logo_mark", "WORLD_DATA"))
    tail = top.row(align=True)
    tail.alignment = "RIGHT"
    tail.label(text=VERSION_LABEL)
    tabs = layout.row(align=True)
    tabs.scale_y = 1.3
    for identifier, label, _description, icon, _index in TABS:
        button = tabs.operator("cozyverse.goto_tab", text="", icon=icon, depress=settings.active_tab == identifier)
        button.tab = identifier
    current = next((tab for tab in TABS if tab[0] == settings.active_tab), TABS[0])
    title = layout.row()
    title.label(text=current[1], icon=current[3])
    status = layout.row()
    status.active = False
    status.label(text=settings.status[:60])
    if settings.last_error:
        error = layout.box()
        error.alert = True
        for line in _wrapped_lines(settings.last_error, width=44, limit=3):
            error.label(text=line, icon="ERROR")
        if settings.recovery_hint:
            for line in _wrapped_lines(settings.recovery_hint, width=44, limit=2):
                error.label(text=line)


def _draw_prompt_field(layout: bpy.types.UILayout, settings) -> None:
    if settings.prompt_text is not None and settings.prompt_text.as_string().strip():
        box = layout.box()
        box.label(text="Using the multiline prompt", icon="TEXT")
        for line in _wrapped_lines(settings.prompt_text.as_string(), width=42, limit=3):
            box.label(text=line)
        box.operator("cozyverse.reset_prompt", text="Use the one-line prompt instead", icon="LOOP_BACK")
        return
    layout.prop(settings, "prompt", text="", placeholder="Describe your world… a rainy cafe on a tiny island")


def _draw_reads_as(layout: bpy.types.UILayout, settings) -> None:
    value = settings.prompt_text.as_string() if settings.prompt_text and settings.prompt_text.as_string().strip() else settings.prompt
    if not value.strip():
        return
    plan = proposed_plan(value, settings.preset)
    profile = profile_for(plan.world_type)
    row = layout.row()
    row.active = False
    row.label(
        text=f"{profile.label} · {plan.architecture_count} buildings · {plan.prop_count} props",
        icon="LIGHT",
    )


def _draw_create(layout: bpy.types.UILayout, settings) -> None:
    world = _active_world(settings)
    if settings.workflow_step == "REVIEW":
        _draw_review(layout, settings)
        return
    if settings.workflow_step == "BUILT" and world is not None:
        _draw_built(layout, settings, world)
        return

    if not settings.onboarding_complete and icon_id("header"):
        layout.template_icon(icon_value=icon_id("header"), scale=6.0)
    _draw_prompt_field(layout, settings)
    _draw_reads_as(layout, settings)

    main = layout.row(align=True)
    main.scale_y = 1.9
    main.operator("cozyverse.conjure", text="Conjure World", icon="WORLD_DATA")
    dice = main.row(align=True)
    dice.scale_x = 0.55
    dice.operator("cozyverse.surprise", text="", icon="SHADERFX")
    hint = layout.row()
    hint.active = False
    hint.label(text="Dice = surprise idea (Ctrl builds it)")

    style = layout.box()
    style.label(text="Style", icon="BRUSH_DATA")
    style.template_icon_view(settings, "preset", show_labels=True, scale=5.0, scale_popup=6.0)
    selected = STYLE_PRESETS.get(settings.preset)
    if selected:
        note = style.row()
        note.active = False
        note.label(text=selected.description)

    header, body = layout.panel("cv_create_ideas", default_closed=settings.onboarding_complete)
    header.label(text="Start from an idea", icon="BOOKMARKS")
    if body is not None:
        for left, right in (
            (("VILLAGE", "Village", "HOME"), ("CITY", "City", "OUTLINER_OB_MESH")),
            (("CAFE", "Cafe", "LIGHT"), ("NATURE", "Nature", "WORLD")),
            (("FANTASY", "Fantasy", "SOLO_ON"), ("RETRO_SCIFI", "Retro Sci-Fi", "ORIENTATION_GIMBAL")),
        ):
            row = body.row(align=True)
            for column, (template, label, fallback) in zip((row.column(align=True), row.column(align=True)), (left, right)):
                card = column.box()
                preview = icon_id(f"template_{template.lower()}")
                if preview:
                    card.template_icon(icon_value=preview, scale=4.2)
                button = card.operator("cozyverse.apply_prompt_template", text=label, **({"icon_value": preview} if preview else {"icon": fallback}))
                button.template = template

    header, body = layout.panel("cv_create_tune", default_closed=True)
    header.label(text="Fine-tune the prompt", icon="PREFERENCES")
    if body is not None:
        body.operator("cozyverse.prompt_composer", text="Compose a detailed prompt", icon="GREASEPENCIL")
        row = body.row(align=True)
        row.operator("cozyverse.paste_prompt", text="Paste", icon="PASTEDOWN")
        row.operator("cozyverse.reset_prompt", text="Reset", icon="LOOP_BACK")
        body.operator("cozyverse.edit_multiline_prompt", text="Open the big text editor", icon="TEXT")
        body.separator()
        body.prop(settings, "review_before_build")
        note = body.row()
        note.active = False
        note.label(text="Builds are always new versions.", icon="LOCKED")
        keys = body.row()
        keys.active = False
        keys.label(text="Alt+W pie menu · Shift+Alt+W quick conjure", icon="EVENT_W")

    if not settings.onboarding_complete:
        layout.operator("cozyverse.dismiss_onboarding", text="Got it", icon="CHECKMARK")


def _draw_review(layout: bpy.types.UILayout, settings) -> None:
    plan = layout.box()
    plan.label(text="Review the plan", icon="DOCUMENTS")
    plan.prop(settings, "plan_title")
    plan.prop(settings, "plan_world_type")
    plan.prop(settings, "plan_base_shape")
    plan.prop(settings, "plan_camera_type")
    grid = plan.grid_flow(row_major=True, columns=2, align=True)
    grid.prop(settings, "plan_architecture_count")
    grid.prop(settings, "plan_prop_count")
    grid.prop(settings, "plan_vegetation_count")
    grid.prop(settings, "plan_character_count")
    plan.prop(settings, "plan_include_road")
    plan.template_icon_view(settings, "preset", show_labels=True, scale=5.0, scale_popup=6.0)
    summary = layout.box()
    summary.label(text=f"Source: {settings.revision_source_world or 'New world'}", icon="OUTLINER_COLLECTION")
    metrics = summary.grid_flow(row_major=True, columns=2, align=True)
    metrics.label(text=f"Create: {settings.revision_created}", icon="ADD")
    metrics.label(text=f"Changed: {settings.revision_changed}", icon="FILE_TICK")
    metrics.label(text=f"Delete: {settings.revision_deleted}", icon="TRASH")
    metrics.label(text=f"Preserve: {settings.revision_skipped}", icon="LOCKED")
    if settings.revision_protected or settings.revision_manual_edits:
        summary.label(text=f"Protected: {settings.revision_protected}   Hand-edited, kept: {settings.revision_manual_edits}", icon="UV_SYNC_SELECT")
    summary.operator("cozyverse.refresh_revision_preview", text="Refresh preview", icon="FILE_REFRESH")
    layout.prop(settings, "plan_approved", icon="CHECKMARK")
    actions = layout.row(align=True)
    actions.operator("cozyverse.cancel_revision", text="Back", icon="BACK")
    build = actions.row(align=True)
    build.enabled = settings.plan_approved
    build.scale_y = 1.6
    build.operator("cozyverse.build_approved_plan", text="Build New Version", icon="MOD_BUILD")


def _draw_built(layout: bpy.types.UILayout, settings, world) -> None:
    objects = world.all_objects
    hero = layout.box()
    top = hero.row()
    top.label(text=world.name, **_ico("success_world_ready", "CHECKMARK"))
    count = top.row()
    count.alignment = "RIGHT"
    count.label(text=f"{len(objects)} objects")
    style = world.get("cv_style_label")
    if style:
        sub = hero.row()
        sub.active = False
        sub.label(text=f"{world.get('cv_composition_label', 'World')} in {style}")

    layout.label(text="What next?")
    steps = layout.column(align=True)
    steps.scale_y = 1.35
    for tab, label, icon in (
        ("ATMOSPHERE", "Set the mood: light, weather, time", "LIGHT_SUN"),
        ("SHOT", "Frame a shot and render a postcard", "CAMERA_DATA"),
        ("STORY", "Bring it to life with motion", "ACTION"),
        ("GENERATE", "Swap in your own or generated assets", "ASSET_MANAGER"),
    ):
        steps.operator("cozyverse.goto_tab", text=label, icon=icon).tab = tab

    again = layout.row(align=True)
    again.scale_y = 1.3
    again.operator("cozyverse.conjure", text="Remix Layout", icon="FILE_REFRESH").remix = True
    again.operator("cozyverse.back_to_description", text="New Version", icon="DUPLICATE")
    layout.operator("cozyverse.select_world", text="Select and Frame", icon="VIEWZOOM")

    header, body = layout.panel("cv_built_protect", default_closed=True)
    header.label(text="Protect and recover", icon="LOCKED")
    if body is not None:
        row = body.row(align=True)
        row.operator("cozyverse.lock_selected_objects", text="Protect Selected", icon="LOCKED")
        row.operator("cozyverse.inspect_manual_edits", text="Check Edits", icon="UV_SYNC_SELECT")
        body.operator("cozyverse.create_checkpoint", text="Save a Recovery Checkpoint", icon="RECOVER_LAST")
        if settings.checkpoint_path:
            body.label(text="Checkpoint saved next to your .blend", icon="FILE_TICK")
        note = body.row()
        note.active = False
        note.label(text="Hand edits are never overwritten.")


def _draw_atmosphere(layout: bpy.types.UILayout, settings) -> None:
    if _needs_world(layout, settings, "light and weather it"):
        return
    layout.template_icon_view(settings, "atmosphere_preset", show_labels=True, scale=8.0, scale_popup=6.0)

    time = layout.box()
    top = time.row()
    top.label(text="Time of day", icon="TIME")
    clock = top.row()
    clock.alignment = "RIGHT"
    clock.label(text=_clock(settings.time_hour))
    time.prop(settings, "time_hour", text="", slider=True)
    chips = time.row(align=True)
    for label, hour in (("Dawn", 6.0), ("Noon", 12.0), ("Golden", 18.0), ("Night", 22.0)):
        chips.operator("cozyverse.set_time_of_day", text=label).hour = hour

    header, body = layout.panel("cv_mood_light", default_closed=False)
    header.label(text="Sky and light", icon="WORLD")
    if body is not None:
        for prop in ("sun_intensity", "warmth", "ambient_intensity", "exposure"):
            body.prop(settings, prop, slider=True)

    header, body = layout.panel("cv_mood_weather", default_closed=False)
    header.label(text="Weather and seasons", icon="FORCE_WIND")
    if body is not None:
        body.prop(settings, "weather", expand=True)
        if settings.weather == "RAIN":
            body.prop(settings, "rain_amount", slider=True)
        if settings.weather == "SNOW":
            body.prop(settings, "snow_amount", slider=True)
        body.prop(settings, "fog_amount", slider=True)
        body.prop(settings, "wind_amount", slider=True)
        body.prop(settings, "wetness_amount", slider=True)
        body.prop(settings, "season", expand=True)

    header, body = layout.panel("cv_mood_practical", default_closed=True)
    header.label(text="Window glow and lamps", icon="LIGHT_POINT")
    if body is not None:
        body.prop(settings, "practical_lights")
        controls = body.column(align=True)
        controls.enabled = settings.practical_lights
        controls.prop(settings, "interior_intensity", slider=True)
        controls.prop(settings, "practical_temperature", slider=True)

    header, body = layout.panel("cv_mood_more", default_closed=True)
    header.label(text="Save and performance", icon="FILE_TICK")
    if body is not None:
        row = body.row(align=True)
        row.operator("cozyverse.save_atmosphere_preset", text="Save Look", icon="FILE_TICK")
        row.operator("cozyverse.load_atmosphere_preset", text="Load Saved", icon="IMPORT")
        body.operator("cozyverse.reset_atmosphere", text="Reset", icon="LOOP_BACK")
        body.prop(settings, "weather_quality", expand=True)


def _draw_shot(layout: bpy.types.UILayout, context: bpy.types.Context, settings) -> None:
    if _needs_world(layout, settings, "film it"):
        return
    layout.label(text="Each shot is its own camera.")
    active = context.scene.camera.get("cv_shot", "WIDE") if context.scene.camera is not None else ""
    keys = {"WIDE": "cinematic_wide", "HERO": "cinematic_hero_medium", "DETAIL": "cinematic_detail_closeup"}
    for identifier, label, description in SHOTS:
        card = layout.box()
        preview = icon_id(keys[identifier])
        if preview:
            card.template_icon(icon_value=preview, scale=5.5)
        row = card.row(align=True)
        row.scale_y = 1.3
        button = row.operator("cozyverse.frame_shot", text=label, icon="CAMERA_DATA", depress=active == identifier)
        button.shot = identifier
        note = card.row()
        note.active = False
        note.label(text=description)
    header, body = layout.panel("cv_shot_turntable", default_closed=False)
    header.label(text="Turntable", icon="ORIENTATION_GIMBAL")
    if body is not None:
        if _turntable_for(_active_world(settings)) is not None:
            body.label(text="The camera orbits the world on a loop.", icon="CHECKMARK")
            row = body.row(align=True)
            row.operator("cozyverse.turntable", text="Rebuild", icon="FILE_REFRESH")
            row.operator("cozyverse.clear_turntable", text="Remove", icon="X")
            hint = body.row()
            hint.active = False
            hint.label(text="Press Space to play. Keyframes are editable.")
        else:
            body.prop(settings, "turntable_frames")
            body.operator("cozyverse.turntable", text="Add Turntable", icon="ORIENTATION_GIMBAL")
    post = layout.column(align=True)
    post.scale_y = 1.7
    post.operator("cozyverse.render_postcard", text="Render Postcard", icon="RENDER_STILL")
    note = layout.row()
    note.active = False
    note.label(text="Set the Mood first; it shows in renders.")


def _draw_image_to_world(layout: bpy.types.UILayout, settings) -> None:
    source = layout.box()
    source.label(text="DIORAMA REFERENCE", icon="IMAGE_DATA")
    source.label(text="Local-first • nothing is uploaded", icon="LOCKED")
    source.operator("cozyverse.select_reference_image", text="Choose Reference Image", icon="FILE_IMAGE")
    if settings.reference_image is not None:
        source.template_ID_preview(settings, "reference_image", rows=4, cols=5, hide_buttons=True)
        source.label(text=f"{settings.reference_image.size[0]} × {settings.reference_image.size[1]} pixels")
    elif icon_id("empty_no_image"):
        source.template_icon(icon_value=icon_id("empty_no_image"), scale=5.0)
    analysis = layout.box()
    analysis.label(text="LOCAL INTERPRETATION", icon="EYEDROPPER")
    analysis.operator("cozyverse.analyze_reference_locally", text="Analyze Composition Locally", icon="COLOR")
    try:
        palette = json.loads(settings.reference_palette_json)
    except (TypeError, ValueError):
        palette = []
    if palette:
        analysis.label(text="Palette: " + "  ".join("#" + "".join(f"{round(channel * 255):02X}" for channel in color) for color in palette))
    analysis.label(text=settings.reference_status, icon="INFO")
    analysis.prop(settings, "reference_quality", expand=True)
    build = layout.column(align=True)
    build.enabled = settings.reference_image is not None
    build.scale_y = 1.5
    build.operator("cozyverse.recreate_reference_mock", text="CREATE EDITABLE INTERPRETATION", icon="MOD_BUILD")
    note = layout.box()
    note.label(text="Current scope", icon="INFO")
    note.label(text="Uses palette, aspect, brightness, contrast and focal cues")
    note.label(text="Approximation only — it does not recognize exact objects")
    note.label(text="All generated parts remain normal editable Blender data")


def _draw_life(layout: bpy.types.UILayout, settings) -> None:
    header, body = layout.panel("cv_motion_life", default_closed=False)
    header.prop(settings, "life_enabled", text="Ambient life", icon="FORCE_WIND")
    if body is not None:
        column = body.column(align=True)
        column.enabled = settings.life_enabled
        column.prop(settings, "life_sway", slider=True)
        column.prop(settings, "life_flicker", slider=True)
        note = body.row()
        note.active = False
        note.label(text="Wind (Mood tab) adds to the sway.")
        body.operator("cozyverse.life_refresh", text="Re-apply to this world", icon="FILE_REFRESH")


def _draw_buildup(layout: bpy.types.UILayout, settings) -> None:
    header, body = layout.panel("cv_motion_buildup", default_closed=False)
    header.label(text="Build-up animation", icon="MOD_BUILD")
    if body is None:
        return
    world = _active_world(settings)
    controller = controller_for(world)
    if controller is None:
        body.prop(settings, "buildup_style", expand=True)
        body.prop(settings, "buildup_order", text="")
        body.prop(settings, "buildup_seconds")
        row = body.row()
        row.scale_y = 1.5
        row.operator("cozyverse.buildup_add", text="Play Build-Up", icon="PLAY")
        note = body.row()
        note.active = False
        note.label(text="The world assembles itself on an editable timeline.")
    else:
        body.label(text="Press Space to watch it.", icon="CHECKMARK")
        row = body.row(align=True)
        row.scale_y = 1.3
        row.operator("cozyverse.buildup_replay", text="Replay", icon="PLAY")
        row.operator("cozyverse.buildup_finish", text="Show Finished", icon="CHECKMARK")
        body.operator("cozyverse.buildup_add", text="Rebuild With These Settings", icon="FILE_REFRESH")
        body.prop(settings, "buildup_style", expand=True)
        body.prop(settings, "buildup_order", text="")
        body.prop(settings, "buildup_seconds")
        body.operator("cozyverse.buildup_remove", text="Remove Build-Up", icon="X")


def _draw_vehicles(layout: bpy.types.UILayout, settings) -> None:
    world = _active_world(settings)
    header, body = layout.panel("cv_motion_vehicles", default_closed=True)
    header.label(text="Cars and trains", icon="AUTO")
    if body is None:
        return
    cars = traffic_for(world)
    box = body.box()
    box.label(text="Traffic", icon="AUTO")
    if road_for(world) is None:
        note = box.row()
        note.active = False
        note.label(text="This world has no road.")
    else:
        box.prop(settings, "traffic_cars")
        box.prop(settings, "traffic_seconds")
        row = box.row(align=True)
        row.operator("cozyverse.traffic_add", text="Rebuild Cars" if cars else "Add Cars", icon="FILE_REFRESH" if cars else "ADD")
        if cars:
            row.operator("cozyverse.traffic_remove", text="Remove", icon="X")
    train = railway_for(world)
    box = body.box()
    box.label(text="Railway", icon="ORIENTATION_GIMBAL")
    box.prop(settings, "train_cars")
    box.prop(settings, "train_seconds")
    row = box.row(align=True)
    row.operator("cozyverse.railway_add", text="Rebuild Train" if train else "Add Train", icon="FILE_REFRESH" if train else "ADD")
    if train:
        row.operator("cozyverse.railway_remove", text="Remove", icon="X")
    note = body.row()
    note.active = False
    note.label(text="They loop forever. Press Space to play.")


def _draw_story(layout: bpy.types.UILayout, settings) -> None:
    _draw_life(layout, settings)
    _draw_buildup(layout, settings)
    _draw_vehicles(layout, settings)
    layout.separator()
    hero = layout.box()
    hero.label(text="STORY MOMENTS", icon_value=icon_id("icon_story_dark"))
    hero.label(text=f"Target: {settings.active_world_name or 'Build or select a world'}", icon="OUTLINER_COLLECTION")
    preview_key = f"story_{settings.story_preset.lower()}"
    if icon_id(preview_key):
        hero.template_icon(icon_value=icon_id(preview_key), scale=11.0)
    hero.prop(settings, "story_preset", text="")
    timing = layout.box()
    timing.label(text="TIMELINE", icon_value=icon_id("icon_timeline_dark"))
    row = timing.row(align=True)
    row.prop(settings, "story_start_frame")
    row.prop(settings, "story_end_frame")
    timing.label(text="24 fps • deterministic three-key loop", icon="INFO")
    review = layout.box()
    review.label(text="REVIEW BEFORE ANIMATING", icon="PREVIEW_RANGE")
    review.operator("cozyverse.preview_story", text="PREVIEW STORY PLAN", icon="VIEWZOOM")
    if settings.story_preview_json:
        metrics = review.grid_flow(row_major=True, columns=2, align=True)
        metrics.label(text=f"Targets: {settings.story_target_count}", icon="OBJECT_DATA")
        metrics.label(text=f"Keyframes: {settings.story_keyframe_count}", icon="KEYFRAME")
        metrics.label(text=f"Skipped: {settings.story_skipped_count}", icon="LOCKED")
        metrics.label(text=f"Frames: {settings.story_start_frame}–{settings.story_end_frame}", icon="TIME")
        review.prop(settings, "story_approved", icon="CHECKMARK")
    review.label(text=settings.story_status, icon="INFO")
    actions = layout.row(align=True)
    apply_column = actions.column(align=True)
    apply_column.enabled = settings.story_approved and not settings.story_active_id
    apply_column.scale_y = 1.5
    apply_column.operator("cozyverse.apply_story", text="APPLY STORY", icon_value=icon_id("icon_animate_dark"))
    clear_column = actions.column(align=True)
    clear_column.enabled = bool(settings.story_active_id)
    clear_column.operator("cozyverse.clear_story", text="Clear", icon="X")
    safety = layout.box()
    safety.label(text="Native editable Actions and keyframes", icon="ACTION")
    safety.label(text="Protected or already animated objects are skipped", icon="LOCKED")
    if settings.life_enabled:
        safety.label(text="Flickering lamps are left to Ambient life", icon="LIGHT_POINT")
    safety.label(text="Preview never changes the scene")


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
    recovery = layout.box()
    recovery.label(text="RECOVERY", icon="RECOVER_LAST")
    recovery.operator("cozyverse.create_checkpoint", text="Create Project Checkpoint", icon="FILE_BACKUP")
    if settings.checkpoint_path:
        recovery.label(text=settings.checkpoint_path[-58:])
    log = layout.box()
    log.label(text="REDACTED ACTIVITY LOG", icon="TEXT")
    if not settings.activity_log:
        log.label(text="No recorded milestone operations yet")
    for item in reversed(list(settings.activity_log)[-8:]):
        row = log.row(align=True)
        row.label(text=item.level, icon="ERROR" if item.level == "ERROR" else "DOT")
        row.label(text=item.message[:58])


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
        review.label(text=f"Estimated provider charge: {settings.generation_estimated_credits} credits")
    mock_box = layout.box()
    mock_box.label(text="ZERO-COST WORKFLOW TEST", icon="GHOST_ENABLED")
    mock_box.prop(settings, "generation_approved")
    mock = mock_box.column()
    mock.enabled = bool(settings.generation_plan_json and settings.generation_approved and settings.generation_job_status == "NONE")
    mock.scale_y = 1.25
    mock.operator("cozyverse.run_mock_generation", text="START SAFE MOCK JOB", icon="PLAY")
    paid = layout.box()
    paid.alert = settings.generation_live_approved
    paid.label(text="PAID PROVIDER SUBMISSION", icon="ERROR")
    paid.prop(settings, "generation_credit_limit")
    paid.prop(settings, "generation_live_approved")
    submit = paid.column()
    submit.enabled = bool(settings.generation_plan_json and settings.generation_live_approved and settings.generation_job_status == "NONE")
    submit.scale_y = 1.3
    submit.operator("cozyverse.submit_live_generation", text="REVIEW & SUBMIT PAID JOB", icon="URL")
    paid.label(text="Final confirmation dialog required • estimates may change")
    job = layout.box()
    job.label(text="JOB STATUS", icon="SORTTIME")
    job.label(text=f"{settings.generation_job_status.replace('_', ' ').title()} • {settings.generation_job_progress}%")
    if settings.generation_job_id:
        job.label(text=f"ID: {settings.generation_job_id[:32]}")
    row = job.row(align=True)
    row.operator("cozyverse.refresh_generation_job", text="Refresh", icon="FILE_REFRESH")
    row.operator("cozyverse.cancel_generation_job", text="Cancel", icon="X")
    download = job.column()
    download.enabled = settings.generation_job_status == "SUCCEEDED"
    download.operator("cozyverse.download_generation_result", text="DOWNLOAD VALIDATED GLB", icon="IMPORT")
    quarantine = layout.box()
    quarantine.label(text="QUARANTINE REVIEW", icon="LOCKED")
    quarantine.prop(settings, "generation_import_approved")
    importer = quarantine.column()
    importer.enabled = bool(settings.generation_download_path and settings.generation_import_approved)
    importer.operator("cozyverse.import_generation_result", text="IMPORT TO QUARANTINE", icon="IMPORT")
    quarantine.label(text=settings.generation_review_summary)
    quarantine.prop(settings, "generation_promotion_approved")
    promote = quarantine.column()
    promote.enabled = bool(settings.generation_quarantine_name and settings.generation_promotion_approved)
    promote.scale_y = 1.25
    promote.operator("cozyverse.promote_generation_asset", text="PROMOTE TO ASSET FACTORY", icon="ASSET_MANAGER")
    boundary = layout.box()
    boundary.label(text="SAFETY BOUNDARY", icon="LOCKED")
    boundary.label(text="Network work is asynchronous; bpy stays on the main thread")
    boundary.label(text="Only allowlisted HTTPS GLB results up to 100 MB")


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
    note.label(text="Live jobs require fingerprint, budget and final confirmation", icon="LOCKED")
    note.label(text="Keys stay session-only and never enter .blend files")
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
    about.label(text="CozyVerse " + VERSION_LABEL)



def _draw_assets(context: bpy.types.Context, layout: bpy.types.UILayout, settings) -> None:
    for idname, label, icon, closed, function in (
        ("cv_assets_local", "Your local assets", "ASSET_MANAGER", False, lambda box: _draw_asset_library(context, box, settings)),
        ("cv_assets_reference", "From a reference image", "IMAGE_DATA", True, lambda box: _draw_image_to_world(box, settings)),
        ("cv_assets_factory", "3D asset factory", "MESH_ICOSPHERE", True, lambda box: _draw_generate(context, box, settings)),
    ):
        header, body = layout.panel(idname, default_closed=closed)
        header.label(text=label, icon=icon)
        if body is not None:
            function(body)


class CV_PT_Main(bpy.types.Panel):
    bl_idname = "CV_PT_main"
    bl_label = "CozyVerse"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CozyVerse"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        settings = context.scene.cozyverse
        _draw_header(layout, context, settings)
        tab = settings.active_tab
        if tab == "CREATE":
            _draw_create(layout, settings)
        elif tab == "ATMOSPHERE":
            _draw_atmosphere(layout, settings)
        elif tab == "SHOT":
            _draw_shot(layout, context, settings)
        elif tab == "STORY":
            if not _needs_world(layout, settings, "animate it"):
                _draw_story(layout, settings)
        elif tab == "GENERATE":
            _draw_assets(context, layout, settings)
        elif tab == "ACTIVITY":
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
        layout.label(text="ADVANCED PROMPT EDITOR", icon="TEXT")
        layout.label(text="Write naturally across multiple lines.")
        layout.label(text="Press Shift+F5 to return to the 3D View.", icon="INFO")
        layout.separator()
        column = layout.column(align=True)
        column.scale_y = 1.4
        column.operator("cozyverse.use_multiline_prompt", text="USE PROMPT AND RETURN", icon="CHECKMARK")
        layout.label(text="Then choose Build Editable World.", icon="INFO")




class CV_MT_PieMain(bpy.types.Menu):
    bl_idname = "CV_MT_pie_main"
    bl_label = "CozyVerse"

    def draw(self, context: bpy.types.Context) -> None:
        pie = self.layout.menu_pie()
        settings = context.scene.cozyverse
        world = _active_world(settings)
        if world is None:
            # Slots run West, East, South, North, then the four corners.
            pie.separator()
            pie.separator()
            pie.operator("cozyverse.quick_conjure", text="Conjure a World", icon="WORLD_DATA")
            pie.operator("cozyverse.surprise", text="Surprise Me", icon="SHADERFX")
            return
        names = dict(LOOKS)
        icons = {"GOLDEN_HOUR": "LIGHT_SUN", "MOONLIT": "SHADING_RENDERED", "RAINY_CAFE": "MOD_FLUID", "MISTY_DAWN": "LIGHT_AREA", "BLUE_HOUR": "LIGHT_POINT"}
        for look in ("GOLDEN_HOUR", "MOONLIT"):
            pie.operator("cozyverse.set_look", text=names[look], icon=icons[look]).look = look
        pie.operator("cozyverse.conjure", text="Remix Layout", icon="FILE_REFRESH").remix = True
        pie.operator("cozyverse.set_look", text=names["RAINY_CAFE"], icon=icons["RAINY_CAFE"]).look = "RAINY_CAFE"
        for look in ("MISTY_DAWN", "BLUE_HOUR"):
            pie.operator("cozyverse.set_look", text=names[look], icon=icons[look]).look = look
        pie.operator("cozyverse.next_shot", text="Next Shot", icon="CAMERA_DATA")
        pie.operator("cozyverse.toggle_turntable", text="Turntable", icon="ORIENTATION_GIMBAL", depress=_turntable_for(world) is not None)


_CLASSES = (CV_PT_Main, CV_TEXT_PT_Prompt, CV_MT_PieMain)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

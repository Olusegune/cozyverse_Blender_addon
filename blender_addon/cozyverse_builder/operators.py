"""Allowlisted CozyVerse operators for recovery milestone R1."""

from __future__ import annotations

import bpy
import dataclasses
import json
import math
import queue
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from .atmosphere import apply_atmosphere
from .core.atmosphere_spec import AtmosphereValues, PRESETS, deserialize_preset, serialize_preset
from .core.demo_spec import DEFAULT_PROMPT
from .world_builder import build_offline_world
from .materials import sync_color
from .providers.contracts import GenerationPlan, build_plan, validate_budget, validate_download_url
from .providers import runtime as provider_runtime
from .core.reference_spec import analyze_composition, dominant_palette, reference_plan, scan_asset_files, validate_reference_path
from .core.style_spec import STYLE_PRESETS, style_items, styled_prompt
from .core.scene_plan import ScenePlan, parse_plan, proposed_plan
from .core.asset_catalog import AssetRecord, match_assets, record_from_path
from .core.revision_spec import make_revision_preview, plan_fingerprint, redact_log_message
from .core.story_spec import PRESETS as STORY_PRESETS, StoryPlan, build_story_plan


_PROVIDER_RESULTS: queue.SimpleQueue = queue.SimpleQueue()


def _generation_plan(settings) -> GenerationPlan:
    try:
        return GenerationPlan(**json.loads(settings.generation_plan_json))
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Preview a valid provider request first") from exc


def _drain_provider_results():
    while True:
        try:
            scene_name, action, ok, value = _PROVIDER_RESULTS.get_nowait()
        except queue.Empty:
            break
        scene = bpy.data.scenes.get(scene_name)
        if scene is None or not hasattr(scene, "cozyverse"):
            continue
        settings = scene.cozyverse
        if not ok:
            settings.generation_status = str(value)[:500]
            if action == "SUBMIT":
                settings.generation_job_status = "FAILED"
            continue
        if action == "SUBMIT":
            settings.generation_job_id = value
            settings.generation_job_status = "PENDING"
            settings.generation_job_progress = 0
            settings.generation_status = f"Provider accepted job {value[:18]}…"
        elif action == "POLL":
            status = value.get("status", "UNKNOWN")
            settings.generation_job_status = status if status in {"PENDING", "IN_PROGRESS", "SUCCEEDED", "FAILED", "CANCELED"} else "FAILED"
            settings.generation_job_progress = max(0, min(100, int(value.get("progress") or 0)))
            url = value.get("download_url") or ""
            if url:
                try:
                    settings.generation_result_url = validate_download_url(_generation_plan(settings).provider, url)
                except ValueError as exc:
                    settings.generation_job_status = "FAILED"
                    settings.generation_status = f"Unsafe provider result rejected: {exc}"
                    continue
            settings.generation_status = f"Job {settings.generation_job_status.replace('_', ' ').title()} — {settings.generation_job_progress}%"
        elif action == "CANCEL":
            settings.generation_job_status = "CANCELED"
            settings.generation_status = "Provider job canceled before import; the scene was unchanged"
        elif action == "DOWNLOAD":
            settings.generation_download_path = str(value)
            settings.generation_status = "Validated GLB downloaded; review and approve quarantine import"
    return 0.25 if any(thread.name.startswith("CozyVerseProvider") and thread.is_alive() for thread in threading.enumerate()) else None


def _start_provider_work(scene_name: str, action: str, function, *args) -> None:
    def worker():
        try:
            result = function(*args)
            _PROVIDER_RESULTS.put((scene_name, action, True, result))
        except Exception as exc:
            _PROVIDER_RESULTS.put((scene_name, action, False, str(exc)))

    threading.Thread(target=worker, name=f"CozyVerseProvider-{action}", daemon=True).start()
    if not bpy.app.timers.is_registered(_drain_provider_results):
        bpy.app.timers.register(_drain_provider_results, first_interval=0.1)


def _prompt_from_settings(settings) -> str:
    if settings.prompt_text is not None:
        multiline = settings.prompt_text.as_string().strip()
        if multiline:
            return multiline[:4000]
    return settings.prompt.strip()[:4000]


def _plan_prompt(settings) -> str:
    """The prompt a plan is built from: what the user wrote plus the chosen style's directive.

    The sidebar keeps the user's own words; the style direction is added here, once.
    """
    base = _prompt_from_settings(settings)
    if not base or "Style direction:" in base:
        return base
    return styled_prompt(base, settings.preset)[:4000]


def _compose_prompt(setting: str, subject: str, mood: str, details: str, avoid: str) -> str:
    parts = []
    if setting.strip():
        parts.append(f"Create {setting.strip()}")
    if subject.strip():
        parts.append(f"The focal subject is {subject.strip()}")
    if mood.strip():
        parts.append(f"Use {mood.strip()}")
    if details.strip():
        parts.append(f"Include {details.strip()}")
    if avoid.strip():
        parts.append(f"Avoid {avoid.strip()}")
    return ". ".join(parts).rstrip(".") + "." if parts else ""


def _plan_from_settings(settings) -> ScenePlan:
    plan = ScenePlan(
        "1.0",
        settings.plan_title.strip(),
        settings.plan_world_type,
        settings.preset,
        settings.plan_base_shape,
        settings.plan_architecture_count,
        settings.plan_prop_count,
        settings.plan_vegetation_count,
        settings.plan_character_count,
        settings.plan_include_road,
        settings.plan_camera_type,
        _plan_prompt(settings),
    )
    plan.validate()
    return plan


def _world_objects(collection):
    objects = list(collection.objects)
    for child in collection.children:
        objects.extend(_world_objects(child))
    return objects


def _known_secrets(context: bpy.types.Context) -> tuple[str, ...]:
    secrets = getattr(context.window_manager, "cozyverse_secrets", None)
    if secrets is None:
        return ()
    return tuple(getattr(secrets, name, "") for name in ("api_key", "tripo_api_key", "meshy_api_key"))


def _log_activity(context: bpy.types.Context, level: str, message: str) -> None:
    settings = context.scene.cozyverse
    item = settings.activity_log.add()
    item.timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    item.level = level[:16]
    item.message = redact_log_message(message, _known_secrets(context))
    while len(settings.activity_log) > 50:
        settings.activity_log.remove(0)


def _atmosphere_owned(obj) -> bool:
    """Objects the Mood tab moves or rescales on purpose (sun, rain, snow, wind, fog) are never hand edits."""
    return bool(obj.get("cv_weather")) or obj.name.startswith("CV_Sun")


def _manual_state(world) -> tuple[int, int]:
    protected = 0
    edited = 0
    for obj in _world_objects(world) if world is not None else ():
        protected += bool(obj.get("cv_locked"))
        baseline = obj.get("cv_generated_transform")
        current = json.dumps([round(value, 6) for value in (*obj.location, *obj.rotation_euler, *obj.scale)])
        edited += bool(baseline and baseline != current and not _atmosphere_owned(obj))
    return protected, edited


def _refresh_revision_preview(context: bpy.types.Context, plan: ScenePlan):
    settings = context.scene.cozyverse
    source = bpy.data.collections.get(settings.active_world_name)
    old_plan = None
    objects = []
    if source is not None and source.get("cv_managed"):
        objects = _world_objects(source)
        try:
            old_plan = json.loads(source.get("cv_scene_plan") or "null")
        except (TypeError, json.JSONDecodeError):
            old_plan = None
    protected, edited = _manual_state(source)
    new_plan = json.loads(plan.canonical_json())
    preview = make_revision_preview(old_plan, new_plan, source.name if source else "", len(objects), protected, edited)
    settings.revision_preview_json = preview.canonical_json()
    settings.revision_fingerprint = preview.plan_fingerprint
    settings.revision_source_world = preview.source_world
    settings.revision_changed = len(preview.changed_fields)
    settings.revision_created = preview.created_objects
    settings.revision_deleted = preview.deleted_objects
    settings.revision_skipped = preview.skipped_objects
    settings.revision_protected = preview.protected_objects
    settings.revision_manual_edits = preview.manually_edited_objects
    return preview


def _atmosphere_from_settings(settings) -> AtmosphereValues:
    return AtmosphereValues(
        settings.time_hour,
        settings.sun_intensity,
        settings.warmth,
        settings.ambient_intensity,
        settings.interior_intensity,
        settings.weather,
        settings.rain_amount,
        settings.exposure,
        settings.practical_temperature,
        settings.practical_lights,
        settings.fog_amount,
        settings.wind_amount,
        settings.wetness_amount,
        settings.snow_amount,
        settings.season,
        settings.weather_quality,
    )


def _set_atmosphere_values(settings, values: AtmosphereValues, preset: str = "CUSTOM") -> None:
    settings.atmosphere_preset = preset if preset in PRESETS else "CUSTOM"
    settings.time_hour = values.time_hour
    settings.sun_intensity = values.sun_intensity
    settings.warmth = values.warmth
    settings.ambient_intensity = values.ambient_intensity
    settings.interior_intensity = values.interior_intensity
    settings.weather = values.weather
    settings.rain_amount = values.rain_amount
    settings.exposure = values.exposure
    settings.practical_temperature = values.practical_temperature
    settings.practical_lights = values.practical_lights
    settings.fog_amount = values.fog_amount
    settings.wind_amount = values.wind_amount
    settings.wetness_amount = values.wetness_amount
    settings.snow_amount = values.snow_amount
    settings.season = values.season
    settings.weather_quality = values.weather_quality


def _has_animation(value) -> bool:
    animation = getattr(value, "animation_data", None)
    if not animation:
        return False
    if animation.action or animation.nla_tracks:
        return True
    if animation.drivers:
        # CozyVerse's own ambient-life and build-up drivers act on delta transforms and must not block Story.
        return not (value.get("cv_life") or value.get("cv_buildup"))
    return False


def _story_candidates(world, preset: str):
    characters, foliage, precipitation, lights, skipped = [], [], [], [], 0
    for obj in _world_objects(world):
        category = None
        if obj.name.startswith("CV_Character_") and obj.type == "MESH":
            category = characters
        elif obj.name.endswith("_Leaves") and obj.type == "MESH":
            category = foliage
        elif preset == "RAINY_EVENING" and obj.name.startswith("CV_Rain_Preview"):
            category = precipitation
        elif obj.name.startswith("CV_Interior_") and isinstance(getattr(obj, "data", None), bpy.types.Light):
            category = lights
        if category is None:
            continue
        if obj.get("cv_locked") or _has_animation(obj) or _has_animation(getattr(obj, "data", None)):
            skipped += 1
        else:
            category.append(obj)
    return characters, foliage, precipitation, lights, skipped


def _story_id_for_world(world) -> str:
    return next((str(obj.get("cv_story_id")) for obj in _world_objects(world) if obj.name.startswith("CV_Story_") and obj.get("cv_story_id")), "")


def _current_story_plan(settings, world) -> tuple[StoryPlan, tuple]:
    candidates = _story_candidates(world, settings.story_preset)
    characters, foliage, precipitation, lights, skipped = candidates
    plan = build_story_plan(
        settings.story_preset,
        world.name,
        settings.story_start_frame,
        settings.story_end_frame,
        len(characters),
        len(foliage),
        len(precipitation),
        len(lights),
        skipped,
    )
    return plan, candidates


def _tag_action(owner, story_id: str, name: str):
    animation = owner.animation_data
    action = animation.action if animation else None
    if action is not None:
        action.name = f"CV_STORY_{story_id}_{name}"[:63]
        action["cv_story_id"] = story_id
        action["cv_managed"] = True
    return action


def _animate_object(obj, story_id: str, frames: tuple[int, int, int], data_path: str, index: int, values: tuple[float, float, float]) -> None:
    original = list(getattr(obj, data_path))
    obj[f"cv_story_original_{data_path}"] = json.dumps(original)
    for frame, value in zip(frames, values):
        getattr(obj, data_path)[index] = value
        obj.keyframe_insert(data_path=data_path, index=index, frame=frame, group="CozyVerse Story")
    getattr(obj, data_path)[index] = original[index]
    obj["cv_story_id"] = story_id
    _tag_action(obj, story_id, obj.name)


def _animate_light(obj, story_id: str, frames: tuple[int, int, int], pulse: float) -> None:
    light = obj.data
    original = float(light.energy)
    light["cv_story_original_energy"] = original
    for frame, value in zip(frames, (original, original * (1.0 + pulse), original)):
        light.energy = value
        light.keyframe_insert(data_path="energy", frame=frame, group="CozyVerse Story")
    light.energy = original
    light["cv_story_id"] = story_id
    _tag_action(light, story_id, obj.name)


def _remove_story_action(owner, story_id: str) -> None:
    animation = getattr(owner, "animation_data", None)
    action = animation.action if animation else None
    if action is not None and action.get("cv_story_id") == story_id:
        animation.action = None
        if action.users == 0:
            bpy.data.actions.remove(action)


class CV_OT_PreviewStory(bpy.types.Operator):
    bl_idname = "cozyverse.preview_story"
    bl_label = "Preview Story Plan"
    bl_description = "Count affected objects and keyframes without changing the scene"

    def execute(self, context):
        settings = context.scene.cozyverse
        world = bpy.data.collections.get(settings.active_world_name)
        if world is None or not world.get("cv_managed"):
            settings.story_status = "Build or select a CozyVerse world first"
            return {"CANCELLED"}
        settings.story_active_id = _story_id_for_world(world)
        if settings.story_active_id:
            settings.story_status = "Clear the active Story before preparing another"
            return {"CANCELLED"}
        try:
            plan, _ = _current_story_plan(settings, world)
        except ValueError as exc:
            settings.story_status = str(exc)
            return {"CANCELLED"}
        settings.story_preview_json = plan.canonical_json()
        settings.story_fingerprint = plan.fingerprint()
        settings.story_target_count = plan.target_count
        settings.story_skipped_count = plan.skipped_count
        settings.story_keyframe_count = plan.keyframe_count
        settings.story_approved = False
        settings.story_status = f"Preview ready: {plan.target_count} targets, {plan.keyframe_count} keyframes, {plan.skipped_count} skipped"
        _log_activity(context, "STORY_REVIEW", settings.story_status)
        return {"FINISHED"}


class CV_OT_ApplyStory(bpy.types.Operator):
    bl_idname = "cozyverse.apply_story"
    bl_label = "Apply Story Moment"
    bl_description = "Create reviewed editable Blender Actions and keyframes"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.cozyverse
        world = bpy.data.collections.get(settings.active_world_name)
        active_story = _story_id_for_world(world) if world is not None else ""
        settings.story_active_id = active_story
        if world is None or not settings.story_approved or active_story:
            settings.story_status = "Preview and approve a Story plan for the active world"
            return {"CANCELLED"}
        plan, candidates = _current_story_plan(settings, world)
        if plan.fingerprint() != settings.story_fingerprint or plan.canonical_json() != settings.story_preview_json:
            settings.story_approved = False
            settings.story_status = "Story targets changed after preview; preview again"
            return {"CANCELLED"}
        story_id = plan.fingerprint()[:12]
        preset = STORY_PRESETS[plan.preset]
        frames = (plan.start_frame, plan.midpoint, plan.end_frame)
        characters, foliage, precipitation, lights, _ = candidates
        for index, obj in enumerate(characters):
            base = obj.location.z
            amplitude = preset.character_motion * (1.0 if index % 2 == 0 else -0.65)
            _animate_object(obj, story_id, frames, "location", 2, (base, base + amplitude, base))
        for index, obj in enumerate(foliage):
            base = obj.rotation_euler.y
            amplitude = math.radians(preset.foliage_sway_degrees) * (1.0 if index % 2 == 0 else -1.0)
            _animate_object(obj, story_id, frames, "rotation_euler", 1, (base, base + amplitude, base))
        for obj in precipitation:
            base = obj.location.z
            _animate_object(obj, story_id, frames, "location", 2, (base, base - preset.precipitation_travel, base))
        for obj in lights:
            _animate_light(obj, story_id, frames, preset.light_pulse)
        story_collection = bpy.data.collections.new(f"CV_STORY_{story_id}")
        world.children.link(story_collection)
        controller = bpy.data.objects.new(f"CV_Story_{plan.preset.title()}", None)
        story_collection.objects.link(controller)
        controller.empty_display_type = "CIRCLE"
        controller["cv_story_id"] = story_id
        controller["cv_story_plan"] = plan.canonical_json()
        controller["cv_world_root"] = world.name
        controller["cv_managed"] = True
        controller["cv_original_frame_start"] = context.scene.frame_start
        controller["cv_original_frame_end"] = context.scene.frame_end
        controller["cv_original_weather"] = settings.weather
        controller["cv_original_rain_amount"] = settings.rain_amount
        story_collection["cv_story_id"] = story_id
        story_collection["cv_managed"] = True
        context.scene.frame_start = plan.start_frame
        context.scene.frame_end = plan.end_frame
        if plan.preset == "RAINY_EVENING":
            settings.weather = "RAIN"
            settings.rain_amount = max(55.0, settings.rain_amount)
        settings.story_active_id = story_id
        settings.story_approved = False
        settings.story_status = f"{preset.label} applied as editable Blender keyframes"
        _log_activity(context, "STORY_APPLY", settings.story_status)
        if context.area is not None and context.area.type == "VIEW_3D":
            bpy.ops.ed.undo_push(message="Apply CozyVerse Story")
        return {"FINISHED"}


class CV_OT_ClearStory(bpy.types.Operator):
    bl_idname = "cozyverse.clear_story"
    bl_label = "Clear Active Story"
    bl_description = "Remove only the active CozyVerse Story actions and restore its original values"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.cozyverse
        world = bpy.data.collections.get(settings.active_world_name)
        story_id = _story_id_for_world(world) if world is not None else ""
        settings.story_active_id = story_id
        if not story_id or world is None:
            settings.story_status = "There is no active Story to clear"
            return {"CANCELLED"}
        controller = next((obj for obj in _world_objects(world) if obj.get("cv_story_id") == story_id and obj.name.startswith("CV_Story_")), None)
        for obj in _world_objects(world):
            if obj.get("cv_story_id") == story_id:
                for data_path in ("location", "rotation_euler"):
                    key = f"cv_story_original_{data_path}"
                    if key in obj:
                        setattr(obj, data_path, json.loads(obj[key]))
                        del obj[key]
                _remove_story_action(obj, story_id)
                if "cv_story_id" in obj and obj is not controller:
                    del obj["cv_story_id"]
            data = getattr(obj, "data", None)
            if data is not None and data.get("cv_story_id") == story_id:
                if "cv_story_original_energy" in data:
                    data.energy = float(data["cv_story_original_energy"])
                    del data["cv_story_original_energy"]
                _remove_story_action(data, story_id)
                del data["cv_story_id"]
        if controller is not None:
            context.scene.frame_start = int(controller.get("cv_original_frame_start", context.scene.frame_start))
            context.scene.frame_end = int(controller.get("cv_original_frame_end", context.scene.frame_end))
            settings.weather = controller.get("cv_original_weather", settings.weather)
            settings.rain_amount = float(controller.get("cv_original_rain_amount", settings.rain_amount))
            owner = controller.users_collection[0] if controller.users_collection else None
            bpy.data.objects.remove(controller, do_unlink=True)
            if owner is not None:
                if owner.name in world.children:
                    world.children.unlink(owner)
                bpy.data.collections.remove(owner)
        settings.story_active_id = ""
        settings.story_preview_json = ""
        settings.story_fingerprint = ""
        settings.story_status = "Story cleared; original static values restored"
        _log_activity(context, "STORY_CLEAR", settings.story_status)
        return {"FINISHED"}


class CV_OT_StartOnboarding(bpy.types.Operator):
    bl_idname = "cozyverse.start_onboarding"
    bl_label = "Start Guided Example"
    bl_description = "Load a safe sample prompt and prepare its scene plan"

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        settings.onboarding_complete = True
        bpy.ops.cozyverse.apply_prompt_template(template="VILLAGE")
        return bpy.ops.cozyverse.prepare_scene_plan()


class CV_OT_DismissOnboarding(bpy.types.Operator):
    bl_idname = "cozyverse.dismiss_onboarding"
    bl_label = "Skip Introduction"

    def execute(self, context: bpy.types.Context):
        context.scene.cozyverse.onboarding_complete = True
        return {"FINISHED"}


class CV_OT_PrepareScenePlan(bpy.types.Operator):
    bl_idname = "cozyverse.prepare_scene_plan"
    bl_label = "Review World Plan"
    bl_description = "Create an editable validated plan without modifying the Blender scene"

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        prompt = _prompt_from_settings(settings)
        if not prompt:
            settings.last_error = "World description is empty"
            settings.recovery_hint = "Open Prompt Composer or choose a Quick Start template."
            settings.status = settings.last_error
            return {"CANCELLED"}
        plan = dataclasses.replace(proposed_plan(prompt, settings.preset), prompt=_plan_prompt(settings))
        settings.plan_title = plan.title
        settings.plan_world_type = plan.world_type
        settings.plan_base_shape = plan.base_shape
        settings.plan_camera_type = plan.camera_type
        settings.plan_architecture_count = plan.architecture_count
        settings.plan_prop_count = plan.prop_count
        settings.plan_vegetation_count = plan.vegetation_count
        settings.plan_character_count = plan.character_count
        settings.plan_include_road = plan.include_road
        settings.scene_plan_json = plan.canonical_json()
        _refresh_revision_preview(context, plan)
        settings.plan_approved = False
        settings.workflow_step = "REVIEW"
        settings.operation_progress = 0.35
        settings.last_error = ""
        settings.recovery_hint = "Review every section, approve the plan, then build a new version."
        settings.status = "Plan ready for review; no objects were created"
        _log_activity(context, "REVIEW", f"Prepared revision preview for {settings.revision_source_world or 'new world'}")
        return {"FINISHED"}


class CV_OT_BackToDescription(bpy.types.Operator):
    bl_idname = "cozyverse.back_to_description"
    bl_label = "Back to Description"

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        settings.workflow_step = "DESCRIBE"
        settings.plan_approved = False
        settings.operation_progress = 0.0
        settings.status = "Update the description, then review a new plan"
        return {"FINISHED"}


class CV_OT_RefreshRevisionPreview(bpy.types.Operator):
    bl_idname = "cozyverse.refresh_revision_preview"
    bl_label = "Refresh Revision Preview"
    bl_description = "Recalculate created, changed, deleted, preserved, locked, and manually edited content without changing the scene"

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        try:
            plan = _plan_from_settings(settings)
            settings.scene_plan_json = plan.canonical_json()
            preview = _refresh_revision_preview(context, plan)
        except (TypeError, ValueError) as exc:
            settings.last_error = f"Preview stopped: {exc}"
            _log_activity(context, "ERROR", settings.last_error)
            return {"CANCELLED"}
        settings.plan_approved = False
        settings.last_error = ""
        settings.status = "Revision preview refreshed; review it before approval"
        _log_activity(context, "REVIEW", f"Revision preview: {len(preview.changed_fields)} changed fields, {preview.created_objects} created, 0 deleted")
        return {"FINISHED"}


class CV_OT_CancelRevision(bpy.types.Operator):
    bl_idname = "cozyverse.cancel_revision"
    bl_label = "Cancel Revision"
    bl_description = "Discard the pending preview without changing any Blender objects"

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        settings.revision_preview_json = ""
        settings.revision_fingerprint = ""
        settings.plan_approved = False
        settings.workflow_step = "DESCRIBE"
        settings.operation_progress = 0.0
        settings.status = "Revision cancelled; the scene was not changed"
        _log_activity(context, "CANCEL", "Revision cancelled before apply; no scene mutation")
        return {"FINISHED"}


class CV_OT_BuildApprovedPlan(bpy.types.Operator):
    bl_idname = "cozyverse.build_approved_plan"
    bl_label = "Build Approved Plan"
    bl_description = "Build a new version from the reviewed plan without overwriting previous worlds"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        if not settings.plan_approved:
            settings.last_error = "The scene plan has not been approved"
            settings.recovery_hint = "Review the plan and enable ‘I reviewed this plan’."
            settings.status = settings.last_error
            return {"CANCELLED"}
        try:
            plan = _plan_from_settings(settings)
            current_plan_json = plan.canonical_json()
            current_fingerprint = plan_fingerprint(current_plan_json)
            if not settings.revision_preview_json or current_fingerprint != settings.revision_fingerprint:
                settings.scene_plan_json = current_plan_json
                _refresh_revision_preview(context, plan)
                settings.plan_approved = False
                settings.last_error = "The plan changed after preview"
                settings.recovery_hint = "Review the refreshed revision summary, approve it again, then build."
                settings.status = settings.last_error
                _log_activity(context, "BLOCKED", settings.last_error)
                return {"CANCELLED"}
            settings.scene_plan_json = current_plan_json
            settings.operation_progress = 0.55
            settings.status = "Building a new editable world version..."
            source_world = settings.revision_source_world
            world = build_offline_world(context.scene, settings, plan.prompt, json.loads(settings.scene_plan_json), variation=settings.variation)
            # Versions share one stage, so earlier ones are hidden (never deleted); the Activity tab brings them back.
            hidden = 0
            for other in bpy.data.collections:
                if other is not world and other.get("cv_managed") and other.name.startswith("CV_WORLD") and not other.hide_viewport:
                    other.hide_viewport = True
                    other.hide_render = True
                    hidden += 1
            world["cv_revision_source"] = source_world
            world["cv_revision_preview"] = settings.revision_preview_json
            world["cv_revision_fingerprint"] = settings.revision_fingerprint
            settings.operation_progress = 1.0
            settings.workflow_step = "BUILT"
            settings.active_world_name = world.name
            settings.story_active_id = ""
            settings.last_demo_prompt = plan.prompt
            settings.last_error = ""
            settings.recovery_hint = "Use Select & Frame to inspect it. Previous versions remain untouched."
            settings.status = f"World ready: {world.name}" + (f" ({hidden} earlier version{'s' if hidden != 1 else ''} hidden)" if hidden else "")
            _log_activity(context, "SUCCESS", f"Built {world.name} from approved revision preview; source={source_world or 'new'}")
            self.report({"INFO"}, settings.status)
            return {"FINISHED"}
        except (ValueError, RuntimeError) as exc:
            settings.last_error = f"Build stopped: {exc}"
            settings.recovery_hint = "Return to the plan, correct invalid values, and try again."
            settings.operation_progress = 0.35
            settings.status = settings.last_error
            _log_activity(context, "ERROR", settings.last_error)
            self.report({"ERROR"}, settings.last_error)
            return {"CANCELLED"}


class CV_OT_SelectWorld(bpy.types.Operator):
    bl_idname = "cozyverse.select_world"
    bl_label = "Select & Frame World"
    bl_description = "Select all objects in a CozyVerse world and frame them when run from a 3D View"

    world_name: StringProperty(name="World")

    def execute(self, context: bpy.types.Context):
        world = bpy.data.collections.get(self.world_name or context.scene.cozyverse.active_world_name)
        if world is None or not world.get("cv_managed"):
            context.scene.cozyverse.status = "World is missing; choose another saved version"
            return {"CANCELLED"}
        bpy.ops.object.select_all(action="DESELECT")
        objects = _world_objects(world)
        # Frame the visible geometry only; the camera and lights sit far outside the diorama.
        meshes = [obj for obj in objects if obj.type == "MESH" and not obj.get("cv_weather")]
        for obj in objects:
            obj.hide_set(False)
            obj.select_set(obj in meshes or not meshes)
        if objects:
            context.view_layer.objects.active = (meshes or objects)[0]
        context.scene.cozyverse.active_world_name = world.name
        context.scene.cozyverse.story_active_id = _story_id_for_world(world)
        context.scene.cozyverse.story_status = "Active Story loaded" if context.scene.cozyverse.story_active_id else "No Story applied to this world"
        context.scene["cv_active_world"] = world.name
        saved_atmosphere = world.get("cv_atmosphere_values")
        if saved_atmosphere:
            try:
                _set_atmosphere_values(
                    context.scene.cozyverse,
                    deserialize_preset(saved_atmosphere),
                    world.get("cv_atmosphere_preset", "CUSTOM"),
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                context.scene.cozyverse.recovery_hint = "This world's older atmosphere data could not be loaded; save a new look to replace it."
        if context.area is not None and context.area.type == "VIEW_3D" and objects:
            bpy.ops.view3d.view_selected(use_all_regions=False)
            for obj in objects:
                obj.select_set(True)
        context.scene.cozyverse.status = f"Selected {world.name}: {len(objects)} objects"
        return {"FINISHED"}


class CV_OT_ArchiveWorld(bpy.types.Operator):
    bl_idname = "cozyverse.archive_world"
    bl_label = "Hide World Version"
    bl_description = "Hide this world version without deleting it"
    bl_options = {"REGISTER", "UNDO"}

    world_name: StringProperty(name="World")
    hidden: BoolProperty(name="Hidden", default=True)

    def execute(self, context: bpy.types.Context):
        world = bpy.data.collections.get(self.world_name or context.scene.cozyverse.active_world_name)
        if world is None or not world.get("cv_managed"):
            return {"CANCELLED"}
        world.hide_viewport = self.hidden
        world.hide_render = self.hidden
        context.scene.cozyverse.status = f"{world.name} {'hidden' if self.hidden else 'visible'}; no data was deleted"
        return {"FINISHED"}


class CV_OT_InspectManualEdits(bpy.types.Operator):
    bl_idname = "cozyverse.inspect_manual_edits"
    bl_label = "Check Manual Edits"
    bl_description = "Report generated objects whose transforms differ from their build snapshot"

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        world = bpy.data.collections.get(settings.active_world_name)
        if world is None:
            settings.status = "No active CozyVerse world to inspect"
            return {"CANCELLED"}
        edited = 0
        locked = 0
        for obj in _world_objects(world):
            locked += bool(obj.get("cv_locked"))
            baseline = obj.get("cv_generated_transform")
            current = json.dumps([round(value, 6) for value in (*obj.location, *obj.rotation_euler, *obj.scale)])
            edited += bool(baseline and baseline != current and not _atmosphere_owned(obj))
        settings.status = f"Manual-edit check: {edited} changed, {locked} locked; rebuilds create new versions"
        settings.recovery_hint = "Edited and locked objects remain untouched because CozyVerse never overwrites an existing world."
        return {"FINISHED"}


class CV_OT_LockSelectedObjects(bpy.types.Operator):
    bl_idname = "cozyverse.lock_selected_objects"
    bl_label = "Protect Selected"
    bl_description = "Mark selected objects as explicitly protected CozyVerse content"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        selected = [obj for obj in context.selected_objects if obj.get("cv_managed")]
        if not selected:
            return {"CANCELLED"}
        for obj in selected:
            obj["cv_locked"] = True
        context.scene.cozyverse.status = f"Protected {len(selected)} selected object(s)"
        return {"FINISHED"}


class CV_OT_CreateCheckpoint(bpy.types.Operator):
    bl_idname = "cozyverse.create_checkpoint"
    bl_label = "Create Recovery Checkpoint"
    bl_description = "Save a timestamped copy of the current .blend without changing the active file"

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        if not bpy.data.filepath:
            settings.status = "Save the .blend file once before creating a checkpoint"
            settings.recovery_hint = "Use File > Save As, then create the checkpoint again."
            _log_activity(context, "BLOCKED", settings.status)
            return {"CANCELLED"}
        current = Path(bpy.data.filepath)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        checkpoint = current.with_name(f"{current.stem}.cv-checkpoint-{stamp}{current.suffix}")
        suffix = 2
        while checkpoint.exists():
            checkpoint = current.with_name(f"{current.stem}.cv-checkpoint-{stamp}-{suffix}{current.suffix}")
            suffix += 1
        try:
            bpy.ops.wm.save_as_mainfile(filepath=str(checkpoint), copy=True)
        except RuntimeError as exc:
            settings.status = f"Checkpoint failed: {exc}"
            settings.recovery_hint = "Confirm the project folder is writable and try again."
            _log_activity(context, "ERROR", settings.status)
            return {"CANCELLED"}
        settings.checkpoint_path = str(checkpoint)
        settings.status = f"Recovery checkpoint created: {checkpoint.name}"
        settings.recovery_hint = "Use File > Open to restore this copy if a later operation fails."
        _log_activity(context, "CHECKPOINT", f"Created recovery checkpoint {checkpoint.name}")
        return {"FINISHED"}


class CV_OT_CreateLocalDemo(bpy.types.Operator):
    bl_idname = "cozyverse.create_local_demo"
    bl_label = "Build World"
    bl_description = "Build a new editable miniature world locally without an AI or paid service"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        prompt = _plan_prompt(settings)
        if not prompt:
            settings.status = "Add a world description before building"
            self.report({"WARNING"}, settings.status)
            return {"CANCELLED"}
        try:
            settings.status = "Building editable offline world..."
            world = build_offline_world(context.scene, settings, prompt)
            settings.last_demo_prompt = prompt
            settings.active_world_name = world.name
            settings.story_active_id = ""
            settings.workflow_step = "BUILT"
            settings.operation_progress = 1.0
            settings.status = f"World ready: {world.name}"
            self.report({"INFO"}, settings.status)
            return {"FINISHED"}
        except Exception as exc:
            settings.status = f"Build failed: {exc}"
            self.report({"ERROR"}, settings.status)
            return {"CANCELLED"}


class CV_OT_EditMultilinePrompt(bpy.types.Operator):
    bl_idname = "cozyverse.edit_multiline_prompt"
    bl_label = "Edit Multiline Prompt"
    bl_description = "Open a Blender Text datablock for a longer world description"

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        text = settings.prompt_text or bpy.data.texts.get("CV_World_Prompt")
        if text is None:
            text = bpy.data.texts.new("CV_World_Prompt")
            text.write(settings.prompt or DEFAULT_PROMPT)
        settings.prompt_text = text
        if context.area is None:
            settings.status = "Multiline prompt created; open CV_World_Prompt in a Text Editor"
            return {"FINISHED"}
        context.area.type = "TEXT_EDITOR"
        context.space_data.text = text
        settings.status = "Editing CV_World_Prompt; press Shift+F5 to return to 3D View"
        self.report({"INFO"}, settings.status)
        return {"FINISHED"}


class CV_OT_PromptComposer(bpy.types.Operator):
    bl_idname = "cozyverse.prompt_composer"
    bl_label = "Prompt Composer"
    bl_description = "Compose a detailed prompt in a bounded dialog without leaving the 3D View"

    setting: StringProperty(name="Setting")
    subject: StringProperty(name="Focal Subject")
    mood: StringProperty(name="Mood and Time")
    details: StringProperty(name="Must Include")
    avoid: StringProperty(name="Avoid")
    style: EnumProperty(name="Visual Style", items=style_items())

    def invoke(self, context: bpy.types.Context, _event):
        settings = context.scene.cozyverse
        self.setting = settings.prompt_setting
        self.subject = settings.prompt_subject
        self.mood = settings.prompt_mood
        self.details = settings.prompt_details
        self.avoid = settings.prompt_avoid
        self.style = settings.preset
        try:
            return context.window_manager.invoke_props_dialog(self, width=620, confirm_text="Apply Prompt")
        except TypeError:
            return context.window_manager.invoke_props_dialog(self, width=620)

    def draw(self, _context: bpy.types.Context) -> None:
        layout = self.layout
        intro = layout.box()
        intro.label(text="Build a clear world description", icon="TEXT")
        intro.label(text="Complete only the fields that matter. Cancel closes this dialog without changes.")
        fields = layout.column(align=True)
        fields.prop(self, "setting")
        fields.prop(self, "subject")
        fields.prop(self, "mood")
        fields.prop(self, "details")
        fields.prop(self, "avoid")
        style_box = layout.box()
        style_box.label(text="STYLE STUDIO", icon="BRUSH_DATA")
        style_box.prop(self, "style")
        preset = STYLE_PRESETS.get(self.style)
        if preset:
            style_box.label(text=preset.description)

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        prompt = _compose_prompt(self.setting, self.subject, self.mood, self.details, self.avoid)
        if not prompt:
            self.report({"WARNING"}, "Add at least one prompt detail")
            return {"CANCELLED"}
        settings.prompt_setting = self.setting
        settings.prompt_subject = self.subject
        settings.prompt_mood = self.mood
        settings.prompt_details = self.details
        settings.prompt_avoid = self.avoid
        settings.preset = self.style
        settings.prompt = prompt[:4000]
        settings.prompt_text = None
        settings.workflow_step = "DESCRIBE"
        settings.plan_approved = False
        settings.status = "Prompt composed and ready to build"
        return {"FINISHED"}


class CV_OT_ApplyPromptTemplate(bpy.types.Operator):
    bl_idname = "cozyverse.apply_prompt_template"
    bl_label = "Apply Prompt Template"
    bl_description = "Start from a curated world-description template"

    template: EnumProperty(
        items=(
            ("VILLAGE", "Village", "Cozy miniature village"),
            ("CITY", "City", "Stylized neighborhood block"),
            ("CAFE", "Cafe", "Intimate miniature cafe"),
            ("NATURE", "Nature", "Miniature natural landscape"),
            ("FANTASY", "Fantasy", "Whimsical fantasy settlement"),
            ("HISTORICAL", "Historical", "Period-inspired streetscape"),
            ("RETRO_SCIFI", "Retro Sci-Fi", "Optimistic analog-future outpost"),
        )
    )

    def execute(self, context: bpy.types.Context):
        templates = {
            "VILLAGE": ("a tiny village on a miniature diorama base", "a welcoming town square", "cozy golden-hour lighting", "small homes, paths, trees and story props", "photorealism and modern vehicles"),
            "CITY": ("a stylized neighborhood city block", "a colorful corner shop", "warm dusk lighting", "a road, signs, plants and street furniture", "dense skyscrapers and excessive traffic"),
            "CAFE": ("an intimate miniature cafe scene", "a warmly lit cafe storefront", "rainy evening ambience", "outdoor tables, plants and glowing windows", "crowds and oversized furniture"),
            "NATURE": ("a miniature natural landscape", "a winding stream and hero tree", "soft morning light", "rocks, layered vegetation and a small path", "buildings and urban clutter"),
            "FANTASY": ("a whimsical fantasy settlement", "a tiny wizard workshop", "magical twilight", "lanterns, unusual plants and curved architecture", "realistic modern objects"),
            "HISTORICAL": ("a period-inspired miniature streetscape", "a traditional market building", "soft late-afternoon light", "era-appropriate stalls, paths and vegetation", "modern signage and vehicles"),
            "RETRO_SCIFI": ("a miniature lunar service station", "a rounded modular workshop", "cinematic alien dusk", "antenna arrays, a landing pad, maintenance rover and illuminated signs", "modern cars and cyberpunk neon clutter"),
        }
        settings = context.scene.cozyverse
        setting, subject, mood, details, avoid = templates[self.template]
        settings.prompt_setting = setting
        settings.prompt_subject = subject
        settings.prompt_mood = mood
        settings.prompt_details = details
        settings.prompt_avoid = avoid
        style_map = {"FANTASY": "COZY_FANTASY", "NATURE": "SOLARPUNK", "RETRO_SCIFI": "RETRO_SCIFI"}
        if self.template in style_map:
            settings.preset = style_map[self.template]
        settings.prompt = _compose_prompt(setting, subject, mood, details, avoid)
        settings.prompt_text = None
        settings.workflow_step = "DESCRIBE"
        settings.plan_approved = False
        settings.status = f"{self.template.title()} prompt template applied"
        return {"FINISHED"}


class CV_OT_PastePrompt(bpy.types.Operator):
    bl_idname = "cozyverse.paste_prompt"
    bl_label = "Paste Prompt"
    bl_description = "Use text currently stored in the system clipboard"

    def execute(self, context: bpy.types.Context):
        value = context.window_manager.clipboard.strip()
        if not value:
            self.report({"WARNING"}, "Clipboard does not contain prompt text")
            return {"CANCELLED"}
        context.scene.cozyverse.prompt = value[:4000]
        context.scene.cozyverse.prompt_text = None
        context.scene.cozyverse.workflow_step = "DESCRIBE"
        context.scene.cozyverse.plan_approved = False
        context.scene.cozyverse.status = "Clipboard prompt ready"
        return {"FINISHED"}


class CV_OT_SelectReferenceImage(bpy.types.Operator, ImportHelper):
    bl_idname = "cozyverse.select_reference_image"
    bl_label = "Choose Diorama Image"
    bl_description = "Choose a local reference image; nothing is uploaded"

    filter_glob: StringProperty(default="*.png;*.jpg;*.jpeg;*.webp;*.tif;*.tiff", options={"HIDDEN"})

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        try:
            path = validate_reference_path(self.filepath)
            image = bpy.data.images.load(str(path), check_existing=True)
        except (ValueError, RuntimeError) as exc:
            settings.reference_status = str(exc)
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        settings.reference_image_path = str(path)
        settings.reference_image = image
        settings.reference_palette_json = "[]"
        settings.reference_analysis_json = ""
        settings.reference_status = f"Loaded {image.name} ({image.size[0]} × {image.size[1]})"
        return {"FINISHED"}


class CV_OT_AnalyzeReferenceLocally(bpy.types.Operator):
    bl_idname = "cozyverse.analyze_reference_locally"
    bl_label = "Analyze Locally"
    bl_description = "Extract a color palette from the image locally without uploading it"

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        image = settings.reference_image
        if image is None:
            settings.reference_status = "Choose a reference image first"
            return {"CANCELLED"}
        try:
            pixels = list(image.pixels)
            palette = dominant_palette(pixels, image.channels, 5)
            analysis = analyze_composition(pixels, image.size[0], image.size[1], image.channels)
        except (RuntimeError, ValueError) as exc:
            settings.reference_status = f"Image analysis failed: {exc}"
            return {"CANCELLED"}
        if not palette:
            settings.reference_status = "The image did not contain readable color pixels"
            return {"CANCELLED"}
        settings.reference_palette_json = json.dumps(palette)
        settings.reference_analysis_json = analysis.to_json()
        settings.reference_status = f"Local cues ready: {analysis.aspect.lower()}, {analysis.suggested_time.lower()}, focal point {analysis.focal_x:.0%} across; not uploaded"
        return {"FINISHED"}


class CV_OT_IndexLocalAssets(bpy.types.Operator):
    bl_idname = "cozyverse.index_local_assets"
    bl_label = "Index Local Assets"
    bl_description = "Scan configured local folders for supported model files without opening them"

    def execute(self, context: bpy.types.Context):
        entry = context.preferences.addons.get(__package__)
        preferences = entry.preferences if entry else None
        if preferences is None:
            return {"CANCELLED"}
        roots = []
        if preferences.custom_asset_folder:
            roots.append((bpy.path.abspath(preferences.custom_asset_folder), "LOCAL_FOLDER"))
        if preferences.include_blender_asset_libraries:
            roots.extend((library.path, "BLENDER_LIBRARY") for library in context.preferences.filepaths.asset_libraries)
        records = []
        seen = set()
        for root, source in roots:
            for path in scan_asset_files([root]):
                if path.casefold() not in seen:
                    records.append(record_from_path(path, source))
                    seen.add(path.casefold())
        settings = context.scene.cozyverse
        settings.asset_items.clear()
        for record in records[:1000]:
            item = settings.asset_items.add()
            item.name = record.name
            item.path = record.path
            item.extension = record.extension
            item.category = record.category
            item.tags = ", ".join(record.tags)
            item.source = record.source
        settings.asset_index = 0 if records else -1
        settings.indexed_asset_count = str(len(records))
        settings.indexed_asset_preview = json.dumps([record.as_dict() for record in records[:100]])
        settings.asset_catalog_status = f"Indexed {len(records)} local model file(s); none were opened"
        settings.reference_status = settings.asset_catalog_status
        return {"FINISHED"}


class CV_OT_MatchLocalAssets(bpy.types.Operator):
    bl_idname = "cozyverse.match_local_assets"
    bl_label = "Find Best Matches"
    bl_description = "Rank indexed local assets against the current scene plan and visual style"

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        records = [AssetRecord(item.path, item.name, item.extension, item.category, tuple(tag.strip() for tag in item.tags.split(",") if tag.strip()), item.source) for item in settings.asset_items]
        style = STYLE_PRESETS.get(settings.preset, STYLE_PRESETS["COZY_VILLAGE"])
        query = " ".join((settings.asset_search, settings.plan_title, settings.plan_world_type, _prompt_from_settings(settings)))
        matched = match_assets(records, query, style.keywords, settings.asset_category)
        settings.asset_items.clear()
        for record in matched:
            item = settings.asset_items.add()
            item.name, item.path, item.extension, item.category = record.name, record.path, record.extension, record.category
            item.tags, item.source, item.match_score = ", ".join(record.tags), record.source, record.score
        settings.asset_index = 0 if matched else -1
        settings.asset_placement_approved = False
        settings.asset_catalog_status = f"Found {len(matched)} matching local asset(s); local files are preferred"
        return {"FINISHED"}


class CV_OT_SelectCatalogAsset(bpy.types.Operator):
    bl_idname = "cozyverse.select_catalog_asset"
    bl_label = "Select Asset"

    index: IntProperty(name="Index")

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        if not 0 <= self.index < len(settings.asset_items):
            return {"CANCELLED"}
        settings.asset_index = self.index
        settings.asset_placement_approved = False
        settings.asset_catalog_status = f"Selected {settings.asset_items[self.index].name}; preview placement before import"
        return {"FINISHED"}


def _asset_preview_collection(scene):
    collection = bpy.data.collections.get("CV_ASSET_PREVIEW")
    if collection is None:
        collection = bpy.data.collections.new("CV_ASSET_PREVIEW")
        scene.collection.children.link(collection)
    collection["cv_managed"] = True
    collection["cv_preview_only"] = True
    return collection


class CV_OT_PreviewAssetPlacement(bpy.types.Operator):
    bl_idname = "cozyverse.preview_asset_placement"
    bl_label = "Preview Placement"
    bl_description = "Create a lightweight proxy without opening or importing the asset file"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        if not 0 <= settings.asset_index < len(settings.asset_items):
            settings.asset_catalog_status = "Select a catalog asset first"
            return {"CANCELLED"}
        item = settings.asset_items[settings.asset_index]
        old = bpy.data.objects.get(settings.asset_preview_name)
        if old is not None and old.get("cv_asset_preview"):
            bpy.data.objects.remove(old, do_unlink=True)
        bpy.ops.mesh.primitive_cube_add(location=settings.asset_place_location)
        proxy = context.object
        proxy.name = f"CV_PREVIEW_{item.name[:40]}"
        proxy.rotation_euler = settings.asset_place_rotation
        dimensions = {"CHARACTER": (0.6, 0.6, 1.8), "BUILDING": (3.0, 2.4, 2.5), "ROAD": (4.0, 1.5, 0.1), "VEGETATION": (1.2, 1.2, 2.2), "VEHICLE": (2.2, 1.1, 0.9), "FURNITURE": (1.2, 0.8, 1.0)}.get(item.category, (1.0, 1.0, 1.0))
        proxy.dimensions = tuple(value * settings.asset_place_scale for value in dimensions)
        proxy.display_type = "WIRE"
        proxy.show_in_front = True
        proxy["cv_asset_preview"] = True
        proxy["cv_source_path"] = item.path
        proxy["cv_category"] = item.category
        preview = _asset_preview_collection(context.scene)
        for owner in list(proxy.users_collection):
            owner.objects.unlink(proxy)
        preview.objects.link(proxy)
        settings.asset_preview_name = proxy.name
        settings.asset_placement_approved = False
        settings.asset_catalog_status = f"Placement proxy ready for {item.name}; source file remains unopened"
        return {"FINISHED"}


def _import_blend_asset(path: str, target) -> list[bpy.types.Object]:
    with bpy.data.libraries.load(path, link=False) as (data_from, data_to):
        if data_from.collections:
            data_to.collections = [data_from.collections[0]]
        elif data_from.objects:
            data_to.objects = [data_from.objects[0]]
        else:
            raise ValueError("Blend file contains no collection or object")
    imported = []
    for collection in data_to.collections:
        if collection is not None:
            target.children.link(collection)
            imported.extend(collection.all_objects)
    for obj in data_to.objects:
        if obj is not None:
            target.objects.link(obj)
            imported.append(obj)
    return list(dict.fromkeys(imported))


def _import_external_asset(path: str, extension: str, target) -> list[bpy.types.Object]:
    before = set(bpy.data.objects)
    if extension in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=path)
    elif extension == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    elif extension == ".fbx" and hasattr(bpy.ops.wm, "fbx_import"):
        bpy.ops.wm.fbx_import(filepath=path)
    else:
        raise ValueError(f"Import is not available for {extension} in this Blender installation")
    imported = [obj for obj in bpy.data.objects if obj not in before]
    for obj in imported:
        for owner in list(obj.users_collection):
            owner.objects.unlink(obj)
        target.objects.link(obj)
    return imported


class CV_OT_PlaceApprovedAsset(bpy.types.Operator):
    bl_idname = "cozyverse.place_approved_asset"
    bl_label = "Import Approved Asset"
    bl_description = "Import the reviewed local model into a dedicated editable collection"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        if not settings.asset_placement_approved or not 0 <= settings.asset_index < len(settings.asset_items):
            settings.asset_catalog_status = "Preview and approve the selected local asset before importing"
            return {"CANCELLED"}
        item = settings.asset_items[settings.asset_index]
        path = Path(bpy.path.abspath(item.path)).resolve()
        if not path.is_file() or path.suffix.lower() not in {".blend", ".glb", ".gltf", ".fbx", ".obj"}:
            settings.asset_catalog_status = "The selected asset is missing or has an unsupported format"
            return {"CANCELLED"}
        target = bpy.data.collections.get("CV_IMPORTED_ASSETS")
        if target is None:
            target = bpy.data.collections.new("CV_IMPORTED_ASSETS")
            context.scene.collection.children.link(target)
        try:
            imported = _import_blend_asset(str(path), target) if item.extension == ".blend" else _import_external_asset(str(path), item.extension, target)
        except (RuntimeError, ValueError) as exc:
            settings.asset_catalog_status = f"Import failed: {exc}"
            return {"CANCELLED"}
        if not imported:
            settings.asset_catalog_status = "Import finished but no objects were found"
            return {"CANCELLED"}
        wrapper = bpy.data.objects.new(f"CV_ASSET_{item.name[:40]}", None)
        target.objects.link(wrapper)
        wrapper.location = settings.asset_place_location
        wrapper.rotation_euler = settings.asset_place_rotation
        wrapper.scale = (settings.asset_place_scale,) * 3
        for obj in imported:
            if obj.parent is None:
                obj.parent = wrapper
            obj["cv_managed"] = True
            obj["cv_asset_source"] = str(path)
            obj["cv_asset_category"] = item.category
            if obj.animation_data and obj.animation_data.drivers:
                obj.animation_data_clear()
        wrapper["cv_managed"] = True
        wrapper["cv_asset_source"] = str(path)
        wrapper["cv_asset_category"] = item.category
        wrapper["cv_provenance"] = "user_approved_local_asset"
        preview = bpy.data.objects.get(settings.asset_preview_name)
        if preview is not None and preview.get("cv_asset_preview"):
            bpy.data.objects.remove(preview, do_unlink=True)
        settings.asset_preview_name = ""
        settings.asset_placement_approved = False
        settings.asset_catalog_status = f"Imported {item.name}: {len(imported)} editable object(s)"
        return {"FINISHED"}


class CV_OT_RecreateReferenceMock(bpy.types.Operator):
    bl_idname = "cozyverse.recreate_reference_mock"
    bl_label = "Create Editable Interpretation"
    bl_description = "Build an offline editable approximation using the extracted palette"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        if settings.reference_image is None:
            settings.reference_status = "Choose a reference image first"
            return {"CANCELLED"}
        if settings.reference_palette_json == "[]":
            result = bpy.ops.cozyverse.analyze_reference_locally()
            if result != {"FINISHED"}:
                return result
        analysis = analyze_composition(list(settings.reference_image.pixels), settings.reference_image.size[0], settings.reference_image.size[1], settings.reference_image.channels)
        prompt = f"Editable approximate interpretation of the diorama reference {settings.reference_image.name}"
        root = build_offline_world(context.scene, settings, prompt, reference_plan(analysis, settings.reference_quality))
        palette = json.loads(settings.reference_palette_json)
        material_names = ("CV_Mat_Earth", "CV_Mat_Shop", "CV_Mat_Roof", "CV_Mat_Trim", "CV_Mat_Leaves")
        colors = dict(zip(material_names, palette))
        for obj in _world_objects(root):
            if getattr(obj, "data", None) is None or not hasattr(obj.data, "materials"):
                continue
            for material in obj.data.materials:
                if material is None:
                    continue
                for prefix, color in colors.items():
                    if material.name == prefix or material.name.startswith(prefix + "."):
                        sync_color(material, (*color, 1.0))
        root["cv_reference_image"] = settings.reference_image_path
        root["cv_reference_mode"] = "local_composition_interpretation"
        root["cv_reference_analysis"] = analysis.to_json()
        root["cv_reference_quality"] = settings.reference_quality
        camera = next((obj for obj in _world_objects(root) if obj.type == "CAMERA"), None)
        if camera is not None:
            camera.data.shift_x = (analysis.focal_x - 0.5) * 0.45
            camera.data.shift_y = (analysis.focal_y - 0.5) * 0.25
        time_map = {"DAY": 12.0, "DUSK": 18.5, "NIGHT": 22.0}
        settings.time_hour = time_map[analysis.suggested_time]
        settings.warmth = analysis.warmth * 100.0
        root["cv_indexed_asset_count"] = int(settings.indexed_asset_count or 0)
        settings.reference_status = f"Editable interpretation ready: {root.name}"
        settings.active_world_name = root.name
        settings.story_active_id = ""
        settings.workflow_step = "BUILT"
        settings.operation_progress = 1.0
        return {"FINISHED"}


class CV_OT_UseMultilinePrompt(bpy.types.Operator):
    bl_idname = "cozyverse.use_multiline_prompt"
    bl_label = "Use Prompt and Return"
    bl_description = "Use the active multiline prompt and return this area to the 3D View"

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        active_text = getattr(context.space_data, "text", None) if context.space_data is not None else None
        text = active_text or settings.prompt_text
        if text is None or not text.as_string().strip():
            settings.status = "The multiline prompt is empty"
            self.report({"WARNING"}, settings.status)
            return {"CANCELLED"}
        settings.prompt_text = text
        settings.prompt = text.as_string().strip()[:4000]
        settings.status = "Multiline prompt ready"
        if context.area is not None:
            context.area.type = "VIEW_3D"
        self.report({"INFO"}, "Multiline prompt ready; select Build World")
        return {"FINISHED"}


class CV_OT_ResetPrompt(bpy.types.Operator):
    bl_idname = "cozyverse.reset_prompt"
    bl_label = "Reset Prompt"
    bl_description = "Restore the bundled offline demonstration prompt"
    bl_options = {"UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        settings.prompt = DEFAULT_PROMPT
        if settings.prompt_text is not None:
            settings.prompt_text.clear()
            settings.prompt_text.write(DEFAULT_PROMPT)
        settings.status = "Prompt reset"
        settings.workflow_step = "DESCRIBE"
        settings.plan_approved = False
        return {"FINISHED"}


class CV_OT_ApplyAtmosphere(bpy.types.Operator):
    bl_idname = "cozyverse.apply_atmosphere"
    bl_label = "Apply Atmosphere"
    bl_description = "Apply all Atmosphere Lab settings to the active CozyVerse world"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        if not apply_atmosphere(context.scene, settings):
            settings.status = "Build a world before applying atmosphere"
            self.report({"WARNING"}, settings.status)
            return {"CANCELLED"}
        settings.status = "Atmosphere applied to Blender lights and weather"
        self.report({"INFO"}, settings.status)
        return {"FINISHED"}


class CV_OT_ResetAtmosphere(bpy.types.Operator):
    bl_idname = "cozyverse.reset_atmosphere"
    bl_label = "Reset Atmosphere"
    bl_description = "Reset Atmosphere Lab to Golden Hour"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        values = PRESETS["GOLDEN_HOUR"]
        _set_atmosphere_values(settings, values, "GOLDEN_HOUR")
        apply_atmosphere(context.scene, settings)
        settings.status = "Atmosphere reset to Golden Hour"
        return {"FINISHED"}


class CV_OT_SaveAtmospherePreset(bpy.types.Operator):
    bl_idname = "cozyverse.save_atmosphere_preset"
    bl_label = "Save Custom Preset"
    bl_description = "Save current atmosphere values in the scene as versioned JSON"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        values = _atmosphere_from_settings(settings)
        context.scene["cv_custom_atmosphere_preset"] = serialize_preset(values)
        settings.atmosphere_preset = "CUSTOM"
        world = bpy.data.collections.get(settings.active_world_name)
        if world is not None and world.get("cv_managed"):
            world["cv_atmosphere_preset"] = "CUSTOM"
            world["cv_atmosphere_values"] = serialize_preset(values)
        settings.status = "Custom atmosphere saved to this scene and active world"
        return {"FINISHED"}


class CV_OT_LoadAtmospherePreset(bpy.types.Operator):
    bl_idname = "cozyverse.load_atmosphere_preset"
    bl_label = "Load Saved Look"
    bl_description = "Load and migrate the active world's saved atmosphere, or the scene custom preset"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        world = bpy.data.collections.get(settings.active_world_name)
        payload = world.get("cv_atmosphere_values") if world is not None else None
        source = world.name if payload and world is not None else "scene custom preset"
        if not payload:
            payload = context.scene.get("cv_custom_atmosphere_preset")
        if not payload:
            settings.status = "No saved atmosphere look is available"
            self.report({"WARNING"}, settings.status)
            return {"CANCELLED"}
        try:
            values = deserialize_preset(payload)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            settings.status = f"Saved atmosphere is invalid: {exc}"
            self.report({"ERROR"}, settings.status)
            return {"CANCELLED"}
        _set_atmosphere_values(settings, values, "CUSTOM")
        migrated = serialize_preset(values)
        context.scene["cv_custom_atmosphere_preset"] = migrated
        if world is not None and world.get("cv_managed"):
            world["cv_atmosphere_schema"] = "2.0"
            world["cv_atmosphere_preset"] = "CUSTOM"
            world["cv_atmosphere_values"] = migrated
        apply_atmosphere(context.scene, settings)
        settings.status = f"Loaded atmosphere from {source}"
        return {"FINISHED"}


class CV_OT_ClearApiKey(bpy.types.Operator):
    bl_idname = "cozyverse.clear_api_key"
    bl_label = "Clear Key"
    bl_description = "Remove the API key from this Blender session"

    def execute(self, context: bpy.types.Context):
        context.window_manager.cozyverse_secrets.api_key = ""
        context.scene.cozyverse.status = "Session API key cleared"
        self.report({"INFO"}, "Session API key cleared")
        return {"FINISHED"}


class CV_OT_ClearGenerationKey(bpy.types.Operator):
    bl_idname = "cozyverse.clear_generation_key"
    bl_label = "Clear Provider Key"
    bl_description = "Clear a session-only 3D provider credential"

    provider: EnumProperty(
        items=(
            ("TRIPO", "Tripo", "Clear the Tripo key"),
            ("MESHY", "Meshy", "Clear the Meshy key"),
        )
    )

    def execute(self, context: bpy.types.Context):
        secrets = context.window_manager.cozyverse_secrets
        if self.provider == "TRIPO":
            secrets.tripo_api_key = ""
        else:
            secrets.meshy_api_key = ""
        context.scene.cozyverse.status = f"{self.provider.title()} session key cleared"
        return {"FINISHED"}


class CV_OT_ValidateGenerationSettings(bpy.types.Operator):
    bl_idname = "cozyverse.validate_generation_settings"
    bl_label = "Check 3D Provider Setup"
    bl_description = "Check the selected Tripo or Meshy credential locally without making a request"

    def execute(self, context: bpy.types.Context):
        entry = context.preferences.addons.get(__package__)
        preferences = entry.preferences if entry else None
        secrets = context.window_manager.cozyverse_secrets
        if preferences is None or preferences.generation_provider == "NONE":
            message = "3D generation is disabled"
        elif preferences.generation_provider == "TRIPO" and not secrets.tripo_api_key.strip():
            message = "Enter a Tripo session key"
            context.scene.cozyverse.status = message
            self.report({"WARNING"}, message)
            return {"CANCELLED"}
        elif preferences.generation_provider == "MESHY" and not secrets.meshy_api_key.strip():
            message = "Enter a Meshy session key"
            context.scene.cozyverse.status = message
            self.report({"WARNING"}, message)
            return {"CANCELLED"}
        else:
            message = f"{preferences.generation_provider.title()} key is loaded for this session; no request was sent"
        context.scene.cozyverse.status = message
        self.report({"INFO"}, message)
        return {"FINISHED"}


class CV_OT_PreviewGeneration(bpy.types.Operator):
    bl_idname = "cozyverse.preview_generation"
    bl_label = "Preview Generation Request"
    bl_description = "Create a reviewable Tripo or Meshy request without sending it"

    def execute(self, context: bpy.types.Context):
        entry = context.preferences.addons.get(__package__)
        preferences = entry.preferences if entry else None
        settings = context.scene.cozyverse
        if preferences is None or preferences.generation_provider == "NONE":
            settings.generation_status = "Select Tripo or Meshy in Settings"
            return {"CANCELLED"}
        try:
            plan = build_plan(preferences.generation_provider, settings.generation_prompt)
        except ValueError as exc:
            settings.generation_status = str(exc)
            return {"CANCELLED"}
        settings.generation_plan_json = plan.canonical_json()
        settings.generation_fingerprint = plan.fingerprint()
        settings.generation_cost_note = plan.cost_note
        settings.generation_estimated_credits = plan.estimated_credits
        settings.generation_approved = False
        settings.generation_live_approved = False
        settings.generation_job_id = ""
        settings.generation_job_status = "NONE"
        settings.generation_job_progress = 0
        settings.generation_result_url = ""
        settings.generation_download_path = ""
        settings.generation_import_approved = False
        settings.generation_promotion_approved = False
        settings.generation_status = f"Ready for review: {plan.provider} {plan.model}"
        self.report({"INFO"}, "Generation request previewed; nothing was sent")
        return {"FINISHED"}


class CV_OT_RunMockGeneration(bpy.types.Operator):
    bl_idname = "cozyverse.run_mock_generation"
    bl_label = "Run Safe Mock Job"
    bl_description = "Exercise the approved generation workflow without contacting a provider or spending credits"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        if not settings.generation_plan_json or not settings.generation_approved:
            settings.generation_status = "Preview the request and approve the exact mock job first"
            return {"CANCELLED"}
        plan = _generation_plan(settings)
        entry = context.preferences.addons.get(__package__)
        preferences = entry.preferences if entry else None
        current_provider = preferences.generation_provider if preferences else plan.provider
        current_plan = build_plan(current_provider, settings.generation_prompt)
        if plan.fingerprint() != settings.generation_fingerprint or current_plan.fingerprint() != settings.generation_fingerprint:
            settings.generation_status = "Request changed after preview; preview it again"
            return {"CANCELLED"}
        settings.generation_job_id = f"mock-{settings.generation_fingerprint[:16]}"
        settings.generation_job_status = "PENDING"
        settings.generation_job_progress = 0
        settings.generation_is_mock = True
        settings.generation_approved = False
        settings.generation_status = "Mock job queued; no provider request or charge occurred"
        _log_activity(context, "MOCK", f"Queued zero-cost {plan.provider} mock job")
        return {"FINISHED"}


class CV_OT_SubmitLiveGeneration(bpy.types.Operator):
    bl_idname = "cozyverse.submit_live_generation"
    bl_label = "Submit Paid Provider Job"
    bl_description = "Submit the exact approved request asynchronously; provider credits may be charged"

    def invoke(self, context, _event):
        return context.window_manager.invoke_props_dialog(self, width=560, confirm_text="SUBMIT APPROVED PAID JOB")

    def draw(self, context):
        settings = context.scene.cozyverse
        layout = self.layout
        layout.alert = True
        layout.label(text="This sends data to the selected external provider.", icon="ERROR")
        layout.label(text=f"Fingerprint: {settings.generation_fingerprint[:16]}")
        layout.label(text=f"Estimated: {settings.generation_estimated_credits} credits • Maximum approved: {settings.generation_credit_limit}")
        layout.label(text="Estimates are not guaranteed provider charges.")

    def execute(self, context):
        settings = context.scene.cozyverse
        entry = context.preferences.addons.get(__package__)
        preferences = entry.preferences if entry else None
        if preferences is None or preferences.generation_provider == "NONE":
            settings.generation_status = "Select Tripo or Meshy first"
            return {"CANCELLED"}
        try:
            plan = _generation_plan(settings)
            current_plan = build_plan(preferences.generation_provider, settings.generation_prompt)
            if current_plan.fingerprint() != settings.generation_fingerprint:
                raise ValueError("Provider or prompt changed after preview; preview the request again")
            validate_budget(plan, settings.generation_credit_limit, settings.generation_fingerprint)
        except ValueError as exc:
            settings.generation_status = str(exc)
            return {"CANCELLED"}
        if not settings.generation_live_approved:
            settings.generation_status = "Approve this exact paid request before submission"
            return {"CANCELLED"}
        secrets = context.window_manager.cozyverse_secrets
        api_key = secrets.tripo_api_key if plan.provider == "TRIPO" else secrets.meshy_api_key
        if not api_key.strip():
            settings.generation_status = f"Enter a {plan.provider.title()} session key"
            return {"CANCELLED"}
        settings.generation_live_approved = False
        settings.generation_job_status = "PENDING"
        settings.generation_job_progress = 0
        settings.generation_is_mock = False
        settings.generation_status = "Submitting approved provider request asynchronously…"
        _start_provider_work(context.scene.name, "SUBMIT", provider_runtime.submit, plan, api_key)
        _log_activity(context, "SUBMIT", f"Submitted approved {plan.provider} request {plan.fingerprint()[:12]}")
        return {"FINISHED"}


class CV_OT_RefreshGenerationJob(bpy.types.Operator):
    bl_idname = "cozyverse.refresh_generation_job"
    bl_label = "Refresh Job Status"
    bl_description = "Poll the mock or provider job without blocking Blender"

    def execute(self, context):
        settings = context.scene.cozyverse
        if not settings.generation_job_id or settings.generation_job_status in {"NONE", "FAILED", "CANCELED"}:
            settings.generation_status = "Start a job before refreshing status"
            return {"CANCELLED"}
        if settings.generation_is_mock:
            if settings.generation_job_status == "PENDING":
                settings.generation_job_status = "IN_PROGRESS"
                settings.generation_job_progress = 50
            elif settings.generation_job_status == "IN_PROGRESS":
                settings.generation_job_status = "SUCCEEDED"
                settings.generation_job_progress = 100
                settings.generation_download_path = "MOCK"
            settings.generation_status = f"Mock job {settings.generation_job_status.replace('_', ' ').title()} — {settings.generation_job_progress}%"
            return {"FINISHED"}
        plan = _generation_plan(settings)
        secrets = context.window_manager.cozyverse_secrets
        api_key = secrets.tripo_api_key if plan.provider == "TRIPO" else secrets.meshy_api_key
        if not api_key:
            settings.generation_status = "Reload the provider session key before polling"
            return {"CANCELLED"}
        settings.generation_status = "Refreshing provider status asynchronously…"
        _start_provider_work(context.scene.name, "POLL", provider_runtime.poll, plan, settings.generation_job_id, api_key)
        return {"FINISHED"}


class CV_OT_CancelGenerationJob(bpy.types.Operator):
    bl_idname = "cozyverse.cancel_generation_job"
    bl_label = "Cancel Pending Job"
    bl_description = "Cancel a mock job or request provider cancellation where officially supported"

    def execute(self, context):
        settings = context.scene.cozyverse
        if settings.generation_job_status not in {"PENDING", "IN_PROGRESS"}:
            settings.generation_status = "Only pending or active jobs can be canceled"
            return {"CANCELLED"}
        if settings.generation_is_mock:
            settings.generation_job_status = "CANCELED"
            settings.generation_status = "Mock job canceled; the scene was unchanged"
            return {"FINISHED"}
        plan = _generation_plan(settings)
        if not plan.cancel_url_template:
            settings.generation_status = plan.cancellation_note
            return {"CANCELLED"}
        secrets = context.window_manager.cozyverse_secrets
        api_key = secrets.tripo_api_key if plan.provider == "TRIPO" else secrets.meshy_api_key
        settings.generation_status = "Requesting provider cancellation asynchronously…"
        _start_provider_work(context.scene.name, "CANCEL", provider_runtime.cancel, plan, settings.generation_job_id, api_key)
        return {"FINISHED"}


class CV_OT_DownloadGenerationResult(bpy.types.Operator):
    bl_idname = "cozyverse.download_generation_result"
    bl_label = "Download Validated Result"
    bl_description = "Download an allowlisted GLB with a 100 MB limit without blocking Blender"

    def execute(self, context):
        settings = context.scene.cozyverse
        if settings.generation_job_status != "SUCCEEDED":
            settings.generation_status = "Wait for a successful job before download"
            return {"CANCELLED"}
        if settings.generation_is_mock:
            settings.generation_download_path = "MOCK"
            settings.generation_status = "Mock result ready for quarantine import"
            return {"FINISHED"}
        try:
            plan = _generation_plan(settings)
            validate_download_url(plan.provider, settings.generation_result_url)
        except ValueError as exc:
            settings.generation_status = f"Unsafe result rejected: {exc}"
            return {"CANCELLED"}
        root = Path(bpy.data.filepath).parent if bpy.data.filepath else Path(bpy.app.tempdir)
        safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", settings.generation_job_id)[:80]
        destination = root / "cozyverse_generated" / f"{plan.provider.lower()}-{safe_id}.glb"
        settings.generation_status = "Downloading and validating GLB asynchronously…"
        _start_provider_work(context.scene.name, "DOWNLOAD", provider_runtime.download, plan.provider, settings.generation_result_url, destination)
        return {"FINISHED"}


def _generation_collection(scene, name: str):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        scene.collection.children.link(collection)
    collection["cv_managed"] = True
    return collection


class CV_OT_ImportGenerationResult(bpy.types.Operator):
    bl_idname = "cozyverse.import_generation_result"
    bl_label = "Import to Quarantine"
    bl_description = "Import the approved result into an isolated editable review collection"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.cozyverse
        if settings.generation_job_status != "SUCCEEDED" or not settings.generation_download_path or not settings.generation_import_approved:
            settings.generation_status = "Download and approve the result before quarantine import"
            return {"CANCELLED"}
        target = _generation_collection(context.scene, "CV_ASSET_QUARANTINE")
        if settings.generation_is_mock:
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.8)
            mock_object = context.object
            imported = [mock_object]
            for owner in list(mock_object.users_collection):
                owner.objects.unlink(mock_object)
            target.objects.link(mock_object)
        else:
            path = Path(settings.generation_download_path)
            if not path.is_file() or path.suffix.lower() != ".glb":
                settings.generation_status = "Validated GLB is missing; download it again"
                return {"CANCELLED"}
            try:
                imported = _import_external_asset(str(path), ".glb", target)
            except (RuntimeError, ValueError) as exc:
                settings.generation_status = f"Quarantine import failed: {exc}"
                return {"CANCELLED"}
        wrapper = bpy.data.objects.new(f"CV_QUARANTINE_{settings.generation_job_id[:28]}", None)
        target.objects.link(wrapper)
        vertices = materials = 0
        for obj in imported:
            if obj.parent is None:
                obj.parent = wrapper
            obj["cv_managed"] = True
            obj["cv_provider_job"] = settings.generation_job_id
            obj["cv_quarantine"] = True
            if isinstance(obj.data, bpy.types.Mesh):
                vertices += len(obj.data.vertices)
                materials += len(obj.data.materials)
            if obj.animation_data and obj.animation_data.drivers:
                obj.animation_data_clear()
        plan = _generation_plan(settings)
        for key, value in {
            "cv_managed": True,
            "cv_quarantine": True,
            "cv_provider": plan.provider,
            "cv_provider_job": settings.generation_job_id,
            "cv_plan_fingerprint": settings.generation_fingerprint,
            "cv_estimated_credits": settings.generation_estimated_credits,
            "cv_provenance": "provider_mock" if settings.generation_is_mock else "user_approved_provider_generation",
        }.items():
            wrapper[key] = value
        settings.generation_quarantine_name = wrapper.name
        settings.generation_review_summary = f"{len(imported)} object(s) • {vertices} vertices • {materials} material slots • drivers removed"
        settings.generation_import_approved = False
        settings.generation_promotion_approved = False
        settings.generation_status = "Result imported to quarantine; inspect before promotion"
        return {"FINISHED"}


class CV_OT_PromoteGenerationAsset(bpy.types.Operator):
    bl_idname = "cozyverse.promote_generation_asset"
    bl_label = "Promote to Asset Factory"
    bl_description = "Move the reviewed generated asset into the reusable local Asset Factory collection"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.cozyverse
        wrapper = bpy.data.objects.get(settings.generation_quarantine_name)
        if wrapper is None or not wrapper.get("cv_quarantine") or not settings.generation_promotion_approved:
            settings.generation_status = "Inspect and approve the quarantine asset before promotion"
            return {"CANCELLED"}
        quarantine = bpy.data.collections.get("CV_ASSET_QUARANTINE")
        factory = _generation_collection(context.scene, "CV_ASSET_FACTORY")
        members = [obj for obj in bpy.data.objects if obj is wrapper or obj.get("cv_provider_job") == settings.generation_job_id]
        for obj in members:
            if quarantine in obj.users_collection:
                quarantine.objects.unlink(obj)
            if obj.name not in factory.objects:
                factory.objects.link(obj)
            obj["cv_quarantine"] = False
            obj["cv_asset_factory"] = True
        wrapper["cv_provenance"] = "approved_asset_factory_item"
        settings.generation_promotion_approved = False
        settings.generation_status = f"Promoted {wrapper.name} to the editable Asset Factory"
        return {"FINISHED"}


class CV_OT_ValidateProviderSettings(bpy.types.Operator):
    bl_idname = "cozyverse.validate_provider_settings"
    bl_label = "Validate Configuration"
    bl_description = "Check local provider fields without making a network request"

    def execute(self, context: bpy.types.Context):
        preferences_entry = context.preferences.addons.get(__package__)
        preferences = preferences_entry.preferences if preferences_entry else None
        secrets = context.window_manager.cozyverse_secrets
        if preferences is None or preferences.provider == "NONE":
            message = "Local-only mode is ready"
        elif not preferences.model_name.strip():
            message = "Add a model name before using this provider"
            context.scene.cozyverse.status = message
            self.report({"WARNING"}, message)
            return {"CANCELLED"}
        elif not secrets.api_key.strip() and not preferences.api_key_environment_variable.strip():
            message = "Enter a session key or environment variable name"
            context.scene.cozyverse.status = message
            self.report({"WARNING"}, message)
            return {"CANCELLED"}
        else:
            message = "Provider fields are configured; no request was sent"
        context.scene.cozyverse.status = message
        self.report({"INFO"}, message)
        return {"FINISHED"}


_CLASSES = (
    CV_OT_StartOnboarding,
    CV_OT_DismissOnboarding,
    CV_OT_PrepareScenePlan,
    CV_OT_BackToDescription,
    CV_OT_RefreshRevisionPreview,
    CV_OT_CancelRevision,
    CV_OT_BuildApprovedPlan,
    CV_OT_SelectWorld,
    CV_OT_ArchiveWorld,
    CV_OT_InspectManualEdits,
    CV_OT_LockSelectedObjects,
    CV_OT_CreateCheckpoint,
    CV_OT_CreateLocalDemo,
    CV_OT_PromptComposer,
    CV_OT_ApplyPromptTemplate,
    CV_OT_PastePrompt,
    CV_OT_SelectReferenceImage,
    CV_OT_AnalyzeReferenceLocally,
    CV_OT_IndexLocalAssets,
    CV_OT_MatchLocalAssets,
    CV_OT_SelectCatalogAsset,
    CV_OT_PreviewAssetPlacement,
    CV_OT_PlaceApprovedAsset,
    CV_OT_RecreateReferenceMock,
    CV_OT_EditMultilinePrompt,
    CV_OT_UseMultilinePrompt,
    CV_OT_ResetPrompt,
    CV_OT_ApplyAtmosphere,
    CV_OT_ResetAtmosphere,
    CV_OT_SaveAtmospherePreset,
    CV_OT_LoadAtmospherePreset,
    CV_OT_PreviewStory,
    CV_OT_ApplyStory,
    CV_OT_ClearStory,
    CV_OT_ClearApiKey,
    CV_OT_ClearGenerationKey,
    CV_OT_ValidateGenerationSettings,
    CV_OT_PreviewGeneration,
    CV_OT_RunMockGeneration,
    CV_OT_SubmitLiveGeneration,
    CV_OT_RefreshGenerationJob,
    CV_OT_CancelGenerationJob,
    CV_OT_DownloadGenerationResult,
    CV_OT_ImportGenerationResult,
    CV_OT_PromoteGenerationAsset,
    CV_OT_ValidateProviderSettings,
)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    if bpy.app.timers.is_registered(_drain_provider_results):
        bpy.app.timers.unregister(_drain_provider_results)
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

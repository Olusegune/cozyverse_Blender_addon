"""One-click clips: the world builds itself while the camera sweeps around it, rendered to an MP4."""

from __future__ import annotations

from pathlib import Path

import bpy

from .core.library_spec import license_note
from .flow import _turntable_for
from .motion import controller_for
from .operators import _log_activity

SIZES = {"HD720": (1280, 720), "HD1080": (1920, 1080)}
MINIMUM_FRAMES = 48


def clip_path(scene: bpy.types.Scene) -> str:
    """The render prefix: Blender adds the frame range and .mp4, e.g. name_clip_0001-0132.mp4."""
    if bpy.data.filepath:
        blend = Path(bpy.data.filepath)
        return str(blend.with_name(f"{blend.stem}_clip_"))
    return str(Path(bpy.app.tempdir) / "cozyverse_clip_")


def prepare_render(scene: bpy.types.Scene, quality: str) -> None:
    engines = {item.identifier for item in scene.render.bl_rna.properties["engine"].enum_items}
    if scene.render.engine == "BLENDER_WORKBENCH":
        scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x, scene.render.resolution_y = SIZES.get(quality, SIZES["HD720"])
    scene.render.resolution_percentage = 100
    if hasattr(scene.render.image_settings, "media_type"):  # Blender 5.x asks for video output explicitly
        scene.render.image_settings.media_type = "VIDEO"
    scene.render.image_settings.file_format = "FFMPEG"
    ffmpeg = scene.render.ffmpeg
    for name, value in (("format", "MPEG4"), ("codec", "H264"), ("constant_rate_factor", "HIGH"), ("ffmpeg_preset", "GOOD"), ("audio_codec", "NONE")):
        try:
            setattr(ffmpeg, name, value)
        except (AttributeError, TypeError):
            pass


class CV_OT_RenderClip(bpy.types.Operator):
    bl_idname = "cozyverse.render_clip"
    bl_label = "Render Clip"
    bl_description = "Build the world up while the camera orbits it, and render an MP4 next to your .blend. Everything is editable keyframes, so you can retime it first"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        scene = context.scene
        world = bpy.data.collections.get(settings.active_world_name) if settings.active_world_name else None
        if world is None or scene.camera is None:
            self.report({"WARNING"}, "Conjure or select a world first")
            return {"CANCELLED"}
        if settings.clip_buildup:
            if bpy.ops.cozyverse.buildup_add(play=False) != {"FINISHED"}:
                return {"CANCELLED"}
            total = scene.frame_end
        else:
            total = max(MINIMUM_FRAMES, int(settings.turntable_frames))
        if settings.clip_orbit:
            settings.turntable_frames = max(24, total)
            if bpy.ops.cozyverse.turntable() != {"FINISHED"}:
                return {"CANCELLED"}
            total = max(total, scene.frame_end)
        scene.frame_start, scene.frame_end = 1, total
        scene.frame_set(1)
        prepare_render(scene, settings.clip_quality)
        scene.render.filepath = clip_path(scene)
        note = license_note([obj["cv_license"] for obj in world.all_objects if "cv_license" in obj])
        if note is not None and note.level == "WARNING":
            self.report({"WARNING"}, note.text)
        output = f"{scene.render.filepath}0001-{total:04d}.mp4"
        settings.status = f"Rendering {total} frames to {Path(output).name}"
        _log_activity(context, "CLIP", f"Rendering a {total}-frame clip to {output}")
        if not bpy.app.background:
            bpy.ops.render.render("INVOKE_DEFAULT", animation=True)
        return {"FINISHED"}


_CLASSES = (CV_OT_RenderClip,)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

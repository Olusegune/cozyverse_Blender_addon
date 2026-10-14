"""Build-up animation: the diorama assembles itself, layer by layer, on an editable timeline.

One controller empty carries a single 0 -> 1 keyframed value (``cv_t``). Every object reads it
through simple-expression drivers on its *delta* transforms, so there are no per-object actions to
collide with Story keyframes, nothing counts as a hand edit, and retiming the whole sequence is just
moving two keys in the Dope Sheet.
"""

from __future__ import annotations

import math
import re

import bpy
from bpy.props import EnumProperty

from .life import add_driver, apply_life, clear_life
from .operators import _log_activity

CONTROLLER = "CV_BuildUp"
HOLD_SECONDS = 1.5
OBJECT_SPAN = 0.18  # how much of the timeline one object takes to appear

# Layer name prefix -> (start, end) as a fraction of the whole build-up.
LAYERS = (
    ("CV_BASE", 0.00, 0.26),
    ("CV_ARCHITECTURE", 0.14, 0.62),
    ("CV_PROPS", 0.42, 0.80),
    ("CV_VEGETATION", 0.50, 0.92),
    ("CV_CHARACTERS", 0.80, 1.00),
    ("CV_RAILWAY", 0.05, 0.30),
    ("CV_TRAFFIC", 0.82, 1.00),
)
PART_SUFFIX = re.compile(r"_(Roof|Window\d*[LR]?|Dome|Antenna|Awning|Lantern|Trunk|Leaves|Beacon|Body|Head|Cabin|Cab|Wheel\d+[LR]?|Hub\d|Headlight\d|Taillight\d|Chimney|Boiler|Lamp|Coupling)$")
PART_DELAY = {"Roof": 0.035, "Dome": 0.03, "Antenna": 0.05, "Awning": 0.04, "Leaves": 0.04, "Head": 0.03, "Lantern": 0.05, "Beacon": 0.05}

STYLES = (
    ("POP", "Pop", "Each piece grows from the ground with a little overshoot"),
    ("RISE", "Rise", "Pieces grow upward like plants"),
    ("DROP", "Drop", "Pieces fall in and bounce once"),
)
ORDERS = (
    ("CENTER", "From the middle", "Ripple outward from the center of the stage"),
    ("SWEEP", "Left to right", "Sweep across the stage"),
)


def controller_for(world):
    return next((obj for obj in world.objects if obj.get("cv_buildup_controller")), None) if world is not None else None


def finish_frame(controller) -> int:
    return int(controller.get("cv_finish_frame", 1)) if controller is not None else 1


def _layer_for(obj, world) -> int:
    for collection in obj.users_collection:
        for index, (prefix, _lo, _hi) in enumerate(LAYERS):
            if collection.name.startswith(prefix):
                return index
    return 1


def _eased(style: str) -> tuple[str, str, str]:
    """(scale expression, vertical offset expression template, horizontal scale) in terms of ``p``."""
    if style == "RISE":
        grow = "(1-(1-p)*(1-p)*(1-p))"
        return f"max(0.0001,{grow})", f"-(1-{grow})*H", f"(0.55+0.45*{grow})"
    if style == "DROP":
        fall = "min(1,p/0.72)"
        return "max(0.0001,min(1,p*400))", f"3.5*(1-{fall}*{fall})+0.28*sin(pi*max(0,(p-0.72)/0.28))", "max(0.0001,min(1,p*400))"
    overshoot = "(1+2.4*(p-1)*(p-1)*(p-1)+1.4*(p-1)*(p-1))"
    return f"max(0.0001,{overshoot})", f"-(1-{overshoot})*H", f"max(0.0001,{overshoot})"


def remove_buildup(world, scene=None) -> int:
    controller = controller_for(world)
    removed = 0
    for obj in world.all_objects:
        if not obj.get("cv_buildup"):
            continue
        for path, index in (("delta_scale", 0), ("delta_scale", 1), ("delta_scale", 2), ("delta_location", 2), ('["cv_p"]', -1)):
            try:
                obj.driver_remove(path, index)
            except (TypeError, RuntimeError):
                pass
        obj.delta_scale = (1.0, 1.0, 1.0)
        obj.delta_location = (obj.delta_location[0], obj.delta_location[1], 0.0)
        for key in ("cv_buildup", "cv_p"):
            if key in obj:
                del obj[key]
        removed += 1
    if controller is not None:
        animation = controller.animation_data
        action = animation.action if animation else None
        if scene is not None and controller.get("cv_original_frame_end") is not None:
            scene.frame_start = int(controller["cv_original_frame_start"])
            scene.frame_end = int(controller["cv_original_frame_end"])
        bpy.data.objects.remove(controller)
        if action is not None and action.users == 0:
            bpy.data.actions.remove(action)
    return removed


def build_buildup(scene, world, style: str, order: str, seconds: float):
    """Create the controller and per-object drivers. Returns (controller, object count)."""
    remove_buildup(world, scene)
    fps = max(1, scene.render.fps)
    frames = max(12, int(round(seconds * fps)))
    start = 1
    finish = start + frames

    controller = bpy.data.objects.new(CONTROLLER, None)
    controller.empty_display_type = "SINGLE_ARROW"
    controller.empty_display_size = 0.8
    world.objects.link(controller)
    controller["cv_managed"] = True
    controller["cv_demo"] = True
    controller["cv_locked"] = False
    controller["cv_buildup_controller"] = True
    controller["cv_world_root"] = world.name
    controller["cv_finish_frame"] = finish
    controller["cv_original_frame_start"] = scene.frame_start
    controller["cv_original_frame_end"] = scene.frame_end
    edit = bpy.context.preferences.edit
    previous = edit.keyframe_new_interpolation_type
    edit.keyframe_new_interpolation_type = "LINEAR"
    try:
        for frame, value in ((start, 0.0), (finish, 1.0)):
            controller["cv_t"] = value
            controller.keyframe_insert(data_path='["cv_t"]', frame=frame, group="CozyVerse Build-Up")
    finally:
        edit.keyframe_new_interpolation_type = previous
    animation = controller.animation_data
    if animation and animation.action:
        animation.action.name = f"CV_BUILDUP_{world.name}"[:63]
        animation.action["cv_managed"] = True
        animation.action["cv_buildup"] = True

    meshes = [obj for obj in world.all_objects if obj.type == "MESH" and not obj.get("cv_weather") and not obj.get("cv_buildup_controller")]
    groups: dict[tuple[int, str], list] = {}
    for obj in meshes:
        groups.setdefault((_layer_for(obj, world), PART_SUFFIX.sub("", obj.name)), []).append(obj)

    def sort_key(item):
        obj = item[1][0]
        return math.hypot(obj.location.x, obj.location.y) if order == "CENTER" else obj.location.x

    for layer_index, (_prefix, low, high) in enumerate(LAYERS):
        # The stage itself always pops into place; only what stands on it falls or rises.
        scale_expr, lift_expr, flat_expr = _eased("POP" if layer_index == 0 else style)
        members = sorted([item for item in groups.items() if item[0][0] == layer_index], key=sort_key)
        for position, (_key, objects) in enumerate(members):
            fraction = position / max(1, len(members) - 1)
            base_delay = low + max(0.0, high - low - OBJECT_SPAN) * fraction
            for obj in objects:
                suffix = PART_SUFFIX.search(obj.name)
                delay = base_delay + (PART_DELAY.get(suffix.group(1).rstrip("0123456789"), 0.045) if suffix else 0.0)
                start_t = min(delay, 1.0 - OBJECT_SPAN)
                end_t = start_t + OBJECT_SPAN
                obj["cv_p"] = 0.0
                obj["cv_buildup"] = True
                add_driver(
                    obj,
                    '["cv_p"]',
                    -1,
                    f"min(1,max(0,(t-{start_t:.4f})/{OBJECT_SPAN:.4f}))",
                    (("t", "OBJECT", controller, '["cv_t"]'),),
                )
                variables = (("p", "OBJECT", obj, '["cv_p"]'),)
                half_height = max(0.001, obj.dimensions.z / 2.0)
                horizontal = flat_expr if (style == "RISE" and layer_index != 0) else scale_expr
                add_driver(obj, "delta_scale", 0, horizontal, variables)
                add_driver(obj, "delta_scale", 1, horizontal, variables)
                add_driver(obj, "delta_scale", 2, scale_expr, variables)
                add_driver(obj, "delta_location", 2, lift_expr.replace("H", f"{half_height:.4f}"), variables)

    hold = int(round(HOLD_SECONDS * fps))
    scene.frame_start = start
    scene.frame_end = finish + hold
    return controller, len(meshes)


class CV_OT_BuildUpAdd(bpy.types.Operator):
    bl_idname = "cozyverse.buildup_add"
    bl_label = "Play Build-Up"
    bl_description = "Make the world assemble itself over time. It is an editable timeline: move the two keys on CV_BuildUp to retime it, or Remove to undo it completely"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        world = bpy.data.collections.get(settings.active_world_name)
        if world is None:
            self.report({"WARNING"}, "Conjure or select a world first")
            return {"CANCELLED"}
        controller, count = build_buildup(context.scene, world, settings.buildup_style, settings.buildup_order, settings.buildup_seconds)
        context.scene.frame_set(1)
        settings.status = f"Build-up ready: {count} pieces over {settings.buildup_seconds:.1f}s"
        _log_activity(context, "BUILDUP", f"Added a {settings.buildup_style.lower()} build-up to {world.name}")
        if not bpy.app.background and context.screen is not None and not context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()
        return {"FINISHED"}


class CV_OT_BuildUpReplay(bpy.types.Operator):
    bl_idname = "cozyverse.buildup_replay"
    bl_label = "Replay"
    bl_description = "Jump to the start and play the build-up"

    def execute(self, context: bpy.types.Context):
        context.scene.frame_set(context.scene.frame_start)
        if not bpy.app.background and context.screen is not None and not context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()
        return {"FINISHED"}


class CV_OT_BuildUpFinish(bpy.types.Operator):
    bl_idname = "cozyverse.buildup_finish"
    bl_label = "Show Finished"
    bl_description = "Stop playback and jump to the completed world"

    def execute(self, context: bpy.types.Context):
        world = bpy.data.collections.get(context.scene.cozyverse.active_world_name)
        controller = controller_for(world)
        if controller is None:
            return {"CANCELLED"}
        if not bpy.app.background and context.screen is not None and context.screen.is_animation_playing:
            bpy.ops.screen.animation_cancel(restore_frame=False)
        context.scene.frame_set(finish_frame(controller))
        return {"FINISHED"}


class CV_OT_BuildUpRemove(bpy.types.Operator):
    bl_idname = "cozyverse.buildup_remove"
    bl_label = "Remove Build-Up"
    bl_description = "Remove the build-up and restore every piece exactly as it was"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        world = bpy.data.collections.get(settings.active_world_name)
        if world is None or controller_for(world) is None:
            return {"CANCELLED"}
        if not bpy.app.background and context.screen is not None and context.screen.is_animation_playing:
            bpy.ops.screen.animation_cancel(restore_frame=False)
        remove_buildup(world, context.scene)
        context.scene.frame_set(context.scene.frame_start)
        settings.status = "Build-up removed; the world is exactly as it was"
        return {"FINISHED"}


class CV_OT_LifeRefresh(bpy.types.Operator):
    bl_idname = "cozyverse.life_refresh"
    bl_label = "Refresh Ambient Life"
    bl_description = "Re-apply foliage sway and lamp flicker to the active world"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        world = bpy.data.collections.get(settings.active_world_name)
        if world is None:
            return {"CANCELLED"}
        foliage, lamps = apply_life(context.scene, world)
        settings.status = f"Ambient life: {foliage} plants swaying, {lamps} lamps flickering"
        return {"FINISHED"}


_CLASSES = (CV_OT_BuildUpAdd, CV_OT_BuildUpReplay, CV_OT_BuildUpFinish, CV_OT_BuildUpRemove, CV_OT_LifeRefresh)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

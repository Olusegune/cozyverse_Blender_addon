"""The magic path: describe -> Conjure -> a framed, lit, revealed world, then guided next steps."""

from __future__ import annotations

import math
import random
import time

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from mathutils import Vector

from .core.scene_plan import proposed_plan
from .core.style_spec import STYLE_PRESETS, style_items
from .operators import _log_activity, _plan_from_settings, _prompt_from_settings, _refresh_revision_preview, _world_objects

TABS = (
    ("CREATE", "Create", "Describe and conjure a world", "MOD_BUILD", 0),
    ("ATMOSPHERE", "Mood", "Light, time of day, weather and seasons", "LIGHT_SUN", 1),
    ("SHOT", "Shot", "Frame cinematic cameras and render a postcard", "CAMERA_DATA", 6),
    ("STORY", "Motion", "Bring the world to life with editable animation", "ACTION", 2),
    ("GENERATE", "Assets", "Local assets, reference images and 3D generation", "ASSET_MANAGER", 3),
    ("ACTIVITY", "Activity", "Versions, recovery and the activity log", "INFO", 4),
    ("SETTINGS", "Settings", "Connections and preferences", "PREFERENCES", 5),
)

SURPRISES = (
    ("a tiny harbor village at the edge of a calm bay", "a crooked lighthouse with a glowing lamp", "misty dawn", "fishing boats, lanterns, crates and rope", "VILLAGE", "STORYBOOK"),
    ("a rainy night cafe corner", "a warmly lit cafe with steamed-up windows", "rainy blue hour", "umbrellas, string lights, plants and a small road", "CAFE", "COZY_VILLAGE"),
    ("a floating fantasy market square", "a wizard's potion stall", "magical twilight", "lanterns, banners, barrels and tiny characters", "MARKET", "COZY_FANTASY"),
    ("a lunar service station", "a rounded modular workshop", "cinematic alien dusk", "antenna arrays, a landing pad and a maintenance rover", "SPACE_OUTPOST", "RETRO_SCIFI"),
    ("a sunny solarpunk farm", "a barn covered in solar canopies", "bright morning", "crop rows, wind turbines, greenhouses and orchards", "FARM", "SOLARPUNK"),
    ("a quiet mountain forest clearing", "a hero tree beside a winding stream", "soft morning light", "rocks, ferns and a narrow path", "NATURE", "CLAY"),
    ("a neon-lit city block after the rain", "a corner noodle shop", "wet night", "signs, street furniture and parked scooters", "CITY", "CYBERPUNK"),
)

SHOTS = (
    ("WIDE", "Wide", "The whole diorama, as built"),
    ("HERO", "Hero", "Closer three-quarter view of the main building"),
    ("DETAIL", "Detail", "Shallow depth of field on the hero"),
)


def _can_animate(context: bpy.types.Context) -> bool:
    return not bpy.app.background and context.window is not None and context.area is not None and context.area.type == "VIEW_3D"


def _view3d_space(context: bpy.types.Context):
    area = context.area
    if area is not None and area.type == "VIEW_3D":
        return area.spaces.active
    return None


def _present_world(context: bpy.types.Context, world: bpy.types.Collection) -> None:
    """Select and frame the new world, switch the viewport to a lit material view, then reveal it."""
    bpy.ops.cozyverse.select_world(world_name=world.name)
    bpy.ops.object.select_all(action="DESELECT")  # keep the framed view, drop the selection tint
    space = _view3d_space(context)
    if space is not None:
        if space.shading.type == "SOLID":
            space.shading.type = "MATERIAL"
        region = space.region_3d
        if region is not None and region.view_perspective == "CAMERA":
            region.view_perspective = "PERSP"
    if _can_animate(context):
        bpy.ops.cozyverse.reveal_world("INVOKE_DEFAULT", world_name=world.name)


class CV_OT_Conjure(bpy.types.Operator):
    bl_idname = "cozyverse.conjure"
    bl_label = "Conjure World"
    bl_description = "Turn the description into a lit, framed, editable world in one step. Every build is a new version; nothing is overwritten"
    bl_options = {"REGISTER", "UNDO"}

    remix: BoolProperty(name="Remix", description="Keep the plan and re-roll the layout", default=False, options={"HIDDEN"})

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        if not _prompt_from_settings(settings):
            self.report({"WARNING"}, "Describe your world first, or press the dice for an idea")
            return {"CANCELLED"}
        if self.remix:
            try:
                plan = _plan_from_settings(settings)
                settings.scene_plan_json = plan.canonical_json()
                _refresh_revision_preview(context, plan)
            except (TypeError, ValueError) as exc:
                self.report({"ERROR"}, f"Remix stopped: {exc}")
                return {"CANCELLED"}
            settings.variation += 1
        else:
            settings.variation = 0
            if bpy.ops.cozyverse.prepare_scene_plan() != {"FINISHED"}:
                return {"CANCELLED"}
            if settings.review_before_build:
                settings.status = "Plan ready. Adjust anything, tick the box, then build"
                return {"FINISHED"}
        settings.plan_approved = True
        _log_activity(context, "APPROVE", "Plan approved by Conjure; a new version is built and nothing is overwritten")
        if bpy.ops.cozyverse.build_approved_plan() != {"FINISHED"}:
            return {"CANCELLED"}
        world = bpy.data.collections.get(settings.active_world_name)
        if world is not None:
            _present_world(context, world)
            settings.status = f"{world.name} is ready" + (f" (remix {settings.variation})" if self.remix else "")
        return {"FINISHED"}


class CV_OT_Surprise(bpy.types.Operator):
    bl_idname = "cozyverse.surprise"
    bl_label = "Surprise Me"
    bl_description = "Pick a random idea, style and mood. Hold Ctrl to conjure it immediately"

    def invoke(self, context: bpy.types.Context, event):
        return self.execute_with(context, conjure=event.ctrl)

    def execute(self, context: bpy.types.Context):
        return self.execute_with(context, conjure=False)

    def execute_with(self, context: bpy.types.Context, conjure: bool):
        from .operators import _compose_prompt
        from .core.style_spec import styled_prompt

        settings = context.scene.cozyverse
        setting, subject, mood, details, _kind, style = random.choice(SURPRISES)
        settings.prompt_setting, settings.prompt_subject, settings.prompt_mood, settings.prompt_details = setting, subject, mood, details
        settings.prompt_avoid = ""
        settings.preset = style
        settings.prompt = styled_prompt(_compose_prompt(setting, subject, mood, details, ""), style)[:4000]
        settings.prompt_text = None
        settings.workflow_step = "DESCRIBE"
        settings.plan_approved = False
        settings.status = f"Idea: {setting}"
        if conjure:
            return bpy.ops.cozyverse.conjure()
        return {"FINISHED"}


class CV_OT_QuickConjure(bpy.types.Operator):
    bl_idname = "cozyverse.quick_conjure"
    bl_label = "CozyVerse: Conjure from Viewport"
    bl_description = "Type a description and conjure a world without leaving the 3D View"

    prompt: StringProperty(name="Describe your world", default="", maxlen=1000)
    style: EnumProperty(name="Style", items=style_items(), default="COZY_VILLAGE")

    def invoke(self, context: bpy.types.Context, _event):
        settings = context.scene.cozyverse
        self.prompt = ""
        self.style = settings.preset
        return context.window_manager.invoke_props_dialog(self, width=520, confirm_text="Conjure")

    def draw(self, _context: bpy.types.Context) -> None:
        layout = self.layout
        layout.label(text="What should we build?", icon="WORLD_DATA")
        layout.prop(self, "prompt", text="", placeholder="a rainy cafe on a tiny island, warm lights, two cats")
        layout.prop(self, "style")
        preset = STYLE_PRESETS.get(self.style)
        if preset:
            layout.label(text=preset.description)

    def execute(self, context: bpy.types.Context):
        from .core.style_spec import styled_prompt

        settings = context.scene.cozyverse
        text = self.prompt.strip()
        if not text:
            self.report({"WARNING"}, "Describe your world first")
            return {"CANCELLED"}
        settings.preset = self.style
        settings.prompt = styled_prompt(text, self.style)[:4000]
        settings.prompt_text = None
        return bpy.ops.cozyverse.conjure()


def _ease_out_back(value: float) -> float:
    value = max(0.0, min(1.0, value))
    c1, c3 = 1.4, 2.4
    return 1.0 + c3 * (value - 1.0) ** 3 + c1 * (value - 1.0) ** 2


class CV_OT_RevealWorld(bpy.types.Operator):
    bl_idname = "cozyverse.reveal_world"
    bl_label = "Reveal World"
    bl_description = "Pop the world's objects in with a short animation; final transforms are restored exactly"

    world_name: StringProperty(options={"HIDDEN"})
    _timer = None
    _items: list = []
    _start = 0.0
    _total = 0.0

    def invoke(self, context: bpy.types.Context, _event):
        world = bpy.data.collections.get(self.world_name)
        if world is None or context.window is None:
            return {"CANCELLED"}
        meshes = [obj for obj in _world_objects(world) if obj.type == "MESH" and not obj.get("cv_weather")]
        if not meshes:
            return {"CANCELLED"}
        rng = random.Random(len(meshes))
        radius = max(0.001, max(math.hypot(obj.location.x, obj.location.y) for obj in meshes))
        self._items = []
        for obj in meshes:
            delay = 0.5 * (math.hypot(obj.location.x, obj.location.y) / radius) + 0.05 * max(0.0, obj.location.z) + rng.uniform(0.0, 0.12)
            self._items.append((obj, obj.location.copy(), obj.scale.copy(), delay))
            obj.scale = (0.0, 0.0, 0.0)
        self._duration = 0.5
        self._total = max(item[3] for item in self._items) + self._duration
        self._start = time.perf_counter()
        self._timer = context.window_manager.event_timer_add(1.0 / 60.0, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _restore(self, context: bpy.types.Context) -> None:
        for obj, location, scale, _delay in self._items:
            try:
                obj.location = location
                obj.scale = scale
            except ReferenceError:
                continue
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        self._items = []

    def modal(self, context: bpy.types.Context, event):
        if event.type == "ESC":
            self._restore(context)
            return {"CANCELLED"}
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        elapsed = time.perf_counter() - self._start
        if elapsed >= self._total:
            self._restore(context)
            if context.area is not None:
                context.area.tag_redraw()
            return {"FINISHED"}
        try:
            for obj, location, scale, delay in self._items:
                progress = (elapsed - delay) / self._duration
                eased = _ease_out_back(progress) if progress > 0.0 else 0.0
                obj.scale = (scale.x * eased, scale.y * eased, scale.z * eased)
                obj.location = (location.x, location.y, location.z + (1.0 - min(1.0, max(0.0, progress))) * 0.35)
        except ReferenceError:
            self._items = []
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
            return {"CANCELLED"}
        if context.area is not None:
            context.area.tag_redraw()
        return {"RUNNING_MODAL"}

    def cancel(self, context: bpy.types.Context) -> None:
        self._restore(context)


class CV_OT_GotoTab(bpy.types.Operator):
    bl_idname = "cozyverse.goto_tab"
    bl_label = "Open Workspace"
    bl_description = "Switch the CozyVerse workspace"

    tab: EnumProperty(items=[(t[0], t[1], t[2]) for t in TABS])

    @classmethod
    def description(cls, _context, properties):
        return next((t[2] for t in TABS if t[0] == properties.tab), cls.bl_description)

    def execute(self, context: bpy.types.Context):
        context.scene.cozyverse.active_tab = self.tab
        return {"FINISHED"}


class CV_OT_SetTimeOfDay(bpy.types.Operator):
    bl_idname = "cozyverse.set_time_of_day"
    bl_label = "Set Time of Day"
    bl_description = "Jump to a time of day; light, sky and window glow update live"

    hour: bpy.props.FloatProperty(default=18.0, options={"HIDDEN"})

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        settings.atmosphere_preset = "CUSTOM"
        settings.time_hour = self.hour
        return {"FINISHED"}


def _camera_collection(world: bpy.types.Collection):
    return next((child for child in world.children if child.name.startswith("CV_CAMERAS")), None)


class CV_OT_FrameShot(bpy.types.Operator):
    bl_idname = "cozyverse.frame_shot"
    bl_label = "Frame Shot"
    bl_description = "Switch to a cinematic camera for this world. Shots are separate cameras; the original is never moved"
    bl_options = {"REGISTER", "UNDO"}

    shot: EnumProperty(items=[(s[0], s[1], s[2]) for s in SHOTS], default="WIDE")
    look_through: BoolProperty(default=True, options={"HIDDEN"})

    def execute(self, context: bpy.types.Context):
        import json

        settings = context.scene.cozyverse
        world = bpy.data.collections.get(settings.active_world_name)
        cameras = _camera_collection(world) if world is not None else None
        if world is None or cameras is None:
            self.report({"WARNING"}, "Conjure or select a world first")
            return {"CANCELLED"}
        base = next((obj for obj in cameras.objects if obj.type == "CAMERA" and not obj.get("cv_shot")), None)
        if base is None:
            return {"CANCELLED"}
        camera = base
        if self.shot != "WIDE":
            camera = next((obj for obj in cameras.objects if obj.get("cv_shot") == self.shot), None)
            hero = next((obj for obj in _world_objects(world) if obj.name.startswith("CV_Hero") and obj.type == "MESH"), None)
            target = hero.location.copy() if hero is not None else Vector((0.0, 0.0, 0.0))
            away = Vector((base.location.x - target.x, base.location.y - target.y, 0.0))
            away = away.normalized() if away.length > 1e-6 else Vector((0.0, -1.0, 0.0))
            if camera is None:
                data = bpy.data.cameras.new(f"CV_Camera_{self.shot.title()}")
                camera = bpy.data.objects.new(f"CV_Camera_{self.shot.title()}", data)
                cameras.objects.link(camera)
                camera["cv_managed"] = True
                camera["cv_demo"] = True
                camera["cv_locked"] = False
                camera["cv_shot"] = self.shot
                camera["cv_world_root"] = world.name
                camera["cv_provenance"] = "offline_procedural_r1"
                data.type = "PERSP"
                if self.shot == "HERO":
                    data.lens = 50.0
                    camera.location = target + away * 6.4 + Vector((0.0, 0.0, 2.7))
                    aim = target + Vector((0.0, 0.0, 1.1))
                else:
                    data.lens = 70.0
                    data.dof.use_dof = True
                    data.dof.aperture_fstop = 1.8
                    if hero is not None:
                        data.dof.focus_object = hero
                    side = Vector((away.x * math.cos(0.45) - away.y * math.sin(0.45), away.x * math.sin(0.45) + away.y * math.cos(0.45), 0.0))
                    camera.location = target + side * 3.6 + Vector((0.0, 0.0, 1.2))
                    aim = target + Vector((0.0, 0.0, 1.0))
                camera.rotation_euler = (aim - camera.location).to_track_quat("-Z", "Y").to_euler()
                camera["cv_generated_transform"] = json.dumps([round(v, 6) for v in (*camera.location, *camera.rotation_euler, *camera.scale)])
        context.scene.camera = camera
        space = _view3d_space(context)
        if self.look_through and space is not None and space.region_3d is not None:
            space.region_3d.view_perspective = "CAMERA"
        settings.status = f"{self.shot.title()} shot ready"
        return {"FINISHED"}


class CV_OT_RenderPostcard(bpy.types.Operator):
    bl_idname = "cozyverse.render_postcard"
    bl_label = "Render Postcard"
    bl_description = "Render the current camera to an image. Uses EEVEE unless you already chose a render engine"

    def execute(self, context: bpy.types.Context):
        scene = context.scene
        if scene.camera is None:
            self.report({"WARNING"}, "Conjure a world first so there is a camera")
            return {"CANCELLED"}
        if scene.render.engine == "BLENDER_WORKBENCH":
            engines = {item.identifier for item in scene.render.bl_rna.properties["engine"].enum_items}
            scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
        if scene.render.resolution_x < 1280:
            scene.render.resolution_x, scene.render.resolution_y = 1600, 1000
            scene.render.resolution_percentage = 100
        if bpy.app.background:
            return {"FINISHED"}
        return bpy.ops.render.render("INVOKE_DEFAULT")


_KEYMAPS: list = []
_CLASSES = (CV_OT_Conjure, CV_OT_Surprise, CV_OT_QuickConjure, CV_OT_RevealWorld, CV_OT_GotoTab, CV_OT_SetTimeOfDay, CV_OT_FrameShot, CV_OT_RenderPostcard)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    wm = bpy.context.window_manager
    keyconfig = wm.keyconfigs.addon if wm is not None else None
    if keyconfig is not None:
        keymap = keyconfig.keymaps.new(name="3D View", space_type="VIEW_3D")
        item = keymap.keymap_items.new("cozyverse.quick_conjure", "W", "PRESS", shift=True, alt=True)
        _KEYMAPS.append((keymap, item))


def unregister() -> None:
    for keymap, item in _KEYMAPS:
        keymap.keymap_items.remove(item)
    _KEYMAPS.clear()
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

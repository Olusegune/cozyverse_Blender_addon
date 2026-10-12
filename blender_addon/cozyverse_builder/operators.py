"""Allowlisted CozyVerse operators for recovery milestone R1."""

from __future__ import annotations

import bpy
import json
from pathlib import Path
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from .atmosphere import apply_atmosphere
from .core.atmosphere_spec import AtmosphereValues, PRESETS, serialize_preset
from .core.demo_spec import DEFAULT_PROMPT
from .world_builder import build_offline_world
from .providers.contracts import build_plan
from .core.reference_spec import dominant_palette, scan_asset_files, validate_reference_path
from .core.style_spec import STYLE_PRESETS, style_items, styled_prompt
from .core.scene_plan import ScenePlan, parse_plan, proposed_plan
from .core.asset_catalog import AssetRecord, match_assets, record_from_path


def _prompt_from_settings(settings) -> str:
    if settings.prompt_text is not None:
        multiline = settings.prompt_text.as_string().strip()
        if multiline:
            return multiline[:4000]
    return settings.prompt.strip()[:4000]


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
        _prompt_from_settings(settings),
    )
    plan.validate()
    return plan


def _world_objects(collection):
    objects = list(collection.objects)
    for child in collection.children:
        objects.extend(_world_objects(child))
    return objects


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
        plan = proposed_plan(prompt, settings.preset)
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
        settings.plan_approved = False
        settings.workflow_step = "REVIEW"
        settings.operation_progress = 0.35
        settings.last_error = ""
        settings.recovery_hint = "Review every section, approve the plan, then build a new version."
        settings.status = "Plan ready for review; no objects were created"
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
            settings.scene_plan_json = plan.canonical_json()
            settings.operation_progress = 0.55
            settings.status = "Building a new editable world version..."
            world = build_offline_world(context.scene, settings, plan.prompt, json.loads(settings.scene_plan_json))
            settings.operation_progress = 1.0
            settings.workflow_step = "BUILT"
            settings.active_world_name = world.name
            settings.last_demo_prompt = plan.prompt
            settings.last_error = ""
            settings.recovery_hint = "Use Select & Frame to inspect it. Previous versions remain untouched."
            settings.status = f"World ready: {world.name}"
            self.report({"INFO"}, settings.status)
            return {"FINISHED"}
        except (ValueError, RuntimeError) as exc:
            settings.last_error = f"Build stopped: {exc}"
            settings.recovery_hint = "Return to the plan, correct invalid values, and try again."
            settings.operation_progress = 0.35
            settings.status = settings.last_error
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
        for obj in objects:
            obj.hide_set(False)
            obj.select_set(True)
        if objects:
            context.view_layer.objects.active = objects[0]
        context.scene.cozyverse.active_world_name = world.name
        context.scene["cv_active_world"] = world.name
        if context.area is not None and context.area.type == "VIEW_3D" and objects:
            bpy.ops.view3d.view_selected(use_all_regions=False)
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
            edited += bool(baseline and baseline != current)
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


class CV_OT_CreateLocalDemo(bpy.types.Operator):
    bl_idname = "cozyverse.create_local_demo"
    bl_label = "Build World"
    bl_description = "Build a new editable miniature world locally without an AI or paid service"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        prompt = _prompt_from_settings(settings)
        if not prompt:
            settings.status = "Add a world description before building"
            self.report({"WARNING"}, settings.status)
            return {"CANCELLED"}
        try:
            settings.status = "Building editable offline world..."
            world = build_offline_world(context.scene, settings, prompt)
            settings.last_demo_prompt = prompt
            settings.active_world_name = world.name
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
        settings.prompt = styled_prompt(prompt, self.style)[:4000]
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
        settings.prompt = styled_prompt(_compose_prompt(setting, subject, mood, details, avoid), settings.preset)
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
            palette = dominant_palette(list(image.pixels), image.channels, 5)
        except (RuntimeError, ValueError) as exc:
            settings.reference_status = f"Image analysis failed: {exc}"
            return {"CANCELLED"}
        if not palette:
            settings.reference_status = "The image did not contain readable color pixels"
            return {"CANCELLED"}
        settings.reference_palette_json = json.dumps(palette)
        settings.reference_status = f"Local palette ready: {len(palette)} colors; image was not uploaded"
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
        prompt = f"Editable local interpretation of the diorama reference {settings.reference_image.name}"
        root = build_offline_world(context.scene, settings, prompt)
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
                        material.diffuse_color = (*color, 1.0)
        root["cv_reference_image"] = settings.reference_image_path
        root["cv_reference_mode"] = "local_palette_interpretation"
        root["cv_indexed_asset_count"] = int(settings.indexed_asset_count or 0)
        settings.reference_status = f"Editable interpretation ready: {root.name}"
        settings.active_world_name = root.name
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
        settings.atmosphere_preset = "GOLDEN_HOUR"
        settings.time_hour = values.time_hour
        settings.sun_intensity = values.sun_intensity
        settings.warmth = values.warmth
        settings.ambient_intensity = values.ambient_intensity
        settings.interior_intensity = values.interior_intensity
        settings.weather = values.weather
        settings.rain_amount = values.rain_amount
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
        values = AtmosphereValues(
            settings.time_hour,
            settings.sun_intensity,
            settings.warmth,
            settings.ambient_intensity,
            settings.interior_intensity,
            settings.weather,
            settings.rain_amount,
        )
        context.scene["cv_custom_atmosphere_preset"] = serialize_preset(values)
        settings.atmosphere_preset = "CUSTOM"
        settings.status = "Custom atmosphere preset saved in this scene"
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
        settings.generation_approved = False
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
        collection = bpy.data.collections.get("CV_GENERATED_PREVIEWS")
        if collection is None:
            collection = bpy.data.collections.new("CV_GENERATED_PREVIEWS")
            context.scene.collection.children.link(collection)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.8)
        obj = context.object
        for owner in list(obj.users_collection):
            owner.objects.unlink(obj)
        collection.objects.link(obj)
        obj.name = "CV_Mock_Generated_Asset"
        obj["cv_provider_mock"] = True
        obj["cv_plan_fingerprint"] = settings.generation_fingerprint
        obj["cv_prompt"] = settings.generation_prompt
        settings.generation_approved = False
        settings.generation_status = "Mock job completed; no provider request or charge occurred"
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
    CV_OT_BuildApprovedPlan,
    CV_OT_SelectWorld,
    CV_OT_ArchiveWorld,
    CV_OT_InspectManualEdits,
    CV_OT_LockSelectedObjects,
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
    CV_OT_ClearApiKey,
    CV_OT_ClearGenerationKey,
    CV_OT_ValidateGenerationSettings,
    CV_OT_PreviewGeneration,
    CV_OT_RunMockGeneration,
    CV_OT_ValidateProviderSettings,
)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

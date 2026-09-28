"""Allowlisted CozyVerse operators for recovery milestone R1."""

from __future__ import annotations

import bpy
import json
from bpy.props import EnumProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from .atmosphere import apply_atmosphere
from .core.atmosphere_spec import AtmosphereValues, PRESETS, serialize_preset
from .core.demo_spec import DEFAULT_PROMPT
from .world_builder import build_offline_world
from .providers.contracts import build_plan
from .core.reference_spec import dominant_palette, scan_asset_files, validate_reference_path
from .core.style_spec import STYLE_PRESETS, style_items, styled_prompt


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
            roots.append(bpy.path.abspath(preferences.custom_asset_folder))
        if preferences.include_blender_asset_libraries:
            roots.extend(library.path for library in context.preferences.filepaths.asset_libraries)
        paths = scan_asset_files(roots)
        settings = context.scene.cozyverse
        settings.indexed_asset_count = str(len(paths))
        settings.indexed_asset_preview = json.dumps(paths[:100])
        settings.reference_status = f"Indexed {len(paths)} supported local model file(s); none were opened"
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
        for material_name, color in zip(material_names, palette):
            material = bpy.data.materials.get(material_name)
            if material is not None:
                material.diffuse_color = (*color, 1.0)
        root["cv_reference_image"] = settings.reference_image_path
        root["cv_reference_mode"] = "local_palette_interpretation"
        root["cv_indexed_asset_count"] = int(settings.indexed_asset_count or 0)
        settings.reference_status = f"Editable interpretation ready: {root.name}"
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
    CV_OT_CreateLocalDemo,
    CV_OT_PromptComposer,
    CV_OT_ApplyPromptTemplate,
    CV_OT_PastePrompt,
    CV_OT_SelectReferenceImage,
    CV_OT_AnalyzeReferenceLocally,
    CV_OT_IndexLocalAssets,
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

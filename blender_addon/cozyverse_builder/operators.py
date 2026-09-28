"""Allowlisted CozyVerse operators for recovery milestone R1."""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty

from .atmosphere import apply_atmosphere
from .core.atmosphere_spec import AtmosphereValues, PRESETS, serialize_preset
from .core.demo_spec import DEFAULT_PROMPT
from .world_builder import build_offline_world


def _prompt_from_settings(settings) -> str:
    if settings.prompt_text is not None:
        multiline = settings.prompt_text.as_string().strip()
        if multiline:
            return multiline[:4000]
    return settings.prompt.strip()[:4000]


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
    CV_OT_EditMultilinePrompt,
    CV_OT_UseMultilinePrompt,
    CV_OT_ResetPrompt,
    CV_OT_ApplyAtmosphere,
    CV_OT_ResetAtmosphere,
    CV_OT_SaveAtmospherePreset,
    CV_OT_ClearApiKey,
    CV_OT_ClearGenerationKey,
    CV_OT_ValidateGenerationSettings,
    CV_OT_ValidateProviderSettings,
)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

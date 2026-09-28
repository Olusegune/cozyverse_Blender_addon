"""CozyVerse sidebar panels."""

from __future__ import annotations

import bpy


class _CVPanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CozyVerse"


class CV_PT_Create(_CVPanel, bpy.types.Panel):
    bl_idname = "CV_PT_create"
    bl_label = "CozyVerse Builder"

    def draw(self, context: bpy.types.Context) -> None:
        settings = context.scene.cozyverse
        layout = self.layout
        layout.label(text="Local demonstration mode", icon="WORLD")
        layout.prop(settings, "prompt", text="")
        layout.prop(settings, "preset")
        row = layout.row(align=True)
        row.operator("cozyverse.create_local_demo", icon="OUTLINER_COLLECTION")
        row.operator("cozyverse.reset_prompt", text="", icon="LOOP_BACK")


class CV_PT_Status(_CVPanel, bpy.types.Panel):
    bl_idname = "CV_PT_status"
    bl_label = "Status"
    bl_parent_id = "CV_PT_create"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        settings = context.scene.cozyverse
        layout = self.layout
        layout.label(text=settings.status, icon="INFO")
        layout.label(text="Offline only - no external requests")
        if settings.last_demo_prompt:
            layout.label(text="The last prompt is stored in scene settings.")


class CV_PT_Settings(_CVPanel, bpy.types.Panel):
    bl_idname = "CV_PT_settings"
    bl_label = "Settings"
    bl_parent_id = "CV_PT_create"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        preferences = context.preferences.addons.get(__package__)
        if preferences is not None:
            layout.prop(preferences.preferences, "local_demo_only")
        else:
            layout.label(text="Local demonstration mode is enforced", icon="LOCKED")
        layout.label(text=f"Blender {bpy.app.version_string}")
        layout.label(text="CozyVerse 0.1.0")


_CLASSES = (CV_PT_Create, CV_PT_Status, CV_PT_Settings)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)


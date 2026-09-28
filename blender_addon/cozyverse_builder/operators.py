"""Allowlisted Blender operators for the CozyVerse foundation milestone."""

from __future__ import annotations

import math

import bpy

from .core.demo_spec import (
    DEMO_COLLECTION_NAME,
    DEMO_ITEMS,
    DEMO_SCHEMA_VERSION,
    normalized_prompt,
    validate_demo_spec,
)


def _prepare_demo_collection(scene: bpy.types.Scene) -> bpy.types.Collection:
    collection = bpy.data.collections.get(DEMO_COLLECTION_NAME)
    if collection is None:
        collection = bpy.data.collections.new(DEMO_COLLECTION_NAME)
        scene.collection.children.link(collection)
    else:
        for obj in list(collection.objects):
            if obj.get("cv_demo") is True:
                bpy.data.objects.remove(obj, do_unlink=True)
    collection["cv_managed"] = True
    collection["cv_demo"] = True
    collection["cv_schema_version"] = DEMO_SCHEMA_VERSION
    return collection


def _move_to_collection(obj: bpy.types.Object, collection: bpy.types.Collection) -> None:
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    collection.objects.link(obj)


def _mark_object(obj: bpy.types.Object, item_name: str) -> None:
    obj.name = item_name
    obj["cv_id"] = item_name.lower()
    obj["cv_managed"] = True
    obj["cv_demo"] = True
    obj["cv_provenance"] = "bundled_procedural_demo"


def _add_tree(item, collection: bpy.types.Collection) -> None:
    x, y, z = item.location
    sx, sy, sz = item.scale
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.18 * sx, depth=1.5 * sz, location=(x, y, z + 0.75 * sz))
    trunk = bpy.context.object
    _mark_object(trunk, f"{item.name}_Trunk")
    _move_to_collection(trunk, collection)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.9 * sx, location=(x, y, z + 1.8 * sz))
    crown = bpy.context.object
    crown.scale = (1.0, sy / sx, 1.15 * sz / sx)
    _mark_object(crown, f"{item.name}_Crown")
    _move_to_collection(crown, collection)


def _create_geometry(collection: bpy.types.Collection) -> None:
    for item in DEMO_ITEMS:
        if item.kind == "tree":
            _add_tree(item, collection)
            continue
        if item.kind == "cube":
            bpy.ops.mesh.primitive_cube_add(location=item.location)
        elif item.kind == "cone4":
            bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=1.0, radius2=0.0, depth=2.0, location=item.location)
            bpy.context.object.rotation_euler[2] = math.radians(45)
        obj = bpy.context.object
        obj.scale = item.scale
        _mark_object(obj, item.name)
        _move_to_collection(obj, collection)


def _create_lighting_and_camera(collection: bpy.types.Collection) -> None:
    sun_data = bpy.data.lights.new("CV_Demo_Sun", type="SUN")
    sun_data.energy = 2.0
    sun_data.color = (1.0, 0.72, 0.48)
    sun = bpy.data.objects.new("CV_Demo_Sun", sun_data)
    sun.rotation_euler = (math.radians(28), math.radians(-18), math.radians(32))
    collection.objects.link(sun)
    _mark_object(sun, "CV_Demo_Sun")

    camera_data = bpy.data.cameras.new("CV_Demo_Camera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 13.0
    camera = bpy.data.objects.new("CV_Demo_Camera", camera_data)
    camera.location = (10.5, -12.0, 10.0)
    camera.rotation_euler = (math.radians(58), 0.0, math.radians(40))
    collection.objects.link(camera)
    _mark_object(camera, "CV_Demo_Camera")
    bpy.context.scene.camera = camera


class CV_OT_CreateLocalDemo(bpy.types.Operator):
    bl_idname = "cozyverse.create_local_demo"
    bl_label = "Create Local Demo"
    bl_description = "Create an editable deterministic miniature scene without network access"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        try:
            validate_demo_spec()
            collection = _prepare_demo_collection(context.scene)
            _create_geometry(collection)
            _create_lighting_and_camera(collection)
            prompt = normalized_prompt(settings.prompt)
            collection["cv_prompt"] = prompt
            collection["cv_preset"] = settings.preset
            settings.last_demo_prompt = prompt
            settings.status = f"Local demo ready: {len(collection.objects)} editable objects"
            self.report({"INFO"}, settings.status)
            return {"FINISHED"}
        except Exception as exc:
            settings.status = f"Demo failed: {exc}"
            self.report({"ERROR"}, settings.status)
            return {"CANCELLED"}


class CV_OT_ResetPrompt(bpy.types.Operator):
    bl_idname = "cozyverse.reset_prompt"
    bl_label = "Reset Prompt"
    bl_description = "Restore the bundled offline demonstration prompt"
    bl_options = {"UNDO"}

    def execute(self, context: bpy.types.Context):
        from .core.demo_spec import DEFAULT_PROMPT

        context.scene.cozyverse.prompt = DEFAULT_PROMPT
        context.scene.cozyverse.status = "Prompt reset"
        return {"FINISHED"}


_CLASSES = (CV_OT_CreateLocalDemo, CV_OT_ResetPrompt)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

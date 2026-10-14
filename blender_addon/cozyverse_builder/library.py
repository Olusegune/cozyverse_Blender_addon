"""The Library: your own models, browsable with thumbnails and usable by CozyVerse.

Sources (folders of .blend, .glb, .gltf, .fbx and .obj files, plus any Blender Asset Library) are
indexed into a small JSON file in Blender's user config folder, so they follow you between
projects. Your per-asset choices (role, licence, front, stylise) live there too. Importing reuses
the same safety rules as the rest of the add-on: nothing runs on scan, drivers on imported objects
are stripped, and everything lands in editable, labelled collections.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import bpy
import bpy.utils.previews
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from mathutils import Vector

from .core import library_spec as spec
from .core.asset_catalog import tokenize
from .materials import create_material
from .operators import _import_external_asset, _log_activity
from .visual_assets import icon_id

MAX_RECORDS = 5000
SCAN_SECONDS = 25.0
PAGE_SIZE = 8
_SKIP_DIRS = {"__pycache__", "node_modules", "textures", "tex", "maps"}
_ROLE_LABELS = {role: label for role, label, _ in spec.ROLES}
_PLACEHOLDER = {"CAR": "vehicle", "TREE": "vegetation", "LAMP": "prop", "BUILDING": "building", "CHARACTER": "character", "PROP": "prop", "UNTAGGED": "other"}

_STATE: dict | None = None
_VERSION = 0
_VIEW: dict = {"key": None, "records": []}
_PREVIEWS = None
_NO_THUMB: set[str] = set()
_SYNCING = False


# ----------------------------------------------------------------------------- store


def store_path() -> Path:
    override = os.environ.get("COZYVERSE_LIBRARY_PATH")
    if override:
        return Path(override)
    return Path(bpy.utils.user_resource("CONFIG", path="cozyverse", create=True)) / "library.json"


def reset_state() -> None:
    """Forget the in-memory copy so the next access reads the file again."""
    global _STATE, _VERSION
    _STATE = None
    _VERSION += 1
    _VIEW["key"] = None


def state() -> dict:
    global _STATE
    if _STATE is None:
        try:
            _STATE = spec.load_state(store_path().read_text(encoding="utf-8"))
        except OSError:
            _STATE = spec.new_state()
    return _STATE


def save_state() -> None:
    global _VERSION
    path = store_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(spec.dump_state(state()), encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        pass  # the library keeps working in memory; it just will not persist this time
    _VERSION += 1
    _VIEW["key"] = None


def sources_by_id() -> dict:
    return {source["id"]: source for source in state()["sources"]}


def effective_records() -> list[dict]:
    st = state()
    sources = sources_by_id()
    return [spec.effective(record, st["overrides"], sources) for record in st["index"]]


def record_for(key: str) -> dict | None:
    return next((record for record in effective_records() if record["key"] == key), None)


def set_override(key: str, **values) -> None:
    overrides = state()["overrides"].setdefault(key, {})
    overrides.update(values)
    save_state()


# ----------------------------------------------------------------------------- scanning


def _peek_blend(path: str) -> list[str]:
    """Names of asset-marked collections and objects, read without loading any data."""
    try:
        with bpy.data.libraries.load(path, link=False, assets_only=True) as (source, _target):
            return [f"Collection:{name}" for name in source.collections] + [f"Object:{name}" for name in source.objects]
    except Exception:
        return []


def _record(path: str, inner: str, source_id: str) -> dict:
    item = Path(path)
    label = inner.partition(":")[2] if inner else item.stem
    name = label.replace("_", " ").replace("-", " ").strip() or item.stem
    return {
        "key": spec.asset_key(path, inner),
        "path": path,
        "inner": inner,
        "name": name,
        "ext": item.suffix.lower(),
        "source": source_id,
        "tags": list(tokenize(f"{name} {item.stem} {item.parent.name}")),
        "role_guess": spec.guess_role(name, item.stem, item.parent.name),
    }


def _walk(root: Path):
    for folder, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith((".", "__")) and d.lower() not in _SKIP_DIRS)
        for filename in sorted(files):
            if Path(filename).suffix.lower() in spec.MODEL_EXTENSIONS:
                yield os.path.join(folder, filename)


def scan(context: bpy.types.Context) -> tuple[int, bool]:
    """Re-index every enabled source. Returns (record count, finished before the time budget)."""
    st = state()
    started = time.monotonic()
    sources = [(source["id"], source["path"]) for source in st["sources"] if source.get("enabled", True)]
    entry = context.preferences.addons.get(__package__)
    if entry is not None and entry.preferences.include_blender_asset_libraries:
        for library in context.preferences.filepaths.asset_libraries:
            if library.path:
                sources.append((f"blender:{library.name}", library.path))
    records: list[dict] = []
    seen: set[str] = set()
    finished = True
    for source_id, raw in sources:
        root = Path(bpy.path.abspath(raw)).expanduser()
        if not root.is_dir():
            continue
        for path in _walk(root):
            if time.monotonic() - started > SCAN_SECONDS or len(records) >= MAX_RECORDS:
                finished = False
                break
            inners = _peek_blend(path) if path.lower().endswith(".blend") else []
            for inner in inners or [""]:
                record = _record(path, inner, source_id)
                if record["key"].casefold() not in seen:
                    seen.add(record["key"].casefold())
                    records.append(record)
        if not finished:
            break
    st["index"] = records
    for source_id, raw in sources:  # remember Blender's own libraries so their licence can be set
        if source_id.startswith("blender:") and source_id not in {s["id"] for s in st["sources"]}:
            st["sources"].append({"id": source_id, "label": source_id.partition(":")[2], "path": raw, "license": "UNKNOWN", "enabled": True})
    save_state()
    return len(records), finished


# ----------------------------------------------------------------------------- view & thumbnails


def view(settings, size: int = PAGE_SIZE):
    """(records on the page, page, total pages, matches). Filtering is cached per library version."""
    key = (_VERSION, settings.library_query, settings.library_role)
    if _VIEW["key"] != key:
        _VIEW["records"] = spec.filter_records(effective_records(), settings.library_query, settings.library_role)
        _VIEW["key"] = key
    records = _VIEW["records"]
    page_records, page, total = spec.page_of(records, settings.library_page, size)
    return page_records, page, total, len(records)


def _previews():
    global _PREVIEWS
    if _PREVIEWS is None:
        _PREVIEWS = bpy.utils.previews.new()
    return _PREVIEWS


def thumb_path(record: dict) -> Path:
    folder = store_path().parent / "thumbs"
    return folder / f"{hashlib.sha1(record['key'].encode('utf-8')).hexdigest()[:24]}.png"


MAX_THUMB_BYTES = 120 * 1024 * 1024


def render_thumbnail(record: dict, size: int = 192) -> Path:
    """Render a small preview of a model in a throwaway scene, then remove everything it created."""
    path = Path(bpy.path.abspath(record["path"]))
    if not path.is_file():
        raise ValueError("The file is missing")
    if path.stat().st_size > MAX_THUMB_BYTES:
        raise ValueError("The file is too large to preview automatically")
    target = thumb_path(record)
    target.parent.mkdir(parents=True, exist_ok=True)
    before = {name: set(getattr(bpy.data, name)) for name in ("meshes", "materials", "images", "node_groups", "cameras", "lights", "curves", "actions")}
    scene = bpy.data.scenes.new("CV_Thumb")
    holder = bpy.data.collections.new("CV_Thumb")
    scene.collection.children.link(holder)
    camera_object = None
    try:
        with bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0]):
            imported = _import_blend(str(path), record.get("inner", ""), holder) if path.suffix.lower() == ".blend" else _import_external_asset(str(path), path.suffix.lower(), holder)
            if not imported:
                raise ValueError("Nothing was found in the file")
            for obj in imported:  # Workbench previews use the viewport color, so mirror each shader's base color
                for slot in obj.material_slots:
                    if slot.material is not None:
                        slot.material.diffuse_color = _base_color(slot.material)
            low, high = _world_bounds(imported)
            center = Vector(((low[0] + high[0]) / 2, (low[1] + high[1]) / 2, (low[2] + high[2]) / 2))
            extent = max(high[0] - low[0], high[1] - low[1], high[2] - low[2], 1e-6)
            camera = bpy.data.cameras.new("CV_Thumb")
            camera.type = "ORTHO"
            camera.ortho_scale = extent * 1.45
            camera_object = bpy.data.objects.new("CV_Thumb", camera)
            holder.objects.link(camera_object)
            camera_object.location = center + Vector((1.0, -1.15, 0.85)).normalized() * extent * 3.0
            camera_object.rotation_euler = (center - camera_object.location).to_track_quat("-Z", "Y").to_euler()
            scene.camera = camera_object
            scene.render.engine = "BLENDER_WORKBENCH"
            scene.render.resolution_x = scene.render.resolution_y = size
            scene.render.resolution_percentage = 100
            scene.render.film_transparent = True
            scene.render.image_settings.file_format = "PNG"
            scene.render.image_settings.color_mode = "RGBA"
            scene.display.shading.light = "STUDIO"
            scene.display.shading.color_type = "MATERIAL"
            scene.display.shading.show_cavity = True
            scene.render.filepath = str(target)
            bpy.ops.render.render(write_still=True, scene=scene.name)
    finally:
        for obj in list(holder.all_objects):
            bpy.data.objects.remove(obj)
        for child in list(holder.children):
            bpy.data.collections.remove(child)
        bpy.data.collections.remove(holder)
        bpy.data.scenes.remove(scene)
        for name, known in before.items():
            for block in list(getattr(bpy.data, name)):
                if block not in known and block.users == 0:
                    getattr(bpy.data, name).remove(block)
    return target


def thumbnail_id(record: dict) -> int:
    """Sidecar image, the .blend's own thumbnail, or a role placeholder, in that order."""
    collection = _previews()
    key = record["key"]
    if key in _NO_THUMB:
        return icon_id(f"placeholder_{_PLACEHOLDER.get(record['role'], 'other')}")
    made = thumb_path(record)
    if made.is_file():
        token = f"{key}@{made.stat().st_mtime_ns}"  # a new render gets a new key, so the preview refreshes
        try:
            return (collection[token] if token in collection else collection.load(token, str(made), "IMAGE")).icon_id
        except Exception:
            pass
    if key in collection:
        return collection[key].icon_id
    if True:
        path = Path(record["path"])
        try:
            for extension in (".png", ".jpg", ".jpeg", ".webp"):
                sidecar = path.with_suffix(extension)
                if sidecar.is_file():
                    return collection.load(key, str(sidecar), "IMAGE").icon_id
            if record["ext"] == ".blend" and path.is_file():
                preview = collection.load(key, str(path), "BLEND")
                if preview.image_size[0] * preview.image_size[1] > 0:
                    return preview.icon_id
        except Exception:
            pass
        _NO_THUMB.add(key)
    return icon_id(f"placeholder_{_PLACEHOLDER.get(record['role'], 'other')}")


def clear_thumbnails() -> None:
    global _PREVIEWS
    if _PREVIEWS is not None:
        bpy.utils.previews.remove(_PREVIEWS)
        _PREVIEWS = None
    _NO_THUMB.clear()


# ----------------------------------------------------------------------------- importing


def _import_blend(path: str, inner: str, target) -> list[bpy.types.Object]:
    kind, name = spec.split_inner(inner)
    with bpy.data.libraries.load(path, link=False) as (source, loaded):
        if kind == "Collection" and name in source.collections:
            loaded.collections = [name]
        elif kind == "Object" and name in source.objects:
            loaded.objects = [name]
        elif source.collections:
            loaded.collections = [source.collections[0]]
        elif source.objects:
            loaded.objects = [source.objects[0]]
        else:
            raise ValueError("The file contains no collection or object")
    imported: list[bpy.types.Object] = []
    for collection in loaded.collections:
        if collection is not None:
            target.children.link(collection)
            imported.extend(collection.all_objects)
    for obj in loaded.objects:
        if obj is not None:
            target.objects.link(obj)
            imported.append(obj)
    return list(dict.fromkeys(imported))


def _base_color(material) -> tuple[float, float, float, float]:
    if material is not None and material.node_tree is not None:
        node = next((n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
        if node is not None:
            return tuple(node.inputs["Base Color"].default_value)
    return tuple(material.diffuse_color) if material is not None else (0.6, 0.6, 0.6, 1.0)


def stylize(objects) -> int:
    """Replace materials with flat clay-like ones of the same color, so a realistic model sits in the diorama."""
    cache: dict[tuple, bpy.types.Material] = {}
    changed = 0
    for obj in objects:
        if obj.type != "MESH":
            continue
        for slot in obj.material_slots:
            color = tuple(round(v, 2) for v in _base_color(slot.material))
            if color not in cache:
                cache[color] = create_material(f"CV_Mat_Lib_{len(cache) + 1}", color, 0.0, 0.8)
            slot.material = cache[color]
            changed += 1
    return changed


def _world_bounds(objects) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    bpy.context.view_layer.update()
    points = []
    for obj in objects:
        if obj.type in {"MESH", "CURVE", "SURFACE", "FONT"}:
            points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    if not points:
        raise ValueError("The model has no geometry to measure")
    return (
        (min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)),
        (max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)),
    )


def place_asset(record: dict, collection: bpy.types.Collection, role: str | None = None, location=(0.0, 0.0, 0.0), parent=None) -> bpy.types.Object:
    """Import a library asset, stand it on the ground facing +X at its role's size, and return its wrapper.

    ``location`` is where the model's bottom centre goes; ``parent`` (a vehicle root, say) makes
    ``location`` local to it. On any failure everything imported is removed again.
    """
    role = role or record["role"]
    path = Path(bpy.path.abspath(record["path"])).resolve()
    if not path.is_file() or path.suffix.lower() not in spec.MODEL_EXTENSIONS:
        raise ValueError("The file is missing or is not a supported model")
    imported: list[bpy.types.Object] = []
    wrapper = None
    try:
        imported = _import_blend(str(path), record.get("inner", ""), collection) if path.suffix.lower() == ".blend" else _import_external_asset(str(path), path.suffix.lower(), collection)
        if not imported:
            raise ValueError("Nothing was found in the file")
        for obj in imported:
            if obj.animation_data is not None and obj.animation_data.drivers:
                obj.animation_data_clear()  # imported drivers are never trusted
        wrapper = bpy.data.objects.new(f"CV_Asset_{record['name'][:40]}", None)
        wrapper.empty_display_type = "PLAIN_AXES"
        wrapper.empty_display_size = 0.2
        collection.objects.link(wrapper)
        roots = [obj for obj in imported if obj.parent is None or obj.parent not in imported]
        for obj in roots:
            obj.parent = wrapper
        fit = spec.fit_transform(*_world_bounds(imported), role, record.get("forward", "AUTO"))
        wrapper.scale = (fit["scale"],) * 3
        wrapper.rotation_euler = (0.0, 0.0, fit["yaw"])
        wrapper.location = tuple(offset + base for offset, base in zip(fit["offset"], location))
        if parent is not None:
            wrapper.parent = parent
        if record.get("stylize"):
            stylize(imported)
        for obj in (*imported, wrapper):
            obj["cv_managed"] = True
            obj["cv_locked"] = False
            obj["cv_asset_source"] = str(path)
            obj["cv_asset_role"] = role
            obj["cv_license"] = record.get("license", "UNKNOWN")
            obj["cv_provenance"] = "user_library_asset"
        return wrapper
    except Exception:
        for obj in (*imported, wrapper):
            if obj is not None and bpy.data.objects.get(obj.name) is obj:
                bpy.data.objects.remove(obj)
        raise


def slot_asset(settings, role: str) -> dict | None:
    """The library asset chosen for a role (currently CAR), when it is switched on and still exists."""
    if role == "CAR" and settings.slot_car_enabled and settings.slot_car_asset:
        record = record_for(settings.slot_car_asset)
        if record is not None and Path(bpy.path.abspath(record["path"])).is_file():
            return record
    return None


def sync_edit_fields(settings, record: dict | None) -> None:
    """Load the selected asset's values into the editable fields without writing them back."""
    global _SYNCING
    if record is None:
        return
    _SYNCING = True
    try:
        settings.library_edit_role = record["role"]
        settings.library_edit_license = record["license"]
        settings.library_edit_forward = record["forward"]
        settings.library_edit_stylize = record["stylize"]
    finally:
        _SYNCING = False


def write_edit_fields(settings) -> None:
    if _SYNCING or not settings.library_selected:
        return
    set_override(
        settings.library_selected,
        role=settings.library_edit_role,
        license=settings.library_edit_license,
        forward=settings.library_edit_forward,
        stylize=settings.library_edit_stylize,
    )


# ----------------------------------------------------------------------------- UI helpers


def draw_browser(layout: bpy.types.UILayout, context: bpy.types.Context, columns: int = 2, size: int = PAGE_SIZE) -> None:
    settings = context.scene.cozyverse
    if not state()["sources"] and not state()["index"]:
        box = layout.box()
        if icon_id("empty_no_assets"):
            box.template_icon(icon_value=icon_id("empty_no_assets"), scale=5.0)
        box.label(text="Add a folder of models to begin", icon="ASSET_MANAGER")
        box.operator("cozyverse.library_add_folder", text="Add Library Folder", icon="NEWFOLDER")
        return
    search = layout.row(align=True)
    search.prop(settings, "library_query", text="", icon="VIEWZOOM", placeholder="Search")
    search.prop(settings, "library_role", text="")
    records, page, total, matches = view(settings, size)
    if not records:
        layout.label(text="Nothing matches. Try another search or role.", icon="INFO")
    grid = layout.grid_flow(row_major=True, columns=columns, even_columns=True, even_rows=False, align=False)
    for record in records:
        cell = grid.box().column(align=True)
        cell.template_icon(icon_value=thumbnail_id(record), scale=4.0 if columns <= 2 else 5.0)
        choose = cell.operator("cozyverse.library_select", text=record["name"][:18], depress=record["key"] == settings.library_selected)
        choose.key = record["key"]
        note = cell.row()
        note.active = False
        label = _ROLE_LABELS.get(record["role"], "")
        note.label(text=label, icon="ERROR" if record["license"] == "EDITORIAL" else "NONE")
    pager = layout.row(align=True)
    large = columns > 2
    previous = pager.operator("cozyverse.library_page", text="", icon="TRIA_LEFT")
    previous.delta = -1
    previous.reopen = large
    pager.label(text=f"{page + 1} / {total}   ({matches})")
    following = pager.operator("cozyverse.library_page", text="", icon="TRIA_RIGHT")
    following.delta = 1
    following.reopen = large
    if not large:
        pager.operator("cozyverse.library_thumbnails", text="", icon="RENDER_RESULT")
        pager.operator("cozyverse.library_browser", text="", icon="FULLSCREEN_ENTER")


def draw_selected(layout: bpy.types.UILayout, context: bpy.types.Context) -> None:
    settings = context.scene.cozyverse
    record = record_for(settings.library_selected) if settings.library_selected else None
    if record is None:
        return
    box = layout.box()
    box.template_icon(icon_value=thumbnail_id(record), scale=6.0)
    box.label(text=record["name"])
    sub = box.row()
    sub.active = False
    sub.label(text=f"{record['source_label'] or 'Library'} · {record['ext'].lstrip('.').upper()}")
    box.prop(settings, "library_edit_role", text="Role")
    box.prop(settings, "library_edit_license", text="Licence")
    box.prop(settings, "library_edit_forward", text="Front")
    box.prop(settings, "library_edit_stylize")
    if record["license"] == "EDITORIAL":
        warning = box.box()
        warning.alert = True
        warning.label(text="Editorial only: check before publishing renders.", icon="ERROR")
    row = box.row(align=True)
    row.scale_y = 1.3
    row.operator("cozyverse.library_place", text="Place in World", icon="IMPORT")
    if record["role"] == "CAR":
        box.operator("cozyverse.library_use_as", text="Use as My Car", icon="AUTO").role = "CAR"


def draw_sources(layout: bpy.types.UILayout) -> None:
    counts: dict[str, int] = {}
    for record in state()["index"]:
        counts[record["source"]] = counts.get(record["source"], 0) + 1
    for source in state()["sources"]:
        row = layout.row(align=True)
        row.label(text=f"{source['label']}  ({counts.get(source['id'], 0)})", icon="FILE_FOLDER")
        license_label = next((label for key, label, _ in spec.LICENSES if key == source["license"]), "Not sure")
        menu = row.operator_menu_enum("cozyverse.library_source_license", "license", text=license_label)
        menu.source = source["id"]
        remove = row.operator("cozyverse.library_remove_source", text="", icon="X")
        remove.source = source["id"]
    buttons = layout.row(align=True)
    buttons.operator("cozyverse.library_add_folder", text="Add Folder", icon="NEWFOLDER")
    buttons.operator("cozyverse.library_rescan", text="Rescan", icon="FILE_REFRESH")


# ----------------------------------------------------------------------------- operators


class CV_OT_LibraryAddFolder(bpy.types.Operator):
    bl_idname = "cozyverse.library_add_folder"
    bl_label = "Add Library Folder"
    bl_description = "Index a folder of .blend, .glb, .gltf, .fbx and .obj models. Files are only listed, never run"

    directory: StringProperty(subtype="DIR_PATH")
    label: StringProperty(name="Name", default="", description="Optional name; defaults to the folder name")

    def invoke(self, context: bpy.types.Context, _event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context: bpy.types.Context):
        root = Path(bpy.path.abspath(self.directory)).expanduser()
        if not root.is_dir():
            self.report({"WARNING"}, "Choose a folder, not a file")
            return {"CANCELLED"}
        st = state()
        if any(Path(bpy.path.abspath(s["path"])).resolve() == root.resolve() for s in st["sources"]):
            self.report({"INFO"}, "That folder is already in your library")
            return {"CANCELLED"}
        numbers = [int(s["id"][1:]) for s in st["sources"] if s["id"][1:].isdigit()]
        st["sources"].append({"id": f"s{max(numbers, default=0) + 1}", "label": (self.label or root.name)[:80], "path": str(root), "license": "UNKNOWN", "enabled": True})
        save_state()
        count, finished = scan(context)
        context.scene.cozyverse.library_page = 0
        context.scene.cozyverse.status = f"Library: {count} model(s)" + ("" if finished else " (scan stopped early; rescan to continue)")
        _log_activity(context, "LIBRARY", f"Added library folder {root.name}: {count} model(s) indexed")
        return {"FINISHED"}


class CV_OT_LibraryRescan(bpy.types.Operator):
    bl_idname = "cozyverse.library_rescan"
    bl_label = "Rescan Library"
    bl_description = "Look for new and removed models in every library folder"

    def execute(self, context: bpy.types.Context):
        count, finished = scan(context)
        context.scene.cozyverse.status = f"Library: {count} model(s)" + ("" if finished else " (scan stopped early)")
        return {"FINISHED"}


class CV_OT_LibraryRemoveSource(bpy.types.Operator):
    bl_idname = "cozyverse.library_remove_source"
    bl_label = "Remove Library Folder"
    bl_description = "Stop listing this folder. Your files are not touched"

    source: StringProperty()

    def execute(self, context: bpy.types.Context):
        st = state()
        st["sources"] = [s for s in st["sources"] if s["id"] != self.source]
        st["index"] = [r for r in st["index"] if r["source"] != self.source]
        save_state()
        return {"FINISHED"}


class CV_OT_LibrarySourceLicense(bpy.types.Operator):
    bl_idname = "cozyverse.library_source_license"
    bl_label = "Set Library Licence"
    bl_description = "The licence assumed for every model in this folder, unless you change a single model"

    source: StringProperty()
    license: EnumProperty(items=[(key, label, note) for key, label, note in spec.LICENSES])

    def execute(self, context: bpy.types.Context):
        for source in state()["sources"]:
            if source["id"] == self.source:
                source["license"] = self.license
        save_state()
        return {"FINISHED"}


class CV_OT_LibrarySelect(bpy.types.Operator):
    bl_idname = "cozyverse.library_select"
    bl_label = "Select Model"
    bl_description = "Show this model's details"

    key: StringProperty()

    @classmethod
    def description(cls, _context, properties):
        record = record_for(properties.key) if properties.key else None
        return f"{record['name']}: {_ROLE_LABELS.get(record['role'], '')}. {record['path']}" if record else cls.bl_description

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        record = record_for(self.key)
        if record is None:
            return {"CANCELLED"}
        settings.library_selected = self.key
        sync_edit_fields(settings, record)
        if not thumb_path(record).is_file():
            try:  # selecting a model gives it a real preview straight away
                render_thumbnail(record)
            except (ValueError, RuntimeError, OSError):
                pass
        return {"FINISHED"}


class CV_OT_LibraryThumbnails(bpy.types.Operator):
    bl_idname = "cozyverse.library_thumbnails"
    bl_label = "Make Thumbnails"
    bl_description = "Render real previews for the models on this page that do not have one. Large files are skipped"

    scope: EnumProperty(items=(("PAGE", "This page", "The models shown now"), ("ALL", "Everything", "Every model in the library")), default="PAGE", options={"HIDDEN"})

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        records = view(settings, PAGE_SIZE)[0] if self.scope == "PAGE" else effective_records()
        made = skipped = failed = 0
        for record in records:
            if thumb_path(record).is_file():
                continue
            try:
                render_thumbnail(record)
                made += 1
            except (ValueError, RuntimeError, OSError):
                failed += 1
            if made + failed >= 40:
                skipped = 1
                break
        settings.status = f"Thumbnails: {made} made" + (f", {failed} skipped (too large or unreadable)" if failed else "") + (" (press again for more)" if skipped else "")
        return {"FINISHED"}


class CV_OT_LibraryPage(bpy.types.Operator):
    bl_idname = "cozyverse.library_page"
    bl_label = "Library Page"
    bl_description = "Previous or next page of models"

    delta: IntProperty(default=1)
    reopen: BoolProperty(default=False, options={"HIDDEN"})

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        size = 12 if self.reopen else PAGE_SIZE
        _records, page, total, _ = view(settings, size)
        settings.library_page = max(0, min(total - 1, page + self.delta))
        if self.reopen:
            bpy.ops.cozyverse.library_browser("INVOKE_DEFAULT")
        return {"FINISHED"}


class CV_OT_LibraryBrowser(bpy.types.Operator):
    bl_idname = "cozyverse.library_browser"
    bl_label = "Library Browser"
    bl_description = "A larger view of your library"

    def invoke(self, context: bpy.types.Context, _event):
        return context.window_manager.invoke_props_dialog(self, width=860, confirm_text="Close")

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        settings = context.scene.cozyverse
        draw_browser(layout, context, columns=4, size=12)

    def execute(self, context: bpy.types.Context):
        return {"FINISHED"}


class CV_OT_LibraryPlace(bpy.types.Operator):
    bl_idname = "cozyverse.library_place"
    bl_label = "Place in World"
    bl_description = "Import the selected model at the 3D cursor, standing on the ground and sized for its role"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        record = record_for(settings.library_selected) if settings.library_selected else None
        if record is None:
            self.report({"WARNING"}, "Select a model in the Library first")
            return {"CANCELLED"}
        world = bpy.data.collections.get(settings.active_world_name) if settings.active_world_name else None
        if world is not None and world.get("cv_managed"):
            target = next((child for child in world.children if child.name.startswith("CV_USER_ASSETS")), None)
            if target is None:
                from .world_builder import _new_collection

                target = _new_collection("CV_USER_ASSETS", world)
        else:
            target = bpy.data.collections.get("CV_IMPORTED_ASSETS") or bpy.data.collections.new("CV_IMPORTED_ASSETS")
            if target.name not in context.scene.collection.children:
                context.scene.collection.children.link(target)
        try:
            wrapper = place_asset(record, target, location=tuple(context.scene.cursor.location))
        except (ValueError, RuntimeError) as exc:
            self.report({"ERROR"}, f"Could not place {record['name']}: {exc}")
            return {"CANCELLED"}
        if world is not None:
            for obj in (wrapper, *wrapper.children_recursive):
                obj["cv_world_root"] = world.name
        settings.status = f"Placed {record['name']} as a {_ROLE_LABELS.get(record['role'], 'model').lower()}"
        _log_activity(context, "LIBRARY", f"Placed {record['name']} ({record['license']})")
        note = spec.license_note([record["license"]])
        if note is not None and note.level == "WARNING":
            self.report({"WARNING"}, note.text)
        return {"FINISHED"}


class CV_OT_LibraryUseAs(bpy.types.Operator):
    bl_idname = "cozyverse.library_use_as"
    bl_label = "Use as My Car"
    bl_description = "Cars in your worlds will use this model instead of the built-in one (with a fallback if it cannot be loaded)"
    bl_options = {"REGISTER", "UNDO"}

    role: EnumProperty(items=(("CAR", "Car", "Cars on the road"),), default="CAR")

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        record = record_for(settings.library_selected) if settings.library_selected else None
        if record is None:
            return {"CANCELLED"}
        settings.slot_car_asset = record["key"]
        settings.slot_car_enabled = True
        settings.status = f"Cars will use {record['name']}"
        world = bpy.data.collections.get(settings.active_world_name) if settings.active_world_name else None
        if world is not None and any(child.name.startswith("CV_TRAFFIC") for child in world.children):
            return bpy.ops.cozyverse.traffic_add()  # swap the cars on the road right away
        return {"FINISHED"}


class CV_OT_LibraryClearSlot(bpy.types.Operator):
    bl_idname = "cozyverse.library_clear_slot"
    bl_label = "Use Built-in Cars"
    bl_description = "Go back to the built-in cars"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        settings.slot_car_enabled = False
        world = bpy.data.collections.get(settings.active_world_name) if settings.active_world_name else None
        if world is not None and any(child.name.startswith("CV_TRAFFIC") for child in world.children):
            return bpy.ops.cozyverse.traffic_add()
        return {"FINISHED"}


_CLASSES = (
    CV_OT_LibraryAddFolder,
    CV_OT_LibraryRescan,
    CV_OT_LibraryRemoveSource,
    CV_OT_LibrarySourceLicense,
    CV_OT_LibrarySelect,
    CV_OT_LibraryPage,
    CV_OT_LibraryThumbnails,
    CV_OT_LibraryBrowser,
    CV_OT_LibraryPlace,
    CV_OT_LibraryUseAs,
    CV_OT_LibraryClearSlot,
)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
    clear_thumbnails()

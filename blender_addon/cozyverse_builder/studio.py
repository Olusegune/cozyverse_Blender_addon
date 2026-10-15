"""The guided three-step flow: step navigation, galleries and the Prompt Studio split editor."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty

from .core.style_spec import STYLE_PRESETS
from .core.demo_spec import DEFAULT_PROMPT
from .operators import _log_activity
from .visual_assets import icon_id, square_id

IDEAS = (
    ("VILLAGE", "Village", "A welcoming town square", "HOME"),
    ("CITY", "City", "A colourful neighbourhood block", "OUTLINER_OB_MESH"),
    ("CAFE", "Cafe", "A warmly lit corner cafe", "LIGHT"),
    ("NATURE", "Nature", "A stream and a hero tree", "WORLD"),
    ("FANTASY", "Fantasy", "A tiny wizard workshop", "SOLO_ON"),
    ("RETRO_SCIFI", "Retro Sci-Fi", "A lunar service station", "ORIENTATION_GIMBAL"),
)

STEPS = (
    ("DESCRIBE", "Describe", "Write what you imagine"),
    ("REVIEW", "Review", "See the plan before anything is built"),
    ("CREATE", "Create", "Your world and everything you can change"),
)


class CV_OT_GotoStep(bpy.types.Operator):
    bl_idname = "cozyverse.goto_step"
    bl_label = "Go to Step"
    bl_description = "Move between Describe, Review and Create"

    step: EnumProperty(items=[(s[0], s[1], s[2]) for s in STEPS])

    @classmethod
    def description(cls, _context, properties):
        return next((s[2] for s in STEPS if s[0] == properties.step), cls.bl_description)

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        settings.active_tab = "CREATE"
        world = bpy.data.collections.get(settings.active_world_name) if settings.active_world_name else None
        if self.step == "DESCRIBE":
            settings.workflow_step = "DESCRIBE"
            settings.plan_approved = False
        elif self.step == "REVIEW":
            if settings.workflow_step != "REVIEW":
                if not settings.prompt.strip() and settings.prompt_text is None:
                    self.report({"INFO"}, "Describe your world first")
                    return {"CANCELLED"}
                return bpy.ops.cozyverse.conjure(review=True)
        else:
            if world is None or not world.get("cv_managed"):
                self.report({"INFO"}, "Nothing to show yet. Review and build your world first")
                return {"CANCELLED"}
            settings.workflow_step = "BUILT"
        return {"FINISHED"}


class CV_OT_BuildReviewed(bpy.types.Operator):
    bl_idname = "cozyverse.build_reviewed"
    bl_label = "Build My World"
    bl_description = "Build the plan you just reviewed. Every build is a new version; nothing is overwritten"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        from .flow import _present_world

        settings = context.scene.cozyverse
        settings.plan_approved = True
        _log_activity(context, "APPROVE", "Plan approved on the review screen; a new version is built and nothing is overwritten")
        if bpy.ops.cozyverse.build_approved_plan() != {"FINISHED"}:
            return {"CANCELLED"}
        world = bpy.data.collections.get(settings.active_world_name)
        if world is not None:
            _present_world(context, world)
            settings.status = f"{world.name} is ready"
        return {"FINISHED"}


class CV_OT_SetStyle(bpy.types.Operator):
    bl_idname = "cozyverse.set_style"
    bl_label = "Use This Style"
    bl_description = "Build in this style"

    style: StringProperty(options={"HIDDEN"})

    @classmethod
    def description(cls, _context, properties):
        preset = STYLE_PRESETS.get(properties.style)
        return f"{preset.label}: {preset.description}" if preset else cls.bl_description

    def execute(self, context: bpy.types.Context):
        if self.style not in STYLE_PRESETS:
            return {"CANCELLED"}
        context.scene.cozyverse.preset = self.style
        return {"FINISHED"}


class CV_OT_StyleGallery(bpy.types.Operator):
    bl_idname = "cozyverse.style_gallery"
    bl_label = "Compare Styles"
    bl_description = "See every style side by side and pick one"

    def invoke(self, context: bpy.types.Context, _event):
        return context.window_manager.invoke_popup(self, width=760)

    def execute(self, context: bpy.types.Context):
        return {"FINISHED"}

    def draw(self, context: bpy.types.Context) -> None:
        current = context.scene.cozyverse.preset
        # A larger interface scale makes the pop-up taller; shrink the pictures so every row still fits on screen.
        ui = max(1.0, float(context.preferences.view.ui_scale))
        size = 7.0 if ui <= 1.3 else max(4.0, 7.0 - (ui - 1.3) * 4.0)
        self.layout.label(text="Style Studio: choose how your world looks")
        grid = self.layout.grid_flow(row_major=True, columns=4, even_columns=True, even_rows=False, align=False)
        for identifier, preset in STYLE_PRESETS.items():
            card = grid.column(align=True)
            key = f"style_{identifier.lower()}"
            if square_id(key):
                card.template_icon(icon_value=square_id(key), scale=size)
            button = card.operator("cozyverse.set_style", text=preset.label, depress=identifier == current)
            button.style = identifier
            note = card.column(align=True)
            note.active = False
            for line in _wrap(preset.description, 24):
                note.label(text=line)


class CV_OT_IdeaGallery(bpy.types.Operator):
    bl_idname = "cozyverse.idea_gallery"
    bl_label = "Start From an Idea"
    bl_description = "Pick a starting idea. It writes a description you can change"

    def invoke(self, context: bpy.types.Context, _event):
        return context.window_manager.invoke_popup(self, width=640)

    def execute(self, context: bpy.types.Context):
        return {"FINISHED"}

    def draw(self, context: bpy.types.Context) -> None:
        self.layout.label(text="Quick Start: choose an idea to begin with")
        grid = self.layout.grid_flow(row_major=True, columns=3, even_columns=True, even_rows=False, align=False)
        for template, label, note, fallback in IDEAS:
            card = grid.column(align=True)
            key = f"template_{template.lower()}"
            if square_id(key):
                card.template_icon(icon_value=square_id(key), scale=7.5)
            card.operator("cozyverse.apply_prompt_template", text=label, **({"icon": fallback} if not square_id(key) else {})).template = template
            hint = card.row()
            hint.active = False
            hint.label(text=note)


def _wrap(text: str, width: int) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    return lines + ([current] if current else [])


def _split_text_editor(context: bpy.types.Context, text: bpy.types.Text):
    """Open the text beside the 3D view so the world and CozyVerse panel stay visible."""
    area = context.area
    if area is None or context.screen is None:
        return None
    before = {a.as_pointer() for a in context.screen.areas}
    region = next((r for r in area.regions if r.type == "WINDOW"), None)
    try:
        with context.temp_override(window=context.window, screen=context.screen, area=area, region=region):
            bpy.ops.screen.area_split(direction="VERTICAL", factor=0.5)
    except RuntimeError:
        return None
    created = next((a for a in context.screen.areas if a.as_pointer() not in before), None)
    if created is None:
        return None
    created.type = "TEXT_EDITOR"
    space = created.spaces.active
    space.text = text
    space.show_word_wrap = True
    space.show_line_numbers = False
    space.show_syntax_highlight = False
    space.font_size = 16
    space.show_region_ui = True
    return created


class CV_OT_PromptStudio(bpy.types.Operator):
    bl_idname = "cozyverse.prompt_studio"
    bl_label = "Write or Edit"
    bl_description = "Open a roomy editor beside the 3D view. Write as much as you like, then press Done"

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        text = settings.prompt_text or bpy.data.texts.get("CV_World_Prompt")
        if text is None:
            text = bpy.data.texts.new("CV_World_Prompt")
        if not text.as_string().strip():
            text.clear()
            text.write(settings.prompt or DEFAULT_PROMPT)
        settings.prompt_text = text
        for area in context.screen.areas if context.screen else ():
            if area.type == "TEXT_EDITOR" and getattr(area.spaces.active, "text", None) == text:
                return {"FINISHED"}  # already open
        if _split_text_editor(context, text) is None:
            settings.status = "Open CV_World_Prompt in a Text Editor to write the description"
            self.report({"INFO"}, settings.status)
        else:
            settings.status = "Write your description, then press Done"
        return {"FINISHED"}


class CV_OT_PromptStudioDone(bpy.types.Operator):
    bl_idname = "cozyverse.prompt_studio_done"
    bl_label = "Done"
    bl_description = "Use this description and close the editor"

    review: BoolProperty(name="Review next", default=False, options={"HIDDEN"})

    def execute(self, context: bpy.types.Context):
        settings = context.scene.cozyverse
        space = context.space_data if context.area is not None and context.area.type == "TEXT_EDITOR" else None
        text = getattr(space, "text", None) or settings.prompt_text
        if text is None or not text.as_string().strip():
            self.report({"WARNING"}, "The description is empty")
            return {"CANCELLED"}
        settings.prompt_text = text
        settings.prompt = text.as_string().strip()[:4000]
        settings.workflow_step = "DESCRIBE"
        settings.status = "Description saved"
        area = context.area
        if area is not None and context.screen is not None:
            others = [a for a in context.screen.areas if a.type == "VIEW_3D"]
            if others:
                with context.temp_override(window=context.window, screen=context.screen, area=area, region=next((r for r in area.regions if r.type == "WINDOW"), None)):
                    try:
                        bpy.ops.screen.area_close()
                    except RuntimeError:
                        area.type = "VIEW_3D"
            else:
                area.type = "VIEW_3D"
        if self.review:
            return bpy.ops.cozyverse.conjure(review=True)
        return {"FINISHED"}


_CLASSES = (CV_OT_GotoStep, CV_OT_BuildReviewed, CV_OT_SetStyle, CV_OT_StyleGallery, CV_OT_IdeaGallery, CV_OT_PromptStudio, CV_OT_PromptStudioDone)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

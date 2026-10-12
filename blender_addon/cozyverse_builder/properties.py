"""CozyVerse settings stored with the Blender scene."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, PointerProperty, StringProperty

from .core.demo_spec import DEFAULT_PROMPT
from .core.style_spec import style_items


def _update_atmosphere(self, context: bpy.types.Context) -> None:
    from .atmosphere import apply_atmosphere

    scene = context.scene if context is not None else getattr(self, "id_data", None)
    if scene is not None:
        apply_atmosphere(scene, self)


def _update_atmosphere_preset(self, context: bpy.types.Context) -> None:
    if self.atmosphere_preset == "CUSTOM":
        return
    from .core.atmosphere_spec import PRESETS

    values = PRESETS[self.atmosphere_preset]
    self.time_hour = values.time_hour
    self.sun_intensity = values.sun_intensity
    self.warmth = values.warmth
    self.ambient_intensity = values.ambient_intensity
    self.interior_intensity = values.interior_intensity
    self.weather = values.weather
    self.rain_amount = values.rain_amount
    self.exposure = values.exposure
    self.practical_temperature = values.practical_temperature
    self.practical_lights = values.practical_lights
    _update_atmosphere(self, context)


class CV_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    local_demo_only: BoolProperty(
        name="Local Demonstration Mode",
        description="Keep CozyVerse offline and use only bundled deterministic demo logic",
        default=True,
    )
    provider: EnumProperty(
        name="AI Provider",
        description="Provider configuration for a future approved planner integration",
        items=(
            ("NONE", "Local Only", "Disable external AI providers"),
            ("OPENAI", "OpenAI", "Configure an OpenAI-compatible provider"),
            ("ANTHROPIC", "Anthropic", "Configure an Anthropic provider"),
            ("CUSTOM", "Custom", "Configure a future provider adapter"),
        ),
        default="NONE",
    )
    model_name: StringProperty(
        name="Model",
        description="Provider model identifier; no request is made in this foundation build",
        default="",
        maxlen=128,
    )
    api_key_environment_variable: StringProperty(
        name="Environment Variable",
        description="Optional environment variable name used by a future provider adapter",
        default="",
        maxlen=128,
    )
    generation_provider: EnumProperty(
        name="3D Generation Provider",
        description="Provider to configure for a future explicitly approved generation adapter",
        items=(
            ("NONE", "Disabled", "Disable external 3D generation"),
            ("TRIPO", "Tripo", "Configure Tripo credentials without sending a request"),
            ("MESHY", "Meshy", "Configure Meshy credentials without sending a request"),
        ),
        default="NONE",
    )
    custom_asset_folder: StringProperty(
        name="Local Asset Folder",
        description="Optional folder containing your .blend, GLB, GLTF, FBX, or OBJ models",
        default="",
        subtype="DIR_PATH",
    )
    include_blender_asset_libraries: BoolProperty(
        name="Use Blender Asset Libraries",
        description="Index model files from asset-library folders configured in Blender",
        default=True,
    )

    def draw(self, _context: bpy.types.Context) -> None:
        layout = self.layout
        layout.prop(self, "local_demo_only")
        layout.prop(self, "provider")
        layout.prop(self, "model_name")
        layout.prop(self, "api_key_environment_variable")
        layout.prop(self, "generation_provider")
        layout.prop(self, "include_blender_asset_libraries")
        layout.prop(self, "custom_asset_folder")
        layout.label(text="API keys are entered only in the CozyVerse sidebar session.", icon="LOCKED")
        layout.label(text="Foundation build: no network or paid provider requests.", icon="INFO")


class CV_SessionSecrets(bpy.types.PropertyGroup):
    """Runtime-only secrets attached to WindowManager, never Scene data."""

    api_key: StringProperty(
        name="API Key",
        description="Session-only credential; never stored in the blend file or logs",
        default="",
        subtype="PASSWORD",
        options={"SKIP_SAVE"},
    )
    tripo_api_key: StringProperty(
        name="Tripo API Key",
        description="Session-only Tripo credential; never stored in the blend file or logs",
        default="",
        subtype="PASSWORD",
        options={"SKIP_SAVE"},
    )
    meshy_api_key: StringProperty(
        name="Meshy API Key",
        description="Session-only Meshy credential; never stored in the blend file or logs",
        default="",
        subtype="PASSWORD",
        options={"SKIP_SAVE"},
    )


class CV_AssetItem(bpy.types.PropertyGroup):
    name: StringProperty(name="Name")
    path: StringProperty(name="Path", subtype="FILE_PATH")
    extension: StringProperty(name="Format")
    category: StringProperty(name="Category")
    tags: StringProperty(name="Tags")
    source: StringProperty(name="Source")
    match_score: FloatProperty(name="Match", default=0.0)


class CV_LogItem(bpy.types.PropertyGroup):
    timestamp: StringProperty(name="Time")
    level: StringProperty(name="Level")
    message: StringProperty(name="Message", maxlen=500)


class CV_SceneSettings(bpy.types.PropertyGroup):
    onboarding_complete: BoolProperty(name="Onboarding Complete", default=False)
    workflow_step: EnumProperty(
        name="Creation Step",
        items=(
            ("DESCRIBE", "1 Describe", "Describe the desired miniature world"),
            ("REVIEW", "2 Review", "Review and edit the structured scene plan"),
            ("BUILT", "3 Built", "Inspect and manage the generated world"),
        ),
        default="DESCRIBE",
    )
    scene_plan_json: StringProperty(name="Scene Plan", default="", options={"HIDDEN"})
    revision_preview_json: StringProperty(name="Revision Preview", default="", options={"HIDDEN"})
    revision_fingerprint: StringProperty(name="Revision Fingerprint", default="", options={"HIDDEN"})
    revision_source_world: StringProperty(name="Revision Source", default="")
    revision_changed: IntProperty(name="Changed", default=0, min=0)
    revision_created: IntProperty(name="Created", default=0, min=0)
    revision_deleted: IntProperty(name="Deleted", default=0, min=0)
    revision_skipped: IntProperty(name="Preserved", default=0, min=0)
    revision_protected: IntProperty(name="Protected", default=0, min=0)
    revision_manual_edits: IntProperty(name="Manual Edits", default=0, min=0)
    checkpoint_path: StringProperty(name="Latest Checkpoint", default="", subtype="FILE_PATH")
    activity_log: CollectionProperty(type=CV_LogItem)
    plan_title: StringProperty(name="World Name", default="Miniature World", maxlen=128)
    plan_world_type: EnumProperty(
        name="Composition",
        items=(
            ("VILLAGE", "Village", "Small settlement composition"),
            ("CITY", "Urban Street", "Street or neighborhood composition"),
            ("CAFE", "Cafe", "Cafe exterior or intimate setting"),
            ("NATURE", "Landscape", "Natural landscape composition"),
            ("SPACE_OUTPOST", "Space Outpost", "Retro or futuristic outpost"),
            ("MARKET", "Market", "Market and stalls"),
            ("FARM", "Farm", "Rural farm composition"),
            ("FANTASY", "Fantasy", "Fantasy settlement composition"),
        ),
        default="VILLAGE",
    )
    plan_base_shape: EnumProperty(
        name="Diorama Base",
        items=(("ROUNDED_RECT", "Rounded Rectangle", "Classic miniature base"), ("CIRCLE", "Circle", "Circular display base"), ("ISLAND", "Organic Island", "Natural irregular presentation")),
        default="ROUNDED_RECT",
    )
    plan_camera_type: EnumProperty(
        name="Camera",
        items=(("ORTHO", "Isometric / Orthographic", "Miniature presentation"), ("PERSPECTIVE", "Perspective", "Cinematic perspective")),
        default="ORTHO",
    )
    plan_architecture_count: IntProperty(name="Buildings", default=3, min=0, max=20)
    plan_prop_count: IntProperty(name="Props", default=6, min=0, max=30)
    plan_vegetation_count: IntProperty(name="Plants", default=6, min=0, max=30)
    plan_character_count: IntProperty(name="Characters", default=2, min=0, max=20)
    plan_include_road: BoolProperty(name="Road or Main Path", default=True)
    plan_approved: BoolProperty(name="I reviewed this plan", default=False)
    operation_progress: FloatProperty(name="Progress", default=0.0, min=0.0, max=1.0, subtype="FACTOR")
    last_error: StringProperty(name="Last Error", default="", maxlen=1024)
    recovery_hint: StringProperty(name="Recovery", default="", maxlen=1024)
    active_world_name: StringProperty(name="Active World", default="")
    asset_items: CollectionProperty(type=CV_AssetItem)
    asset_index: IntProperty(name="Selected Asset", default=-1)
    asset_search: StringProperty(name="Search Assets", default="", maxlen=256)
    asset_category: EnumProperty(
        name="Category",
        items=(("ALL", "All", "All indexed assets"), ("CHARACTER", "Characters", "Character models"), ("BUILDING", "Buildings", "Architecture"), ("ROAD", "Roads", "Roads and paths"), ("PROP", "Props", "Set props"), ("VEGETATION", "Vegetation", "Plants and trees"), ("VEHICLE", "Vehicles", "Vehicles"), ("FURNITURE", "Furniture", "Furniture"), ("OTHER", "Other", "Uncategorized")),
        default="ALL",
    )
    asset_catalog_status: StringProperty(name="Catalog Status", default="Index your local sources to begin")
    asset_preview_name: StringProperty(name="Preview Object", default="")
    asset_place_location: FloatVectorProperty(name="Location", subtype="TRANSLATION", default=(0.0, 0.0, 0.0))
    asset_place_rotation: FloatVectorProperty(name="Rotation", subtype="EULER", default=(0.0, 0.0, 0.0))
    asset_place_scale: FloatProperty(name="Scale", default=1.0, min=0.01, max=100.0)
    asset_placement_approved: BoolProperty(name="I approve importing this local asset", default=False)
    reference_image_path: StringProperty(
        name="Reference Image",
        description="Local diorama image used for an editable offline interpretation",
        default="",
        subtype="FILE_PATH",
    )
    reference_image: PointerProperty(
        name="Reference Preview",
        description="Loaded reference image preview",
        type=bpy.types.Image,
    )
    reference_palette_json: StringProperty(name="Reference Palette", default="[]", options={"HIDDEN"})
    reference_status: StringProperty(name="Reference Status", default="Choose a diorama reference image")
    indexed_asset_count: StringProperty(name="Indexed Assets", default="0")
    indexed_asset_preview: StringProperty(name="Asset Index Preview", default="", options={"HIDDEN"})
    prompt: StringProperty(
        name="World Prompt",
        description="Describe the miniature world for the local demonstration",
        default=DEFAULT_PROMPT,
        maxlen=4000,
    )
    prompt_text: PointerProperty(
        name="Multiline Prompt",
        description="Optional Blender Text datablock used for a multiline world description",
        type=bpy.types.Text,
    )
    prompt_setting: StringProperty(name="Setting", default="a tiny neighborhood on a miniature diorama base", maxlen=500)
    prompt_subject: StringProperty(name="Focal Subject", default="a welcoming sari-sari store", maxlen=500)
    prompt_mood: StringProperty(name="Mood and Time", default="cozy golden-hour lighting", maxlen=500)
    prompt_details: StringProperty(name="Must Include", default="a road, tropical plants, warm shop lights", maxlen=1000)
    prompt_avoid: StringProperty(name="Avoid", default="photorealism, excessive clutter", maxlen=500)
    preset: EnumProperty(
        name="Visual Style",
        description="Shared style direction for prompts, materials, and future asset matching",
        items=style_items(),
        default="COZY_VILLAGE",
    )
    status: StringProperty(name="Status", default="Ready for a local demonstration")
    last_demo_prompt: StringProperty(name="Last Demo Prompt", default="", maxlen=4000)
    active_tab: EnumProperty(
        name="Workspace",
        items=(
            ("CREATE", "Create", "Create an editable local demonstration", "MOD_BUILD", 0),
            ("ATMOSPHERE", "Atmosphere", "Control lighting, time, and rain", "LIGHT_SUN", 1),
            ("GENERATE", "Generate", "Preview and approve optional 3D generation", "MESH_ICOSPHERE", 2),
            ("ACTIVITY", "Activity", "Review current status and local activity", "INFO", 3),
            ("SETTINGS", "Settings", "Configure local and future provider settings", "PREFERENCES", 4),
        ),
        default="CREATE",
    )
    atmosphere_preset: EnumProperty(
        name="Atmosphere Preset",
        items=(
            ("GOLDEN_HOUR", "Golden Hour", "Warm sunset lighting"),
            ("RAINY_CAFE", "Rainy Cafe", "Evening practical lights and visible rain"),
            ("MOONLIT", "Moonlit", "Cool low-light night"),
            ("MISTY_DAWN", "Misty Dawn", "Soft dawn lighting; fog remains unsupported"),
            ("BRIGHT_DAY", "Bright Day", "Clean daylight with practical lights off"),
            ("BLUE_HOUR", "Blue Hour", "Cool twilight with warm practical lights"),
            ("CUSTOM", "Custom", "Current custom values"),
        ),
        default="GOLDEN_HOUR",
        update=_update_atmosphere_preset,
    )
    time_hour: FloatProperty(
        name="Time of Day",
        description="Artistic time of day in hours",
        default=18.0,
        min=0.0,
        max=24.0,
        precision=1,
        update=_update_atmosphere,
    )
    sun_intensity: FloatProperty(
        name="Sun Intensity",
        default=55.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_update_atmosphere,
    )
    warmth: FloatProperty(
        name="Warmth",
        default=88.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_update_atmosphere,
    )
    ambient_intensity: FloatProperty(
        name="Ambient Light",
        default=38.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_update_atmosphere,
    )
    interior_intensity: FloatProperty(
        name="Interior Lights",
        default=70.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_update_atmosphere,
    )
    practical_lights: BoolProperty(
        name="Practical Lights",
        description="Enable or disable the active world's editable interior lights",
        default=True,
        update=_update_atmosphere,
    )
    practical_temperature: FloatProperty(
        name="Light Temperature",
        description="Color temperature of practical lights in Kelvin",
        default=2700.0,
        min=1800.0,
        max=6500.0,
        step=100.0,
        precision=0,
        update=_update_atmosphere,
    )
    exposure: FloatProperty(
        name="Exposure",
        description="Scene color-management exposure in stops",
        default=0.0,
        min=-3.0,
        max=3.0,
        step=10.0,
        precision=2,
        update=_update_atmosphere,
    )
    weather: EnumProperty(
        name="Weather",
        items=(
            ("CLEAR", "Clear", "Hide the rain preview"),
            ("RAIN", "Rain", "Show the editable rain preview"),
        ),
        default="CLEAR",
        update=_update_atmosphere,
    )
    rain_amount: FloatProperty(
        name="Rain Amount",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_update_atmosphere,
    )
    fog_amount: FloatProperty(name="Fog", default=0.0, min=0.0, max=100.0, subtype="PERCENTAGE")
    wind_amount: FloatProperty(name="Wind", default=0.0, min=0.0, max=100.0, subtype="PERCENTAGE")
    wetness_amount: FloatProperty(name="Wetness", default=0.0, min=0.0, max=100.0, subtype="PERCENTAGE")
    generation_prompt: StringProperty(
        name="Asset Prompt",
        description="Describe one missing 3D asset for Tripo or Meshy",
        default="A stylized low-poly market stall with a fabric awning",
        maxlen=1024,
    )
    generation_plan_json: StringProperty(name="Generation Plan", default="", options={"HIDDEN"})
    generation_fingerprint: StringProperty(name="Plan Fingerprint", default="", options={"HIDDEN"})
    generation_cost_note: StringProperty(name="Cost Notice", default="No provider request has been prepared")
    generation_approved: BoolProperty(
        name="I approve this mock job",
        description="Approval applies only to the exact previewed request and resets after submission",
        default=False,
    )
    generation_status: StringProperty(name="Generation Status", default="Not prepared")


_CLASSES = (CV_AddonPreferences, CV_SessionSecrets, CV_AssetItem, CV_LogItem, CV_SceneSettings)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.cozyverse = PointerProperty(type=CV_SceneSettings)
    bpy.types.WindowManager.cozyverse_secrets = PointerProperty(type=CV_SessionSecrets)


def unregister() -> None:
    if hasattr(bpy.types.Scene, "cozyverse"):
        del bpy.types.Scene.cozyverse
    if hasattr(bpy.types.WindowManager, "cozyverse_secrets"):
        del bpy.types.WindowManager.cozyverse_secrets
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

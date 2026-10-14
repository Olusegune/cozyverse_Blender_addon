"""CozyVerse settings stored with the Blender scene."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, PointerProperty, StringProperty

from .core.demo_spec import DEFAULT_PROMPT
from .core.library_spec import FORWARDS, LICENSES, ROLES
from .core.style_spec import style_items
from .visual_assets import icon_id


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
    self.fog_amount = values.fog_amount
    self.wind_amount = values.wind_amount
    self.wetness_amount = values.wetness_amount
    self.snow_amount = values.snow_amount
    self.season = values.season
    self.weather_quality = values.weather_quality
    self.clouds_amount = values.clouds_amount
    _update_atmosphere(self, context)


_ENUM_KEEPALIVE: dict[str, list] = {}

_LOOK_PREVIEWS = {
    "GOLDEN_HOUR": ("atmosphere_golden_hour", "LIGHT_SUN"),
    "RAINY_CAFE": ("atmosphere_rainy_cafe", "OUTLINER_OB_LIGHT"),
    "MOONLIT": ("atmosphere_moonlit", "SHADING_RENDERED"),
    "MISTY_DAWN": ("atmosphere_misty_dawn", "LIGHT_AREA"),
    "BRIGHT_DAY": ("season_summer", "LIGHT_SUN"),
    "BLUE_HOUR": ("atmosphere_wet_night", "LIGHT_POINT"),
    "CUSTOM": ("", "OPTIONS"),
    "STARRY_NIGHT": ("atmosphere_moonlit", "SHADING_RENDERED"),
    "SUNSET_GLOW": ("atmosphere_golden_hour", "LIGHT_SUN"),
    "OVERCAST": ("atmosphere_foggy_morning", "OUTLINER_OB_LIGHT"),
    "FIRST_SNOW": ("atmosphere_snowy_twilight", "FREEZE"),
}


def _style_items_with_previews(_self, _context):
    items = [
        (identifier, label, description, icon_id(f"style_{identifier.lower()}") or "BRUSH_DATA", index)
        for index, (identifier, label, description) in enumerate(style_items())
    ]
    _ENUM_KEEPALIVE["style"] = items
    return items


def _look_items_with_previews(_self, _context):
    base = (
        ("GOLDEN_HOUR", "Golden Hour", "Warm sunset lighting"),
        ("RAINY_CAFE", "Rainy Cafe", "Evening practical lights and visible rain"),
        ("MOONLIT", "Moonlit", "Cool low-light night"),
        ("MISTY_DAWN", "Misty Dawn", "Soft dawn lighting"),
        ("BRIGHT_DAY", "Bright Day", "Clean daylight with practical lights off"),
        ("BLUE_HOUR", "Blue Hour", "Cool twilight with warm practical lights"),
        ("CUSTOM", "Custom", "Current custom values"),
        ("STARRY_NIGHT", "Starry Night", "A clear sky full of stars"),
        ("SUNSET_GLOW", "Sunset Glow", "A deep orange horizon"),
        ("OVERCAST", "Overcast", "Soft grey, even light"),
        ("FIRST_SNOW", "First Snow", "Gentle snowfall at dusk"),
    )
    items = []
    for index, (identifier, label, description) in enumerate(base):
        key, fallback = _LOOK_PREVIEWS[identifier]
        items.append((identifier, label, description, (icon_id(key) if key else 0) or fallback, index))
    _ENUM_KEEPALIVE["look"] = items
    return items


def _refresh_drivers(self, _context: bpy.types.Context) -> None:
    # Drivers read these sliders through the scene; tag it so they re-evaluate immediately.
    scene = getattr(self, "id_data", None)
    if scene is not None:
        scene.update_tag()


def _update_life(self, context: bpy.types.Context) -> None:
    from .life import apply_life, clear_life

    scene = context.scene if context is not None else getattr(self, "id_data", None)
    world = bpy.data.collections.get(self.active_world_name) if self.active_world_name else None
    if scene is None or world is None or not world.get("cv_managed"):
        return
    if self.life_enabled:
        apply_life(scene, world)
    else:
        clear_life(world)


def _reset_library_page(self, _context: bpy.types.Context) -> None:
    self.library_page = 0


def _update_library_edit(self, _context: bpy.types.Context) -> None:
    from .library import write_edit_fields

    write_edit_fields(self)


def _invalidate_story_preview(self, _context: bpy.types.Context) -> None:
    self.story_approved = False
    self.story_fingerprint = ""
    self.story_status = "Story settings changed; preview again"


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
        description="Provider used only after an exact request, credit limit, and paid-job consent are approved",
        items=(
            ("NONE", "Disabled", "Disable external 3D generation"),
            ("TRIPO", "Tripo", "Tripo v2 API adapter"),
            ("MESHY", "Meshy", "Meshy Text-to-3D v2 adapter"),
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
        layout.label(text="Paid jobs require an exact preview, budget and final confirmation.", icon="INFO")


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
    review_before_build: BoolProperty(
        name="Review the plan first",
        description="Pause after Conjure so you can adjust the plan before anything is built. Off by default: builds are always new versions and never overwrite your work",
        default=False,
    )
    life_enabled: BoolProperty(
        name="Ambient life",
        description="Foliage sways with the wind and lamps flicker. Native drivers: they render, scrub and survive saving",
        default=True,
        update=_update_life,
    )
    life_sway: FloatProperty(name="Foliage sway", description="How much plants move, on top of the Wind slider in Mood", default=50.0, min=0.0, max=100.0, subtype="PERCENTAGE", update=_refresh_drivers)
    life_flicker: FloatProperty(name="Lamp flicker", description="How much practical lights waver like candle flames", default=35.0, min=0.0, max=100.0, subtype="PERCENTAGE", update=_refresh_drivers)
    buildup_style: EnumProperty(
        name="Style",
        items=(
            ("POP", "Pop", "Each piece grows from the ground with a little overshoot"),
            ("RISE", "Rise", "Pieces grow upward like plants"),
            ("DROP", "Drop", "Pieces fall in and bounce once"),
        ),
        default="POP",
    )
    buildup_order: EnumProperty(
        name="Order",
        items=(("CENTER", "From the middle", "Ripple outward from the center"), ("SWEEP", "Left to right", "Sweep across the stage")),
        default="CENTER",
    )
    buildup_seconds: FloatProperty(name="Length", description="How long the assembly takes", default=4.0, min=1.0, max=30.0, unit="TIME_ABSOLUTE")
    clouds_amount: FloatProperty(name="Clouds", description="How much of the sky is covered. Rain and snow always bring heavy cloud", default=35.0, min=0.0, max=100.0, subtype="PERCENTAGE", update=_update_atmosphere)
    clip_buildup: BoolProperty(name="Build the world up", description="Open the clip with the diorama assembling itself", default=True)
    clip_orbit: BoolProperty(name="Orbit the camera", description="Sweep the camera once around the world while it plays", default=True)
    clip_quality: EnumProperty(name="Quality", items=(("HD720", "720p", "1280 x 720, quick"), ("HD1080", "1080p", "1920 x 1080")), default="HD720")
    stars_amount: FloatProperty(name="Stars", description="How many stars show on a clear night", default=70.0, min=0.0, max=100.0, subtype="PERCENTAGE", update=_update_atmosphere)
    ui_advanced: BoolProperty(name="Advanced controls", description="Show every lighting, weather and season control", default=False)
    daycycle_seconds: FloatProperty(name="Length", description="How long one full day and night takes", default=12.0, min=2.0, max=120.0, unit="TIME_ABSOLUTE")
    library_query: StringProperty(name="Search", default="", update=_reset_library_page)
    library_role: EnumProperty(
        name="Role",
        items=(("ALL", "All roles", "Show everything"), *[(key, label, note) for key, label, note in ROLES]),
        default="ALL",
        update=_reset_library_page,
    )
    library_page: IntProperty(name="Page", default=0, min=0)
    library_selected: StringProperty(name="Selected Model", default="")
    library_edit_role: EnumProperty(name="Role", description="What this model is. Cars on the road use models marked Car", items=[(key, label, note) for key, label, note in ROLES], default="UNTAGGED", update=_update_library_edit)
    library_edit_license: EnumProperty(name="Licence", description="What the licence allows. Editorial-only models warn you before you publish renders", items=[(key, label, note) for key, label, note in LICENSES], default="UNKNOWN", update=_update_library_edit)
    library_edit_forward: EnumProperty(name="Front", description="Which way the model faces, so it can drive forward", items=[(key, label, note) for key, label, note in FORWARDS], default="AUTO", update=_update_library_edit)
    library_edit_stylize: BoolProperty(name="Flatten to clay colors", description="Replace the model's materials with flat clay-like ones of the same colors so it matches the diorama", default=False, update=_update_library_edit)
    slot_car_asset: StringProperty(name="My Car", default="")
    slot_car_enabled: BoolProperty(name="Use my car", description="Cars on the road use your chosen model instead of the built-in one", default=False)
    traffic_cars: IntProperty(name="Cars", description="How many cars drive the road", default=2, min=1, max=4)
    traffic_seconds: FloatProperty(name="Trip time", description="Seconds for a car to cross the road", default=7.0, min=2.0, max=60.0, unit="TIME_ABSOLUTE")
    train_cars: IntProperty(name="Carriages", description="Carriages behind the locomotive", default=2, min=1, max=2)
    train_seconds: FloatProperty(name="Cycle time", description="Seconds for one tunnel to tunnel visit, including the station stop", default=14.0, min=4.0, max=120.0, unit="TIME_ABSOLUTE")
    turntable_frames: IntProperty(
        name="Frames per turn",
        description="Length of one full orbit; at 24 fps, 120 frames is five seconds",
        default=120,
        min=24,
        max=1200,
    )
    variation: IntProperty(name="Remix", description="Layout variation number for the active prompt", default=0, min=0)
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
    reference_analysis_json: StringProperty(name="Reference Analysis", default="", options={"HIDDEN"})
    reference_quality: EnumProperty(
        name="Interpretation Detail",
        description="Controls deterministic object counts; Blockout is the lowest-cost viewport preview",
        items=(("BLOCKOUT", "Blockout", "Fast composition preview"), ("BALANCED", "Balanced", "Moderate editable detail"), ("DETAILED", "Detailed", "More editable objects")),
        default="BALANCED",
    )
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
        items=_style_items_with_previews,
    )
    status: StringProperty(name="Status", default="Ready for a local demonstration")
    last_demo_prompt: StringProperty(name="Last Demo Prompt", default="", maxlen=4000)
    active_tab: EnumProperty(
        name="Workspace",
        items=(
            ("CREATE", "Create", "Describe and conjure a world", "MOD_BUILD", 0),
            ("ATMOSPHERE", "Mood", "Light, time of day, weather and seasons", "LIGHT_SUN", 1),
            ("STORY", "Motion", "Bring the world to life with editable animation", "ACTION", 2),
            ("GENERATE", "Assets", "Local assets, reference images and 3D generation", "ASSET_MANAGER", 3),
            ("ACTIVITY", "Activity", "Versions, recovery and the activity log", "INFO", 4),
            ("SETTINGS", "Settings", "Connections and preferences", "PREFERENCES", 5),
            ("SHOT", "Shot", "Frame cinematic cameras and render a postcard", "CAMERA_DATA", 6),
        ),
        default="CREATE",
    )
    atmosphere_preset: EnumProperty(
        name="Atmosphere Preset",
        items=_look_items_with_previews,
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
            ("CLEAR", "Clear", "Hide precipitation"),
            ("RAIN", "Rain", "Show the editable rain preview"),
            ("FOG", "Fog", "Show native volumetric fog"),
            ("SNOW", "Snow", "Show the editable snow preview"),
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
    snow_amount: FloatProperty(name="Snow Amount", default=45.0, min=0.0, max=100.0, subtype="PERCENTAGE", update=_update_atmosphere)
    fog_amount: FloatProperty(name="Fog", default=0.0, min=0.0, max=100.0, subtype="PERCENTAGE", update=_update_atmosphere)
    wind_amount: FloatProperty(name="Wind", default=0.0, min=0.0, max=100.0, subtype="PERCENTAGE", update=_update_atmosphere)
    wetness_amount: FloatProperty(name="Wetness", default=0.0, min=0.0, max=100.0, subtype="PERCENTAGE", update=_update_atmosphere)
    season: EnumProperty(name="Season", items=(("SPRING", "Spring", "Fresh green foliage"), ("SUMMER", "Summer", "Deep green foliage"), ("AUTUMN", "Autumn", "Warm orange foliage"), ("WINTER", "Winter", "Pale winter foliage")), default="SUMMER", update=_update_atmosphere)
    weather_quality: EnumProperty(name="Preview Quality", items=(("LOW", "Low", "Fastest viewport preview"), ("MEDIUM", "Medium", "Balanced preview"), ("HIGH", "High", "Denser precipitation preview")), default="MEDIUM", update=_update_atmosphere)
    story_preset: EnumProperty(
        name="Story Moment",
        items=(("QUIET_MORNING", "Quiet Morning", "Gentle idle motion and foliage"), ("BUSY_MARKET", "Busy Market", "Livelier character and environment motion"), ("RAINY_EVENING", "Rainy Evening", "Rain travel and warm practical-light pulse")),
        default="QUIET_MORNING",
        update=_invalidate_story_preview,
    )
    story_start_frame: IntProperty(name="Start", default=1, min=0, max=100000, update=_invalidate_story_preview)
    story_end_frame: IntProperty(name="End", default=120, min=1, max=100000, update=_invalidate_story_preview)
    story_preview_json: StringProperty(name="Story Preview", default="", options={"HIDDEN"})
    story_fingerprint: StringProperty(name="Story Fingerprint", default="", options={"HIDDEN"})
    story_approved: BoolProperty(name="I reviewed this Story plan", default=False)
    story_status: StringProperty(name="Story Status", default="Choose a world and preview a Story Moment")
    story_target_count: IntProperty(name="Targets", default=0, min=0)
    story_skipped_count: IntProperty(name="Skipped", default=0, min=0)
    story_keyframe_count: IntProperty(name="Keyframes", default=0, min=0)
    story_active_id: StringProperty(name="Active Story", default="")
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
    generation_estimated_credits: IntProperty(name="Estimated Credits", default=0, min=0)
    generation_credit_limit: IntProperty(
        name="Maximum Credits",
        description="Hard approval ceiling for this exact provider request",
        default=20,
        min=0,
        max=1000,
    )
    generation_live_approved: BoolProperty(
        name="I approve this exact paid request",
        description="Consent applies only to the displayed fingerprint and credit ceiling",
        default=False,
    )
    generation_job_id: StringProperty(name="Provider Job ID", default="")
    generation_job_status: EnumProperty(
        name="Job Status",
        items=(("NONE", "Not Started", "No job"), ("PENDING", "Pending", "Waiting"), ("IN_PROGRESS", "In Progress", "Running"), ("SUCCEEDED", "Succeeded", "Ready"), ("FAILED", "Failed", "Failed"), ("CANCELED", "Canceled", "Canceled")),
        default="NONE",
    )
    generation_job_progress: IntProperty(name="Progress", default=0, min=0, max=100, subtype="PERCENTAGE")
    generation_is_mock: BoolProperty(name="Mock Job", default=True)
    generation_result_url: StringProperty(name="Validated Result URL", default="", options={"HIDDEN"})
    generation_download_path: StringProperty(name="Downloaded Model", default="", subtype="FILE_PATH")
    generation_quarantine_name: StringProperty(name="Quarantine Asset", default="")
    generation_review_summary: StringProperty(name="Inspection", default="Not imported")
    generation_import_approved: BoolProperty(name="I approve importing this result", default=False)
    generation_promotion_approved: BoolProperty(name="I approve adding this asset to the factory", default=False)


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

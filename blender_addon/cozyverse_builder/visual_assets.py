"""Bundled preview artwork for the native Blender sidebar."""

from __future__ import annotations

from pathlib import Path

import bpy.utils.previews


_PREVIEWS = None
_ROOT = Path(__file__).with_name("assets")

FILES = {
    "header": "brand/header_cozy_world.png",
    "logo_mark": "brand/cozyverse_logo_mark.png",
    "empty_no_world": "premium/empty_no_world.png",
    **{f"template_{name}": f"templates/template_{name}.png" for name in ("village", "city", "cafe", "nature", "fantasy", "farm", "market", "retro_scifi")},
    **{f"style_{name}": f"styles/style_{name}.png" for name in ("cozy_village", "retro_scifi", "cozy_fantasy", "solarpunk", "cyberpunk", "storybook", "low_poly", "clay", "papercraft", "art_deco", "gothic", "tropical")},
    **{f"atmosphere_{name}": f"atmosphere/atmosphere_{name}.png" for name in ("golden_hour", "misty_dawn", "rainy_cafe", "moonlit", "foggy_morning", "snowy_twilight", "windy_day", "wet_night")},
    **{f"season_{name}": f"seasons/season_{name}.png" for name in ("spring", "summer", "autumn", "winter")},
    **{f"story_{name}": f"story/story_{name}.png" for name in ("quiet_morning", "busy_market", "rainy_evening")},
    **{f"cinematic_{name}": f"cinematic/cinematic_{name}.png" for name in ("wide", "hero_medium", "detail_closeup")},
    **{f"placeholder_{name}": f"placeholders/placeholder_{name}.png" for name in ("building", "character", "furniture", "other", "prop", "road", "vegetation", "vehicle")},
    "empty_no_image": "premium/empty_no_image.png",
    "empty_no_assets": "premium/empty_no_assets.png",
    "success_world_ready": "premium/success_world_ready.png",
    "empty_no_story": "premium/empty_no_story.png",
    **{f"icon_{name}_{theme}": f"icons/{theme}/icon_{name}_{theme}.png" for theme in ("dark", "light") for name in ("story", "animate", "timeline", "shot", "export")},
}


def register() -> None:
    global _PREVIEWS
    if _PREVIEWS is not None:
        return
    _PREVIEWS = bpy.utils.previews.new()
    for key, relative in FILES.items():
        path = _ROOT / relative
        if path.is_file():
            _PREVIEWS.load(key, str(path), "IMAGE")


def unregister() -> None:
    global _PREVIEWS
    if _PREVIEWS is not None:
        bpy.utils.previews.remove(_PREVIEWS)
        _PREVIEWS = None


def icon_id(key: str) -> int:
    if _PREVIEWS is None or key not in _PREVIEWS:
        return 0
    return _PREVIEWS[key].icon_id

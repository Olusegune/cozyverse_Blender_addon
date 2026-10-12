"""Bundled preview artwork for the native Blender sidebar."""

from __future__ import annotations

from pathlib import Path

import bpy.utils.previews


_PREVIEWS = None
_ROOT = Path(__file__).with_name("assets")

FILES = {
    "header": "brand/header_cozy_world.png",
    **{f"template_{name}": f"templates/template_{name}.png" for name in ("village", "city", "cafe", "nature", "fantasy", "farm", "market", "retro_scifi")},
    **{f"style_{name}": f"styles/style_{name}.png" for name in ("cozy_village", "retro_scifi", "cozy_fantasy", "solarpunk", "cyberpunk", "storybook", "low_poly", "clay", "papercraft", "art_deco", "gothic", "tropical")},
    **{f"atmosphere_{name}": f"atmosphere/atmosphere_{name}.png" for name in ("golden_hour", "misty_dawn", "rainy_cafe", "moonlit")},
    "empty_no_image": "premium/empty_no_image.png",
    "empty_no_assets": "premium/empty_no_assets.png",
    "success_world_ready": "premium/success_world_ready.png",
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

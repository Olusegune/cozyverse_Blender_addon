"""CozyVerse Builder Blender extension entry point."""

from __future__ import annotations

_MODULES = ()


def register() -> None:
    global _MODULES
    from . import clip, director, flow, library, motion, operators, properties, studio, ui, vehicles, visual_assets

    visual_assets.register()
    _MODULES = (properties, operators, library, motion, vehicles, director, flow, studio, clip, ui)
    for module in _MODULES:
        module.register()


def unregister() -> None:
    for module in reversed(_MODULES):
        module.unregister()
    from . import visual_assets
    visual_assets.unregister()

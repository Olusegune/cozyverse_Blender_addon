"""CozyVerse Builder Blender extension entry point."""

from __future__ import annotations

_MODULES = ()


def register() -> None:
    global _MODULES
    from . import flow, library, motion, operators, properties, ui, vehicles, visual_assets

    visual_assets.register()
    _MODULES = (properties, operators, library, motion, vehicles, flow, ui)
    for module in _MODULES:
        module.register()


def unregister() -> None:
    for module in reversed(_MODULES):
        module.unregister()
    from . import visual_assets
    visual_assets.unregister()

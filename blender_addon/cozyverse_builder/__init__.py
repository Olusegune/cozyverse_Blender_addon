"""CozyVerse Builder Blender extension entry point."""

from __future__ import annotations

_MODULES = ()


def register() -> None:
    global _MODULES
    from . import operators, properties, ui, visual_assets

    visual_assets.register()
    _MODULES = (properties, operators, ui)
    for module in _MODULES:
        module.register()


def unregister() -> None:
    for module in reversed(_MODULES):
        module.unregister()
    from . import visual_assets
    visual_assets.unregister()

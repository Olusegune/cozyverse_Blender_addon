"""Deterministic specification for the offline foundation demo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


DEMO_COLLECTION_NAME: Final = "CV_DEMO"
DEMO_SCHEMA_VERSION: Final = "1.0"
DEFAULT_PROMPT: Final = (
    "Create a cozy miniature village with two houses, trees, a path, "
    "warm lighting, and a diorama base."
)


@dataclass(frozen=True)
class DemoItem:
    name: str
    kind: str
    location: tuple[float, float, float]
    scale: tuple[float, float, float]


DEMO_ITEMS: Final[tuple[DemoItem, ...]] = (
    DemoItem("CV_Base", "cube", (0.0, 0.0, -0.35), (5.5, 4.0, 0.35)),
    DemoItem("CV_Path", "cube", (0.0, 0.0, 0.03), (0.65, 3.2, 0.05)),
    DemoItem("CV_House_A", "cube", (-2.0, 0.4, 0.9), (1.25, 1.15, 0.9)),
    DemoItem("CV_House_B", "cube", (2.0, -0.3, 0.75), (1.05, 1.0, 0.75)),
    DemoItem("CV_Roof_A", "cone4", (-2.0, 0.4, 2.0), (1.65, 1.55, 0.9)),
    DemoItem("CV_Roof_B", "cone4", (2.0, -0.3, 1.7), (1.4, 1.35, 0.75)),
    DemoItem("CV_Tree_A", "tree", (-3.7, -2.0, 0.0), (1.0, 1.0, 1.0)),
    DemoItem("CV_Tree_B", "tree", (3.6, 1.9, 0.0), (0.85, 0.85, 0.85)),
)


def normalized_prompt(value: str | None) -> str:
    """Return a bounded prompt for project metadata and UI display."""
    prompt = (value or "").strip()
    if not prompt:
        return DEFAULT_PROMPT
    return prompt[:4000]


def validate_demo_spec(items: tuple[DemoItem, ...] = DEMO_ITEMS) -> None:
    """Reject malformed demo data before it reaches Blender operators."""
    if not items:
        raise ValueError("The demo specification must contain at least one item")
    names = [item.name for item in items]
    if len(names) != len(set(names)):
        raise ValueError("Demo item names must be unique")
    allowed_kinds = {"cube", "cone4", "tree"}
    for item in items:
        if item.kind not in allowed_kinds:
            raise ValueError(f"Unsupported demo item kind: {item.kind}")
        if any(value <= 0 for value in item.scale):
            raise ValueError(f"Demo item scale must be positive: {item.name}")


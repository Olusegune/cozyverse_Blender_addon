"""Pure validation and indexing helpers for local reference workflows."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import json
from pathlib import Path


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
ASSET_EXTENSIONS = {".blend", ".glb", ".gltf", ".fbx", ".obj"}


@dataclass(frozen=True)
class ReferenceComposition:
    aspect: str
    brightness: float
    contrast: float
    warmth: float
    focal_x: float
    focal_y: float
    horizon: float
    suggested_time: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


def validate_reference_path(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError("Choose an existing reference image")
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError("Reference must be PNG, JPEG, WebP, or TIFF")
    return path


def scan_asset_files(roots: list[str], limit: int = 5000) -> list[str]:
    """Return supported local model paths without opening or executing them."""
    found: list[str] = []
    seen: set[Path] = set()
    for raw_root in roots:
        if not raw_root.strip():
            continue
        root = Path(raw_root).expanduser().resolve()
        if not root.is_dir() or root in seen:
            continue
        seen.add(root)
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in ASSET_EXTENSIONS:
                found.append(str(path))
                if len(found) >= limit:
                    return sorted(found, key=str.casefold)
    return sorted(found, key=str.casefold)


def dominant_palette(pixels: list[float], channels: int = 4, count: int = 5) -> list[tuple[float, float, float]]:
    """Find a small deterministic palette by quantizing sampled RGB pixels."""
    if channels < 3 or not pixels:
        return []
    stride = max(channels, (len(pixels) // channels // 12000) * channels)
    buckets: Counter[tuple[int, int, int]] = Counter()
    for index in range(0, len(pixels) - channels + 1, stride):
        rgb = tuple(max(0, min(7, int(pixels[index + offset] * 7.999))) for offset in range(3))
        buckets[rgb] += 1
    return [tuple(round(channel / 7.0, 4) for channel in color) for color, _ in buckets.most_common(count)]


def analyze_composition(pixels: list[float], width: int, height: int, channels: int = 4) -> ReferenceComposition:
    """Derive inexpensive visual cues; this deliberately makes no semantic claims."""
    if width < 1 or height < 1 or channels < 3 or len(pixels) < width * height * channels:
        raise ValueError("Reference pixels do not match the image dimensions")
    step = max(1, (width * height) // 12000)
    samples = []
    for pixel_index in range(0, width * height, step):
        offset = pixel_index * channels
        r, g, b = (max(0.0, min(1.0, float(pixels[offset + index]))) for index in range(3))
        luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
        x = (pixel_index % width) / max(1, width - 1)
        y = (pixel_index // width) / max(1, height - 1)
        samples.append((r, g, b, luminance, x, y))
    brightness = sum(item[3] for item in samples) / len(samples)
    contrast = (sum((item[3] - brightness) ** 2 for item in samples) / len(samples)) ** 0.5
    warmth = sum((item[0] - item[2] + 1.0) * 0.5 for item in samples) / len(samples)
    weights = [abs(item[3] - brightness) + max(item[:3]) - min(item[:3]) + 0.02 for item in samples]
    weight_total = sum(weights)
    focal_x = sum(item[4] * weight for item, weight in zip(samples, weights)) / weight_total
    focal_y = sum(item[5] * weight for item, weight in zip(samples, weights)) / weight_total
    row_values = []
    for row in range(1, height):
        if row % max(1, height // 100) != 0:
            continue
        top = [item[3] for item in samples if abs(item[5] - ((row - 1) / max(1, height - 1))) < (step / max(1, width * height)) + 0.01]
        bottom = [item[3] for item in samples if abs(item[5] - (row / max(1, height - 1))) < (step / max(1, width * height)) + 0.01]
        if top and bottom:
            row_values.append((abs(sum(top) / len(top) - sum(bottom) / len(bottom)), row / height))
    horizon = max(row_values, default=(0.0, 0.5))[1]
    suggested_time = "NIGHT" if brightness < 0.22 else "DUSK" if brightness < 0.43 else "DAY"
    ratio = width / height
    aspect = "WIDE" if ratio > 1.2 else "TALL" if ratio < 0.83 else "SQUARE"
    return ReferenceComposition(aspect, round(brightness, 4), round(contrast, 4), round(warmth, 4), round(focal_x, 4), round(focal_y, 4), round(horizon, 4), suggested_time)


def reference_plan(composition: ReferenceComposition, quality: str) -> dict:
    counts = {"BLOCKOUT": (2, 2, 2), "BALANCED": (4, 6, 6), "DETAILED": (7, 12, 12)}
    architecture, props, vegetation = counts.get(quality, counts["BALANCED"])
    return {
        "world_type": "VILLAGE",
        "base_shape": "ROUNDED_RECT" if composition.aspect != "SQUARE" else "CIRCLE",
        "camera_type": "PERSPECTIVE" if composition.aspect == "WIDE" else "ORTHO",
        "architecture_count": architecture,
        "prop_count": props,
        "vegetation_count": vegetation,
        "character_count": 0 if quality == "BLOCKOUT" else 2,
        "include_road": composition.horizon < 0.72,
    }

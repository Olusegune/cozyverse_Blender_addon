"""Pure validation and indexing helpers for local reference workflows."""

from __future__ import annotations

from collections import Counter
from pathlib import Path


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
ASSET_EXTENSIONS = {".blend", ".glb", ".gltf", ".fbx", ".obj"}


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

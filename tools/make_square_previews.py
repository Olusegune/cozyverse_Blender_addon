"""Create cover-cropped square copies of the bundled artwork for Blender's square preview cells.

Blender draws every preview in a square cell, so wide art is letterboxed with empty bars.
This centre-crops each image to a square (no stretching) and saves it under assets/square/.
Run:  python tools/make_square_previews.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parents[1] / "blender_addon" / "cozyverse_builder" / "assets"
GROUPS = ("templates", "styles", "atmosphere", "seasons", "story", "cinematic", "onboarding", "premium")
SIZE = 384
SKIP = {"icons", "placeholders", "brand"}


def square(source: Path, target: Path) -> None:
    with Image.open(source) as image:
        image = image.convert("RGB")
        side = min(image.size)
        left, top = (image.width - side) // 2, (image.height - side) // 2
        image.crop((left, top, left + side, top + side)).resize((SIZE, SIZE), Image.LANCZOS).save(target, quality=88, optimize=True)


def main() -> int:
    count = 0
    for group in GROUPS:
        for source in sorted((ASSETS / group).glob("*.png")):
            target = ASSETS / "square" / group / source.with_suffix(".jpg").name
            target.parent.mkdir(parents=True, exist_ok=True)
            square(source, target)
            count += 1
    print(f"wrote {count} square previews to {ASSETS / 'square'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

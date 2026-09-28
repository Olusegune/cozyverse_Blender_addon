"""Validated style presets shared by prompts, procedural builds, and asset matching."""

from __future__ import annotations

from dataclasses import dataclass


Color = tuple[float, float, float, float]


@dataclass(frozen=True)
class StylePreset:
    label: str
    description: str
    directive: str
    avoid: str
    keywords: tuple[str, ...]
    palette: tuple[Color, Color, Color, Color, Color]
    metallic: float = 0.0


STYLE_PRESETS = {
    "COZY_VILLAGE": StylePreset("Cozy Village", "Warm handcrafted neighborhood", "cozy handcrafted miniature village, rounded forms, warm practical lights", "harsh industrial forms", ("cozy", "village", "handcrafted", "warm"), ((0.12, .20, .12, 1), (.15, .52, .62, 1), (.62, .11, .08, 1), (.95, .55, .08, 1), (.08, .42, .16, 1))),
    "RETRO_SCIFI": StylePreset("Retro Sci-Fi", "Optimistic analog future", "retro 1950s science fiction, rounded modules, antennae, enamel panels, optimistic analog technology", "modern minimalism and cyberpunk clutter", ("retro", "sci-fi", "rounded", "modular", "space"), ((.08, .10, .14, 1), (.12, .55, .58, 1), (.72, .22, .10, 1), (.92, .68, .20, 1), (.30, .55, .42, 1)), .35),
    "COZY_FANTASY": StylePreset("Cozy Fantasy", "Whimsical storybook settlement", "cozy fantasy storybook forms, curved roofs, lanterns and oversized foliage", "modern technology and sharp corporate forms", ("fantasy", "storybook", "lantern", "curved"), ((.16, .12, .10, 1), (.48, .25, .52, 1), (.32, .12, .10, 1), (.92, .62, .18, 1), (.16, .46, .20, 1))),
    "SOLARPUNK": StylePreset("Solarpunk", "Green optimistic technology", "solarpunk architecture, abundant plants, solar canopies and bright optimistic materials", "pollution, dystopian decay and dark cyberpunk", ("solarpunk", "green", "solar", "optimistic"), ((.08, .24, .16, 1), (.20, .68, .52, 1), (.85, .52, .12, 1), (.94, .82, .30, 1), (.12, .58, .24, 1)), .12),
    "CYBERPUNK": StylePreset("Cyberpunk", "Dense neon future", "dense cyberpunk streets, layered signage, industrial forms and controlled neon accents", "pastoral simplicity and medieval props", ("cyberpunk", "neon", "industrial", "future"), ((.025, .03, .06, 1), (.08, .22, .34, 1), (.62, .04, .30, 1), (.10, .78, .82, 1), (.22, .10, .34, 1)), .55),
    "STORYBOOK": StylePreset("Storybook", "Soft illustrated world", "illustrated storybook miniature, soft shapes, playful proportions and painted surfaces", "photorealism and sharp technical detail", ("storybook", "painted", "soft", "playful"), ((.22, .30, .18, 1), (.46, .66, .76, 1), (.72, .28, .22, 1), (.92, .72, .30, 1), (.30, .58, .28, 1))),
    "LOW_POLY": StylePreset("Low-Poly", "Clean faceted geometry", "clean low-poly miniature, faceted silhouettes, restrained detail and readable shapes", "micro-detail and photorealistic surfaces", ("low-poly", "faceted", "game-ready", "simple"), ((.10, .18, .16, 1), (.18, .48, .62, 1), (.64, .22, .16, 1), (.88, .60, .18, 1), (.16, .46, .24, 1))),
    "CLAY": StylePreset("Clay Miniature", "Soft sculpted maquette", "hand-sculpted clay miniature, soft edges, fingerprints and matte materials", "glossy metal and photorealism", ("clay", "sculpted", "matte", "soft"), ((.22, .15, .12, 1), (.62, .38, .30, 1), (.58, .20, .16, 1), (.88, .60, .38, 1), (.30, .48, .28, 1))),
    "PAPERCRAFT": StylePreset("Paper Craft", "Layered cut-paper model", "layered paper-craft diorama, folded planes, cut edges and graphic colors", "realistic stone, glass and heavy texture", ("paper", "cutout", "folded", "graphic"), ((.12, .18, .20, 1), (.30, .62, .72, 1), (.76, .28, .22, 1), (.94, .72, .28, 1), (.28, .56, .34, 1))),
    "ART_DECO": StylePreset("Art Deco", "Geometric 1920s glamour", "Art Deco geometry, stepped silhouettes, brass accents and elegant symmetry", "rustic clutter and contemporary minimalism", ("art-deco", "geometric", "brass", "1920s"), ((.04, .08, .10, 1), (.10, .34, .38, 1), (.42, .12, .14, 1), (.82, .62, .20, 1), (.12, .30, .24, 1)), .45),
    "GOTHIC": StylePreset("Gothic", "Dramatic vertical architecture", "stylized Gothic miniature, pointed arches, vertical silhouettes and moody stone", "bright modern plastics", ("gothic", "arches", "stone", "dramatic"), ((.06, .07, .08, 1), (.18, .20, .24, 1), (.24, .08, .10, 1), (.52, .40, .20, 1), (.10, .22, .14, 1)), .15),
    "TROPICAL": StylePreset("Tropical", "Bright lush island setting", "lush tropical miniature, breezy structures, vivid plants and sun-washed color", "snow, heavy industry and cold lighting", ("tropical", "lush", "island", "bright"), ((.10, .26, .14, 1), (.10, .56, .66, 1), (.74, .20, .10, 1), (.96, .66, .16, 1), (.06, .52, .20, 1))),
}


def style_items() -> tuple[tuple[str, str, str], ...]:
    return tuple((identifier, preset.label, preset.description) for identifier, preset in STYLE_PRESETS.items())


def styled_prompt(prompt: str, style_id: str) -> str:
    preset = STYLE_PRESETS.get(style_id, STYLE_PRESETS["COZY_VILLAGE"])
    base = prompt.strip().rstrip(".")
    return f"{base}. Style direction: {preset.directive}. Avoid: {preset.avoid}." if base else f"Create a world with {preset.directive}. Avoid: {preset.avoid}."

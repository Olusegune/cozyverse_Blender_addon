"""Pure local-asset catalog, categorization, and matching logic."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path


CATEGORIES = ("CHARACTER", "BUILDING", "ROAD", "PROP", "VEGETATION", "VEHICLE", "FURNITURE", "OTHER")
CATEGORY_WORDS = {
    "CHARACTER": {"character", "person", "human", "woman", "man", "girl", "boy", "npc", "actor"},
    "BUILDING": {"building", "house", "home", "shop", "cafe", "castle", "station", "garage", "hut"},
    "ROAD": {"road", "street", "path", "sidewalk", "bridge", "rail", "track"},
    "VEGETATION": {"tree", "plant", "bush", "grass", "flower", "palm", "vegetation"},
    "VEHICLE": {"car", "truck", "rover", "bike", "vehicle", "ship", "boat", "train"},
    "FURNITURE": {"chair", "table", "bench", "sofa", "shelf", "bed", "furniture"},
    "PROP": {"prop", "crate", "barrel", "sign", "lamp", "antenna", "tool", "cart"},
}


@dataclass(frozen=True)
class AssetRecord:
    path: str
    name: str
    extension: str
    category: str
    tags: tuple[str, ...]
    source: str = "LOCAL_FOLDER"
    score: float = 0.0

    def as_dict(self) -> dict:
        value = asdict(self)
        value["tags"] = list(self.tags)
        return value


def tokenize(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(token for token in re.split(r"[^a-z0-9]+", value.casefold()) if len(token) > 1))


def categorize(name: str) -> str:
    words = set(tokenize(name))
    ranked = [(len(words & keywords), category) for category, keywords in CATEGORY_WORDS.items()]
    score, category = max(ranked, default=(0, "OTHER"))
    return category if score else "OTHER"


def record_from_path(path: str, source: str = "LOCAL_FOLDER") -> AssetRecord:
    item = Path(path)
    name = item.stem.replace("_", " ").replace("-", " ").strip()
    tags = tokenize(f"{name} {item.parent.name}")
    return AssetRecord(str(item), name or item.name, item.suffix.lower(), categorize(name), tags, source)


def match_assets(records: list[AssetRecord], query: str, style_keywords: tuple[str, ...] = (), category: str = "ALL") -> list[AssetRecord]:
    query_words = set(tokenize(query))
    style_words = set(tokenize(" ".join(style_keywords)))
    results = []
    for record in records:
        if category != "ALL" and record.category != category:
            continue
        tags = set(record.tags)
        score = len(tags & query_words) * 4.0 + len(tags & style_words) * 1.5
        if query_words and not score:
            continue
        score += 0.25 if record.extension == ".blend" else 0.0
        results.append(AssetRecord(record.path, record.name, record.extension, record.category, record.tags, record.source, score))
    return sorted(results, key=lambda item: (-item.score, item.name.casefold(), item.path.casefold()))

"""Place search: embeddings fused with fuzzy name matching."""

import re
from pathlib import Path

import numpy as np
from rapidfuzz import fuzz

from .embed import Embedder
from .mall import Mall

CATEGORY_LABELS = {
    "phone_repair": "Phone repair", "shoe_repair": "Shoe repair", "food": "Kain", "cafe": "Kape",
    "clothing": "Damit", "shoes": "Sapatos", "accessories": "Accessories", "gift": "Regalo",
    "home": "Home", "books_stationery": "Books & stationery", "beauty": "Beauty",
    "department_store": "Department store", "electronics": "Electronics", "gaming": "Gaming",
    "appliances": "Appliances", "grocery": "Grocery", "pharmacy": "Pharmacy", "bank": "Bank",
    "atm": "ATM", "remittance": "Padala", "courier": "Courier", "pet": "Pet", "restroom": "CR",
}

CATEGORY_ALIASES = {
    "cr": "restroom", "c.r.": "restroom", "banyo": "restroom", "restroom": "restroom", "toilet": "restroom",
    "comfort room": "restroom", "atm": "atm", "kain": "food", "gutom": "food", "food": "food",
    "pagkain": "food", "eat": "food", "pharmacy": "pharmacy", "botika": "pharmacy", "gamot": "pharmacy",
    "drugstore": "pharmacy", "phone repair": "phone_repair", "cellphone repair": "phone_repair",
    "kape": "cafe", "coffee": "cafe", "grocery": "grocery", "supermarket": "grocery",
    "padala": "remittance", "regalo": "gift", "damit": "clothing", "shoe repair": "shoe_repair",
}

MIN_NAME_WORD_LEN = 3


def _norm(text: str) -> str:
    return re.sub(r"[^\w&. ]+", " ", text.lower()).strip()


class Search:
    def __init__(self, mall: Mall, embedder: Embedder, cache_dir: Path | None = None):
        self.mall = mall
        self.embedder = embedder
        self.ids = list(mall.places)
        texts = [self._place_text(pid) for pid in self.ids]
        self.vectors = self._load_or_embed(texts, cache_dir)

    def _place_text(self, pid: str) -> str:
        p = self.mall.places[pid]
        return f"{p.name}. {CATEGORY_LABELS.get(p.category, p.category)}. {' '.join(p.tags)}"

    def _load_or_embed(self, texts: list[str], cache_dir: Path | None) -> np.ndarray:
        path = cache_dir / f"{self.mall.hash}-{self.embedder.model_id}.npy" if cache_dir else None
        if path and path.exists():
            return np.load(path)
        vectors = self.embedder.embed(texts, "passage")
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            np.save(path, vectors)
        return vectors

    def search(self, query: str, category: str | None = None, k: int = 5,
               floor: str | None = None) -> list[tuple[str, float]]:
        q = self.embedder.embed([query], "query")[0]
        cos = self.vectors @ q
        ql = query.lower()
        scored = []
        for i, pid in enumerate(self.ids):
            p = self.mall.places[pid]
            if floor and p.floor != floor:
                continue
            score = 0.7 * float(cos[i]) + 0.3 * fuzz.WRatio(ql, p.name.lower()) / 100
            if category and p.category == category:
                score += 0.15
            scored.append((pid, score))
        scored.sort(key=lambda t: -t[1])
        return scored[:k]

    def by_category(self, category: str) -> list[str]:
        order = {f: i for i, f in enumerate(self.mall.floor_order())}
        ids = [pid for pid in self.ids if self.mall.places[pid].category == category]
        return sorted(ids, key=lambda pid: (order[self.mall.places[pid].floor], pid))

    def alias_category(self, text: str) -> str | None:
        t = _norm(text)
        if t in CATEGORY_ALIASES:
            return CATEGORY_ALIASES[t]
        for cat, label in CATEGORY_LABELS.items():
            if t in (label.lower(), cat.replace("_", " ")):
                return cat
        return None

    def names_in(self, text: str) -> list[str]:
        tl = text.lower()
        found = []
        for name in sorted({p.name for p in self.mall.places.values()}, key=len, reverse=True):
            nl = name.lower()
            if len(nl) <= MIN_NAME_WORD_LEN:
                hit = re.search(rf"(?<![\w&]){re.escape(nl)}(?![\w&])", tl) is not None
            else:
                hit = fuzz.partial_ratio(nl, tl) >= 90
            if hit and not any(nl in f.lower() for f in found):
                found.append(name)
        return found

    def place_ids_named(self, name: str) -> list[str]:
        nl = name.lower().strip()
        return [pid for pid in self.ids
                if fuzz.WRatio(nl, self.mall.places[pid].name.lower()) >= 85]

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

NAME_SIM_MIN = 0.8
LEXICAL_WEIGHT = 0.2


GENERIC_NAME_WORDS = {"cafe", "store", "concept", "coffee", "express", "mobile", "authorized", "filipino",
                      "center", "shop", "the", "sm", "makati", "99"}
SHORT_ALIAS_LEN = 5


def _aliases(name: str) -> list[str]:
    """Full name plus the name with generic words removed ("ASUS Concept Store" -> "asus")."""
    full = name.lower()
    core = " ".join(w for w in re.findall(r"[\w&']+", full) if w not in GENERIC_NAME_WORDS)
    return [full] + ([core] if core and core != full and len(core) >= 3 else [])


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
        q_words = {w for w in re.findall(r"[\w&]+", ql) if len(w) >= 3}
        scored = []
        for i, pid in enumerate(self.ids):
            p = self.mall.places[pid]
            if floor and p.floor != floor:
                continue
            name_sim = fuzz.WRatio(ql, p.name.lower()) / 100
            score = 0.7 * float(cos[i]) + (0.3 * name_sim if name_sim >= NAME_SIM_MIN else 0.0)
            score += LEXICAL_WEIGHT * self._lexical(pid, ql, q_words)
            if category and p.category == category:
                score += 0.15
            scored.append((pid, score))
        scored.sort(key=lambda t: -t[1])
        return scored[:k]

    def _lexical(self, pid: str, query: str, q_words: set[str]) -> float:
        """Share of query words found verbatim in the place's name or tags (whole phrase counts fully)."""
        p = self.mall.places[pid]
        tags = [t.lower() for t in p.tags]
        if query in tags:
            return 1.0
        if not q_words:
            return 0.0
        vocab = set(re.findall(r"[\w&]+", " ".join(tags + [p.name.lower()])))
        return len(q_words & vocab) / len(q_words)

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
        """Store names mentioned in free text, matched by full name or by its distinctive part."""
        tl = text.lower()
        found = []
        for name in sorted({p.name for p in self.mall.places.values()}, key=len, reverse=True):
            if any(name.lower() in f.lower() for f in found):
                continue
            if any(self._mentions(alias, tl) for alias in _aliases(name)):
                found.append(name)
        return found

    @staticmethod
    def _mentions(alias: str, text: str) -> bool:
        if len(alias) <= SHORT_ALIAS_LEN:
            return re.search(rf"(?<![\w&]){re.escape(alias)}(?![\w&])", text) is not None
        return fuzz.partial_ratio(alias, text) >= 90

    def place_ids_named(self, name: str) -> list[str]:
        nl = name.lower().strip()
        return [pid for pid in self.ids
                if fuzz.WRatio(nl, self.mall.places[pid].name.lower()) >= 85]

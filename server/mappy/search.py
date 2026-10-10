"""Place search: embeddings fused with fuzzy name matching."""

import re
from pathlib import Path

import numpy as np
from rapidfuzz import fuzz

from .embed import Embedder
from .mall import Mall

CATEGORY_LABELS = {
    "phone_repair": "Phone repair", "shoe_repair": "Shoe repair", "food": "Food", "cafe": "Coffee",
    "clothing": "Clothes", "shoes": "Shoes", "accessories": "Accessories", "gift": "Gifts",
    "home": "Home", "books_stationery": "Books & stationery", "beauty": "Beauty",
    "department_store": "Department store", "electronics": "Electronics", "gaming": "Gaming",
    "appliances": "Appliances", "grocery": "Grocery", "pharmacy": "Pharmacy", "bank": "Bank",
    "atm": "ATM", "remittance": "Money transfer", "courier": "Courier", "pet": "Pet", "restroom": "Restroom",
    "services": "Customer service", "nursing_room": "Nursing room", "chapel": "Chapel", "clinic": "Clinic",
}

# A category's places as a plural noun phrase ("other shoe stores"), where the label alone would not read.
PLACE_LABELS = {
    "food": "food places", "cafe": "coffee shops", "clothing": "clothing stores", "shoes": "shoe stores",
    "accessories": "accessories stores", "gift": "gift shops", "home": "home stores",
    "books_stationery": "bookstores", "beauty": "beauty stores", "department_store": "department stores",
    "electronics": "electronics stores", "gaming": "gaming stores", "appliances": "appliance stores",
    "grocery": "groceries", "pharmacy": "pharmacies", "bank": "banks", "atm": "ATMs",
    "remittance": "money-transfer counters", "courier": "couriers", "pet": "pet stores", "restroom": "restrooms",
    "phone_repair": "phone repair shops", "shoe_repair": "shoe repair shops",
    "services": "service counters", "nursing_room": "nursing rooms", "chapel": "chapels", "clinic": "clinics",
}


def places_label(category: str) -> str:
    """A category's places mid-sentence: "coffee shops", "ATMs", "food places"."""
    return PLACE_LABELS.get(category) or f"{CATEGORY_LABELS.get(category, category).lower()} places"


# Words that point at a category anywhere in a short question ("san next kainan?"). Whole-word
# matches only, so Tagalog verb forms are listed rather than stemmed.
CATEGORY_WORDS = {
    "phone_repair": ["phone repair", "cellphone repair"],
    "shoe_repair": ["shoe repair"],
    "food": ["kain", "kainan", "makakainan", "kakain", "kumain", "kainin", "gutom", "nagugutom", "nagutom",
             "pagkain", "food", "foods", "eat", "eating", "hungry", "restaurant", "restaurants", "resto",
             "restos", "eatery", "food court", "foodcourt", "lunch", "dinner", "breakfast", "merienda",
             "tanghalian", "hapunan", "almusal"],
    "cafe": ["kape", "coffee", "cafe", "coffee shop", "uhaw", "nauuhaw", "thirsty"],
    "restroom": ["cr", "c.r.", "banyo", "restroom", "restrooms", "toilet", "comfort room", "bathroom",
                 "washroom", "ihi", "iihi", "naiihi", "jingle"],
    "atm": ["atm", "withdraw", "magwithdraw", "mag withdraw", "cash"],
    "bank": ["bank", "bangko"],
    "pharmacy": ["pharmacy", "botika", "gamot", "drugstore", "medicine", "vitamins"],
    "grocery": ["grocery", "supermarket", "groceries", "palengke"],
    "remittance": ["padala", "remittance", "remit", "money transfer"],
    "gift": ["regalo", "gift", "gifts", "present", "pasalubong"],
    "clothing": ["damit", "clothes", "clothing", "shirt", "pants"],
    "shoes": ["sapatos", "shoes", "sneakers", "tsinelas"],
    "books_stationery": ["bookstore", "books", "libro", "school supplies", "stationery", "notebook", "ballpen"],
    "beauty": ["makeup", "cosmetics", "skincare"],
    "pet": ["pet", "pets", "aso", "pusa", "pet shop", "pet store", "petshop", "dog", "cat", "dog food",
            "cat food", "pet food"],
    "gaming": ["gaming", "games", "console"],
    "electronics": ["electronics", "gadget", "gadgets"],
    "appliances": ["appliance", "appliances"],
    "services": ["customer service", "info desk", "information desk", "lost and found", "concierge"],
    "nursing_room": ["nursing room", "breastfeeding", "breast feeding", "lactation", "padede", "magpapadede",
                     "diaper change", "baby room"],
    "chapel": ["chapel", "simbahan", "misa", "mass", "magsimba", "prayer room", "dasal", "magdasal"],
    "clinic": ["clinic", "first aid", "doctor", "nurse", "nahihilo", "hinimatay"],
}
# Verb + object pairs that name a service, e.g. "ipapaayos sapatos" is shoe repair, not shoes.
# A matched pair consumes its words, so the object's own category doesn't also count.
REPAIR_WORDS = {"ayos", "paayos", "ipaayos", "ipapaayos", "papaayos", "magpaayos", "ayusin", "repair",
                "fix", "sira", "nasira", "basag", "broken", "cracked", "ipagawa", "pagawa", "magpagawa"}
SEND_WORDS = {"padala", "magpadala", "ipadala", "magpapadala", "send", "remit", "ship"}
CATEGORY_COMBOS = [
    (REPAIR_WORDS, {"phone", "cellphone", "cellfone", "cp", "tablet", "screen", "iphone", "android"},
     "phone_repair"),
    (REPAIR_WORDS, {"sapatos", "shoes", "shoe", "tsinelas", "takong", "heels"}, "shoe_repair"),
    (SEND_WORDS, {"pera", "money", "cash"}, "remittance"),
    (SEND_WORDS, {"package", "parcel", "box", "documents", "dokumento"}, "courier"),
]

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


_PHRASE_CATEGORY = {phrase: cat for cat, phrases in CATEGORY_WORDS.items() for phrase in phrases}
_PHRASE_RE = {phrase: re.compile(rf"(?<![\w&]){re.escape(phrase)}(?![\w&])")
              for phrase in sorted(_PHRASE_CATEGORY, key=len, reverse=True)}


def categories_in(text: str) -> set[str]:
    """Every category the text mentions, by service combo ("paayos sapatos") or category word."""
    t = _norm(text)
    words = set(re.findall(r"[\w&]+", t))
    found, used = set(), set()
    for verbs, objects, cat in CATEGORY_COMBOS:
        if (v := words & verbs) and (o := words & objects):
            found.add(cat)
            used |= v | o
    for phrase, pattern in _PHRASE_RE.items():  # longest first, so "dog food" is pet and not also food
        words_of = set(re.findall(r"[\w&]+", phrase))
        if not words_of <= used and pattern.search(t):
            found.add(_PHRASE_CATEGORY[phrase])
            used |= words_of
    return found


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

    @staticmethod
    def specific_words(query: str, category: str) -> set[str]:
        """The words of a request beyond its category's own: "korean" in "korean food"."""
        generic = {w for phrase in CATEGORY_WORDS.get(category, ()) for w in re.findall(r"[\w&]+", phrase)}
        generic |= set(re.findall(r"[\w&]+", CATEGORY_LABELS.get(category, "").lower()))
        return {w for w in re.findall(r"[\w&]+", query.lower()) if len(w) >= 3 and w not in generic}

    def word_score(self, pid: str, words: set[str]) -> int:
        """How many of these words a place's name or tags contain."""
        p = self.mall.places[pid]
        return len(words & set(re.findall(r"[\w&]+", " ".join([p.name, *p.tags]).lower())))

    def by_category(self, category: str) -> list[str]:
        order = {f: i for i, f in enumerate(self.mall.floor_order())}
        ids = [pid for pid in self.ids if self.mall.places[pid].category == category]
        return sorted(ids, key=lambda pid: (order[self.mall.places[pid].floor], pid))

    def matched_traits(self, pid: str, traits: tuple[str, ...]) -> list[str]:
        """The traits a place matches, by whole word/phrase in its tags or name, in the given order."""
        p = self.mall.places[pid]
        texts = [_norm(s) for s in (p.name, *p.tags)]
        return [t for t in traits
                if any(re.search(rf"(?<![\w&]){re.escape(_norm(t))}(?![\w&])", s) for s in texts)]

    def trait_score(self, pid: str, traits: tuple[str, ...]) -> int:
        """How many of the traits a place matches, by whole word/phrase in its tags or name."""
        return len(self.matched_traits(pid, traits))

    def distinctive_tags(self, pid: str) -> tuple[str, ...]:
        """What sets a place apart within its category: its tags minus the category's own words and
        minus the tags every place of that category carries ("chickenjoy", not "kain")."""
        p = self.mall.places[pid]
        shared = set(CATEGORY_WORDS.get(p.category, ()))
        shared |= set.intersection(*(set(self.mall.places[o].tags) for o in self.by_category(p.category)))
        return tuple(t for t in dict.fromkeys(p.tags) if t not in shared)

    def alternatives(self, category: str, traits: tuple[str, ...], exclude: tuple[str, ...] = ()) -> list[str]:
        """Places of a category ranked by trait overlap (desc), then floor order; `exclude` ids are dropped."""
        ids = [pid for pid in self.by_category(category) if pid not in exclude]
        return sorted(ids, key=lambda pid: -self.trait_score(pid, traits))  # stable: keeps floor order

    def alias_category(self, text: str) -> str | None:
        """The one category a short request points at, or None if it names a store or several things."""
        t = _norm(text)
        for cat, label in CATEGORY_LABELS.items():
            if t in (label.lower(), cat.replace("_", " ")):
                return cat
        if t in _PHRASE_CATEGORY:
            return _PHRASE_CATEGORY[t]
        if self.names_in(text):
            return None
        cats = categories_in(t)
        return cats.pop() if len(cats) == 1 else None

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
        if len(text) < len(alias):  # a slice of a longer name isn't a mention: "pet shop" in "the body shop"
            return fuzz.ratio(alias, text) >= 90
        return fuzz.partial_ratio(alias, text) >= 90

    def place_ids_named(self, name: str) -> list[str]:
        nl = name.lower().strip()
        return [pid for pid in self.ids
                if fuzz.WRatio(nl, self.mall.places[pid].name.lower()) >= 85]

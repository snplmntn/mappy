"""What well-known brands are, so a missing store can be answered with the nearest thing like it.
Categories are the app's own (see search.CATEGORY_LABELS); traits are plain words that also appear
in place tags, so alternatives can be ranked by what the shopper was really after."""

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

SHORT_ALIAS_LEN = 5
FUZZY_MIN = 90


@dataclass(frozen=True)
class Brand:
    name: str          # display name, e.g. "Jollibee"
    category: str      # one of CATEGORY_LABELS keys
    traits: tuple[str, ...]
    aliases: tuple[str, ...] = ()   # extra spellings/nicknames, lowercase: ("mcdo", "mcdonalds")
    everyday: bool = False          # name is also a common word ("mango"): only the whole request counts


BRANDS: tuple[Brand, ...] = (
    # food
    Brand("Jollibee", "food", ("fried chicken", "chicken", "burger", "spaghetti", "fast food"), ("jabee", "jolibee")),
    Brand("McDonald's", "food", ("burger", "fries", "chicken", "fast food"), ("mcdo", "mcdonalds", "mcdonald")),
    Brand("KFC", "food", ("fried chicken", "chicken", "fast food"), ("kentucky",)),
    Brand("Mang Inasal", "food", ("chicken", "filipino", "rice")),
    Brand("Chowking", "food", ("chinese", "noodles", "halo-halo", "fast food")),
    Brand("Greenwich", "food", ("pizza", "pasta")),
    Brand("Shakey's", "food", ("pizza", "chicken"), ("shakeys",)),
    Brand("Pizza Hut", "food", ("pizza", "pasta")),
    Brand("Yellow Cab", "food", ("pizza", "pasta")),
    Brand("Burger King", "food", ("burger", "fries", "fast food")),
    Brand("Wendy's", "food", ("burger", "fries", "fast food"), ("wendys",)),
    Brand("Army Navy", "food", ("burger", "burrito")),
    Brand("Max's Restaurant", "food", ("chicken", "filipino"), ("max's", "maxs")),
    Brand("Kenny Rogers", "food", ("chicken", "roast chicken")),
    Brand("BonChon", "food", ("chicken", "korean")),
    Brand("Tokyo Tokyo", "food", ("japanese", "rice")),
    Brand("Pepper Lunch", "food", ("japanese", "rice", "steak")),
    Brand("Ramen Nagi", "food", ("ramen", "japanese")),
    Brand("Pancake House", "food", ("pancake", "filipino")),
    Brand("Red Ribbon", "food", ("cake", "bakery", "dessert")),
    Brand("Goldilocks", "food", ("cake", "bakery", "dessert")),
    Brand("Chatime", "food", ("milk tea",)),
    Brand("Macao Imperial", "food", ("milk tea",)),
    Brand("Serenitea", "food", ("milk tea",)),
    Brand("Dairy Queen", "food", ("ice cream", "dessert")),
    Brand("Potato Corner", "food", ("fries", "snack")),
    Brand("Andok's", "food", ("chicken", "filipino"), ("andoks",)),
    Brand("Samgyupsalamat", "food", ("korean", "bbq")),
    Brand("Zark's", "food", ("burger",), ("zarks",)),
    Brand("Subway", "food", ("sandwich",)),
    Brand("Taco Bell", "food", ("tacos", "burrito", "mexican")),
    Brand("Sbarro", "food", ("pizza", "pasta")),
    Brand("Classic Savory", "food", ("chicken", "chinese")),
    Brand("Conti's", "food", ("cake", "bakery", "dessert"), ("contis",)),
    Brand("Shawarma Shack", "food", ("shawarma",)),
    Brand("Mister Donut", "food", ("donut", "dessert"), ("mr donut",)),
    # cafe
    Brand("Starbucks", "cafe", ("coffee", "pastry")),
    Brand("Coffee Bean & Tea Leaf", "cafe", ("coffee", "tea", "pastry"), ("coffee bean", "cbtl")),
    Brand("Seattle's Best", "cafe", ("coffee", "pastry"), ("seattles best",)),
    Brand("Bo's Coffee", "cafe", ("coffee",), ("bos coffee",)),
    Brand("UCC", "cafe", ("coffee", "japanese")),
    Brand("Tim Hortons", "cafe", ("coffee", "donut")),
    Brand("Dunkin", "cafe", ("donut", "coffee"), ("dunkin donuts",)),
    Brand("Krispy Kreme", "cafe", ("donut", "coffee")),
    Brand("Figaro", "cafe", ("coffee",)),
    Brand("Mary Grace", "cafe", ("coffee", "ensaymada", "pastry")),
    Brand("Delifrance", "cafe", ("coffee", "bread", "sandwich")),
    Brand("Kumori", "cafe", ("bakery", "japanese", "pastry")),
    Brand("Tiger Sugar", "cafe", ("milk tea",)),
    Brand("Gong Cha", "cafe", ("milk tea",)),
    # clothing
    Brand("Uniqlo", "clothing", ("fashion", "basics")),
    Brand("H&M", "clothing", ("fashion",)),
    Brand("Zara", "clothing", ("fashion",)),
    Brand("Bench", "clothing", ("fashion", "basics"), everyday=True),
    Brand("Penshoppe", "clothing", ("fashion",)),
    Brand("Forever 21", "clothing", ("fashion",)),
    Brand("Cotton On", "clothing", ("fashion", "basics")),
    Brand("Mango", "clothing", ("fashion",), everyday=True),
    Brand("Giordano", "clothing", ("fashion", "basics")),
    Brand("Oxygen", "clothing", ("fashion",), everyday=True),
    Brand("Levi's", "clothing", ("jeans", "fashion"), ("levis",)),
    Brand("Lacoste", "clothing", ("fashion",)),
    Brand("Guess", "clothing", ("fashion",), everyday=True),
    Brand("Old Navy", "clothing", ("fashion", "basics")),
    Brand("Gap", "clothing", ("fashion", "basics"), everyday=True),
    Brand("Terranova", "clothing", ("fashion",)),
    Brand("Regatta", "clothing", ("fashion",)),
    # shoes
    Brand("Nike", "shoes", ("sneakers", "sportswear")),
    Brand("Adidas", "shoes", ("sneakers", "sportswear")),
    Brand("Skechers", "shoes", ("sneakers", "shoes")),
    Brand("Converse", "shoes", ("sneakers",), everyday=True),
    Brand("Vans", "shoes", ("sneakers",), everyday=True),
    Brand("Crocs", "shoes", ("sandals",)),
    Brand("Havaianas", "shoes", ("sandals", "tsinelas")),
    Brand("World Balance", "shoes", ("sneakers", "shoes")),
    Brand("Payless", "shoes", ("shoes", "sandals")),
    Brand("Toms", "shoes", ("shoes",), everyday=True),
    Brand("Birkenstock", "shoes", ("sandals",)),
    Brand("Puma", "shoes", ("sneakers", "sportswear")),
    Brand("New Balance", "shoes", ("sneakers", "sportswear")),
    # accessories
    Brand("Pandora", "accessories", ("jewelry",)),
    Brand("Swatch", "accessories", ("watch",)),
    Brand("Casio", "accessories", ("watch",)),
    Brand("Fossil", "accessories", ("watch", "bag")),
    Brand("Lovisa", "accessories", ("jewelry",)),
    Brand("Charles & Keith", "accessories", ("bag", "shoes"), ("charles and keith",)),
    Brand("Sunnies Studios", "accessories", ("sunglasses", "eyeglasses"), ("sunnies",)),
    Brand("Owndays", "accessories", ("eyeglasses",)),
    # beauty
    Brand("Watsons", "beauty", ("skincare", "medicine", "vitamins")),
    Brand("Sephora", "beauty", ("makeup", "skincare")),
    Brand("The Body Shop", "beauty", ("skincare",), ("body shop",)),
    Brand("Innisfree", "beauty", ("skincare", "korean")),
    Brand("Nature Republic", "beauty", ("skincare", "korean")),
    Brand("Etude House", "beauty", ("makeup", "korean"), ("etude",)),
    Brand("Beauty Bar", "beauty", ("makeup", "skincare")),
    Brand("Kiehl's", "beauty", ("skincare",), ("kiehls",)),
    Brand("MAC", "beauty", ("makeup",), ("mac cosmetics",), everyday=True),
    Brand("Colourette", "beauty", ("makeup",)),
    Brand("Human Nature", "beauty", ("skincare",)),
    Brand("BYS", "beauty", ("makeup",)),
    # pharmacy
    Brand("Mercury Drug", "pharmacy", ("medicine", "vitamins"), ("mercury",)),
    Brand("Southstar Drug", "pharmacy", ("medicine", "vitamins"), ("southstar",)),
    Brand("Rose Pharmacy", "pharmacy", ("medicine", "vitamins")),
    Brand("Generika", "pharmacy", ("medicine",)),
    Brand("TGP", "pharmacy", ("medicine",), ("the generics pharmacy",)),
    # electronics
    Brand("Power Mac Center", "electronics", ("apple", "phone", "laptop"), ("power mac",)),
    Brand("Samsung", "electronics", ("phone", "gadget")),
    Brand("Apple", "electronics", ("apple", "phone", "laptop"), everyday=True),
    Brand("Huawei", "electronics", ("phone", "gadget")),
    Brand("Oppo", "electronics", ("phone",)),
    Brand("Vivo", "electronics", ("phone",)),
    Brand("Realme", "electronics", ("phone",)),
    Brand("Xiaomi", "electronics", ("phone", "gadget"), ("mi store",)),
    Brand("Silicon Valley", "electronics", ("laptop", "gadget")),
    Brand("Octagon", "electronics", ("laptop", "gadget")),
    Brand("Digital Walker", "electronics", ("gadget",)),
    Brand("Beyond the Box", "electronics", ("apple", "phone", "laptop")),
    Brand("PC Express", "electronics", ("laptop", "gadget")),
    # gaming
    Brand("Datablitz", "gaming", ("games", "console")),
    Brand("GameXtreme", "gaming", ("games", "console"), ("game xtreme",)),
    Brand("iTech", "gaming", ("games", "gadget")),
    Brand("Nintendo", "gaming", ("games", "console")),
    Brand("PlayStation", "gaming", ("games", "console"), ("ps5",)),
    Brand("Timezone", "gaming", ("arcade", "games")),
    # appliances
    Brand("Abenson", "appliances", ("appliance",)),
    Brand("Anson's", "appliances", ("appliance", "gadget"), ("ansons",)),
    Brand("Automatic Centre", "appliances", ("appliance",), ("automatic center",)),
    Brand("Western Appliances", "appliances", ("appliance",)),
    Brand("Dyson", "appliances", ("appliance",)),
    Brand("SM Appliance", "appliances", ("appliance",), ("sm appliance center",)),
    # gift
    Brand("Toy Kingdom", "gift", ("toys", "gift")),
    Brand("Toys R Us", "gift", ("toys", "gift"), ("toysrus",)),
    Brand("Papemelroti", "gift", ("gift", "souvenir")),
    Brand("Kultura", "gift", ("souvenir", "gift", "filipino")),
    Brand("Hallmark", "gift", ("gift", "cards")),
    Brand("Typo", "gift", ("gift", "school supplies"), everyday=True),
    # books_stationery
    Brand("National Book Store", "books_stationery", ("books", "school supplies"),
          ("national bookstore", "nbs")),
    Brand("Fully Booked", "books_stationery", ("books",)),
    Brand("Powerbooks", "books_stationery", ("books",)),
    # grocery
    Brand("SM Supermarket", "grocery", ("grocery",)),
    Brand("Robinsons Supermarket", "grocery", ("grocery",)),
    Brand("Landers", "grocery", ("grocery",)),
    Brand("S&R", "grocery", ("grocery",), ("s and r", "snr")),
    Brand("7-Eleven", "grocery", ("snack", "convenience"), ("7 eleven", "7-11", "711", "seven eleven")),
    Brand("Ministop", "grocery", ("snack", "convenience")),
    Brand("FamilyMart", "grocery", ("snack", "convenience"), ("family mart",)),
    Brand("Alfamart", "grocery", ("snack", "convenience")),
    # department_store
    Brand("SM Store", "department_store", ("fashion", "home")),
    Brand("Rustan's", "department_store", ("fashion", "luxury"), ("rustans",)),
    Brand("Landmark", "department_store", ("fashion", "grocery"), everyday=True),
    Brand("Robinsons Department Store", "department_store", ("fashion", "home")),
    Brand("Metro", "department_store", ("fashion", "home"), everyday=True),
    # home
    Brand("Miniso", "home", ("home", "gift")),
    Brand("Daiso", "home", ("home", "kitchen")),
    Brand("Muji", "home", ("home", "japanese")),
    Brand("IKEA", "home", ("home", "furniture")),
    Brand("Ace Hardware", "home", ("hardware", "home")),
    Brand("Wilcon", "home", ("hardware", "home"), ("wilcon depot",)),
    Brand("True Value", "home", ("hardware", "home")),
    Brand("Our Home", "home", ("home", "furniture")),
    Brand("SM Home", "home", ("home", "kitchen")),
    # bank
    Brand("BDO", "bank", ("withdraw",)),
    Brand("BPI", "bank", ("withdraw",)),
    Brand("Metrobank", "bank", ("withdraw",)),
    Brand("Landbank", "bank", ("withdraw",)),
    Brand("UnionBank", "bank", ("withdraw",)),
    Brand("Security Bank", "bank", ("withdraw",)),
    Brand("RCBC", "bank", ("withdraw",)),
    Brand("PNB", "bank", ("withdraw",)),
    Brand("Chinabank", "bank", ("withdraw",), ("china bank",)),
    Brand("EastWest", "bank", ("withdraw",), ("eastwest bank", "east west")),
    # remittance
    Brand("Western Union", "remittance", ("remittance",)),
    Brand("Palawan Express", "remittance", ("remittance",), ("palawan",)),
    Brand("Cebuana Lhuillier", "remittance", ("remittance",), ("cebuana",)),
    Brand("MLhuillier", "remittance", ("remittance",), ("m lhuillier",)),
    Brand("GCash", "remittance", ("remittance",)),
    Brand("Maya", "remittance", ("remittance",), ("paymaya",), everyday=True),
    # courier
    Brand("LBC", "courier", ("package",)),
    Brand("JRS Express", "courier", ("package",), ("jrs",)),
    Brand("J&T Express", "courier", ("package",), ("j&t", "j and t")),
    Brand("DHL", "courier", ("package",)),
    Brand("FedEx", "courier", ("package",)),
    Brand("2GO", "courier", ("package",)),
    Brand("Grab Express", "courier", ("package",)),
    # pet
    Brand("Pet Express", "pet", ("pet",)),
    Brand("Pet Lovers Centre", "pet", ("pet",), ("pet lovers",)),
    Brand("Bow & Wow", "pet", ("pet",), ("bow and wow",)),
    Brand("Dogs and the City", "pet", ("pet",)),
)


def _norm(text: str) -> str:
    """Lowercase, punctuation (except & and ') turned into spaces, spaces collapsed."""
    return " ".join(re.sub(r"[^\w&' ]+", " ", text.lower()).split())


def _spellings(brand: Brand) -> tuple[str, ...]:
    """The brand's name and aliases, normalized."""
    return tuple(_norm(alias) for alias in (brand.name, *brand.aliases))


# Every spelling of every brand, longest first, so "coffee bean & tea leaf" beats "coffee bean".
_ALIASES: list[tuple[str, Brand]] = sorted(
    ((alias, b) for b in BRANDS for alias in _spellings(b)),
    key=lambda t: len(t[0]), reverse=True,
)
_BY_NAME: dict[str, Brand] = {alias: b for alias, b in reversed(_ALIASES)}


def _whole_phrase(alias: str, text: str) -> bool:
    return re.search(rf"(?<![\w&]){re.escape(alias)}(?![\w&])", text) is not None


def _named(alias: str, brand: Brand, text: str) -> bool:
    """The alias is spelled out in the text (the whole text, for a brand that is also a plain word)."""
    return alias == text if brand.everyday else _whole_phrase(alias, text)


def _windows(text: str, size: int) -> list[str]:
    words = text.split()
    return [" ".join(words[i:i + size]) for i in range(len(words) - size + 1)]


def _typo_of(alias: str, brand: Brand, text: str) -> bool:
    """A run of words in the text as long as the alias (give or take one) nearly spells it ("jolibee").
    Whole windows only: a score against a slice of the text would let "mi store" pass as SM Store."""
    if brand.everyday or len(alias) <= SHORT_ALIAS_LEN:
        return False
    n = len(alias.split())
    return any(fuzz.ratio(alias, w) >= FUZZY_MIN
               for size in (n, n - 1, n + 1) if size > 0 for w in _windows(text, size))


def brand_in(text: str) -> Brand | None:
    """The brand a short request names, matched by full name or alias, else None. An exact spelling
    anywhere in the text wins (longest first, so "coffee bean" does not lose to "bean"); only then
    is a near-miss spelling tried, so "pet express" is Pet Express, never a typo of J&T Express."""
    t = _norm(text)
    for match in (_named, _typo_of):
        if found := next((b for alias, b in _ALIASES if match(alias, b, t)), None):
            return found
    return None


def is_store_of(brand: Brand, place_name: str, tags: tuple[str, ...] = ()) -> bool:
    """Whether a place is one of the brand's stores: a spelling of the brand is a whole phrase of the
    place name ("The SM Store", "BDO ATM") or of a tag ("Mi Store" tagged "xiaomi"), or the two
    names nearly coincide. Not a loose score, so "Mi Store" is not SM Store and "Pet Express" is
    not J&T Express. Tags count only for brands that are not plain words ("apple" is a tag of a
    fruit stand)."""
    pn = _norm(place_name)
    spellings = _spellings(brand)
    if any(_whole_phrase(alias, pn) or fuzz.ratio(alias, pn) >= FUZZY_MIN for alias in spellings):
        return True
    return not brand.everyday and any(_whole_phrase(alias, _norm(tag)) for tag in tags for alias in spellings)


def traits_of(name: str) -> tuple[str, ...]:
    """Traits for a brand/store named exactly by its name or an alias (case- and punctuation-
    insensitive), or () when unknown. Used to rank alternatives for a store that exists but is far
    (Task 4)."""
    b = _BY_NAME.get(_norm(name))
    return b.traits if b else ()

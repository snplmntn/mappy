"""What well-known brands are, so a missing store can be answered with the nearest thing like it.
Categories are the app's own (see search.CATEGORY_LABELS); traits are plain words that also appear
in place tags, so alternatives can be ranked by what the shopper was really after."""

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

SHORT_ALIAS_LEN = 5
FUZZY_MIN = 90
# A request shorter than an alias is a typo of it only if at most this many characters are missing
# ("jolibee" for "jollibee"), not a phrase inside it ("department store" in "sm department store").
MAX_TYPO_GAP = 2


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
    Brand("Xiaomi", "electronics", ("phone", "gadget")),
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


# Every spelling of every brand, longest first, so "coffee bean & tea leaf" beats "coffee bean".
_ALIASES: list[tuple[str, Brand]] = sorted(
    ((_norm(alias), b) for b in BRANDS for alias in (b.name, *b.aliases)),
    key=lambda t: len(t[0]), reverse=True,
)
_BY_NAME: dict[str, Brand] = {alias: b for alias, b in reversed(_ALIASES)}


def _mentions(alias: str, brand: Brand, text: str) -> bool:
    if brand.everyday:
        return alias == text
    if len(alias) <= SHORT_ALIAS_LEN:
        return re.search(rf"(?<![\w&]){re.escape(alias)}(?![\w&])", text) is not None
    if len(alias) > len(text):
        # partial_ratio would find a short text inside a long alias ("coffee" in "coffee bean").
        return len(alias) - len(text) <= MAX_TYPO_GAP and fuzz.ratio(alias, text) >= FUZZY_MIN
    return fuzz.partial_ratio(alias, text) >= FUZZY_MIN


def brand_in(text: str) -> Brand | None:
    """The brand a short request names, matched by full name or alias (typo-tolerant), else None.
    Longest alias wins so "coffee bean" does not lose to "bean"."""
    t = _norm(text)
    return next((b for alias, b in _ALIASES if _mentions(alias, b, t)), None)


def traits_of(name: str) -> tuple[str, ...]:
    """Traits for a brand/store named exactly by its name or an alias (case- and punctuation-
    insensitive), or () when unknown. Used to rank alternatives for a store that exists but is far
    (Task 4)."""
    b = _BY_NAME.get(_norm(name))
    return b.traits if b else ()

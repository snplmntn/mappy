import pytest

from mappy.brands import BRANDS, brand_in, is_store_of, traits_of
from mappy.search import CATEGORY_LABELS, CATEGORY_WORDS

_BRAND = {b.name: b for b in BRANDS}


def test_names_a_brand_inside_a_request():
    b = brand_in("take me to jollibee")
    assert b.name == "Jollibee"
    assert b.category == "food"


def test_resolves_alias_and_typo():
    assert brand_in("mcdo").name == "McDonald's"
    assert brand_in("jolibee").name == "Jollibee"


def test_longest_alias_wins():
    assert brand_in("coffee bean").name == "Coffee Bean & Tea Leaf"


def test_categories_of_known_brands():
    assert brand_in("may uniqlo ba dito").category == "clothing"
    assert brand_in("mercury drug").category == "pharmacy"
    assert brand_in("nike").category == "shoes"
    assert brand_in("lbc").category == "courier"


def test_unknown_text_and_category_words_are_not_brands():
    assert brand_in("zzyzx emporium") is None
    assert brand_in("food") is None
    assert brand_in("coffee") is None
    assert brand_in("atm") is None


def test_no_category_label_or_phrase_is_a_brand():
    phrases = {label.lower() for label in CATEGORY_LABELS.values()}
    phrases |= {cat.replace("_", " ") for cat in CATEGORY_LABELS}
    phrases |= {w for ws in CATEGORY_WORDS.values() for w in ws}
    assert {p: brand_in(p).name for p in phrases if brand_in(p)} == {}


def test_everyday_word_brands_need_the_whole_request():
    assert brand_in("mango").name == "Mango"
    assert brand_in("bench").name == "Bench"
    assert brand_in("mango shake") is None
    assert brand_in("i guess so") is None
    assert brand_in("where is a bench") is None
    assert brand_in("mind the gap") is None
    assert brand_in("apple pie") is None
    assert brand_in("metro manila") is None


def test_apostrophe_ampersand_and_hyphen_spellings():
    assert brand_in("mcdonald's").name == "McDonald's"
    assert brand_in("j&t express").name == "J&T Express"
    assert brand_in("7-11").name == "7-Eleven"


def test_short_alias_needs_whole_word():
    assert brand_in("backfcolor") is None  # "kfc" inside a word


def test_exact_spelling_beats_a_near_miss_of_another_brand():
    assert brand_in("pet express").name == "Pet Express"  # not a typo of "j&t express"
    assert brand_in("mi store").name == "Xiaomi"           # never SM Store
    assert brand_in("department store") is None            # not a slice of "robinsons department store"


def test_typo_must_cover_a_whole_run_of_words():
    assert brand_in("jollibe").name == "Jollibee"
    assert brand_in("sa jolibee tayo").name == "Jollibee"
    assert brand_in("sm department store") is None


def test_table_is_consistent():
    names = [b.name for b in BRANDS]
    assert len(names) == len(set(names))
    category_words = {w for ws in CATEGORY_WORDS.values() for w in ws}
    category_words |= {label.lower() for label in CATEGORY_LABELS.values()}
    category_words |= {cat.replace("_", " ") for cat in CATEGORY_LABELS}
    for b in BRANDS:
        assert b.category in CATEGORY_LABELS, b.name
        assert b.traits, b.name
        for alias in b.aliases:
            assert alias == alias.lower(), alias
        for alias in (b.name.lower(), *b.aliases):
            assert alias not in category_words, alias


def test_traits_of():
    assert "chicken" in traits_of("Jollibee")
    assert "chicken" in traits_of("jollibee")
    assert traits_of("Unknown") == ()


@pytest.mark.parametrize("brand, place, expected", [
    ("Jollibee", "Jollibee", True),
    ("McDonald's", "Jollibee", False),
    ("SM Store", "The SM Store", True),
    ("SM Store", "Mi Store", False),
    ("SM Store", "SM Makati Foodcourt", False),
    ("SM Store", "ASUS Concept Store", False),
    ("Seattle's Best", "Seattle's Best Coffee", True),
    ("J&T Express", "Pet Express", False),
    ("Kultura", "Kultura Filipino", True),
    ("BDO", "BDO", True),
    ("BDO", "BDO ATM", True),
    ("Mary Grace", "Mary Grace Cafe", True),
    ("Nintendo", "Nintendo Authorized Store", True),
    ("DHL", "DHL Express", True),
    ("Coffee Bean & Tea Leaf", "Buttons & Wrap", False),
    ("National Book Store", "Mi Store", False),
    ("National Book Store", "The SM Store", False),
    ("Ramen Nagi", "Kyu Kyu Ramen 99", False),
])
def test_is_store_of(brand, place, expected):
    assert is_store_of(_BRAND[brand], place) is expected


def test_a_store_no_brand_owns():
    assert not [b.name for b in BRANDS if is_store_of(b, "Buttons & Wrap")]


def test_a_tag_names_the_brand_of_a_store():
    assert is_store_of(_BRAND["Xiaomi"], "Mi Store", ("gadget", "xiaomi")) is True
    assert is_store_of(_BRAND["SM Store"], "Mi Store", ("gadget", "xiaomi")) is False
    assert is_store_of(_BRAND["Apple"], "Fruit Stand", ("apple",)) is False  # everyday word: name only

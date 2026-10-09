from mappy.brands import BRANDS, brand_in, traits_of
from mappy.search import CATEGORY_LABELS, CATEGORY_WORDS


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


def test_short_alias_needs_whole_word():
    assert brand_in("backfcolor") is None  # "kfc" inside a word


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

from mappy.llm import SCHEMA, fallback_extract, from_short, trip_summary
from mappy.models import Errand, Trip


def test_fallback_splits_taglish():
    x = fallback_extract("papaayos ko phone, kain, tapos bili damit", Trip())
    assert x.intent == "plan" and len(x.errands) == 3 and x.source == "fallback"
    assert x.errands[0].query == "phone"


def test_fallback_single_is_find():
    assert fallback_extract("pharmacy", Trip()).intent == "find"


def test_fallback_caps_five():
    assert len(fallback_extract("a1, b2, c3, d4, e5, f6, g7", Trip()).errands) == 5


def test_trip_summary():
    t = Trip(errands=[Errand(id="e1", label="Phone repair", query="q", candidates=["fixit-ax"],
                             duration_min=45, **{"async": True})])
    assert trip_summary(t, {"fixit-ax": "FixIt Mobile"}.get) == "e1: Phone repair, FixIt Mobile, 45 min, async, todo"


def test_from_short_maps_keys():
    x = from_short({"i": "plan", "e": [{"q": "phone screen repair", "c": "phone_repair"}],
                    "d": [{"op": "set_duration", "e": "e1", "n": 30}], "l": ["Jollibee"], "f": "4F"})
    assert x.intent == "plan" and x.errands[0].category == "phone_repair"
    assert x.edits[0].minutes == 30 and x.edits[0].errand == "e1"
    assert x.landmarks == ["Jollibee"] and x.floor == "4F" and x.source == "llm"


def test_from_short_drops_unknown_ops_and_null_category():
    x = from_short({"i": "edit", "e": [{"q": "x", "c": None}], "d": [{"op": "fly"}], "l": [], "f": None})
    assert x.edits == [] and x.errands[0].category is None


def test_schema_has_categories():
    s = SCHEMA(["food", "atm"])
    assert "food" in s["properties"]["e"]["items"]["properties"]["c"]["anyOf"][0]["enum"]

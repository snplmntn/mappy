import asyncio

from mappy.chat import ChatService
from mappy.llm import LLMBusy
from mappy.models import Edit, ErrandReq, Extraction, Trip
from mappy.router import Router

AT = {"anchor": "gf-entrance"}


class BusyLLM:
    async def extract(self, message, trip, summary=""):
        raise LLMBusy()


class FixedLLM:
    def __init__(self, x):
        self.x = x

    async def extract(self, message, trip, summary=""):
        return self.x


def svc(mall, search, llm=None):
    return ChatService(mall=mall, search=search, router=Router(mall), router_elev=Router(mall, True),
                       llm=llm or BusyLLM())


def run(coro):
    return asyncio.run(coro)


def test_chip_cr(mall, search):
    out = run(svc(mall, search).chat("CR", AT, "14:00", Trip()))
    assert out["result"]["type"] == "places" and out["result"]["places"][0]["id"] == "cr-gf"
    assert out["result"]["places"][0]["floor_name"] == "Ground Floor"
    assert out["meta"] == {"engine": "rules", "intent": "find"}


def test_plan_via_llm_then_steer(mall, search):
    x = Extraction(intent="plan", source="llm", errands=[
        ErrandReq(query="phone screen repair", category="phone_repair"),
        ErrandReq(query="eat", category="food"), ErrandReq(query="clothes", category="clothing")])
    s = svc(mall, search, FixedLLM(x))
    out = run(s.chat("papaayos ko phone, kain, damit", AT, "14:00", Trip()))
    assert out["result"]["type"] == "plan" and len(out["trip"]["errands"]) == 3
    assert out["trip"]["errands"][0]["async"] is True
    trip = Trip.model_validate(out["trip"])
    out2 = run(s.chat("sabi ng technician 30 mins lang", AT, "14:05", trip))
    assert out2["result"]["type"] == "plan" and "30" in out2["result"]["changes"][0]
    assert out2["trip"]["errands"][0]["duration_source"] == "user"


def test_find_shows_the_nearest_places(mall, search, monkeypatch):
    monkeypatch.setattr("mappy.chat.FIND_RESULTS", 1)
    out = run(svc(mall, search).chat("san next kainan?", {"node": "2F-c3"}, "14:00", Trip()))
    assert [p["id"] for p in out["result"]["places"]] == ["foodcourt-2f"]


def test_category_word_beats_the_llm_guess(mall, search):
    x = Extraction(intent="plan", source="llm", errands=[
        ErrandReq(query="gutom", category="restroom"), ErrandReq(query="kape", category="food")])
    out = run(svc(mall, search, FixedLLM(x)).chat("gutom na ko, ano ba yan, kape", AT, "14:00", Trip()))
    assert [e["category"] for e in out["trip"]["errands"]] == ["food", "cafe"]


class CountingLLM(FixedLLM):
    calls = 0

    async def extract(self, message, trip, summary=""):
        self.calls += 1
        return self.x


def test_rules_dead_end_asks_the_llm(mall, search):
    llm = CountingLLM(Extraction(intent="find", source="llm", errands=[ErrandReq(query="meal", category="food")]))
    out = run(svc(mall, search, llm).chat("saan yung zzyzx", AT, "14:00", Trip()))
    assert llm.calls == 1 and out["meta"]["engine"] == "llm" and out["result"]["type"] == "places"


def test_rules_hit_skips_the_llm(mall, search):
    llm = CountingLLM(Extraction(intent="other", source="llm"))
    out = run(svc(mall, search, llm).chat("CR", AT, "14:00", Trip()))
    assert llm.calls == 0 and out["result"]["type"] == "places"


def test_llm_dead_end_keeps_the_rules_reply(mall, search):
    llm = CountingLLM(Extraction(intent="locate", source="llm", landmarks=["Zzyzx"]))
    out = run(svc(mall, search, llm).chat("saan yung zzyzx", AT, "14:00", Trip()))
    assert llm.calls == 1 and "couldn't find" in out["reply"] and out["meta"]["engine"] == "rules"


def test_dead_end_with_busy_llm_keeps_the_rules_reply(mall, search):
    out = run(svc(mall, search).chat("saan yung zzyzx", AT, "14:00", Trip()))
    assert "couldn't find" in out["reply"] and out["meta"]["engine"] == "rules"


def test_busy_llm_falls_back(mall, search):
    out = run(svc(mall, search).chat("phone, kain, damit", AT, "14:00", Trip()))
    assert out["result"]["type"] == "plan" and len(out["trip"]["errands"]) >= 2


def test_locate(mall, search):
    out = run(svc(mall, search).chat("nasa tabi ako ng Starbucks katapat ng H&M", None, "14:00", Trip()))
    assert out["result"]["type"] == "locate" and out["result"]["candidates"][0]["floor"] == "GF"


def test_steer_without_plan_asks(mall, search):
    out = run(svc(mall, search).chat("30 mins lang", AT, "14:00", Trip()))
    assert out["result"]["type"] == "text" and "don't have a trip yet" in out["reply"]


def test_greeting_other(mall, search):
    out = run(svc(mall, search).chat("salamat!", AT, "14:00", Trip()))
    assert out["result"]["type"] == "text"


def test_chat_unknown_store_says_not_found(mall, search):
    x = Extraction(intent="find", source="llm", errands=[ErrandReq(query="Zzyzx Emporium")])
    out = run(svc(mall, search, FixedLLM(x)).chat("saan ang Zzyzx Emporium sa mall na ito", None, "14:00", Trip()))
    assert out["result"]["type"] == "text" and "couldn't find" in out["reply"].lower()


def test_chat_caps_errands_at_five(mall, search):
    x = Extraction(intent="plan", source="llm", errands=[ErrandReq(query=q) for q in
                   ["kape", "kain", "damit", "regalo", "cellphone", "phone repair"]])
    out = run(svc(mall, search, FixedLLM(x)).chat("lahat lahat na gusto ko gawin dito", None, "14:00", Trip()))
    assert len(out["trip"]["errands"]) <= 5 and "5" in out["reply"]


def test_plan_endpoint_applies_tap_edit(mall, search):
    s = svc(mall, search)
    trip = Trip.model_validate(run(s.chat("phone, kain", AT, "14:00", Trip()))["trip"])
    out = s.plan(AT, "14:01", trip, [Edit(op="set_duration", errand="e1", minutes=15)])
    assert out["trip"]["errands"][0]["duration_min"] == 15 and out["changes"]


def test_route_to_place(mall, search):
    out = svc(mall, search).route(AT, {"place": "starbucks-2f"}, elevator_only=False)
    assert out["legs"] and out["legs"][-1]["floor"] == "2F" and out["walk_min"] >= 1


def test_start_node_defaults_to_first_anchor(mall, search):
    assert svc(mall, search).start_node(None) == "GF-c1"
    assert svc(mall, search).start_node({"node": "2F-c3"}) == "2F-c3"


def test_fallback_six_errands_says_capped(mall, search):
    out = run(svc(mall, search).chat("kape, kain, damit, regalo, cellphone, sapatos", AT, "14:00", Trip()))
    assert len(out["trip"]["errands"]) <= 5 and "first 5" in out["reply"]


def test_kain_muna_then_kape_muna_does_not_crash(mall, search):
    s = svc(mall, search)
    trip = Trip.model_validate(run(s.chat("phone, kain, kape, damit", AT, "14:00", Trip()))["trip"])
    trip = Trip.model_validate(run(s.chat("kain muna", AT, "14:01", trip))["trip"])
    out = run(s.chat("kape muna", AT, "14:02", trip))
    assert out["result"]["type"] == "plan"


def test_not_found_suggests_what_to_try(mall, search):
    x = Extraction(intent="find", source="llm", errands=[ErrandReq(query="Zzyzx Emporium")])
    out = run(svc(mall, search, FixedLLM(x)).chat("saan ang Zzyzx Emporium", None, "14:00", Trip()))
    assert "Try a store name" in out["reply"]


def test_edit_that_changes_nothing_says_so(mall, search):
    s = svc(mall, search)
    trip = Trip.model_validate(run(s.chat("phone, kain", AT, "14:00", Trip()))["trip"])
    x = Extraction(intent="edit", source="llm", edits=[Edit(op="set_duration", errand="e1")])
    out = run(svc(mall, search, FixedLLM(x)).chat("pakiayos naman yung plano ko please", AT, "14:01", trip))
    assert out["result"]["type"] == "text" and "didn't catch" in out["reply"]


def test_help_with_a_trip_suggests_edits(mall, search):
    s = svc(mall, search)
    trip = Trip.model_validate(run(s.chat("phone, kain", AT, "14:00", Trip()))["trip"])
    out = run(s.chat("salamat!", AT, "14:01", trip))
    label = trip.errands[0].label.lower()
    assert f"skip {label}" in out["reply"]


def test_missing_brand_lists_same_kind(mall, search):
    out = run(svc(mall, search).chat("mcdo", AT, "14:00", Trip()))
    result = out["result"]
    assert result["type"] == "places" and result["alternatives_for"] == "McDonald's"
    assert result["places"] and all(p["category"] == "food" for p in result["places"])
    assert out["reply"].startswith("No McDonald's in this mall, but here are other food places.")
    assert out["reply"].endswith(" min away.")
    assert out["meta"]["engine"] == "rules"


def test_missing_clothing_brand_lists_clothes(mall, search):
    out = run(svc(mall, search).chat("zara", AT, "14:00", Trip()))
    assert out["result"]["type"] == "places" and [p["id"] for p in out["result"]["places"]] == ["hm-gf"]
    assert "other clothes places" in out["reply"]


def test_missing_brand_without_its_category_says_not_found(mall, search):
    out = run(svc(mall, search).chat("watsons", AT, "14:00", Trip()))
    assert out["result"]["type"] == "text" and "couldn't find" in out["reply"]


def test_llm_category_guess_lists_alternatives(mall, search):
    x = Extraction(intent="find", source="llm", errands=[ErrandReq(query="Zzyzx Burgers", category="food")])
    out = run(svc(mall, search, FixedLLM(x)).chat("saan ang Zzyzx Burgers dito", AT, "14:00", Trip()))
    assert out["result"]["type"] == "places" and out["result"]["alternatives_for"] == "Zzyzx Burgers"
    assert all(p["category"] == "food" for p in out["result"]["places"])


def test_alternatives_lead_with_matching_traits(mall, search):
    out = run(svc(mall, search).chat("ramen nagi", AT, "14:00", Trip()))
    assert out["result"]["places"][0]["id"] == "foodcourt-2f"
    assert "also do ramen" in out["reply"]


def test_plan_swaps_a_missing_brand(mall, search):
    out = run(svc(mall, search).chat("mcdo, phone repair", AT, "14:00", Trip()))
    errands = out["trip"]["errands"]
    assert out["result"]["type"] == "plan" and len(errands) == 2
    food = next(e for e in errands if e["category"] == "food")
    assert set(food["candidates"]) <= set(search.by_category("food"))
    assert "No McDonald's here, so I added other food places instead." in out["reply"]

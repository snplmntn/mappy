"""Brand questions against the real demo mall (hash embedder, no cache), so a store that is here is
never answered with "No X in this mall"."""

import asyncio
from pathlib import Path

import pytest

from mappy.chat import ChatService
from mappy.embed import HashEmbedder
from mappy.mall import load_mall
from mappy.models import ErrandReq, Extraction, Trip
from mappy.router import Router
from mappy.search import Search

P = Path(__file__).resolve().parents[2] / "data" / "sm-makati" / "mall.json"
AT = {"anchor": "gf-mrt-entrance"}


@pytest.fixture(scope="module")
def real():
    mall = load_mall(P)
    search = Search(mall, HashEmbedder())
    return ChatService(mall=mall, search=search, router=Router(mall), router_elev=Router(mall, True), llm=None)


def ask(svc, text):
    return asyncio.run(svc.chat(text, AT, "14:00", Trip()))


@pytest.mark.parametrize("text, pid", [
    ("pet express", "pet-express-gf"),   # not a typo of J&T Express
    ("mi store", "mi-store-3f"),         # not a typo of SM Store
    ("xiaomi", "mi-store-3f"),           # Mi Store is tagged "xiaomi"
    ("sm store", "the-sm-store-gf"),
])
def test_a_store_that_is_here_is_a_name_hit(real, text, pid):
    out = ask(real, text)
    assert out["result"]["type"] == "places" and "alternatives_for" not in out["result"], out["reply"]
    assert out["result"]["places"][0]["id"] == pid


class FixedLLM:
    def __init__(self, x):
        self.x = x

    async def extract(self, message, trip, summary=""):
        return self.x


def with_llm(real, x):
    return ChatService(mall=real.mall, search=real.search, router=real.router, router_elev=real.router_elev,
                       llm=FixedLLM(x))


def say(svc, text, trip=None, at=AT, now="14:00"):
    return asyncio.run(svc.chat(text, at, now, Trip.model_validate(trip) if trip else Trip()))


def test_dropped_repair_is_picked_up_where_it_was_dropped(real):
    planned = say(real, "papaayos ko phone ko, kakain, tapos bibili ng regalo")
    drop = next(s["place"] for s in planned["result"]["plan"]["stops"] if s["kind"] == "drop")
    dropped = say(real, "naiwan ko na yung phone", planned["trip"])
    assert dropped["trip"]["errands"][0]["chosen"] == drop
    later = say(real, "dagdag mo kape", dropped["trip"])
    assert next(s["place"] for s in later["result"]["plan"]["stops"] if s["kind"] == "pick") == drop


def test_a_generic_stop_uses_the_nearest_places(real):
    out = say(real, "cr muna tapos kape", at={"anchor": "3f-ace-hardware"})
    start = real.mall.anchors["3f-ace-hardware"].node
    restrooms = [p for p in real.mall.places.values() if p.category == "restroom"]
    nearest = min(restrooms, key=lambda p: real.router.seconds(start, p.node))
    assert nearest.floor == "3F" and out["result"]["plan"]["stops"][0]["place"] == nearest.id


def test_a_new_list_skips_stops_already_planned(real):
    first = say(real, "cr muna tapos kape")
    out = say(real, "atm, kape", first["trip"])
    assert [e["category"] for e in out["trip"]["errands"]] == ["restroom", "cafe", "atm"]
    assert "already in your plan" in out["reply"]


def test_two_named_stores_of_one_kind_are_two_stops(real):
    out = say(real, "uniqlo and h&m")
    assert out["result"]["type"] == "plan" and len(out["trip"]["errands"]) == 2


def test_a_friend_described_spot_is_for_navigating(real):
    out = say(real, "my friend is near gong cha")
    assert out["result"]["type"] == "locate" and out["result"]["friend"] is True
    assert "friend" in out["reply"]


def test_where_am_i_explains_how_to_set_the_spot(real):
    out = say(real, "nasaan ako")
    assert out["result"]["type"] == "text" and "location code" in out["reply"]


def test_llm_small_talk_doesnt_hide_not_found(real):
    out = say(with_llm(real, Extraction(intent="other", source="llm")), "sinehan")
    assert "couldn't find" in out["reply"]


def test_llm_cant_turn_one_request_into_a_plan(real):
    x = Extraction(intent="plan", source="llm", errands=[ErrandReq(query="phone repair", category="phone_repair"),
                                                         ErrandReq(query="coffee", category="cafe")])
    out = say(with_llm(real, x), "nasira yung charger ng laptop ko")
    assert out["result"]["type"] == "places" and out["trip"]["errands"] == []


@pytest.mark.parametrize("text, pid", [("pet shop", "pet-express-gf"), ("dog food", "pet-express-gf"),
                                       ("korean food", "ssamjang-express-lg")])
def test_category_requests_find_the_right_store(real, text, pid):
    assert ask(real, text)["result"]["places"][0]["id"] == pid


def test_no_nudge_for_a_dish(real):
    out = ask(real, "ramen")
    assert not any(p.get("nudge") for p in out["result"]["places"])


def test_repair_carries_to_a_bare_object(real):
    out = say(real, "papaayos ko phone ko at sapatos ko tapos kakain")
    assert [e["category"] for e in out["trip"]["errands"]] == ["phone_repair", "shoe_repair", "food"]


def test_skipping_a_stop_not_in_the_plan_removes_nothing(real):
    planned = say(real, "papaayos ko phone ko tapos kakain")
    out = say(real, "skip shoe repair", planned["trip"])
    assert "isn't in your plan" in out["reply"] and len(out["trip"]["errands"]) == 2


def test_a_bare_hour_already_past_means_evening(real):
    planned = say(real, "papaayos ko phone ko tapos kakain", now="20:30")
    out = say(real, "aalis ako ng 8", planned["trip"], now="20:30")
    assert out["trip"]["constraints"]["deadline"] == "20:00"


def test_steering_with_no_trip_says_so(real):
    assert "don't have a trip" in say(real, "skip food")["reply"]
    out = say(real, "aalis ako ng 5")
    assert out["result"]["type"] == "text" and out["trip"]["constraints"]["deadline"] == "17:00"


def test_a_named_store_narrows_a_stand_in_for_the_same_stop(real):
    out = say(real, "zara and h&m")
    assert [e["candidates"] for e in out["trip"]["errands"]] == [["h-m-gf"]]

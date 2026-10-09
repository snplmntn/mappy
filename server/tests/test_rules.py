import pytest

from mappy.models import Errand, Trip
from mappy.rules import floor_hint, parse, parse_minutes, parse_time


@pytest.mark.parametrize("s,m", [("30 mins lang", 30), ("1 oras daw", 60), ("isang oras", 60),
                                 ("1.5 oras", 90), ("kalahating oras", 30), ("45 minuto", 45),
                                 ("2 hrs", 120), ("dalawang oras", 120)])
def test_minutes(s, m):
    assert parse_minutes(s) == m


def test_minutes_none():
    assert parse_minutes("kain muna") is None


@pytest.mark.parametrize("s,t", [("ready by 4pm", "16:00"), ("4:30", "16:30"), ("umalis ng 6", "18:00"),
                                 ("10am", "10:00"), ("12:15", "12:15"), ("9 pm", "21:00")])
def test_time(s, t):
    assert parse_time(s) == t


def test_floor_hint():
    assert floor_hint("nasa 4th floor ako") == "4F"
    assert floor_hint("sa annex") == "AX"
    assert floor_hint("ground floor") == "GF"
    assert floor_hint("hello") is None


def trip():
    return Trip(errands=[
        Errand(id="e1", label="Phone repair", query="phone repair", category="phone_repair",
               candidates=["fixit-ax"], duration_min=45, **{"async": True}),
        Errand(id="e2", label="Damit", query="damit", category="clothing", candidates=["hm-gf"], duration_min=25),
    ])


def test_steer_duration_and_deadline(search):
    x = parse("sabi ng technician 1 oras daw, tapos kailangan ko umalis ng 5", trip(), search)
    ops = {e.op: e for e in x.edits}
    assert x.intent == "edit"
    assert ops["set_duration"].minutes == 60 and ops["deadline"].time == "17:00"


def test_steer_ready_at(search):
    x = parse("ready daw by 4pm", trip(), search)
    assert x.edits[0].op == "set_ready_at" and x.edits[0].time == "16:00"


def test_steer_remove(search):
    x = parse("wag na yung H&M", trip(), search)
    assert x.edits[0].op == "remove" and "H&M" in x.edits[0].errand


def test_steer_eat_first(search):
    x = parse("gutom na ko, kain muna", trip(), search)
    assert any(e.op == "order" and e.rule == "first" and "kain" in e.errand for e in x.edits)


def test_dropped(search):
    assert parse("naiwan ko na yung phone", trip(), search).edits[0].status == "dropped"


def test_done(search):
    assert parse("nakuha ko na yung phone", trip(), search).edits[0].status == "done"


def test_stroller(search):
    assert parse("may stroller ako", trip(), search).edits[0].op == "elevator_only"


def test_chip_find(search):
    x = parse("CR", Trip(), search)
    assert x.intent == "find" and x.errands[0].category == "restroom"


def test_short_query_find(search):
    x = parse("phone repair", Trip(), search)
    assert x.intent == "find" and x.errands[0].category == "phone_repair"


def test_locate(search):
    x = parse("nasa tabi ako ng Starbucks, katapat ng H&M", Trip(), search)
    assert x.intent == "locate" and set(x.landmarks) == {"Starbucks", "H&M"}


def test_locate_with_floor(search):
    x = parse("andito ako sa 2F tapat ng Starbucks", Trip(), search)
    assert x.intent == "locate" and x.floor == "2F"


def test_multi_errand_goes_to_llm(search):
    assert parse("papaayos ko screen ng phone ko, kakain, tapos bibili ng regalo", Trip(), search) is None


def test_steering_without_trip_is_edit_so_chat_can_ask(search):
    x = parse("30 mins lang", Trip(), search)
    assert x.intent == "edit" and x.edits[0].op == "set_duration"


def test_muna_without_trip_is_not_edit(search):
    x = parse("withdraw muna ako sa atm then kape", Trip(), search)
    assert x is None or x.intent != "edit"


def test_add_errand(search):
    for msg in ("dagdag mo yung pharmacy", "pasama na rin ng ATM", "isama mo ang regalo"):
        x = parse(msg, trip(), search)
        assert x.intent == "edit" and x.edits[0].op == "add", msg
    assert parse("pasama na rin ng ATM", trip(), search).edits[0].query == "ATM"


def test_greetings_are_other(search):
    for msg in ("salamat po!", "hello", "hi", "thank you", "anong oras kayo nagsasara"):
        assert parse(msg, Trip(), search).intent == "other", msg


def test_question_is_find(search):
    x = parse("where can I fix my cracked phone screen", Trip(), search)
    assert x.intent == "find" and "phone" in x.errands[0].query

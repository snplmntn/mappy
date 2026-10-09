from conftest import write_mall
from mappy.mall import load_mall
from mappy.models import Constraints, Errand, OrderRule, Trip
from mappy.planner import plan_trip
from mappy.router import Router

NOW = 14 * 60


def E(id, label, cat, place, dur, async_=False, **kw):
    return Errand(id=id, label=label, query=label, category=cat, candidates=[place],
                  duration_min=dur, **{"async": async_}, **kw)


def base(repair_dur=45, **c):
    return Trip(errands=[E("e1", "Phone repair", "phone_repair", "fixit-ax", repair_dur, True),
                         E("e2", "Kain", "food", "jollibee-gf", 30),
                         E("e3", "Damit", "clothing", "hm-gf", 25)],
                constraints=Constraints(**c))


def seq(plan):
    return [(s.kind, s.place) for s in plan.stops]


def test_acceptance_wait_aware_order(mall):
    p = plan_trip(base(), "GF-c1", NOW, Router(mall), mall)
    assert seq(p) == [("drop", "fixit-ax"), ("visit", "jollibee-gf"), ("visit", "hm-gf"), ("pick", "fixit-ax")]
    assert p.idle_min == 0
    assert p.stops[0].reason.startswith("Drop off first")
    assert p.stops[1].reason == "Eat while waiting"


def test_short_repair_flips_to_pick_immediately(mall):
    long_plan = plan_trip(base(), "GF-c1", NOW, Router(mall), mall)
    short = plan_trip(base(repair_dur=5), "GF-c1", NOW, Router(mall), mall)
    kinds = [s.kind for s in short.stops]
    assert kinds.index("pick") == kinds.index("drop") + 1
    assert seq(short) != seq(long_plan)


def test_order_rule_first(mall):
    p = plan_trip(base(order=[OrderRule(errand="e3", rule="first")]), "GF-c1", NOW, Router(mall), mall)
    assert seq(p)[0] == ("visit", "hm-gf")


def test_dropped_only_pick(mall):
    t = base()
    t.errands[0].status = "dropped"
    t.errands[0].dropped_at = "13:30"
    p = plan_trip(t, "GF-c1", NOW, Router(mall), mall)
    kinds = [s.kind for s in p.stops]
    assert "drop" not in kinds and ("pick", "fixit-ax") in seq(p)


def test_ready_at_overrides_duration(mall):
    t = base()
    t.errands[0].ready_at = "17:00"
    p = plan_trip(t, "GF-c1", NOW, Router(mall), mall)
    pick = next(s for s in p.stops if s.kind == "pick")
    assert pick.arrive_min >= 17 * 60 - 1 or p.idle_min > 0


def test_done_errands_skipped(mall):
    t = base()
    t.errands[2].status = "done"
    assert all(s.errand != "e3" for s in plan_trip(t, "GF-c1", NOW, Router(mall), mall).stops)


def test_user_duration_in_reason(mall):
    t = base()
    t.errands[0].duration_min = 30
    t.errands[0].duration_source = "user"
    stops = plan_trip(t, "GF-c1", NOW, Router(mall), mall).stops
    assert "(you said)" in next(s for s in stops if s.kind == "drop").reason


def test_deadline_warning(mall):
    p = plan_trip(base(deadline="14:30"), "GF-c1", NOW, Router(mall), mall)
    assert p.warnings and "14:30" in p.warnings[0]


def test_deadline_already_passed_warns(mall):
    p = plan_trip(base(deadline="13:00"), "GF-c1", NOW, Router(mall), mall)
    assert any("13:00" in w for w in p.warnings)


def test_picks_nearer_candidate(mall):
    t = Trip(errands=[Errand(id="e1", label="Kape", query="kape", category="cafe",
                             candidates=["starbucks-2f", "starbucks-gf"], duration_min=20)])
    assert plan_trip(t, "GF-c1", NOW, Router(mall), mall).stops[0].place == "starbucks-gf"


def test_chosen_candidate_respected(mall):
    t = Trip(errands=[Errand(id="e1", label="Kape", query="kape", category="cafe", chosen="starbucks-2f",
                             candidates=["starbucks-2f", "starbucks-gf"], duration_min=20)])
    assert plan_trip(t, "GF-c1", NOW, Router(mall), mall).stops[0].place == "starbucks-2f"


def test_legs_cover_floors(mall):
    p = plan_trip(base(), "GF-c1", NOW, Router(mall), mall)
    assert {l.floor for l in p.legs} >= {"GF", "AX"}
    assert all(l.stop_index < len(p.stops) for l in p.legs)


def test_times_are_consistent(mall):
    p = plan_trip(base(), "GF-c1", NOW, Router(mall), mall)
    assert all(a.leave_min <= b.arrive_min for a, b in zip(p.stops, p.stops[1:]))
    assert p.finish_at == p.stops[-1].leave and p.total_min == p.stops[-1].leave_min - NOW


def test_unreachable_candidate_skipped(tmp_path, sample_raw):
    sample_raw["connectors"] = [c for c in sample_raw["connectors"] if c["kind"] != "bridge"]
    m = load_mall(write_mall(tmp_path, sample_raw))
    p = plan_trip(base(), "GF-c1", NOW, Router(m), m)
    assert all(s.place != "fixit-ax" for s in p.stops)
    assert any("Phone repair" in w for w in p.warnings)


def test_five_errands_stays_fast(mall):
    import time
    t = Trip(errands=[E("e1", "Phone repair", "phone_repair", "fixit-ax", 45, True),
                      E("e2", "Shoe repair", "shoe_repair", "bos-ax", 30, True),
                      Errand(id="e3", label="Kape", query="k", category="cafe",
                             candidates=["starbucks-gf", "starbucks-2f"], duration_min=20),
                      Errand(id="e4", label="Kain", query="k", category="food",
                             candidates=["jollibee-gf", "foodcourt-2f"], duration_min=30),
                      E("e5", "Damit", "clothing", "hm-gf", 25)])
    start = time.perf_counter()
    p = plan_trip(t, "GF-c1", NOW, Router(mall), mall)
    assert time.perf_counter() - start < 2.0 and len(p.stops) == 7


def test_empty_trip(mall):
    p = plan_trip(Trip(), "GF-c1", NOW, Router(mall), mall)
    assert p.stops == [] and p.finish_at == "14:00"


def test_conflicting_order_rules_do_not_crash(mall):
    t = base(order=[OrderRule(errand="e2", rule="first"), OrderRule(errand="e3", rule="first")])
    p = plan_trip(t, "GF-c1", NOW, Router(mall), mall)
    assert len(p.stops) == 4 and p.warnings


def test_all_unreachable_keeps_warnings(mall):
    t = Trip(errands=[E("e1", "Ghost", "food", "no-such-place", 30)])
    p = plan_trip(t, "GF-c1", NOW, Router(mall), mall)
    assert p.stops == [] and any("Ghost" in w for w in p.warnings)

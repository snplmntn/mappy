from mappy.models import Edit, Errand, Trip
from mappy.trip import apply_edits, new_errand_id


def E(id, label, cat, async_=False, cands=("p1",), dur=30, status="todo"):
    return Errand(id=id, label=label, query=label, category=cat, candidates=list(cands),
                  duration_min=dur, status=status, **{"async": async_})


NAMES = {"fixit-ax": "FixIt Mobile", "jollibee-gf": "Jollibee", "foodcourt-2f": "Food Court",
         "hm-gf": "H&M", "bos-ax": "BOS Shoe Repair", "kultura-gf": "Kultura", "p1": "P1"}
FLOORS = {"jollibee-gf": "GF", "foodcourt-2f": "2F", "hm-gf": "GF", "fixit-ax": "AX"}


def run(trip, edits, now=600, make=lambda q, c, i: None):
    return apply_edits(trip, edits, now, make, NAMES.get, FLOORS.get)


def trip3():
    return Trip(errands=[E("e1", "Phone repair", "phone_repair", True, ("fixit-ax",), 45),
                         E("e2", "Kain", "food", cands=("jollibee-gf", "foodcourt-2f")),
                         E("e3", "Damit", "clothing", cands=("hm-gf",), dur=25)])


def test_new_errand_id():
    assert new_errand_id(trip3()) == "e4" and new_errand_id(Trip()) == "e1"


def test_set_duration_defaults_to_only_async():
    t, changes, q = run(trip3(), [Edit(op="set_duration", minutes=30)])
    assert q is None
    assert t.errands[0].duration_min == 30 and t.errands[0].duration_source == "user"
    assert "45 → 30" in changes[0]


def test_ambiguous_reference_asks():
    tr = trip3()
    tr.errands.append(E("e4", "Shoe repair", "shoe_repair", True, ("bos-ax",), 30))
    t, changes, q = run(tr, [Edit(op="set_duration", minutes=30)])
    assert q and "Phone repair" in q and "Shoe repair" in q
    assert changes == [] and t == tr


def test_text_reference_by_place_name():
    t, _, q = run(trip3(), [Edit(op="remove", errand="H&M")])
    assert q is None and [e.id for e in t.errands] == ["e1", "e2"]


def test_remove_drops_order_rules():
    tr = trip3()
    t, _, _ = run(tr, [Edit(op="order", errand="e3", rule="first"), Edit(op="remove", errand="e3")])
    assert t.constraints.order == []


def test_order_first_replaces_previous():
    t, _, _ = run(trip3(), [Edit(op="order", errand="e3", rule="first"),
                            Edit(op="order", errand="e3", rule="last")])
    assert [(o.errand, o.rule) for o in t.constraints.order] == [("e3", "last")]


def test_order_by_label_text():
    t, _, q = run(trip3(), [Edit(op="order", errand="kain", rule="first")])
    assert q is None and t.constraints.order[0].errand == "e2"


def test_status_dropped_sets_time():
    t, _, _ = run(trip3(), [Edit(op="status", status="dropped")], now=14 * 60)
    assert t.errands[0].status == "dropped" and t.errands[0].dropped_at == "14:00"


def test_set_ready_at():
    t, changes, _ = run(trip3(), [Edit(op="set_ready_at", time="16:00")])
    assert t.errands[0].ready_at == "16:00" and "16:00" in changes[0]


def test_choose_by_floor():
    t, _, _ = run(trip3(), [Edit(op="choose", errand="e2", place_hint="yung nasa 2F")])
    assert t.errands[1].chosen == "foodcourt-2f"


def test_add_uses_factory():
    made = E("tmp", "Regalo", "gift", cands=("kultura-gf",), dur=15)
    t, changes, _ = run(trip3(), [Edit(op="add", query="regalo")],
                        make=lambda q, c, i: made.model_copy(update={"id": i}))
    assert t.errands[-1].id == "e4" and changes


def test_add_nothing_found_reports():
    t, changes, q = run(trip3(), [Edit(op="add", query="spaceship")])
    assert len(t.errands) == 3 and "spaceship" in changes[0] and q is None


def test_deadline_and_elevator():
    t, _, _ = run(trip3(), [Edit(op="deadline", time="18:00"), Edit(op="elevator_only", value=True)])
    assert t.constraints.deadline == "18:00" and t.constraints.elevator_only


def test_edit_without_errands_asks():
    t, changes, q = run(Trip(), [Edit(op="set_duration", minutes=30)])
    assert q and "don't have a trip yet" in q


def test_does_not_mutate_input():
    tr = trip3()
    run(tr, [Edit(op="set_duration", minutes=30)])
    assert tr.errands[0].duration_min == 45


def test_new_first_rule_replaces_other_first_rule():
    t, _, _ = run(trip3(), [Edit(op="order", errand="e2", rule="first"), Edit(op="order", errand="e3", rule="first")])
    assert [(o.errand, o.rule) for o in t.constraints.order] == [("e3", "first")]


def test_choose_unmatched_asks_instead_of_silently_doing_nothing():
    t, changes, q = run(trip3(), [Edit(op="choose", errand="e2", place_hint="Zzyzx")])
    assert t.errands[1].chosen is None and not changes and "Zzyzx" in q

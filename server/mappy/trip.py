"""Apply structured edits to a trip. Deterministic: the model proposes, this code disposes."""

import re
from collections.abc import Callable

from rapidfuzz import fuzz

from .models import Edit, Errand, OrderRule, Trip, min_to_hhmm
from .search import CATEGORY_LABELS

MakeErrand = Callable[[str, str | None, str], Errand | None]
NameOf = Callable[[str], str | None]

NO_PLAN_QUESTION = "You don't have a trip yet. What do you need to do at the mall?"
ERRAND_OPS = {"set_duration", "set_ready_at", "remove", "order", "status", "choose"}
ASYNC_OPS = {"set_duration", "set_ready_at", "status"}
MATCH_MIN = 70
TIE_MARGIN = 3
FLOOR_TOKEN = re.compile(r"\b(LG|UG|GF|[1-5]F|AX)\b", re.I)


class _Question(Exception):
    pass


def new_errand_id(trip: Trip) -> str:
    nums = [int(e.id[1:]) for e in trip.errands if re.fullmatch(r"e\d+", e.id)]
    return f"e{max(nums, default=0) + 1}"


def _labels(errands: list[Errand]) -> str:
    return ", ".join(e.label for e in errands)


def _texts(e: Errand, place_name: NameOf) -> list[str]:
    texts = [e.label, e.query]
    if e.category:
        texts += [CATEGORY_LABELS.get(e.category, e.category), e.category.replace("_", " ")]
    for pid in ([e.chosen] if e.chosen else []) + e.candidates:
        name = place_name(pid)
        if name:
            texts.append(name)
    return [t.lower() for t in texts if t]


def resolve_errand(trip: Trip, ref: str | None, op: str, place_name: NameOf) -> tuple[str | None, str | None]:
    active = [e for e in trip.errands if e.status != "done"]
    if not trip.errands:
        return None, NO_PLAN_QUESTION
    if ref and any(e.id == ref for e in trip.errands):
        return ref, None
    if ref:
        rl = ref.lower().strip()
        scored = sorted(((max(fuzz.WRatio(rl, t) for t in _texts(e, place_name)), e) for e in trip.errands),
                        key=lambda t: -t[0])
        best = scored[0][0]
        if best < MATCH_MIN:
            return None, f"Which one do you mean: {_labels(trip.errands)}?"
        tied = [e for s, e in scored if best - s <= TIE_MARGIN]
        if len(tied) > 1:
            return None, f"Which one: {_labels(tied)}?"
        return scored[0][1].id, None
    pool = active
    if op in ASYNC_OPS:
        async_active = [e for e in active if e.async_]
        if async_active:
            pool = async_active
    if len(pool) == 1:
        return pool[0].id, None
    return None, f"Which one: {_labels(pool)}?"


def _find(trip: Trip, eid: str) -> Errand:
    return next(e for e in trip.errands if e.id == eid)


def _resolve(trip: Trip, ref: str | None, op: str, place_name: NameOf) -> Errand:
    eid, question = resolve_errand(trip, ref, op, place_name)
    if question:
        raise _Question(question)
    return _find(trip, eid)


def _choose(e: Errand, hint: str, place_name: NameOf, place_floor: NameOf) -> str | None:
    m = FLOOR_TOKEN.search(hint)
    floor = m.group(1).upper() if m else ("AX" if "annex" in hint.lower() else None)
    if floor:
        on_floor = [pid for pid in e.candidates if place_floor(pid) == floor]
        if on_floor:
            return on_floor[0]
    scored = [(fuzz.WRatio(hint.lower(), (place_name(pid) or "").lower()), pid) for pid in e.candidates]
    best = max(scored, default=(0, None))
    return best[1] if best[0] >= 60 else None


def apply_edits(trip: Trip, edits: list[Edit], now_min: int, make_errand: MakeErrand,
                place_name: NameOf, place_floor: NameOf) -> tuple[Trip, list[str], str | None]:
    if not trip.errands and any(e.op in ERRAND_OPS for e in edits):
        return trip, [], NO_PLAN_QUESTION
    t = trip.model_copy(deep=True)
    changes: list[str] = []
    try:
        for ed in edits:
            if ed.op == "set_duration" and ed.minutes:
                e = _resolve(t, ed.errand, ed.op, place_name)
                changes.append(f"{e.label}: {e.duration_min} → {ed.minutes} min (you said)")
                e.duration_min, e.duration_source = ed.minutes, "user"
            elif ed.op == "set_ready_at" and ed.time:
                e = _resolve(t, ed.errand, ed.op, place_name)
                e.ready_at = ed.time
                changes.append(f"{e.label}: ready by {ed.time}")
            elif ed.op == "add" and ed.query:
                made = make_errand(ed.query, ed.category, new_errand_id(t))
                if made is None:
                    changes.append(f"Couldn't find “{ed.query}”")
                else:
                    t.errands.append(made)
                    changes.append(f"Added {made.label}")
            elif ed.op == "remove":
                e = _resolve(t, ed.errand, ed.op, place_name)
                t.errands = [x for x in t.errands if x.id != e.id]
                t.constraints.order = [o for o in t.constraints.order if e.id not in (o.errand, o.other)]
                changes.append(f"Removed {e.label}")
            elif ed.op == "order" and ed.rule:
                e = _resolve(t, ed.errand, ed.op, place_name)
                other = _resolve(t, ed.other, ed.op, place_name).id if ed.rule in ("before", "after") else None
                exclusive = ed.rule in ("first", "last")
                t.constraints.order = [o for o in t.constraints.order
                                       if o.errand != e.id and not (exclusive and o.rule == ed.rule)]
                t.constraints.order.append(OrderRule(errand=e.id, rule=ed.rule, other=other))
                word = {"first": "first", "last": "last"}.get(ed.rule, ed.rule)
                changes.append(f"{e.label}: {word}")
            elif ed.op == "deadline" and ed.time:
                t.constraints.deadline = ed.time
                changes.append(f"Leaving by {ed.time}")
            elif ed.op == "status" and ed.status in ("dropped", "done"):
                e = _resolve(t, ed.errand, ed.op, place_name)
                e.status = ed.status
                if ed.status == "dropped":
                    e.dropped_at = min_to_hhmm(now_min)
                    changes.append(f"{e.label}: dropped off at {e.dropped_at}")
                else:
                    changes.append(f"{e.label}: done")
            elif ed.op == "choose" and ed.place_hint:
                e = _resolve(t, ed.errand, ed.op, place_name)
                pid = _choose(e, ed.place_hint, place_name, place_floor)
                if not pid:
                    names = ", ".join(place_name(c) or c for c in e.candidates)
                    raise _Question(f"I couldn't match “{ed.place_hint}”. Which one: {names}?")
                e.chosen = pid
                changes.append(f"{e.label}: {place_name(pid)}")
            elif ed.op == "elevator_only" and ed.value is not None:
                t.constraints.elevator_only = ed.value
                changes.append("Elevators only" if ed.value else "Escalators allowed")
    except _Question as q:
        return trip, [], str(q)
    return t, changes, None

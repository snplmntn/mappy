"""Wait-aware trip planner.

An async errand (a repair) is two stops: drop and pick, with a ready time in between.
The planner searches stop orders and branch choices and minimizes elapsed time, so the
user's other errands naturally fill the waiting gap. Nothing about order is hardcoded.
"""

import itertools
import math
from dataclasses import dataclass

from .mall import Mall
from .models import Errand, Plan, Stop, Trip, hhmm_to_min, min_to_hhmm
from .router import Router

SHOP = {"clothing", "shoes", "accessories", "gift", "beauty", "home", "department_store",
        "books_stationery", "electronics", "appliances", "gaming"}
EATS = {"food", "cafe"}
HANDOFF_MIN = 3
IDLE_WEIGHT = 0.5
SHOP_BEFORE_EAT_PENALTY = 3
LATE_WEIGHT = 100
MAX_COMBOS = 20_000
MAX_CANDIDATES = 3


@dataclass(frozen=True)
class _Tok:
    kind: str  # visit | drop | pick
    errand: Errand


def _ready_override(e: Errand) -> float | None:
    return hhmm_to_min(e.ready_at) if e.ready_at else None


class _Planner:
    def __init__(self, trip: Trip, start: str, now: int, router: Router, mall: Mall):
        self.trip, self.start, self.now, self.router, self.mall = trip, start, now, router, mall
        self.warnings: list[str] = []
        self.ignore_order = False
        self.deadline = hhmm_to_min(trip.constraints.deadline) if trip.constraints.deadline else None
        self.errands: list[Errand] = []
        self.cands: dict[str, list[str]] = {}
        for e in trip.errands:
            if e.status == "done":
                continue
            pool = [e.chosen] if e.chosen else e.candidates
            reachable = [p for p in pool if p in mall.places
                         and router.seconds(start, mall.places[p].node) is not None]
            if not reachable:
                self.warnings.append(f"Can't reach {e.label}")
                continue
            self.errands.append(e)
            self.cands[e.id] = reachable
        self.tokens: list[_Tok] = []
        for e in self.errands:
            if e.async_ and e.status == "todo":
                self.tokens += [_Tok("drop", e), _Tok("pick", e)]
            elif e.async_:
                self.tokens.append(_Tok("pick", e))
            else:
                self.tokens.append(_Tok("visit", e))

    def _walk(self, a: str, b: str) -> float:
        return self.router.seconds(a, b) / 60

    def _valid(self, seq: tuple[_Tok, ...]) -> bool:
        first: dict[str, int] = {}
        last: dict[str, int] = {}
        for i, tok in enumerate(seq):
            eid = tok.errand.id
            if tok.kind == "pick" and tok.errand.status == "todo" and eid not in first:
                return False
            first.setdefault(eid, i)
            last[eid] = i
        for rule in [] if self.ignore_order else self.trip.constraints.order:
            if rule.errand not in first:
                continue
            if rule.rule == "first" and first[rule.errand] != 0:
                return False
            if rule.rule == "last" and last[rule.errand] != len(seq) - 1:
                return False
            if rule.other in first:
                if rule.rule == "before" and first[rule.errand] > first[rule.other]:
                    return False
                if rule.rule == "after" and first[rule.errand] < first[rule.other]:
                    return False
        return True

    def _simulate(self, seq, assign: dict[str, str]):
        t, pos, walk, idle = float(self.now), self.start, 0.0, 0.0
        ready: dict[str, float] = {}
        timeline = []
        for tok in seq:
            e = tok.errand
            node = self.mall.places[assign[e.id]].node
            w = self._walk(pos, node)
            t += w
            walk += w
            arrive = t
            if tok.kind == "pick":
                r = _ready_override(e)
                if r is None:
                    r = ready.get(e.id)
                if r is None:
                    r = hhmm_to_min(e.dropped_at) + e.duration_min if e.dropped_at else t
                if t < r:
                    idle += r - t
                    t = r
                t += HANDOFF_MIN
            elif tok.kind == "drop":
                t += HANDOFF_MIN
                ready[e.id] = _ready_override(e) or t + e.duration_min
            else:
                t += e.duration_min
            timeline.append((tok, assign[e.id], arrive, t, ready.get(e.id)))
            pos = node
        soft = 0
        for i, a in enumerate(seq):
            if a.kind == "visit" and a.errand.category in SHOP:
                soft += sum(SHOP_BEFORE_EAT_PENALTY for b in seq[i + 1:]
                            if b.kind == "visit" and b.errand.category in EATS)
        late = max(0.0, t - self.deadline) if self.deadline is not None else 0.0
        cost = (t - self.now) + IDLE_WEIGHT * idle + soft + LATE_WEIGHT * late
        return (cost, walk), t, walk, idle, timeline

    def _assignments(self, k: int) -> list[dict[str, str]]:
        ids = [e.id for e in self.errands]
        pools = [self.cands[i][:k] for i in ids]
        return [dict(zip(ids, combo)) for combo in itertools.product(*pools)]

    def _n_orders(self) -> float:
        n_split = sum(1 for e in self.errands if e.async_ and e.status == "todo")
        return math.factorial(len(self.tokens)) / (2 ** n_split)

    def _exhaustive(self, k: int):
        best = None
        orders = [s for s in itertools.permutations(self.tokens) if self._valid(s)]
        for assign in self._assignments(k):
            for seq in orders:
                result = self._simulate(seq, assign)
                if best is None or result[0] < best[0]:
                    best = result
        return best

    def _greedy(self):
        remaining = list(self.tokens)
        seq: list[_Tok] = []
        assign: dict[str, str] = {}
        while remaining:
            options = []
            for tok in remaining:
                if not self._valid_prefix(seq + [tok]):
                    continue
                places = [assign[tok.errand.id]] if tok.errand.id in assign else self.cands[tok.errand.id]
                for pid in places:
                    trial = dict(assign, **{tok.errand.id: pid})
                    options.append((self._simulate(seq + [tok], trial)[0], tok, pid))
            _, tok, pid = min(options, key=lambda o: o[0])
            seq.append(tok)
            assign[tok.errand.id] = pid
            remaining.remove(tok)
        return self._simulate(seq, assign)

    def _valid_prefix(self, seq: list[_Tok]) -> bool:
        seen = {t.errand.id for t in seq[:-1]}
        tok = seq[-1]
        return not (tok.kind == "pick" and tok.errand.status == "todo" and tok.errand.id not in seen)

    def run(self) -> Plan:
        if not self.tokens:
            return Plan(stops=[], legs=[], total_min=0, walk_min=0, idle_min=0,
                        finish_at=min_to_hhmm(self.now), warnings=self.warnings + self._deadline_warnings(self.now))
        k = MAX_CANDIDATES
        while k > 1 and self._n_orders() * len(self._assignments(k)) > MAX_COMBOS:
            k -= 1
        if self._n_orders() * len(self._assignments(k)) > MAX_COMBOS:
            best = self._greedy()
        else:
            best = self._exhaustive(k)
            if best is None:
                self.ignore_order = True
                self.warnings.append("Couldn't keep the order you asked for, so I picked the fastest one.")
                best = self._exhaustive(k)
        _, t_end, walk, idle, timeline = best
        return self._to_plan(timeline, t_end, walk, idle)

    def _deadline_warnings(self, t_end: float) -> list[str]:
        if self.deadline is None:
            return []
        dl = self.trip.constraints.deadline
        if self.now >= self.deadline:
            return [f"It's already past {dl}."]
        if t_end > self.deadline:
            visits = [e for e in self.errands if not e.async_]
            longest = max(visits, key=lambda e: e.duration_min, default=None)
            hint = f" Skip {longest.label}?" if longest else ""
            return [f"You won't make it by {dl}.{hint}"]
        return []

    def _reason(self, tok: _Tok, index: int, ready_at: float | None, pending: set[str], ate: bool) -> str:
        e = tok.errand
        src = " (you said)" if e.duration_source == "user" else ""
        if tok.kind == "drop":
            if index == 0:
                return f"Drop off first — {e.label} takes {e.duration_min} min{src}"
            return f"Drop off — ready by {min_to_hhmm(ready_at)} ({e.duration_min} min{src})"
        if tok.kind == "pick":
            r = _ready_override(e) or ready_at
            if r is None and e.dropped_at:
                r = hhmm_to_min(e.dropped_at) + e.duration_min
            return f"Pick up — ready by {min_to_hhmm(r)}" if r is not None else "Pick up"
        if pending:
            return {"food": "Eat while waiting", "cafe": "Coffee while waiting"}.get(e.category, f"{e.label} while waiting")
        if ate and e.category in SHOP:
            return "Shop after eating"
        return e.label

    def _to_plan(self, timeline, t_end: float, walk: float, idle: float) -> Plan:
        stops: list[Stop] = []
        legs = []
        pending = {e.id for e in self.errands if e.async_ and e.status == "dropped"}
        ate = False
        prev = self.start
        for i, (tok, pid, arrive, leave, ready_at) in enumerate(timeline):
            reason = self._reason(tok, i, ready_at, pending, ate)
            if tok.kind == "drop":
                pending.add(tok.errand.id)
            elif tok.kind == "pick":
                pending.discard(tok.errand.id)
            elif tok.errand.category in EATS:
                ate = True
            stops.append(Stop(kind=tok.kind, errand=tok.errand.id, place=pid,
                              arrive_min=round(arrive), leave_min=round(leave),
                              arrive=min_to_hhmm(arrive), leave=min_to_hhmm(leave), reason=reason))
            node = self.mall.places[pid].node
            path = self.router.path(prev, node)
            if path and len(path) > 1:
                legs += self.router.legs(path, i, self.mall.places[pid].name)
            prev = node
        return Plan(stops=stops, legs=legs, total_min=stops[-1].leave_min - self.now,
                    walk_min=round(walk), idle_min=round(idle), finish_at=min_to_hhmm(t_end),
                    warnings=self.warnings + self._deadline_warnings(t_end))


def plan_trip(trip: Trip, start_node: str, now_min: int, router: Router, mall: Mall) -> Plan:
    return _Planner(trip, start_node, now_min, router, mall).run()

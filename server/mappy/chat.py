"""Chat orchestration: rules first, then the local LLM, then a deterministic fallback.
Every path ends in deterministic code (search, trip edits, planner, locator)."""

import asyncio
import math
from dataclasses import dataclass
from typing import Protocol

import httpx

from .brands import brand_in
from .llm import LLMBusy, LLMError, fallback_extract, trip_summary
from .locator import locate
from .mall import Mall
from .models import Edit, Errand, ErrandReq, Extraction, Trip, hhmm_to_min
from .planner import plan_trip
from .router import Router
from .rules import parse
from .search import CATEGORY_LABELS, Search
from .trip import apply_edits, new_errand_id

MAX_ERRANDS = 5
CANDIDATES = 3
FIND_RESULTS = 5
MAX_REPLY_TRAITS = 2  # traits named in the "also do ..." sentence
MAX_REPLY_NAMES = 2   # stores named in it
SCORE_BAND = 0.06
LLM_TIMEOUT_S = 8.5
# Minimum fused search score that counts as "found", per embedder (calibrated on the eval set).
MIN_SCORE = {"hash-256": 0.35, "multilingual-e5-small": 0.60}
HELP = "Tell me what you need to do. For example: “fix my phone, eat, then buy a gift”."
TRY_INSTEAD = "Try a store name, or a type like “food”, “ATM” or “phone repair”."
NOTHING_CHANGED = "I didn't catch what to change. Try “30 mins lang” or “skip food”."


class Extractor(Protocol):
    async def extract(self, message: str, trip: Trip, summary: str = "") -> Extraction: ...


def _text(reply: str, trip: Trip) -> dict:
    return {"reply": reply, "result": {"type": "text"}, "trip": trip.model_dump(by_alias=True)}


@dataclass(frozen=True)
class StandIn:
    """Same-kind places listed in place of a store this mall doesn't have."""
    name: str                       # what the shopper asked for, as shown: "McDonald's"
    category: str
    traits: tuple[str, ...] = ()
    swapped: bool = False           # a known brand (so plans say so), not just the LLM's category guess


def _not_found(queries: list[str]) -> str:
    return f"I couldn't find “{', '.join(queries)}” in this mall. {TRY_INSTEAD}"


def _dead_end(x: Extraction, out: dict) -> bool:
    """A search, plan or locate that ended in plain text found nothing."""
    return x.intent in ("find", "plan", "locate") and out["result"]["type"] == "text"


def _label(category: str) -> str:
    """A category as it reads mid-sentence: "food", "coffee", "clothes"."""
    return CATEGORY_LABELS.get(category, category).lower()


def _help(trip: Trip) -> str:
    """When a message isn't understood, suggest the next useful thing for where the user is."""
    active = [e for e in trip.errands if e.status != "done"]
    if not active:
        return HELP
    label = active[0].label.lower()
    return f"I didn't catch that. To change your plan, try “30 mins lang”, “{label} muna” or “skip {label}”."


@dataclass
class ChatService:
    mall: Mall
    search: Search
    router: Router
    router_elev: Router
    llm: Extractor | None

    def _router(self, trip: Trip) -> Router:
        return self.router_elev if trip.constraints.elevator_only else self.router

    def _name(self, pid: str) -> str | None:
        p = self.mall.places.get(pid)
        return p.name if p else None

    def _floor(self, pid: str) -> str | None:
        p = self.mall.places.get(pid)
        return p.floor if p else None

    def start_node(self, at: dict | None) -> str:
        if at:
            if (a := at.get("anchor")) in self.mall.anchors:
                return self.mall.anchors[a].node
            if (n := at.get("node")) in self.mall.nodes:
                return n
        return next(iter(self.mall.anchors.values())).node

    def _min_score(self) -> float:
        return MIN_SCORE.get(self.search.embedder.model_id, 0.5)

    def _matches(self, query: str, category: str | None) -> list[str]:
        if category and self.search.by_category(category):
            hits = [pid for pid, _ in self.search.search(query, category, k=len(self.mall.places))
                    if self.mall.places[pid].category == category]
            return hits[:CANDIDATES]
        hits = self.search.search(query, k=8)
        if not hits or hits[0][1] < self._min_score():
            return []
        top_cat = self.mall.places[hits[0][0]].category
        return [pid for pid, s in hits
                if s >= hits[0][1] - SCORE_BAND and self.mall.places[pid].category == top_cat][:CANDIDATES]

    def _find_category(self, req: ErrandReq) -> str | None:
        """The category to list for a search. The LLM's guess only counts when search agrees with it,
        so "sinehan" in a mall without a cinema isn't answered with gift shops."""
        if cat := self.search.alias_category(req.query):
            return cat
        hits = self._matches(req.query, None) if req.category else []
        return req.category if hits and self.mall.places[hits[0]].category == req.category else None

    def _errand(self, new_id: str, query: str, ids: list[str]) -> Errand:
        first = self.mall.places[ids[0]]
        duration, is_async = self.mall.service_for(first.id)
        return Errand(id=new_id, label=CATEGORY_LABELS.get(first.category) or query.capitalize(), query=query,
                      category=first.category, candidates=ids, duration_min=duration,
                      duration_source="store" if first.service else "default", **{"async": is_async})

    def _resolve(self, query: str, category: str | None) -> tuple[list[str], StandIn | None]:
        """Places for a store request: a known brand that is here, then same-kind stand-ins for a known
        brand that isn't (before search, so "coffee bean" isn't quietly answered by a "coffee" tag),
        then a search hit, then the LLM's category guess."""
        brand = brand_in(query)
        if brand and (named := self.search.place_ids_named(brand.name)):
            return named, None
        if brand and self.search.by_category(brand.category):
            return (self.search.alternatives(brand.category, brand.traits),
                    StandIn(brand.name, brand.category, brand.traits, swapped=True))
        if hits := self._matches(query, None):
            return hits, None
        if category and self.search.by_category(category):
            return self._matches(query, category), StandIn(query, category)
        return [], None

    def _errand_or_alternative(self, query: str, category: str | None,
                               new_id: str) -> tuple[Errand | None, StandIn | None]:
        """The errand for a request, and what it stands in for when a missing brand was swapped."""
        if cat := self.search.alias_category(query):  # a category word in the user's own text beats the LLM's guess
            ids, stand_in = self._matches(query, cat), None
        else:
            ids, stand_in = self._resolve(query, category)
        if not ids:
            return None, None
        return self._errand(new_id, query, ids[:CANDIDATES]), stand_in if stand_in and stand_in.swapped else None

    def make_errand(self, query: str, category: str | None, new_id: str) -> Errand | None:
        return self._errand_or_alternative(query, category, new_id)[0]

    async def _ask_llm(self, message: str, trip: Trip) -> Extraction | None:
        if self.llm is None:
            return None
        try:
            summary = trip_summary(trip, self._name)
            return await asyncio.wait_for(self.llm.extract(message, trip, summary), LLM_TIMEOUT_S)
        except (LLMBusy, LLMError, asyncio.TimeoutError, httpx.HTTPError):
            return None

    async def _extract(self, message: str, trip: Trip) -> Extraction:
        x = parse(message, trip, self.search)
        if x is not None:
            return x
        return await self._ask_llm(message, trip) or fallback_extract(message, trip)

    def _walk_min(self, start: str, pid: str, router: Router) -> int | None:
        s = router.seconds(start, self.mall.places[pid].node)
        return None if s is None else max(1, math.ceil(s / 60))

    def _places_result(self, query: str, ids: list[str], start: str, router: Router,
                       scores: dict[str, int] | None = None) -> dict:
        """Tappable rows, nearest first, or best `scores` first then nearest."""
        scores = scores or {}
        rows = []
        for pid in ids:
            p = self.mall.places[pid]
            rows.append({"id": pid, "name": p.name, "floor": p.floor, "floor_name": self.mall.floors[p.floor].name,
                         "category": p.category, "fictional": p.fictional,
                         "walk_min": self._walk_min(start, pid, router)})
        rows.sort(key=lambda r: (-scores.get(r["id"], 0), r["walk_min"] is None, r["walk_min"] or 0))
        return {"type": "places", "query": query, "places": rows[:FIND_RESULTS]}

    def _alternatives_result(self, alt: StandIn, start: str, router: Router, exclude: tuple[str, ...] = ()) -> dict:
        ids = self.search.alternatives(alt.category, alt.traits, exclude)
        scores = {pid: self.search.trait_score(pid, alt.traits) for pid in ids}
        result = self._places_result(alt.name, ids, start, router, scores)
        return {**result, "category": alt.category, "alternatives_for": alt.name}

    def _alternatives_reply(self, alt: StandIn, rows: list[dict]) -> str:
        reply = f"No {alt.name} in this mall, but here are other {_label(alt.category)} places."
        matched = [(r, m) for r in rows if (m := self.search.matched_traits(r["id"], alt.traits))]
        if matched:
            shown = matched[:MAX_REPLY_NAMES]
            verb = "does" if len(shown) == 1 else "do"
            names = " and ".join(r["name"] for r, _ in shown)
            reply += f" {names} also {verb} {' and '.join(matched[0][1][:MAX_REPLY_TRAITS])}."
        if rows and rows[0]["walk_min"] is not None:
            reply += f" {rows[0]['name']} is {rows[0]['walk_min']} min away."
        return reply

    def _plan_payload(self, trip: Trip, start: str, now_min: int, changes: list[str]) -> dict:
        plan = plan_trip(trip, start, now_min, self._router(trip), self.mall)
        return {"type": "plan", "plan": plan.model_dump(), "changes": changes}

    async def chat(self, message: str, at: dict | None, now: str, trip: Trip) -> dict:
        x = await self._extract(message, trip)
        out = self._respond(x, at, now, trip)
        if x.source == "rules" and _dead_end(x, out):
            # The rules were sure but found nothing, so let the LLM read it before giving up.
            # Keep the rules' plain "couldn't find" unless the LLM gets somewhere.
            if (retry := await self._ask_llm(message, trip)) is not None:
                retry_out = self._respond(retry, at, now, trip)
                if not _dead_end(retry, retry_out):
                    x, out = retry, retry_out
        out["meta"] = {"engine": x.source, "intent": x.intent}  # which engine understood it, for the receipt line
        return out

    def _respond(self, x: Extraction, at: dict | None, now: str, trip: Trip) -> dict:
        now_min = hhmm_to_min(now)
        start = self.start_node(at)
        router = self._router(trip)

        if x.intent == "find" and x.errands:
            req = x.errands[0]
            if (cat := self._find_category(req)) and self.search.by_category(cat):
                ids, alt = self.search.by_category(cat), None
            else:
                ids, alt = self._resolve(req.query, req.category)
            if alt:
                result = self._alternatives_result(alt, start, router)
                return {"reply": self._alternatives_reply(alt, result["places"]), "result": result,
                        "trip": trip.model_dump(by_alias=True)}
            if not ids:
                return _text(_not_found([req.query]), trip)
            result = self._places_result(req.query, ids, start, router)
            return {"reply": f"Here's what I found for “{req.query}”:", "result": result,
                    "trip": trip.model_dump(by_alias=True)}

        if x.intent == "plan" and x.errands:
            t = trip.model_copy(deep=True)
            capped = len(x.errands) > MAX_ERRANDS
            missing, swapped, added = [], {}, 0
            for req in x.errands[:MAX_ERRANDS]:
                made, stand_in = self._errand_or_alternative(req.query, req.category, new_errand_id(t))
                if made is None:
                    missing.append(req.query)
                    continue
                t.errands.append(made)
                added += 1
                if stand_in:
                    swapped[stand_in.name] = stand_in.category  # one sentence per missing brand
            if not added:
                return _text(_not_found(missing), trip)
            payload = self._plan_payload(t, start, now_min, [])
            reply = f"Here's your plan: {len(payload['plan']['stops'])} stops, done by {payload['plan']['finish_at']}."
            for name, cat in swapped.items():
                reply += f" No {name} here, so I added other {_label(cat)} places instead."
            if missing:
                reply += f" I couldn't find: {', '.join(missing)}."
            if capped:
                reply += f" I planned the first {MAX_ERRANDS}; add the rest after."
            return {"reply": reply, "result": payload, "trip": t.model_dump(by_alias=True)}

        if x.intent == "edit" and x.edits:
            t, changes, question = apply_edits(trip, x.edits, now_min, self.make_errand, self._name, self._floor)
            if question:
                return _text(question, trip)
            if not changes:
                return _text(NOTHING_CHANGED, trip)
            payload = self._plan_payload(t, start, now_min, changes)
            return {"reply": "Updated your plan.", "result": payload, "trip": t.model_dump(by_alias=True)}

        if x.intent == "locate" and x.landmarks:
            cands, ask = locate(self.mall, self.search, x.landmarks, x.floor)
            if not cands:
                return _text("I couldn't place you. Which store is closest to you?", trip)
            reply = {None: "Is this where you are? Tap the right spot.", "floor": "Which floor are you on?",
                     "more_landmarks": "Can you name another store you can see?"}[ask]
            return {"reply": reply, "result": {"type": "locate", "candidates": [c.model_dump() for c in cands],
                                               "ask": ask}, "trip": trip.model_dump(by_alias=True)}

        return _text(_help(trip), trip)

    def plan(self, at: dict | None, now: str, trip: Trip, edits: list[Edit]) -> dict:
        now_min = hhmm_to_min(now)
        changes: list[str] = []
        if edits:
            trip, changes, question = apply_edits(trip, edits, now_min, self.make_errand, self._name, self._floor)
            if question:
                return {"plan": None, "trip": trip.model_dump(by_alias=True), "changes": [], "question": question}
        plan = plan_trip(trip, self.start_node(at), now_min, self._router(trip), self.mall)
        return {"plan": plan.model_dump(), "trip": trip.model_dump(by_alias=True), "changes": changes}

    def route(self, at: dict | None, to: dict, elevator_only: bool) -> dict:
        router = self.router_elev if elevator_only else self.router
        start = self.start_node(at)
        if (pid := to.get("place")) in self.mall.places:
            dest, label = self.mall.places[pid].node, self.mall.places[pid].name
        else:
            dest, label = to.get("node"), "meet-up point"
        path = router.path(start, dest) if dest in self.mall.nodes else None
        if path is None:
            # Say why, so the app can tell "elevators only blocks this" apart from "no way there at all".
            blocked = elevator_only and dest in self.mall.nodes and self.router.path(start, dest) is not None
            return {"legs": [], "walk_min": None, "reason": "elevator_only" if blocked else "no_route"}
        legs = router.legs(path, 0, label) if len(path) > 1 else []
        return {"legs": [leg.model_dump() for leg in legs],
                "walk_min": max(1, math.ceil(router.seconds(start, dest) / 60))}

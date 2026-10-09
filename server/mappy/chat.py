"""Chat orchestration: rules first, then the local LLM, then a deterministic fallback.
Every path ends in deterministic code (search, trip edits, planner, locator)."""

import asyncio
import math
from dataclasses import dataclass
from typing import Protocol

import httpx

from .llm import LLMBusy, LLMError, fallback_extract, trip_summary
from .locator import locate
from .mall import Mall
from .models import Edit, Errand, Extraction, Trip, hhmm_to_min
from .planner import plan_trip
from .router import Router
from .rules import parse
from .search import CATEGORY_LABELS, Search
from .trip import apply_edits, new_errand_id

MAX_ERRANDS = 5
CANDIDATES = 3
SCORE_BAND = 0.06
LLM_TIMEOUT_S = 8.5
# Minimum fused search score that counts as "found", per embedder (calibrated on the eval set).
MIN_SCORE = {"hash-256": 0.35, "multilingual-e5-small": 0.60}
HELP = "Sabihin mo lang ang kailangan mo — hal. “papaayos ng phone, tapos kain”."


class Extractor(Protocol):
    async def extract(self, message: str, trip: Trip, summary: str = "") -> Extraction: ...


def _text(reply: str, trip: Trip) -> dict:
    return {"reply": reply, "result": {"type": "text"}, "trip": trip.model_dump(by_alias=True)}


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

    def make_errand(self, query: str, category: str | None, new_id: str) -> Errand | None:
        ids = self._matches(query, category)
        if not ids:
            return None
        first = self.mall.places[ids[0]]
        duration, is_async = self.mall.service_for(first.id)
        return Errand(id=new_id, label=CATEGORY_LABELS.get(first.category) or query.capitalize(), query=query,
                      category=first.category, candidates=ids, duration_min=duration,
                      duration_source="store" if first.service else "default", **{"async": is_async})

    async def _extract(self, message: str, trip: Trip) -> Extraction:
        x = parse(message, trip, self.search)
        if x is not None:
            return x
        if self.llm is not None:
            try:
                summary = trip_summary(trip, self._name)
                return await asyncio.wait_for(self.llm.extract(message, trip, summary), LLM_TIMEOUT_S)
            except (LLMBusy, LLMError, asyncio.TimeoutError, httpx.HTTPError):
                pass
        return fallback_extract(message, trip)

    def _walk_min(self, start: str, pid: str, router: Router) -> int | None:
        s = router.seconds(start, self.mall.places[pid].node)
        return None if s is None else max(1, math.ceil(s / 60))

    def _places_result(self, query: str, ids: list[str], start: str, router: Router) -> dict:
        rows = []
        for pid in ids:
            p = self.mall.places[pid]
            rows.append({"id": pid, "name": p.name, "floor": p.floor, "floor_name": self.mall.floors[p.floor].name,
                         "category": p.category, "fictional": p.fictional,
                         "walk_min": self._walk_min(start, pid, router)})
        rows.sort(key=lambda r: (r["walk_min"] is None, r["walk_min"] or 0))
        return {"type": "places", "query": query, "places": rows}

    def _plan_payload(self, trip: Trip, start: str, now_min: int, changes: list[str]) -> dict:
        plan = plan_trip(trip, start, now_min, self._router(trip), self.mall)
        return {"type": "plan", "plan": plan.model_dump(), "changes": changes}

    async def chat(self, message: str, at: dict | None, now: str, trip: Trip) -> dict:
        now_min = hhmm_to_min(now)
        start = self.start_node(at)
        router = self._router(trip)
        x = await self._extract(message, trip)

        if x.intent == "find" and x.errands:
            req = x.errands[0]
            cat = req.category or self.search.alias_category(req.query)
            ids = self.search.by_category(cat) if cat and self.search.by_category(cat) else self._matches(req.query, None)
            if not ids:
                return _text(f"Pasensya, wala akong nahanap para sa “{req.query}”.", trip)
            result = self._places_result(req.query, ids[:5], start, router)
            return {"reply": f"Eto ang mga pwede para sa “{req.query}”:", "result": result,
                    "trip": trip.model_dump(by_alias=True)}

        if x.intent == "plan" and x.errands:
            t = trip.model_copy(deep=True)
            capped = len(x.errands) > MAX_ERRANDS
            missing, added = [], 0
            for req in x.errands[:MAX_ERRANDS]:
                made = self.make_errand(req.query, req.category, new_errand_id(t))
                if made is None:
                    missing.append(req.query)
                else:
                    t.errands.append(made)
                    added += 1
            if not added:
                return _text(f"Pasensya, wala akong nahanap para sa “{', '.join(missing)}”.", trip)
            payload = self._plan_payload(t, start, now_min, [])
            reply = f"Ayos! {len(payload['plan']['stops'])} stops, tapos ka by {payload['plan']['finish_at']}."
            if missing:
                reply += f" Hindi ko nahanap: {', '.join(missing)}."
            if capped:
                reply += f" Hanggang {MAX_ERRANDS} lang muna."
            return {"reply": reply, "result": payload, "trip": t.model_dump(by_alias=True)}

        if x.intent == "edit" and x.edits:
            t, changes, question = apply_edits(trip, x.edits, now_min, self.make_errand, self._name, self._floor)
            if question:
                return _text(question, trip)
            payload = self._plan_payload(t, start, now_min, changes)
            return {"reply": "Updated! " + "; ".join(changes), "result": payload, "trip": t.model_dump(by_alias=True)}

        if x.intent == "locate" and x.landmarks:
            cands, ask = locate(self.mall, self.search, x.landmarks, x.floor)
            if not cands:
                return _text("Hindi kita mahanap. Anong store ang pinakamalapit sa'yo?", trip)
            reply = {None: "Ito ba ang lugar? Pindutin ang tamang pin.", "floor": "Anong floor?",
                     "more_landmarks": "May iba pang nakikitang store?"}[ask]
            return {"reply": reply, "result": {"type": "locate", "candidates": [c.model_dump() for c in cands],
                                               "ask": ask}, "trip": trip.model_dump(by_alias=True)}

        return _text(HELP, trip)

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
            return {"legs": [], "walk_min": None}
        legs = router.legs(path, 0, label) if len(path) > 1 else []
        return {"legs": [leg.model_dump() for leg in legs],
                "walk_min": max(1, math.ceil(router.seconds(start, dest) / 60))}

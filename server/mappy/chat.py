"""Chat orchestration: rules first, then the local LLM, then a deterministic fallback.
Every path ends in deterministic code (search, trip edits, planner, locator)."""

import asyncio
import math
from functools import partial
from dataclasses import dataclass, field
from typing import NamedTuple, Protocol

import httpx
from rapidfuzz import fuzz

from .brands import brand_in, is_store_of, trait_phrase, traits_of
from .learn import Picks
from .llm import LLMBusy, LLMError, fallback_extract, trip_summary
from .locator import locate
from .mall import Mall
from .models import Edit, Errand, ErrandReq, Extraction, Trip, hhmm_to_min
from .planner import plan_trip
from .router import Router
from .rules import FRIEND_RE, NEAREST_RE, PLAN_SEPARATORS, parse
from .search import ANY_WILL_DO, CATEGORY_LABELS, Search, categories_in, places_label
from .trip import MAX_ERRANDS, apply_edits, duplicate_of, new_errand_id

CANDIDATES = 3
FIND_RESULTS = 5
MAX_REPLY_TRAITS = 2  # traits named in the "also do ..." sentence
MAX_REPLY_NAMES = 2   # stores named in it
SCORE_BAND = 0.06
NUDGE_MIN = 2  # minutes closer before we mention another store of the same kind
LLM_TIMEOUT_S = 8.5
# Minimum fused search score that counts as "found", per embedder (calibrated on the eval set).
MIN_SCORE = {"hash-256": 0.35, "multilingual-e5-small": 0.60}
HELP = "Tell me what you need to do. For example: “fix my phone, eat, then buy a gift”."
TRY_INSTEAD = "Try a store name, or a type like “food”, “ATM” or “phone repair”."
NOTHING_CHANGED = "I didn't catch what to change. Try “30 mins lang” or “skip food”."
WHERE_AM_I = "Scan the location code nearest you, or tell me a store you can see, like “nasa tabi ako ng Starbucks”."
LANDMARK_MIN = 80  # how closely an LLM landmark must appear in the message, so it can't invent one


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


class Nudge(NamedTuple):
    """A nearer same-kind store than the one the shopper named, and the sentence pointing to it."""
    row: dict
    sentence: str


def _not_found(queries: list[str]) -> str:
    return f"I couldn't find “{', '.join(queries)}” in this mall. {TRY_INSTEAD}"


def _dead_end(x: Extraction, out: dict) -> bool:
    """A search, plan or locate that ended in plain text found nothing ("where am I" has nothing to find)."""
    asked = x.intent in ("find", "plan") or (x.intent == "locate" and bool(x.landmarks))
    return asked and out["result"]["type"] == "text"


FRIEND_ASKS = {None: "Is this where your friend is? Tap the right spot.", "floor": "Which floor is your friend on?",
               "more_landmarks": "Can you name another store your friend can see?"}


def _for_friend(out: dict) -> dict:
    """A spot someone else described is a place to walk to, not where the shopper is."""
    result = out["result"]
    if result["type"] != "locate":
        return out
    return {**out, "reply": FRIEND_ASKS[result["ask"]], "result": {**result, "friend": True}}


def _stops(n: int) -> str:
    return f"{n} stop" if n == 1 else f"{n} stops"


def _clauses(message: str) -> int:
    """How many parts a message lists ("ayos phone, tapos kain" is two)."""
    return sum(1 for c in PLAN_SEPARATORS.split(message) if c.strip(" .!?"))


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
    picks: Picks = field(default_factory=lambda: Picks(None))  # what shoppers tapped for a missing brand

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

    def _matches(self, query: str) -> list[str]:
        hits = self.search.search(query, k=8)
        if not hits or hits[0][1] < self._min_score():
            return []
        top_cat = self.mall.places[hits[0][0]].category
        return [pid for pid, s in hits
                if s >= hits[0][1] - SCORE_BAND and self.mall.places[pid].category == top_cat][:CANDIDATES]

    def _own_category(self, query: str) -> str | None:
        """A category word in the user's own text, unless the text names a known brand ("coffee bean"
        is Coffee Bean & Tea Leaf, not just coffee)."""
        return None if brand_in(query) else self.search.alias_category(query)

    def _find_category(self, req: ErrandReq) -> str | None:
        """The category to list for a search. The LLM's guess only counts when search agrees with it,
        so "sinehan" in a mall without a cinema isn't answered with gift shops."""
        if cat := self._own_category(req.query):
            return cat
        if not req.category or brand_in(req.query):  # a known brand resolves by name or swaps, see _resolve
            return None
        hits = self._matches(req.query)
        return req.category if hits and self.mall.places[hits[0]].category == req.category else None

    def _errand(self, new_id: str, query: str, ids: list[str]) -> Errand:
        first = self.mall.places[ids[0]]
        duration, is_async = self.mall.service_for(first.id)
        return Errand(id=new_id, label=CATEGORY_LABELS.get(first.category) or query.capitalize(), query=query,
                      category=first.category, candidates=ids, duration_min=duration,
                      duration_source="store" if first.service else "default", **{"async": is_async})

    def _word_scores(self, query: str, category: str) -> dict[str, int]:
        """How many of the request's own words beyond its category each place of it matches."""
        words = self.search.specific_words(query, category)
        return {pid: self.search.word_score(pid, words) for pid in self.search.by_category(category)}

    def _nearest(self, query: str, category: str, start: str, router: Router) -> list[str]:
        """A category's places for a request: those matching more of its own words first ("korean" in
        "korean food"), then the shortest walk from where the shopper is."""
        scores = self._word_scores(query, category)
        walks = {pid: self._walk_min(start, pid, router) for pid in scores}
        return sorted(scores, key=lambda pid: (-scores[pid], walks[pid] is None, walks[pid] or 0))

    def _resolve(self, query: str, category: str | None, start: str,
                 router: Router) -> tuple[list[str], StandIn | None]:
        """Places for a store request: a known brand that is here, then same-kind stand-ins for a known
        brand that isn't (before search, so "coffee bean" isn't quietly answered by a "coffee" tag),
        then a search hit, then the LLM's category guess."""
        brand = brand_in(query)
        if brand and (stores := [pid for pid in self.search.ids
                                 if is_store_of(brand, self.mall.places[pid].name, self.mall.places[pid].tags)]):
            named = set(self.search.names_in(query))  # "BDO ATM" is the ATMs, not the BDO branch
            return [pid for pid in stores if self.mall.places[pid].name in named] or stores, None
        if brand and self.search.by_category(brand.category):
            return (self.search.alternatives(brand.category, brand.traits),
                    StandIn(brand.name, brand.category, brand.traits, swapped=True))
        if hits := self._matches(query):
            return hits, None
        if category and self.search.by_category(category):
            return self._nearest(query, category, start, router), StandIn(query, category)
        return [], None

    def _errand_or_alternative(self, query: str, category: str | None, new_id: str, start: str,
                               router: Router) -> tuple[Errand | None, StandIn | None]:
        """The errand for a request, and what it stands in for when it isn't here: a missing brand, or a
        thing the shopper named that only the LLM's category guess matched ("dentist" -> pharmacies)."""
        if cat := self._own_category(query):  # a category word in the user's own text beats the LLM's guess
            ids, stand_in = self._nearest(query, cat, start, router), None
        else:
            ids, stand_in = self._resolve(query, category, start, router)
        if not ids:
            return None, None
        said = stand_in and (stand_in.swapped or stand_in.category not in categories_in(query))
        return self._errand(new_id, query, ids[:CANDIDATES]), stand_in if said else None

    def make_errand(self, query: str, category: str | None, new_id: str, start: str,
                    router: Router) -> Errand | None:
        return self._errand_or_alternative(query, category, new_id, start, router)[0]

    def _apply(self, trip: Trip, edits: list[Edit], now_min: int, start: str) -> tuple[Trip, list[str], str | None]:
        """Apply edits; something just dropped off is picked up from the shop the plan dropped it at."""
        make = partial(self.make_errand, start=start, router=self._router(trip))
        t, changes, question = apply_edits(trip, edits, now_min, make, self._name, self._floor)
        was_todo = {e.id for e in trip.errands if e.status == "todo"}
        dropped = [e for e in t.errands if e.status == "dropped" and not e.chosen and e.id in was_todo]
        if dropped and not question:
            plan = plan_trip(trip, start, now_min, self._router(trip), self.mall)
            drops = {st.errand: st.place for st in plan.stops if st.kind == "drop"}
            for e in dropped:
                e.chosen = drops.get(e.id)
        return t, changes, question

    async def _ask_llm(self, message: str, trip: Trip) -> Extraction | None:
        if self.llm is None:
            return None
        try:
            summary = trip_summary(trip, self._name)
            x = await asyncio.wait_for(self.llm.extract(message, trip, summary), LLM_TIMEOUT_S)
        except (LLMBusy, LLMError, asyncio.TimeoutError, httpx.HTTPError):
            return None
        return self._grounded(message, x)

    @staticmethod
    def _grounded(message: str, x: Extraction) -> Extraction:
        """Keep the LLM to what the message says: a one-part message is one search, not a plan of
        made-up errands, and a landmark must be one the shopper actually named."""
        if x.intent == "plan" and x.errands and _clauses(message) < 2:
            return x.model_copy(update={"intent": "find", "errands": x.errands[:1]})
        if x.intent == "locate":
            m = message.lower()
            named = [lm for lm in x.landmarks if fuzz.partial_ratio(lm.lower(), m) >= LANDMARK_MIN]
            return x.model_copy(update={"landmarks": named})
        return x

    async def _extract(self, message: str, trip: Trip) -> Extraction:
        x = parse(message, trip, self.search)
        if x is not None:
            return x
        return await self._ask_llm(message, trip) or fallback_extract(message, trip)

    def _walk_min(self, start: str, pid: str, router: Router) -> int | None:
        s = router.seconds(start, self.mall.places[pid].node)
        return None if s is None else max(1, math.ceil(s / 60))

    def _row(self, pid: str, start: str, router: Router) -> dict:
        """One tappable place row as the phone renders it."""
        p = self.mall.places[pid]
        return {"id": pid, "name": p.name, "floor": p.floor, "floor_name": self.mall.floors[p.floor].name,
                "category": p.category, "fictional": p.fictional, "walk_min": self._walk_min(start, pid, router)}

    def _places_result(self, query: str, ids: list[str], start: str, router: Router,
                       scores: dict[str, int] | None = None, category: str | None = None,
                       shown: tuple[str, ...] = ()) -> dict:
        """Tappable rows, nearest first, or best `scores` first then nearest. `category` is what the list
        is of (the top place's when not given) and `shown` every id listed so far in this paging chain
        (earlier pages, then this one), so "iba pa" can page through the rest of it."""
        scores = scores or {}
        rows = [self._row(pid, start, router) for pid in ids]
        rows.sort(key=lambda r: (-scores.get(r["id"], 0), r["walk_min"] is None, r["walk_min"] or 0))
        rows = rows[:FIND_RESULTS]
        category = category or (rows[0]["category"] if rows else None)
        return {"type": "places", "query": query, "category": category, "places": rows,
                "shown": [*shown, *(r["id"] for r in rows)]}

    def _ranked(self, category: str, traits: tuple[str, ...],
                exclude: tuple[str, ...] = ()) -> tuple[list[str], dict[str, int]]:
        """A category's places ranked by these traits, and each one's trait score."""
        ids = self.search.alternatives(category, traits, exclude)
        return ids, {pid: self.search.trait_score(pid, traits) for pid in ids}

    def _alternatives_result(self, alt: StandIn, start: str, router: Router) -> dict:
        """Same-kind places for a missing store: what shoppers here picked instead first (most picked
        first), then the rest by trait match."""
        ids, scores = self._ranked(alt.category, alt.traits)
        learned = [pid for pid in self.picks.ranked(alt.name) if pid in ids]
        lead = max(scores.values(), default=0) + len(learned)
        scores |= {pid: lead - i for i, pid in enumerate(learned)}
        result = self._places_result(alt.name, ids, start, router, scores, alt.category)
        return {**result, "alternatives_for": alt.name}

    def _more(self, prev: dict | None, start: str, router: Router, trip: Trip) -> dict:
        """The rest of the last list's category, minus what the phone already showed. A swap's list keeps
        its trait ranking. `prev` comes from the phone, so anything malformed reads as no list at all."""
        prev = prev if isinstance(prev, dict) else {}
        places, category = prev.get("places"), prev.get("category")
        if not isinstance(places, list) or not isinstance(category, str) or not self.search.by_category(category):
            return _text("Ask for a store or a type first, then say “more”.", trip)
        shown = prev.get("shown")
        if not isinstance(shown, list):  # an older result without the chain: just its own page
            shown = [p.get("id") for p in places if isinstance(p, dict)]
        shown = tuple(pid for pid in shown if isinstance(pid, str))
        swapped = prev.get("alternatives_for")
        brand = brand_in(swapped) if isinstance(swapped, str) else None
        ids, scores = self._ranked(category, brand.traits if brand else (), shown)
        if not ids:
            return _text(f"Those are all the {places_label(category)} in this mall.", trip)
        result = self._places_result(str(prev.get("query") or ""), ids, start, router, scores, category, shown)
        if isinstance(swapped, str) and swapped:
            result["alternatives_for"] = swapped  # so later "more" keeps the trait ranking
        return {"reply": f"More {places_label(category)}:", "result": result, "trip": trip.model_dump(by_alias=True)}

    def _alternatives_reply(self, alt: StandIn, rows: list[dict]) -> str:
        reply = f"No {alt.name} in this mall, but here are other {places_label(alt.category)}."
        if (top := self.picks.top(alt.name)) and (row := next((r for r in rows if r["id"] == top), None)):
            reply = f"Shoppers here usually pick {row['name']} instead of {alt.name}. {reply}"
        matched = [(r, m) for r in rows if (m := self.search.matched_traits(r["id"], alt.traits))]
        if matched:
            # The first match sets which traits are named; another store is named only if it has them all.
            (lead, traits), *rest = matched
            traits = traits[:MAX_REPLY_TRAITS]
            names = [lead["name"], *(r["name"] for r, m in rest if set(traits) <= set(m))][:MAX_REPLY_NAMES]
            verb = "does" if len(names) == 1 else "do"
            reply += f" {' and '.join(names)} also {verb} {' and '.join(trait_phrase(t) for t in traits)}."
        if rows and rows[0]["walk_min"] is not None:
            reply += f" {rows[0]['name']} is {rows[0]['walk_min']} min away."
        return reply

    def _nudge(self, query: str, rows: list[dict], start: str, router: Router,
               exclude: tuple[str, ...]) -> Nudge | None:
        """A same-kind store at least NUDGE_MIN minutes nearer than the store the shopper named (best
        trait match first). Only for a store named outright: "ramen" isn't asking for Kyu Kyu Ramen."""
        top = rows[0]
        if top["walk_min"] is None or top["name"] not in self.search.names_in(query):
            return None
        traits = traits_of(top["name"]) or self.search.distinctive_tags(top["id"])
        pid = next((pid for pid in self.search.alternatives(top["category"], traits, exclude)
                    if (w := self._walk_min(start, pid, router)) is not None and w <= top["walk_min"] - NUDGE_MIN),
                   None)
        if pid is None:
            return None
        near = self._row(pid, start, router)
        kind = next((trait_phrase(t) for t in self.search.matched_traits(pid, traits)), _label(near["category"]))
        return Nudge(near, f"{top['name']} is {top['walk_min']} min away on {top['floor_name']}. "
                           f"{near['name']} on {near['floor_name']} does {kind} too, {near['walk_min']} min.")

    def _go(self, message: str, out: dict) -> dict:
        """Head straight to the top place when it is the obvious answer: the nearest of a kind where any
        one will do (or the shopper asked for the nearest), or a store named outright. A nudge or a swap
        is a real choice, so those stay a list. Only from a known spot: from the entrance it's a guess."""
        result = out["result"]
        if result["type"] != "places" or result.get("alternatives_for") or not result["places"]:
            return out
        top = result["places"][0]
        if top["walk_min"] is None or any(p.get("nudge") for p in result["places"]):
            return out
        nearest = result["category"] in ANY_WILL_DO or NEAREST_RE.search(message)
        if not (nearest or top["name"] in self.search.names_in(message)):
            return out
        where = f"The nearest is {top['name']}," if nearest else f"{top['name']} is"
        return {**out, "reply": f"{where} on {top['floor_name']}, {top['walk_min']} min away. Taking you there.",
                "result": {**result, "go": top["id"]}}

    def _plan_payload(self, trip: Trip, start: str, now_min: int, changes: list[str]) -> dict:
        plan = plan_trip(trip, start, now_min, self._router(trip), self.mall)
        return {"type": "plan", "plan": plan.model_dump(), "changes": changes}

    async def chat(self, message: str, at: dict | None, now: str, trip: Trip, prev: dict | None = None) -> dict:
        x = await self._extract(message, trip)
        out = self._respond(x, at, now, trip, prev)
        if x.source == "rules" and _dead_end(x, out):
            # The rules were sure but found nothing, so let the LLM read it before giving up.
            # Keep the rules' plain "couldn't find" unless the LLM finds something to show.
            if (retry := await self._ask_llm(message, trip)) is not None:
                retry_out = self._respond(retry, at, now, trip, prev)
                if retry_out["result"]["type"] != "text":
                    x, out = retry, retry_out
        if FRIEND_RE.search(message):
            out = _for_friend(out)
        elif x.intent == "find" and at:
            out = self._go(message, out)
        out["meta"] = {"engine": x.source, "intent": x.intent}  # which engine understood it, for the receipt line
        return out

    def _respond(self, x: Extraction, at: dict | None, now: str, trip: Trip, prev: dict | None = None) -> dict:
        now_min = hhmm_to_min(now)
        start = self.start_node(at)
        router = self._router(trip)

        if x.intent == "more":
            return self._more(prev, start, router, trip)

        if x.intent == "find" and x.errands:
            req = x.errands[0]
            scores = None
            if (cat := self._find_category(req)) and self.search.by_category(cat):
                ids, alt, scores = self.search.by_category(cat), None, self._word_scores(req.query, cat)
            else:
                ids, alt = self._resolve(req.query, req.category, start, router)
            if alt:
                result = self._alternatives_result(alt, start, router)
                return {"reply": self._alternatives_reply(alt, result["places"]), "result": result,
                        "trip": trip.model_dump(by_alias=True)}
            if not ids:
                return _text(_not_found([req.query]), trip)
            result = self._places_result(req.query, ids, start, router, scores, category=cat)
            reply = f"Here's what I found for “{req.query}”:"
            if cat is None and (nudge := self._nudge(req.query, result["places"], start, router, tuple(ids))):
                result["places"].append({**nudge.row, "nudge": True})
                result["shown"].append(nudge.row["id"])
                reply += f" {nudge.sentence}"
            return {"reply": reply, "result": result,
                    "trip": trip.model_dump(by_alias=True)}

        if x.intent == "plan" and x.errands:
            # A new list adds to the trip: a stop already planned isn't added twice, and the
            # whole trip keeps to MAX_ERRANDS.
            t = trip.model_copy(deep=True)
            capped = False
            missing, already, swapped, added = [], [], {}, 0
            for req in x.errands:
                active = [e for e in t.errands if e.status != "done"]
                if len(active) >= MAX_ERRANDS:
                    capped = True
                    break
                made, stand_in = self._errand_or_alternative(req.query, req.category, new_errand_id(t), start, router)
                if made is None:
                    missing.append(req.query)
                    continue
                if dup := duplicate_of(made, t):
                    if set(made.candidates) < set(dup.candidates):  # "zara and h&m": the one named wins
                        dup.candidates, dup.query = made.candidates, made.query
                    already.append(made.label)
                    continue
                t.errands.append(made)
                added += 1
                if stand_in:
                    swapped[stand_in.name] = stand_in.category  # one sentence per missing brand
            if not added and not already and not capped:
                return _text(_not_found(missing), trip)
            payload = self._plan_payload(t, start, now_min, [])
            reply = f"Here's your plan: {_stops(len(payload['plan']['stops']))}, done by {payload['plan']['finish_at']}."
            for name, cat in swapped.items():
                reply += f" No {name} here, so I added other {places_label(cat)} instead."
            if already:
                names = list(dict.fromkeys(already))
                reply += f" {', '.join(names)} {'is' if len(names) == 1 else 'are'} already in your plan."
            if missing:
                reply += f" I couldn't find: {', '.join(missing)}."
            if capped:
                reply += f" Your plan has {MAX_ERRANDS} errands; finish one before adding more."
            return {"reply": reply, "result": payload, "trip": t.model_dump(by_alias=True)}

        if x.intent == "edit" and x.edits:
            t, changes, question = self._apply(trip, x.edits, now_min, start)
            if question:
                return _text(question, trip)
            if not changes:
                return _text(NOTHING_CHANGED, trip)
            if not t.errands:  # a deadline or elevators-only said before there is any trip
                return _text(f"Got it: {'; '.join(changes)}. What do you need to do?", t)
            payload = self._plan_payload(t, start, now_min, changes)
            return {"reply": "Updated your plan.", "result": payload, "trip": t.model_dump(by_alias=True)}

        if x.intent == "locate" and not x.landmarks:
            return _text(WHERE_AM_I, trip)

        if x.intent == "locate":
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
            trip, changes, question = self._apply(trip, edits, now_min, self.start_node(at))
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

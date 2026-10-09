"""Client for the local Ollama server (Qwen3-1.7B) plus a deterministic fallback.

The model only extracts structure from Taglish text. It never plans, routes or edits trips.
"""

import asyncio
import json
import re
from collections import OrderedDict
from collections.abc import Callable

import httpx
from pydantic import ValidationError

from .models import Edit, ErrandReq, Extraction, Trip
from .rules import SEPARATORS

EDIT_OPS = ["set_duration", "set_ready_at", "add", "remove", "order", "deadline", "status", "choose", "elevator_only"]
MAX_ERRANDS = 5
FILLER = re.compile(
    r"\b(ko|ako|yung|ng|na|lang|daw|muna|mag|ma|pa|papa|ang|sa|po|i|want|to|need|gusto|kailangan|"
    r"papaayos|ipaayos|magpaayos|ipagawa|ayusin|bili|bibili|bumili|mamili|kakain|kumain)\b",
    re.I,
)


class LLMBusy(Exception):
    pass


class LLMError(Exception):
    pass


def SCHEMA(categories: list[str]) -> dict:  # noqa: N802 - reads like a constant at call sites
    nullable = lambda s: {"anyOf": [s, {"type": "null"}]}  # noqa: E731
    return {
        "type": "object",
        "properties": {
            "i": {"enum": ["find", "plan", "edit", "locate", "other"]},
            "e": {"type": "array", "maxItems": MAX_ERRANDS, "items": {
                "type": "object",
                "properties": {"q": {"type": "string"}, "c": nullable({"enum": categories})},
                "required": ["q"]}},
            "d": {"type": "array", "maxItems": 4, "items": {
                "type": "object",
                "properties": {
                    "op": {"enum": EDIT_OPS}, "e": nullable({"type": "string"}),
                    "n": nullable({"type": "integer"}), "t": nullable({"type": "string"}),
                    "r": nullable({"enum": ["first", "last"]}), "s": nullable({"enum": ["dropped", "done"]}),
                    "q": nullable({"type": "string"}), "v": nullable({"type": "boolean"})},
                "required": ["op"]}},
            "l": {"type": "array", "maxItems": 4, "items": {"type": "string"}},
            "f": nullable({"type": "string"}),
        },
        "required": ["i"],
    }


def system_prompt(categories: list[str]) -> str:
    return (
        "You read short Taglish (Tagalog+English) messages from shoppers inside a mall and output JSON only.\n"
        "Keys: i=intent (find: one thing to look for; plan: two or more errands; edit: change the current trip; "
        "locate: user describes stores they can see; other). "
        "e=errands, each {q: short ENGLISH search phrase, c: category or null}. "
        "d=edits to the current trip: {op, e: errand id like e1, n: minutes, t: time HH:MM 24h, r: first|last, "
        "s: dropped|done, q: new errand phrase, v: true/false}. l=store names the user can see. f=floor like 4F or GF.\n"
        f"Categories: {', '.join(categories)}.\n"
        "Examples:\n"
        'MSG: papaayos ko screen ng phone ko, kakain, tapos bibili ng regalo kay mama\n'
        '{"i":"plan","e":[{"q":"phone screen repair","c":"phone_repair"},{"q":"meal","c":"food"},'
        '{"q":"gift for mom","c":"gift"}]}\n'
        "TRIP: e1: Phone repair, FixHub Mobile, 45 min, async, todo | e2: Kain, Foodcourt, 30 min, sync, todo\n"
        "MSG: sabi ng technician isang oras daw, at dagdag mo yung sapatos na ipapaayos\n"
        '{"i":"edit","d":[{"op":"set_duration","e":"e1","n":60},{"op":"add","q":"shoe repair"}]}\n'
        "MSG: basag yung screen ng tablet ko, nauuhaw na rin ako\n"
        '{"i":"plan","e":[{"q":"tablet screen repair","c":"phone_repair"},{"q":"cold drink","c":"cafe"}]}\n'
        "MSG: where can I buy a birthday present\n"
        '{"i":"find","e":[{"q":"birthday gift","c":"gift"}]}\n'
        "MSG: nasa harap ako ng Watsons, tapos kita ko yung Jollibee sa kaliwa\n"
        '{"i":"locate","l":["Watsons","Jollibee"]}\n'
        "MSG: salamat!\n"
        '{"i":"other"}'
    )


def from_short(d: dict, source: str = "llm") -> Extraction:
    errands = [ErrandReq(query=e["q"], category=e.get("c")) for e in d.get("e") or [] if e.get("q")]
    edits = []
    for raw in d.get("d") or []:
        if raw.get("op") not in EDIT_OPS:
            continue
        try:
            edits.append(Edit(op=raw["op"], errand=raw.get("e"), minutes=raw.get("n"), time=raw.get("t"),
                              rule=raw.get("r"), status=raw.get("s"), query=raw.get("q"), value=raw.get("v")))
        except ValidationError:
            continue
    intent = d.get("i") if d.get("i") in ("find", "plan", "edit", "locate", "other") else "other"
    return Extraction(intent=intent, errands=errands[:MAX_ERRANDS], edits=edits,
                      landmarks=[x for x in d.get("l") or [] if x], floor=d.get("f"), source=source)


def trip_summary(trip: Trip, place_name: Callable[[str], str | None]) -> str:
    rows = []
    for e in trip.errands:
        pid = e.chosen or (e.candidates[0] if e.candidates else None)
        where = place_name(pid) if pid else "?"
        rows.append(f"{e.id}: {e.label}, {where}, {e.duration_min} min, {'async' if e.async_ else 'sync'}, {e.status}")
    return " | ".join(rows)


def fallback_extract(message: str, trip: Trip) -> Extraction:
    chunks = []
    for raw in SEPARATORS.split(message):
        raw = raw.strip(" .!?")
        if not raw:
            continue
        cleaned = re.sub(r"\s+", " ", FILLER.sub(" ", raw)).strip()
        chunks.append(cleaned or raw)
    chunks = chunks[:MAX_ERRANDS]
    intent = "plan" if len(chunks) >= 2 else "find"
    return Extraction(intent=intent, errands=[ErrandReq(query=c) for c in chunks], source="fallback")


class LLMClient:
    def __init__(self, base_url: str, categories: list[str], model: str = "qwen3:1.7b", threads: int = 4,
                 timeout_s: float = 8.0, cache_size: int = 256):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.threads = threads
        self.timeout_s = timeout_s
        self._system = system_prompt(categories)
        self._schema = SCHEMA(categories)
        self._lock = asyncio.Lock()
        self._cache: OrderedDict[tuple[str, str], Extraction] = OrderedDict()
        self._cache_size = cache_size
        self._http = httpx.AsyncClient(timeout=timeout_s + 1)

    async def health(self) -> bool:
        try:
            r = await self._http.get(f"{self.base_url}/api/version", timeout=2)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def extract(self, message: str, trip: Trip, summary: str = "") -> Extraction:
        key = (message.strip().lower(), summary)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        if self._lock.locked():
            raise LLMBusy()
        async with self._lock:
            body = {
                "model": self.model, "stream": False, "think": False, "keep_alive": -1,
                "format": self._schema,
                "options": {"temperature": 0, "num_ctx": 2048, "num_thread": self.threads, "num_predict": 200},
                "messages": [
                    {"role": "system", "content": self._system},
                    {"role": "user", "content": f"TRIP: {summary or 'none'}\nMSG: {message.strip()}"},
                ],
            }
            try:
                r = await asyncio.wait_for(self._http.post(f"{self.base_url}/api/chat", json=body), self.timeout_s)
                r.raise_for_status()
                content = r.json()["message"]["content"]
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.S).strip()
                result = from_short(json.loads(content))
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                raise LLMError(str(exc)) from exc
        self._cache[key] = result
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return result

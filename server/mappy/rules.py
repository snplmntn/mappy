"""Rule-first message parsing. Handles chips, short searches, steering and landmark
descriptions without calling the LLM, which is slow on a CPU-only laptop."""

import re

from .models import Edit, ErrandReq, Extraction, Trip
from .search import CATEGORY_LABELS, Search

SEPARATORS = re.compile(r",|;|\btapos\b(?!\s+na\b)|\band\b|\bthen\b|\bsaka\b|\bpati\b|\bpagkatapos\b", re.I)
# Tagalog "at" (and) is too ambiguous to split on in general, but fine when every part names a category.
PLAN_SEPARATORS = re.compile(rf"{SEPARATORS.pattern}|\bat\b|\btsaka\b", re.I)
LOCATE_CUES = ("nasa ", "andito", "nandito", "i'm at", "im at", "i am at", "katapat", "tabi ng",
               "beside", "near ", "kita ko", "i see", "harap ng", "tapat ng", "nandyan", "andyan")
QUESTION_WORDS = re.compile(r"^(?:where can i (?:find|get|buy)|where can i|where do i|where is|where's|where|"
                            r"saan (?:ako )?pwede|saan|nasaan|asan|san|may|gusto ko(?:ng)?|kailangan ko(?:ng)?|"
                            r"need ko|hanap(?: ako)?|naghahanap ako|i want(?: to)?|i need(?: to)?|looking for)"
                            r"\s+(?:ang|ng|ba|po|yung|the)?\s*", re.I)
OTHER_RE = re.compile(r"^\s*(?:hi|hello|hey|yo|salamat|thanks?|thank you|ty|ok(?:ay)?|sige|"
                      r"good (?:morning|afternoon|evening)|anong oras|what time)\b", re.I)
NUM_WORDS = {"isa": 1, "isang": 1, "dalawa": 2, "dalawang": 2, "tatlo": 3, "tatlong": 3}
UNIT_AHEAD = r"(?!\s*(?:mins?\b|minutes?|minutos?|oras|hrs?\b|hours?))"

HOURS_RE = re.compile(r"(\d+(?:\.\d+)?|isang|isa|dalawang|dalawa|tatlong|tatlo)\s*(?:oras|hrs?|hours?)\b", re.I)
MINS_RE = re.compile(r"(\d+)\s*(?:mins?|minutes?|minutos?)\b", re.I)
TIME_RE = re.compile(rf"(?<![\d:])(\d{{1,2}})(?::(\d{{2}}))?\s*(a\.?m\.?|p\.?m\.?)?(?![\d]){UNIT_AHEAD}", re.I)
READY_RE = re.compile(r"\bready\b\s*(?:na\s+)?(?:daw\s+)?(?:by|ng|sa|at|mga|ng mga)?\s*(.*)", re.I)
LEAVE_RE = re.compile(r"\b(?:aalis|umalis|uuwi|umuwi|leave|alis|uwi)\b(.*)", re.I)
REMOVE_RE = re.compile(r"\b(?:wag na|huwag na|skip|cancel|tanggalin|tanggal|ayoko na ng|ayaw ko na ng)\s+"
                       r"(?:(?:yung|ang|sa|ng)\s+)?(.+)", re.I)
ADD_RE = re.compile(r"\b(?:dagdag(?:an)?|isama|pasama|isali|add|samahan)\b(?:\s+(?:mo|na|rin|din|yung|ang|ng|sa|pa))*"
                    r"\s+(.+)", re.I)
FIRST_RE = re.compile(r"(?:^|\s)([\w&' ]+?)\s+(?:muna|first)\b", re.I)
DROPPED_RE = re.compile(r"\b(naiwan|iniwan|na-?drop|dinrop|binigay|na-?iwan|dropped off|drop off na)\b", re.I)
DONE_RE = re.compile(r"\b(nakuha ko na|kinuha ko na|tapos na|done na|picked up)\b", re.I)
ELEVATOR_RE = re.compile(r"\b(stroller|wheelchair|pwd|senior|elevator lang|bawal (?:sa )?escalator)\b", re.I)
FILLER_MAX_WORDS = 3
SHORT_FIND_MAX_WORDS = 4


def parse_minutes(text: str) -> int | None:
    t = text.lower()
    if "kalahating oras" in t:
        return 30
    total = 0.0
    if m := HOURS_RE.search(t):
        n = m.group(1)
        total += (NUM_WORDS[n] if n in NUM_WORDS else float(n)) * 60
    if m := MINS_RE.search(t):
        total += int(m.group(1))
    return int(total) if total else None


def parse_time(text: str) -> str | None:
    m = TIME_RE.search(text)
    if not m:
        return None
    h, mins = int(m.group(1)), int(m.group(2) or 0)
    ampm = (m.group(3) or "").lower().replace(".", "")
    if h > 23 or mins > 59:
        return None
    if ampm == "pm" and h < 12:
        h += 12
    elif ampm == "am" and h == 12:
        h = 0
    elif not ampm and 1 <= h <= 7:
        h += 12
    return f"{h:02d}:{mins:02d}"


FLOOR_PATTERNS = [
    (re.compile(r"\b(lg|lower ground|basement)\b", re.I), lambda m: "LG"),
    (re.compile(r"\b(ug|upper ground)\b", re.I), lambda m: "UG"),
    (re.compile(r"\b(gf|ground)\b", re.I), lambda m: "GF"),
    (re.compile(r"\b([1-5])\s*f\b", re.I), lambda m: f"{m.group(1)}F"),
    (re.compile(r"\b([1-5])(?:st|nd|rd|th)\b", re.I), lambda m: f"{m.group(1)}F"),
    (re.compile(r"\bika-?\s*([1-5])\b", re.I), lambda m: f"{m.group(1)}F"),
    (re.compile(r"\bannex\b", re.I), lambda m: "AX"),
]


def floor_hint(text: str) -> str | None:
    for pattern, to_floor in FLOOR_PATTERNS:
        if m := pattern.search(text):
            return to_floor(m)
    return None


def _mention(clause: str, trip: Trip) -> str | None:
    words = set(re.findall(r"[\w&]+", clause.lower()))
    for e in trip.errands:
        names = [e.label, CATEGORY_LABELS.get(e.category or "", "")]
        for name in names:
            if any(w in words for w in re.findall(r"[\w&]+", name.lower()) if len(w) >= 4):
                return e.label
    return None


def _clause_edits(clause: str, trip: Trip) -> list[Edit]:
    edits: list[Edit] = []
    has_trip = bool(trip.errands)
    ref = _mention(clause, trip)
    if m := READY_RE.search(clause):
        if t := parse_time(m.group(1)):
            edits.append(Edit(op="set_ready_at", errand=ref, time=t))
    if m := LEAVE_RE.search(clause):
        if t := parse_time(m.group(1)):
            edits.append(Edit(op="deadline", time=t))
    if not edits and (mins := parse_minutes(clause)):
        edits.append(Edit(op="set_duration", errand=ref, minutes=mins))
    if not has_trip:
        pass
    elif m := ADD_RE.search(clause):
        edits.append(Edit(op="add", query=m.group(1).strip(" .!?")))
    elif m := REMOVE_RE.search(clause):
        edits.append(Edit(op="remove", errand=m.group(1).strip(" .!?")))
    elif m := FIRST_RE.search(clause):
        target = re.sub(r"^(?:mag|yung|ang)\s+", "", m.group(1).strip(), flags=re.I)
        edits.append(Edit(op="order", errand=target, rule="first"))
    if DROPPED_RE.search(clause):
        edits.append(Edit(op="status", errand=ref, status="dropped"))
    elif DONE_RE.search(clause):
        edits.append(Edit(op="status", errand=ref, status="done"))
    if ELEVATOR_RE.search(clause):
        edits.append(Edit(op="elevator_only", value=True))
    return edits


def _steering(message: str, trip: Trip) -> Extraction | None:
    edits: list[Edit] = []
    for clause in SEPARATORS.split(message):
        clause = clause.strip()
        if not clause:
            continue
        found = _clause_edits(clause, trip)
        if not found and len(clause.split()) > FILLER_MAX_WORDS:
            return None
        edits += found
    return Extraction(intent="edit", edits=edits) if edits else None


def _category_plan(message: str, search: Search) -> Extraction | None:
    """A multi-errand message where every part names one clear category ("cr muna tapos kape") needs no LLM."""
    chunks = [c.strip(" .!?") for c in PLAN_SEPARATORS.split(message)]
    chunks = [c for c in chunks if c]
    if len(chunks) < 2:
        return None
    errands: dict[str, ErrandReq] = {}
    for chunk in chunks:
        cat = search.alias_category(chunk)
        if cat is None:
            return None
        errands.setdefault(cat, ErrandReq(query=chunk, category=cat))  # "notebook at ballpen" is one stop
    if len(errands) < 2:
        return None
    return Extraction(intent="plan", errands=list(errands.values()))


def parse(message: str, trip: Trip, search: Search) -> Extraction | None:
    msg = message.strip()
    lower = msg.lower()
    if any(cue in f" {lower}" for cue in LOCATE_CUES):
        names = search.names_in(msg)
        if names:
            return Extraction(intent="locate", landmarks=names, floor=floor_hint(msg))
    if OTHER_RE.search(msg):
        return Extraction(intent="other")
    if steer := _steering(msg, trip):
        return steer
    if PLAN_SEPARATORS.search(msg):
        if plan := _category_plan(msg, search):
            return plan
        if SEPARATORS.search(msg):
            return None
    query = QUESTION_WORDS.sub("", msg).strip(" ?!.") or msg
    asked = query != msg.strip(" ?!.")
    if cat := search.alias_category(query):
        return Extraction(intent="find", errands=[ErrandReq(query=query, category=cat)])
    if asked or len(query.split()) <= SHORT_FIND_MAX_WORDS:
        return Extraction(intent="find", errands=[ErrandReq(query=query)])
    return None

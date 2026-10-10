"""Rule-first message parsing. Handles chips, short searches, steering and landmark
descriptions without calling the LLM, which is slow on a CPU-only laptop."""

import re

from .brands import brand_in
from .models import Edit, ErrandReq, Extraction, Trip
from .search import CATEGORY_LABELS, REPAIR_WORDS, Search, categories_in

SEPARATORS = re.compile(r",|;|\btapos\b(?!\s+na\b)|\band\b|\bthen\b|\bsaka\b|\bpati\b|\bpagkatapos\b", re.I)
# Tagalog "at" (and) is too ambiguous to split on in general, but fine when every part names a category.
PLAN_SEPARATORS = re.compile(rf"{SEPARATORS.pattern}|\bat\b|\btsaka\b", re.I)
LOCATE_CUES = ("nasa ", "andito", "nandito", "i'm at", "im at", "i am at", "katapat", "tabi ng",
               "beside", "near ", "kita ko", "i see", "harap ng", "tapat ng", "nandyan", "andyan")
QUESTION_WORDS = re.compile(r"^(?:take me to|bring me to|how do i get to|dalhin mo ako sa|"
                            r"where can i (?:find|get|buy)|where can i|where do i|where is|where's|where|"
                            r"saan (?:ako )?pwede|saan|nasaan|asan|san|may|gusto ko(?:ng)?|kailangan ko(?:ng)?|"
                            r"need ko|hanap(?: ako)?|naghahanap ako|i want(?: to)?|i need(?: to)?|looking for)"
                            r"\s+(?:ang|ng|ba|po|yung|the)?\s*", re.I)
OTHER_RE = re.compile(r"^\s*(?:hi|hello|hey|yo|help|tulong|salamat|thanks?|thank you|ty|ok(?:ay)?|sige|"
                      r"good (?:morning|afternoon|evening)|anong oras|what time)\b", re.I)
# "Show me more" of the last list, only when the whole message is the cue ("more coffee" is a find);
# trailing particles ("iba pa po", "meron pa ba") are still just the cue.
MORE_RE = re.compile(r"^\s*(?:iba pa|iba pang|yung iba|meron pa|may iba pa|ano pa|"
                     r"show more|more|others?|something else|next)\b(?:\s+(?:po|ba|naman|nga))*[\s?!.]*$", re.I)
# Particles after the thing asked for: "may starbucks ba dito" asks for "starbucks".
TRAILING_RE = re.compile(r"(?:\s+(?:ba|po|dito|rito|here|meron|nga|naman))+\s*$", re.I)
WHERE_AM_I_RE = re.compile(r"^\s*(?:(?:nasaan|nasan|asan|saan)\s+(?:na\s+)?ako(?:\s+(?:ngayon|ba|po))*|"
                           r"where am i(?:\s+now)?)[\s?!.]*$", re.I)
# Asking for the closest one: "nearest coffee", "pinakamalapit na CR".
NEAREST_RE = re.compile(r"\b(?:the\s+)?(?:nearest|closest|pinaka\s*malapit)\b(?:\s+(?:na|ng))?", re.I)
# Someone else is the one at the spot being described ("my friend is near Gong Cha").
FRIEND_RE = re.compile(r"\b(?:friend|friends|kaibigan|tropa|barkada|kasama ko|si [a-z]+ (?:ay )?nasa)\b", re.I)
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
    cats = categories_in(clause)  # "tapos na ako kumain" is the food stop
    return next((e.label for e in trip.errands if e.status != "done" and e.category in cats), None)


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
        if m := REMOVE_RE.search(clause):  # so "skip food" with no trip says there is no trip
            edits.append(Edit(op="remove", errand=m.group(1).strip(" .!?")))
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


CARRY_MAX_WORDS = 2  # "sapatos ko" after "papaayos ko phone ko at" is repaired too


def _chunk_errand(chunk: str, repairing: bool, search: Search) -> ErrandReq | None:
    """The errand a plan part names by category; a bare object after a repair ("... at sapatos ko") is
    repaired, and its query says so, so it isn't read back as shopping for shoes."""
    words = set(re.findall(r"[\w&]+", chunk.lower()))
    if repairing and not words & REPAIR_WORDS and len(words) <= CARRY_MAX_WORDS:
        query = f"{chunk} repair"
        cats = categories_in(query)
        if len(cats) == 1 and (cat := next(iter(cats))).endswith("_repair"):
            return ErrandReq(query=query, category=cat)
    cat = search.alias_category(chunk)
    return ErrandReq(query=chunk, category=cat) if cat else None


def _category_plan(message: str, search: Search) -> Extraction | None:
    """A multi-errand message where every part names one clear category or store ("cr muna tapos kape",
    "uniqlo and starbucks") needs no LLM."""
    chunks = [c.strip(" .!?") for c in PLAN_SEPARATORS.split(message)]
    chunks = [c for c in chunks if c]
    if len(chunks) < 2:
        return None
    repairing = bool(set(re.findall(r"[\w&]+", message.lower())) & REPAIR_WORDS)
    errands: dict[str, ErrandReq] = {}
    for chunk in chunks:
        if req := _chunk_errand(chunk, repairing, search):
            errands.setdefault(req.category, req)  # "notebook at ballpen" is one stop
        elif search.names_in(chunk) or brand_in(chunk):
            errands.setdefault(chunk.lower(), ErrandReq(query=chunk))
        else:
            return None
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
    if WHERE_AM_I_RE.search(msg):
        return Extraction(intent="locate")
    if OTHER_RE.search(msg) or not re.search(r"\w", msg):  # a greeting, or only punctuation
        return Extraction(intent="other")
    if MORE_RE.search(msg):
        return Extraction(intent="more")
    if steer := _steering(msg, trip):
        return steer
    if PLAN_SEPARATORS.search(msg):
        if plan := _category_plan(msg, search):
            return plan
        if SEPARATORS.search(msg):
            return None
    query = TRAILING_RE.sub("", QUESTION_WORDS.sub("", msg).strip(" ?!.")) or msg
    query = NEAREST_RE.sub("", query).strip() or query  # "nearest restroom" asks for restrooms, nearest first
    asked = query != msg.strip(" ?!.")
    if cat := search.alias_category(query):
        return Extraction(intent="find", errands=[ErrandReq(query=query, category=cat)])
    if asked or len(query.split()) <= SHORT_FIND_MAX_WORDS:
        return Extraction(intent="find", errands=[ErrandReq(query=query)])
    return None

"""Shared data models. Trip state travels between phone and server as JSON."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DAY_MIN = 24 * 60


def hhmm_to_min(s: str) -> int:
    h, m = s.strip().split(":")
    return int(h) * 60 + int(m)


def min_to_hhmm(m: float) -> str:
    m = int(round(m)) % DAY_MIN
    return f"{m // 60:02d}:{m % 60:02d}"


_TIME_RE = re.compile(r"^(\d{1,2})(?::(\d{2}))?(?::\d{2})?\s*(a\.?m\.?|p\.?m\.?)?$", re.I)


def normalize_hhmm(value: object) -> str | None:
    """Accept '15:30', '3:30 pm', '3pm', '15:30:00'; return 'HH:MM', or None when unreadable.
    A bare 1-7 without am/pm means afternoon (mall hours)."""
    if not isinstance(value, str):
        return None
    m = _TIME_RE.match(value.strip())
    if not m:
        return None
    h, mins = int(m.group(1)), int(m.group(2) or 0)
    ampm = (m.group(3) or "").lower().replace(".", "")
    if ampm == "pm" and h < 12:
        h += 12
    elif ampm == "am" and h == 12:
        h = 0
    elif not ampm and not m.group(2) and 1 <= h <= 7:
        h += 12
    return f"{h:02d}:{mins:02d}" if h < 24 and mins < 60 else None


def _time_field(*names: str):
    return field_validator(*names, mode="before")(lambda cls, v: normalize_hhmm(v))


class Errand(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    label: str
    query: str
    category: str | None = None
    candidates: list[str]
    chosen: str | None = None
    duration_min: int
    duration_source: Literal["default", "store", "user"] = "default"
    async_: bool = Field(default=False, alias="async")
    ready_at: str | None = None
    status: Literal["todo", "dropped", "done"] = "todo"
    dropped_at: str | None = None

    _times = _time_field("ready_at", "dropped_at")


class OrderRule(BaseModel):
    errand: str
    rule: Literal["first", "last", "before", "after"]
    other: str | None = None


class Constraints(BaseModel):
    deadline: str | None = None
    order: list[OrderRule] = []
    elevator_only: bool = False

    _times = _time_field("deadline")


class Trip(BaseModel):
    errands: list[Errand] = []
    constraints: Constraints = Constraints()


EditOp = Literal[
    "set_duration", "set_ready_at", "add", "remove", "order",
    "deadline", "status", "choose", "elevator_only",
]


class Edit(BaseModel):
    op: EditOp
    errand: str | None = None
    minutes: int | None = None
    time: str | None = None
    query: str | None = None
    category: str | None = None
    rule: str | None = None
    other: str | None = None
    status: str | None = None
    place_hint: str | None = None
    value: bool | None = None

    _times = _time_field("time")


class ErrandReq(BaseModel):
    query: str
    category: str | None = None


class Extraction(BaseModel):
    intent: Literal["find", "plan", "edit", "locate", "other"]
    errands: list[ErrandReq] = []
    edits: list[Edit] = []
    landmarks: list[str] = []
    floor: str | None = None
    source: str = "rules"


class Stop(BaseModel):
    kind: Literal["visit", "drop", "pick"]
    errand: str
    place: str
    arrive_min: int
    leave_min: int
    arrive: str
    leave: str
    reason: str


class Leg(BaseModel):
    floor: str
    path: list[tuple[float, float]]
    instruction: str
    stop_index: int
    connector: dict | None = None


class Plan(BaseModel):
    stops: list[Stop]
    legs: list[Leg]
    total_min: int
    walk_min: int
    idle_min: int
    finish_at: str
    warnings: list[str] = []


class Candidate(BaseModel):
    node: str
    floor: str
    x: float
    y: float
    score: float
    matched: list[str]

"""Shared data models. Trip state travels between phone and server as JSON."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DAY_MIN = 24 * 60


def hhmm_to_min(s: str) -> int:
    h, m = s.strip().split(":")
    return int(h) * 60 + int(m)


def min_to_hhmm(m: float) -> str:
    m = int(round(m)) % DAY_MIN
    return f"{m // 60:02d}:{m % 60:02d}"


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


class OrderRule(BaseModel):
    errand: str
    rule: Literal["first", "last", "before", "after"]
    other: str | None = None


class Constraints(BaseModel):
    deadline: str | None = None
    order: list[OrderRule] = []
    elevator_only: bool = False


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

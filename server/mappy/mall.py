"""Load and validate mall.json into an immutable in-memory model."""

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path


class MallError(Exception):
    def __init__(self, issues: list[str]):
        super().__init__("; ".join(issues))
        self.issues = issues


@dataclass(frozen=True)
class Floor:
    id: str
    name: str
    level: int
    width: float
    height: float
    scale: float
    outline: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class Node:
    id: str
    floor: str
    x: float
    y: float


@dataclass(frozen=True)
class Place:
    id: str
    name: str
    floor: str
    rect: tuple[float, float, float, float]
    node: str
    category: str
    tags: tuple[str, ...]
    service: dict | None
    fictional: bool


@dataclass(frozen=True)
class Connector:
    id: str
    kind: str
    direction: str
    stops: tuple[str, ...]
    name: str
    seconds: float | None


@dataclass(frozen=True)
class Anchor:
    id: str
    label: str
    floor: str
    node: str
    heading_deg: float


class Mall:
    def __init__(self, raw: dict, digest: str):
        self.raw = raw
        self.hash = digest
        self.name = raw.get("mall", {}).get("name", "Mall")
        self.floors = {
            f["id"]: Floor(f["id"], f["name"], int(f["level"]), f["width"], f["height"],
                           float(f["scale_m_per_px"]), tuple(tuple(p) for p in f.get("outline", [])))
            for f in raw["floors"]
        }
        self.nodes = {n["id"]: Node(n["id"], n["floor"], n["x"], n["y"]) for n in raw["nodes"]}
        self.edges = [tuple(e) for e in raw["edges"]]
        self.connectors = [
            Connector(c["id"], c["kind"], c.get("direction", "both"), tuple(c["stops"]),
                      c.get("name", c["id"]), c.get("seconds"))
            for c in raw.get("connectors", [])
        ]
        self.places = {
            p["id"]: Place(p["id"], p["name"], p["floor"], tuple(p["rect"]), p["node"], p["category"],
                           tuple(p.get("tags", [])), p.get("service"), bool(p.get("fictional", False)))
            for p in raw["places"]
        }
        self.anchors = {
            a["id"]: Anchor(a["id"], a["label"], a["floor"], a["node"], float(a.get("heading_deg", 0)))
            for a in raw.get("anchors", [])
        }
        self.category_defaults = raw.get("category_defaults", {})

    def service_for(self, place_id: str) -> tuple[int, bool]:
        p = self.places[place_id]
        default = self.category_defaults[p.category]
        svc = p.service or {}
        return int(svc.get("duration_min", default["duration_min"])), bool(svc.get("async", default["async"]))

    def center(self, place_id: str) -> tuple[float, float]:
        x, y, w, h = self.places[place_id].rect
        return (x + w / 2, y + h / 2)

    def meters(self, floor_id: str, a: tuple[float, float], b: tuple[float, float]) -> float:
        return math.dist(a, b) * self.floors[floor_id].scale

    def floor_order(self) -> list[str]:
        return sorted(self.floors, key=lambda f: (self.floors[f].level, f))


def _validate(raw: dict) -> list[str]:
    issues: list[str] = []
    floors = {f["id"] for f in raw.get("floors", [])}
    nodes: dict[str, str] = {}
    for n in raw.get("nodes", []):
        if n["id"] in nodes:
            issues.append(f"duplicate node {n['id']}")
        if n["floor"] not in floors:
            issues.append(f"node {n['id']} on unknown floor {n['floor']}")
        nodes[n["id"]] = n["floor"]
    for a, b in raw.get("edges", []):
        for end in (a, b):
            if end not in nodes:
                issues.append(f"edge {a}-{b} references unknown node {end}")
    for c in raw.get("connectors", []):
        stops = c.get("stops", [])
        missing = [s for s in stops if s not in nodes]
        issues += [f"connector {c['id']} references unknown node {s}" for s in missing]
        stop_floors = [nodes[s] for s in stops if s in nodes]
        if len(stops) < 2:
            issues.append(f"connector {c['id']} needs at least 2 stops")
        if len(set(stop_floors)) != len(stop_floors):
            issues.append(f"connector {c['id']} has two stops on the same floor")
    defaults = raw.get("category_defaults", {})
    seen: set[str] = set()
    for p in raw.get("places", []):
        if p["id"] in seen:
            issues.append(f"duplicate place {p['id']}")
        seen.add(p["id"])
        if p["floor"] not in floors:
            issues.append(f"place {p['id']} on unknown floor {p['floor']}")
        if p["node"] not in nodes:
            issues.append(f"place {p['id']} references unknown node {p['node']}")
        elif nodes[p["node"]] != p["floor"]:
            issues.append(f"place {p['id']} node {p['node']} is on another floor")
        if p["category"] not in defaults:
            issues.append(f"place {p['id']} category {p['category']} has no category_defaults entry")
    for a in raw.get("anchors", []):
        if a["node"] not in nodes:
            issues.append(f"anchor {a['id']} references unknown node {a['node']}")
    return issues


def load_mall(path: str | Path) -> Mall:
    data = Path(path).read_bytes()
    raw = json.loads(data.decode("utf-8"))
    issues = _validate(raw)
    if issues:
        raise MallError(issues)
    return Mall(raw, hashlib.sha256(data).hexdigest()[:16])

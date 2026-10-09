"""Locate a person from the stores they can see. Orientation-free: only proximity matters."""

import math

from rapidfuzz import fuzz

from .mall import Mall
from .models import Candidate
from .search import Search

VISIBLE_M = 25.0
NOT_VISIBLE_PENALTY = 40.0
MISSING_ON_FLOOR_PENALTY = 60.0
MERGE_M = 8.0
TOP_N = 3
FLOOR_TIE_RATIO = 1.15
FALLBACK_NAME_MIN = 70


def _instances(search: Search, name: str) -> list[str]:
    ids = search.place_ids_named(name)
    if ids:
        return ids
    return [pid for pid, _ in search.search(name, k=2)
            if fuzz.WRatio(name.lower(), search.mall.places[pid].name.lower()) >= FALLBACK_NAME_MIN]


def locate(mall: Mall, search: Search, landmarks: list[str],
           floor: str | None = None) -> tuple[list[Candidate], str | None]:
    resolved = {name: _instances(search, name) for name in landmarks}
    resolved = {k: v for k, v in resolved.items() if v}
    if not resolved:
        return [], "more_landmarks"
    floors = {mall.places[pid].floor for ids in resolved.values() for pid in ids}
    if floor:
        floors &= {floor}
    connector_nodes = {s for c in mall.connectors for s in c.stops}
    scored: list[tuple[float, str, list[str]]] = []
    for node in mall.nodes.values():
        if node.floor not in floors or node.id in connector_nodes:
            continue
        total, matched = 0.0, []
        for ids in resolved.values():
            on_floor = [pid for pid in ids if mall.places[pid].floor == node.floor]
            if not on_floor:
                total += MISSING_ON_FLOOR_PENALTY
                continue
            d, pid = min((mall.meters(node.floor, (node.x, node.y), mall.center(p)), p) for p in on_floor)
            total += d + (NOT_VISIBLE_PENALTY if d > VISIBLE_M else 0.0)
            matched.append(pid)
        scored.append((total, node.id, matched))
    scored.sort(key=lambda s: (s[0], s[1]))
    kept: list[Candidate] = []
    for total, node_id, matched in scored:
        n = mall.nodes[node_id]
        if any(c.floor == n.floor and math.dist((c.x, c.y), (n.x, n.y)) * mall.floors[n.floor].scale < MERGE_M
               for c in kept):
            continue
        kept.append(Candidate(node=node_id, floor=n.floor, x=n.x, y=n.y, score=round(total, 1), matched=matched))
        if len(kept) == TOP_N:
            break
    ask = None
    if len({c.floor for c in kept}) > 1 and len(kept) > 1 and kept[1].score <= kept[0].score * FLOOR_TIE_RATIO + 1:
        ask = "floor"
    elif len(resolved) < 2 and len(kept) > 1:
        ask = "more_landmarks"
    return kept, ask

"""Walking graph over all floors: Dijkstra with directional escalators."""

import heapq
import math
from collections import defaultdict

from .mall import Connector, Mall
from .models import Leg

WALK_MPS = 1.2
ESCALATOR_S_PER_FLOOR = 30.0
ELEVATOR_WAIT_S = 60.0
ELEVATOR_S_PER_FLOOR = 10.0
BRIDGE_DEFAULT_S = 60.0


class Router:
    def __init__(self, mall: Mall, elevator_only: bool = False):
        self.mall = mall
        self.elevator_only = elevator_only
        self._adj: dict[str, list[tuple[str, float, Connector | None]]] = defaultdict(list)
        self._cache: dict[str, tuple[dict[str, float], dict[str, str]]] = {}
        self._build()

    def _add(self, a: str, b: str, seconds: float, conn: Connector | None = None) -> None:
        self._adj[a].append((b, seconds, conn))

    def _level(self, node_id: str) -> int:
        return self.mall.floors[self.mall.nodes[node_id].floor].level

    def _build(self) -> None:
        m = self.mall
        for a, b in m.edges:
            na, nb = m.nodes[a], m.nodes[b]
            s = m.meters(na.floor, (na.x, na.y), (nb.x, nb.y)) / WALK_MPS
            self._add(a, b, s)
            self._add(b, a, s)
        for c in m.connectors:
            if c.kind == "escalator":
                if self.elevator_only:
                    continue
                for a, b in zip(c.stops, c.stops[1:]):
                    floors = max(1, abs(self._level(a) - self._level(b)))
                    self._add(a, b, ESCALATOR_S_PER_FLOOR * floors, c)
                    if c.direction == "both":
                        self._add(b, a, ESCALATOR_S_PER_FLOOR * floors, c)
            elif c.kind == "elevator":
                for i, a in enumerate(c.stops):
                    for b in c.stops[i + 1:]:
                        s = ELEVATOR_WAIT_S + ELEVATOR_S_PER_FLOOR * abs(self._level(a) - self._level(b))
                        self._add(a, b, s, c)
                        self._add(b, a, s, c)
            else:
                s = c.seconds if c.seconds is not None else BRIDGE_DEFAULT_S
                for a, b in zip(c.stops, c.stops[1:]):
                    self._add(a, b, s, c)
                    self._add(b, a, s, c)

    def _dijkstra(self, src: str) -> tuple[dict[str, float], dict[str, str]]:
        if src in self._cache:
            return self._cache[src]
        dist = {src: 0.0}
        prev: dict[str, str] = {}
        heap = [(0.0, src)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist.get(u, math.inf):
                continue
            for v, w, _ in self._adj[u]:
                nd = d + w
                if nd < dist.get(v, math.inf):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(heap, (nd, v))
        self._cache[src] = (dist, prev)
        return dist, prev

    def seconds(self, src: str, dst: str) -> float | None:
        return self._dijkstra(src)[0].get(dst)

    def path(self, src: str, dst: str) -> list[str] | None:
        dist, prev = self._dijkstra(src)
        if dst not in dist:
            return None
        out = [dst]
        while out[-1] != src:
            out.append(prev[out[-1]])
        return out[::-1]

    def _connector_between(self, a: str, b: str) -> Connector | None:
        best = None
        for v, w, c in self._adj[a]:
            if v == b and c is not None and (best is None or w < best[0]):
                best = (w, c)
        return best[1] if best else None

    def legs(self, path: list[str], stop_index: int, dest_label: str) -> list[Leg]:
        m = self.mall
        legs: list[Leg] = []
        points: list[tuple[float, float]] = []
        for i, node_id in enumerate(path):
            n = m.nodes[node_id]
            points.append((n.x, n.y))
            nxt = path[i + 1] if i + 1 < len(path) else None
            if nxt is None or m.nodes[nxt].floor == n.floor:
                continue
            conn = self._connector_between(node_id, nxt)
            to_floor = m.nodes[nxt].floor
            floor_name = m.floors[to_floor].name
            if conn is not None and conn.kind == "bridge":
                instruction = f"Cross {conn.name} to {floor_name}"
            else:
                up = self._level(nxt) > self._level(node_id)
                down = self._level(nxt) < self._level(node_id)
                arrow = "↑" if up else "↓" if down else "→"
                name = conn.name if conn else "the connector"
                instruction = f"Take {name} {arrow} to {floor_name}"
            legs.append(Leg(
                floor=n.floor, path=points, instruction=instruction, stop_index=stop_index,
                connector={"id": conn.id if conn else None, "kind": conn.kind if conn else None,
                           "name": conn.name if conn else None, "to_floor": to_floor},
            ))
            points = []
        if points:
            legs.append(Leg(floor=m.nodes[path[-1]].floor, path=points,
                            instruction=f"Walk to {dest_label}", stop_index=stop_index))
        return legs

    def nearest_node(self, floor: str, x: float, y: float) -> str:
        candidates = [n for n in self.mall.nodes.values() if n.floor == floor]
        return min(candidates, key=lambda n: math.dist((n.x, n.y), (x, y))).id

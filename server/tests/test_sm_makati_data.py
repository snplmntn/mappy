import json
import math
import sys
from pathlib import Path

import pytest

from mappy.mall import load_mall
from mappy.router import Router

P = Path(__file__).resolve().parents[2] / "data" / "sm-makati" / "mall.json"


def test_valid_and_connected():
    m = load_mall(P)
    assert set(m.floors) == {"LG", "GF", "2F", "3F", "4F", "AX"} and len(m.places) >= 55
    r = Router(m)
    anchor = m.anchors["gf-mrt-entrance"].node
    assert [p.id for p in m.places.values() if r.seconds(anchor, p.node) is None] == []
    assert any(p.category == "phone_repair" and p.floor == "4F" for p in m.places.values())
    assert sum(1 for c in m.connectors if c.kind == "escalator") == 4


def test_elevator_only_reaches_everything():
    m = load_mall(P)
    r = Router(m, elevator_only=True)
    a = m.anchors["gf-mrt-entrance"].node
    assert all(r.seconds(a, p.node) is not None for p in m.places.values())


def _inside(poly, x, y):
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def test_every_floor_has_restroom_and_stores_do_not_overlap():
    import json

    m = load_mall(P)
    assert {p.floor for p in m.places.values() if p.category == "restroom"} == set(m.floors)
    raw = json.loads(P.read_text(encoding="utf-8"))
    for place in raw["places"]:
        x, y = place["label"][:2]
        assert _inside(place["shape"], x, y), place["id"]
        others = [o for o in raw["places"] if o["floor"] == place["floor"] and o["id"] != place["id"]]
        assert not any(_inside(o["shape"], x, y) for o in others), place["id"]


def test_floors_are_shaped_like_the_building():
    import json

    raw = json.loads(P.read_text(encoding="utf-8"))
    for f in raw["floors"]:
        assert f["walk_path"].startswith("M") and len(f["outline"]) >= 10, f["id"]


def _bearing(a, b):
    """Compass bearing from latlon a to latlon b, degrees clockwise from north."""
    dlat, dlon = b[0] - a[0], (b[1] - a[1]) * math.cos(math.radians(a[0]))
    return math.degrees(math.atan2(dlon, dlat)) % 360


def test_north_deg_turns_map_directions_into_compass_bearings():
    pytest.importorskip("shapely")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    import build_sm_makati as b

    pts, angle = b.project(b.MAIN_LATLON)
    px = b.to_portrait(pts)
    north = b.map_north_deg(angle)
    for i, j in [(0, 6), (5, 11), (12, 17)]:
        on_map = math.degrees(math.atan2(px[j][0] - px[i][0], -(px[j][1] - px[i][1])))
        diff = ((on_map + north) - _bearing(b.MAIN_LATLON[i], b.MAIN_LATLON[j]) + 180) % 360 - 180
        assert abs(diff) < 1


def test_floors_carry_north():
    m = json.loads(P.read_text(encoding="utf-8"))
    assert len({f["north_deg"] for f in m["floors"]}) == 1

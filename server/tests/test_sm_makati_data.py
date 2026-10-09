from pathlib import Path

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


def test_every_floor_has_restroom_and_stores_do_not_overlap():
    m = load_mall(P)
    assert {p.floor for p in m.places.values() if p.category == "restroom"} == set(m.floors)
    for f in m.floors:
        rects = [p.rect for p in m.places.values() if p.floor == f]
        for i, (x1, y1, w1, h1) in enumerate(rects):
            for x2, y2, w2, h2 in rects[i + 1:]:
                assert x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + h1 <= y2 or y2 + h2 <= y1

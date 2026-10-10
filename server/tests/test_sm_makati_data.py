from pathlib import Path

from mappy.mall import load_mall
from mappy.router import Router

P = Path(__file__).resolve().parents[2] / "data" / "sm-makati" / "mall.json"


def test_valid_and_connected():
    m = load_mall(P)
    assert set(m.floors) == {"LG", "GF", "2F", "3F", "4F", "5F", "AX"} and len(m.places) >= 55
    r = Router(m)
    anchor = m.anchors["gf-mrt-entrance"].node
    assert [p.id for p in m.places.values() if r.seconds(anchor, p.node) is None] == []
    assert any(p.category == "phone_repair" and p.floor == "2F" for p in m.places.values())
    assert sum(1 for c in m.connectors if c.kind == "escalator" and c.name.startswith("Escalator")) == 4
    assert {m.nodes[s].floor for c in m.connectors if c.name == "Travelator" for s in c.stops} == {"LG", "GF"}


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


def test_no_empty_storefronts_and_restrooms_on_every_floor():
    import json

    raw = json.loads(P.read_text(encoding="utf-8"))
    assert {f["id"]: len(f["blanks"]) for f in raw["floors"]} == {f["id"]: 0 for f in raw["floors"]}
    m = load_mall(P)
    for fid in ("GF", "2F", "3F", "4F"):
        assert sum(1 for p in m.places.values() if p.floor == fid and p.category == "restroom") == 2, fid
    assert not any(p.fictional for p in m.places.values() if p.category == "restroom")

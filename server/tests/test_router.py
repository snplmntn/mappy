from conftest import write_mall
from mappy.mall import load_mall
from mappy.router import Router


def test_up_uses_escalator_a(mall):
    p = Router(mall).path("GF-c1", "2F-c1")
    assert "GF-esc-a" in p and "2F-esc-a" in p and "GF-el" not in p


def test_down_uses_escalator_b_not_a(mall):
    p = Router(mall).path("2F-c5", "GF-c5")
    assert "2F-esc-b" in p and "GF-esc-a" not in p


def test_elevator_only(mall):
    p = Router(mall, elevator_only=True).path("GF-c1", "2F-c1")
    assert "GF-el" in p and "GF-esc-a" not in p


def test_bridge_cost_counts(mall):
    assert Router(mall).seconds("GF-c5", "AX-br") >= 480


def test_same_node_is_zero(mall):
    r = Router(mall)
    assert r.seconds("GF-c1", "GF-c1") == 0 and r.path("GF-c1", "GF-c1") == ["GF-c1"]


def test_legs_split_per_floor_with_connector(mall):
    r = Router(mall)
    legs = r.legs(r.path("GF-c1", "2F-c4"), stop_index=0, dest_label="Starbucks")
    assert [l.floor for l in legs] == ["GF", "2F"]
    assert legs[0].connector["kind"] == "escalator" and legs[0].connector["to_floor"] == "2F"
    assert "Escalator A" in legs[0].instruction and "2nd Floor" in legs[0].instruction
    assert legs[1].instruction == "Walk to Starbucks"
    assert legs[0].path[0] == (100, 300)


def test_bridge_leg_instruction(mall):
    r = Router(mall)
    legs = r.legs(r.path("GF-c4", "AX-c2"), stop_index=1, dest_label="FixIt")
    assert legs[0].instruction.startswith("Cross Annex Bridge") and legs[0].stop_index == 1


def test_unreachable_returns_none(tmp_path, sample_raw):
    sample_raw["connectors"] = [c for c in sample_raw["connectors"] if c["kind"] != "elevator"]
    r = Router(load_mall(write_mall(tmp_path, sample_raw)), elevator_only=True)
    assert r.seconds("GF-c1", "2F-c1") is None and r.path("GF-c1", "2F-c1") is None


def test_nearest_node(mall):
    assert Router(mall).nearest_node("GF", 690, 310) == "GF-c4"


def test_multi_floor_ride_is_one_leg():
    from pathlib import Path

    m = load_mall(Path(__file__).resolve().parents[2] / "data" / "sm-makati" / "mall.json")
    r = Router(m)
    start = m.anchors["gf-mrt-entrance"].node
    dest = m.anchors["4f-cyberzone-entrance"].node
    legs = r.legs(r.path(start, dest), stop_index=0, dest_label="Cyberzone")
    assert [l.floor for l in legs][0] == "GF" and legs[-1].floor == "4F"
    assert len(legs) == 2
    assert "4th Floor" in legs[0].instruction and legs[0].connector["to_floor"] == "4F"

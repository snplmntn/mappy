import pytest

from conftest import write_mall
from mappy.mall import MallError, load_mall


def test_loads_sample(mall):
    assert set(mall.floors) == {"GF", "2F", "AX"}
    assert mall.places["fixit-ax"].fictional is True
    assert mall.floor_order() == ["AX", "GF", "2F"]


def test_service_defaults(mall):
    assert mall.service_for("fixit-ax") == (45, True)
    assert mall.service_for("jollibee-gf") == (30, False)


def test_service_override(tmp_path, sample_raw):
    sample_raw["places"][-1]["service"] = {"duration_min": 60}
    m = load_mall(write_mall(tmp_path, sample_raw))
    assert m.service_for("fixit-ax") == (60, True)


def test_meters_uses_scale(mall):
    assert mall.meters("GF", (100, 300), (300, 300)) == pytest.approx(20.0)


def test_center(mall):
    assert mall.center("hm-gf") == (700, 200)


def test_rejects_unknown_node_reference(tmp_path, sample_raw):
    sample_raw["edges"].append(["GF-c1", "NOPE"])
    with pytest.raises(MallError) as e:
        load_mall(write_mall(tmp_path, sample_raw))
    assert any("NOPE" in i for i in e.value.issues)


def test_rejects_connector_stops_on_same_floor(tmp_path, sample_raw):
    sample_raw["connectors"][0]["stops"] = ["GF-esc-a", "GF-c1"]
    with pytest.raises(MallError):
        load_mall(write_mall(tmp_path, sample_raw))


def test_rejects_category_without_default(tmp_path, sample_raw):
    sample_raw["places"][0]["category"] = "spaceport"
    with pytest.raises(MallError) as e:
        load_mall(write_mall(tmp_path, sample_raw))
    assert any("spaceport" in i for i in e.value.issues)


def test_time_helpers():
    from mappy.models import hhmm_to_min, min_to_hhmm

    assert hhmm_to_min("16:05") == 965
    assert min_to_hhmm(965) == "16:05"
    assert min_to_hhmm(24 * 60 + 5) == "00:05"

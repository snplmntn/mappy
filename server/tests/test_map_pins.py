"""Hand-placed stores from tools/map_editor.py (data/sm-makati/units.json) survive a rebuild in their own units."""

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("shapely")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import build_sm_makati as b  # noqa: E402


def _build(tmp_path, monkeypatch, stores):
    pins = tmp_path / "units.json"
    pins.write_text(json.dumps({"version": 1, "stores": stores}), encoding="utf-8")
    monkeypatch.setattr(b, "PINS", pins)
    editor: dict = {}
    return b.build(editor), editor


def test_unit_ids_are_unique_and_stable(tmp_path, monkeypatch):
    _, first = _build(tmp_path, monkeypatch, [])
    _, again = _build(tmp_path, monkeypatch, [])
    ids = [u["id"] for f in first["floors"].values() for u in f["units"]]
    assert len(ids) == len(set(ids))
    assert ids == [u["id"] for f in again["floors"].values() for u in f["units"]]


def test_pinned_store_keeps_its_units_and_replaces_the_table_row(tmp_path, monkeypatch):
    data, editor = _build(tmp_path, monkeypatch, [
        {"name": "Starbucks", "floor": "GF", "category": "cafe", "tags": ["kape"], "units": ["GF-p01", "GF-p02"]},
        {"name": "Jollibee", "floor": "GF", "category": "food", "units": ["GF-p03"]},
    ])
    gf = {s["name"]: s for s in editor["floors"]["GF"]["stores"]}
    assert gf["Starbucks"]["units"] == ["GF-p01", "GF-p02"] and gf["Starbucks"]["pinned"]
    assert gf["Jollibee"]["units"] == ["GF-p03"]
    assert sum(1 for p in data["places"] if p["name"] == "Starbucks" and p["floor"] == "GF") == 1
    others = [u for s in editor["floors"]["GF"]["stores"] if not s["pinned"] for u in s["units"]]
    assert not {"GF-p01", "GF-p02", "GF-p03"} & set(others)


def test_pin_on_a_vanished_unit_is_reported_not_placed(tmp_path, monkeypatch):
    data, editor = _build(tmp_path, monkeypatch, [
        {"name": "Ghost Cafe", "floor": "GF", "category": "cafe", "units": ["GF-p99"]},
    ])
    assert editor["orphans"] == [{"name": "Ghost Cafe", "floor": "GF", "missing": ["GF-p99"]}]
    assert not any(p["name"] == "Ghost Cafe" for p in data["places"])

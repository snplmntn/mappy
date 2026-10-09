from test_api_version import client


def test_pick_records_a_known_place(tmp_path):
    r = client(tmp_path).post("/api/pick", json={"asked": "McDonald's", "place": "foodcourt-2f"})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert "foodcourt-2f" in (tmp_path / "picks.json").read_text(encoding="utf-8")


def test_pick_rejects_an_unknown_place(tmp_path):
    r = client(tmp_path).post("/api/pick", json={"asked": "McDonald's", "place": "nowhere"})
    assert r.status_code == 404 and "error" in r.json()
    assert not (tmp_path / "picks.json").exists()

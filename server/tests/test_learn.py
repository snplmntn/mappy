from mappy.learn import Picks


def test_ranked_by_pick_count(tmp_path):
    p = Picks(tmp_path / "picks.json")
    p.record("McDonald's", "jollibee-gf")
    p.record("McDonald's", "foodcourt-2f")
    p.record("mcdonald's", "foodcourt-2f")
    assert p.ranked("McDonald's") == ["foodcourt-2f", "jollibee-gf"]
    assert p.top("MCDONALD'S") == "foodcourt-2f"


def test_ties_keep_first_recorded_order():
    p = Picks(None)
    p.record("Zara", "hm-gf")
    p.record("Zara", "other")
    assert p.ranked("Zara") == ["hm-gf", "other"]


def test_persists_across_instances(tmp_path):
    path = tmp_path / "picks.json"
    Picks(path).record("McDonald's", "foodcourt-2f")
    assert path.exists() and not path.with_suffix(".json.tmp").exists()
    assert Picks(path).ranked("McDonald's") == ["foodcourt-2f"]


def test_memory_only_without_a_path(tmp_path):
    p = Picks(None)
    p.record("McDonald's", "foodcourt-2f")
    assert p.top("McDonald's") == "foodcourt-2f"
    assert list(tmp_path.iterdir()) == []


def test_unknown_brand_is_empty():
    p = Picks(None)
    assert p.ranked("Zara") == [] and p.top("Zara") is None


def test_corrupt_file_is_ignored(tmp_path):
    path = tmp_path / "picks.json"
    path.write_text("{not json", encoding="utf-8")
    p = Picks(path)
    assert p.ranked("McDonald's") == []
    p.record("McDonald's", "foodcourt-2f")
    assert Picks(path).top("McDonald's") == "foodcourt-2f"


def test_wrong_shape_file_is_ignored(tmp_path):
    path = tmp_path / "picks.json"
    path.write_text('["a", "b"]', encoding="utf-8")
    assert Picks(path).ranked("a") == []


def test_save_failure_keeps_the_pick_in_memory(tmp_path, monkeypatch, caplog):
    from pathlib import Path

    def refuse(self, target):
        raise PermissionError("locked by another writer")

    monkeypatch.setattr(Path, "replace", refuse)
    p = Picks(tmp_path / "picks.json")
    p.record("McDonald's", "foodcourt-2f")  # must not raise
    assert p.top("McDonald's") == "foodcourt-2f"
    assert "could not save picks" in caplog.text


def test_concurrent_records_count_every_pick(tmp_path):
    import threading

    p = Picks(tmp_path / "picks.json")
    threads = [threading.Thread(target=p.record, args=("McDonald's", "foodcourt-2f")) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert p.counts["mcdonald's"]["foodcourt-2f"] == 20
    assert Picks(tmp_path / "picks.json").counts["mcdonald's"]["foodcourt-2f"] == 20

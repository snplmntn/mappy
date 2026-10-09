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

from mappy.edge import EdgeMonitor


def test_phones_get_stable_names_in_join_order():
    m = EdgeMonitor()
    assert [m.phone("10.0.0.7"), m.phone("10.0.0.3"), m.phone("10.0.0.7")] == ["Phone 1", "Phone 2", "Phone 1"]
    assert m.phone("127.0.0.1") == "Laptop"


def test_stats_split_llm_from_everything_else():
    m = EdgeMonitor()
    for engine, ms in [("rules", 4), ("llm", 300), ("llm", 200), ("cache", 2), ("weird", 9)]:
        m.record("10.0.0.7", "hi", engine, "find", ms, now=1000)
    s = m.stats(now=1000)
    assert s["requests"] == 5 and s["served"]["fallback"] == 1
    assert s["without_llm_pct"] == 60 and s["llm_median_ms"] == 250
    assert s["events"][0]["engine"] == "fallback"


def test_only_recent_phones_count_as_connected():
    m = EdgeMonitor()
    m.seen("10.0.0.7", now=0)
    m.seen("10.0.0.8", now=1000)
    assert m.stats(now=1000)["phones"] == 1

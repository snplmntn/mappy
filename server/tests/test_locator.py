from mappy.locator import locate


def test_two_landmarks_disambiguate_floor(mall, search):
    cands, ask = locate(mall, search, ["Starbucks", "H&M"])
    assert cands[0].floor == "GF" and cands[0].node in {"GF-c2", "GF-c3", "GF-c4"}
    assert ask is None
    assert set(cands[0].matched) == {"starbucks-gf", "hm-gf"}


def test_single_ambiguous_landmark_asks_floor(mall, search):
    cands, ask = locate(mall, search, ["Starbucks"])
    assert ask == "floor" and {c.floor for c in cands} == {"GF", "2F"}


def test_floor_hint_filters(mall, search):
    cands, _ = locate(mall, search, ["Starbucks"], floor="2F")
    assert cands and all(c.floor == "2F" for c in cands)


def test_candidates_are_spread_out(mall, search):
    cands, _ = locate(mall, search, ["Starbucks"])
    pts = [(c.floor, c.x, c.y) for c in cands]
    assert len(set(pts)) == len(pts) <= 3


def test_connector_nodes_not_candidates(mall, search):
    cands, _ = locate(mall, search, ["Starbucks", "H&M"])
    assert all("esc" not in c.node and "-el" not in c.node for c in cands)


def test_unknown_landmark(mall, search):
    assert locate(mall, search, ["Zzyzx Emporium"]) == ([], "more_landmarks")

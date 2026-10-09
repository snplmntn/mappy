import numpy as np

from mappy.embed import HashEmbedder


def test_hash_embedder_normalized():
    v = HashEmbedder().embed(["kain tayo", "damit"], "query")
    assert v.shape[0] == 2 and np.allclose(np.linalg.norm(v, axis=1), 1.0)


def test_category_hint_wins(search):
    assert search.search("phone repair", category="phone_repair")[0][0] == "fixit-ax"


def test_fuzzy_name(search):
    assert search.search("Jolibee")[0][0] == "jollibee-gf"


def test_tags_taglish(search):
    assert search.search("damit")[0][0] == "hm-gf"


def test_by_category(search):
    assert search.by_category("restroom") == ["cr-gf"]


def test_alias(search):
    assert search.alias_category("CR") == "restroom"
    assert search.alias_category("gutom") == "food"
    assert search.alias_category("papaayos ko phone tapos kain") is None


def test_names_in_text(search):
    assert set(search.names_in("nasa tabi ako ng starbucks, katapat ng H&M")) == {"Starbucks", "H&M"}


def test_names_in_ignores_substrings_of_words(search):
    assert search.names_in("hmm okay") == []


def test_place_ids_named_returns_all_instances(search):
    assert set(search.place_ids_named("Starbucks")) == {"starbucks-gf", "starbucks-2f"}


def test_floor_filter(search):
    assert all(pid.endswith("-2f") for pid, _ in search.search("Starbucks", floor="2F"))

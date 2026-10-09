import numpy as np

from mappy.embed import HashEmbedder
from mappy.search import CATEGORY_LABELS, PLACE_LABELS, places_label


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
    assert search.alias_category("malapit na kainan") == "food"
    assert search.alias_category("magpadala ng pera") == "remittance"


def test_alias_yields_to_a_named_store(search):
    assert search.alias_category("kape sa Starbucks") is None


def test_names_in_text(search):
    assert set(search.names_in("nasa tabi ako ng starbucks, katapat ng H&M")) == {"Starbucks", "H&M"}


def test_names_in_ignores_substrings_of_words(search):
    assert search.names_in("hmm okay") == []


def test_place_ids_named_returns_all_instances(search):
    assert set(search.place_ids_named("Starbucks")) == {"starbucks-gf", "starbucks-2f"}


def test_floor_filter(search):
    assert all(pid.endswith("-2f") for pid, _ in search.search("Starbucks", floor="2F"))


class FlatEmbedder:
    """Every text gets the same vector, so ranking must come from lexical signals."""

    model_id = "flat"

    def embed(self, texts, kind):
        v = np.ones((len(texts), 4), dtype=np.float32)
        return v / np.linalg.norm(v, axis=1, keepdims=True)


def test_exact_tag_beats_noise(mall):
    from mappy.search import Search

    s = Search(mall, FlatEmbedder())
    assert s.search("ramen")[0][0] == "foodcourt-2f"
    assert s.search("pasalubong")[0][0] == "kultura-gf"


def test_unrelated_query_scores_below_tag_match(mall):
    from mappy.search import Search

    s = Search(mall, FlatEmbedder())
    assert s.search("spaceship")[0][1] < s.search("ramen")[0][1] - 0.15


def test_names_in_matches_without_generic_suffix(search):
    assert search.names_in("nasa tabi ako ng FixIt") == ["FixIt Mobile"]
    assert search.names_in("kita ko yung Food Court") == ["Food Court"]


def test_alternatives_rank_by_traits(search):
    assert search.alternatives("food", ("chickenjoy",)) == ["jollibee-gf", "foodcourt-2f"]
    assert search.alternatives("food", ("ramen",)) == ["foodcourt-2f", "jollibee-gf"]


def test_alternatives_exclude(search):
    assert search.alternatives("food", (), exclude=("jollibee-gf",)) == ["foodcourt-2f"]


def test_trait_score_matches_whole_words(search):
    assert search.trait_score("foodcourt-2f", ("ramen", "japanese")) == 1
    assert search.trait_score("foodcourt-2f", ("ram",)) == 0


def test_distinctive_tags_drop_category_words_and_shared_tags(search):
    assert search.distinctive_tags("jollibee-gf") == ("chickenjoy",)   # not "kain" or "meal"
    assert search.distinctive_tags("foodcourt-2f") == ("ramen",)
    assert search.distinctive_tags("starbucks-gf") == ()               # nothing the other Starbucks lacks


def test_places_label_reads_as_a_plural_noun_phrase():
    assert places_label("cafe") == "coffee shops"
    assert places_label("atm") == "ATMs"
    assert places_label("food") == "food places"
    assert places_label("mystery") == "mystery places"
    assert set(PLACE_LABELS) <= set(CATEGORY_LABELS)

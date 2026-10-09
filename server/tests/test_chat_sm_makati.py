"""Brand questions against the real demo mall (hash embedder, no cache), so a store that is here is
never answered with "No X in this mall"."""

import asyncio
from pathlib import Path

import pytest

from mappy.chat import ChatService
from mappy.embed import HashEmbedder
from mappy.mall import load_mall
from mappy.models import Trip
from mappy.router import Router
from mappy.search import Search

P = Path(__file__).resolve().parents[2] / "data" / "sm-makati" / "mall.json"
AT = {"anchor": "gf-mrt-entrance"}


@pytest.fixture(scope="module")
def real():
    mall = load_mall(P)
    search = Search(mall, HashEmbedder())
    return ChatService(mall=mall, search=search, router=Router(mall), router_elev=Router(mall, True), llm=None)


def ask(svc, text):
    return asyncio.run(svc.chat(text, AT, "14:00", Trip()))


@pytest.mark.parametrize("text, pid", [
    ("pet express", "pet-express-gf"),   # not a typo of J&T Express
    ("mi store", "mi-store-3f"),         # not a typo of SM Store
    ("xiaomi", "mi-store-3f"),           # Mi Store is tagged "xiaomi"
    ("sm store", "the-sm-store-gf"),
])
def test_a_store_that_is_here_is_a_name_hit(real, text, pid):
    out = ask(real, text)
    assert out["result"]["type"] == "places" and "alternatives_for" not in out["result"], out["reply"]
    assert out["result"]["places"][0]["id"] == pid

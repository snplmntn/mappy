from fastapi.testclient import TestClient

from mappy.api import create_app
from mappy.config import Settings
from mappy.embed import HashEmbedder


class NoLLM:
    async def extract(self, *args, **kwargs):
        raise RuntimeError("unused")

    async def health(self):
        return False


def test_web_files_are_always_revalidated(tmp_path):
    from conftest import SAMPLE

    client = TestClient(create_app(Settings(mall_path=SAMPLE, cache_dir=tmp_path), embedder=HashEmbedder(), llm=NoLLM()))
    for path in ("/", "/js/main.js", "/css/app.css"):
        r = client.get(path)
        assert r.status_code == 200 and "no-cache" in r.headers.get("cache-control", ""), path

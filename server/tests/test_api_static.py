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


def test_qr_endpoint_serves_standalone_svg(tmp_path):
    """An <img> only renders SVG that declares the SVG namespace."""
    from conftest import SAMPLE

    client = TestClient(create_app(Settings(mall_path=SAMPLE, cache_dir=tmp_path), embedder=HashEmbedder(), llm=NoLLM()))
    r = client.get("/api/qr", params={"data": "https://192.168.1.2:8443/?at=gf-entrance"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
    assert 'xmlns="http://www.w3.org/2000/svg"' in r.text

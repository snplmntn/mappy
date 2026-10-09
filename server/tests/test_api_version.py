from fastapi.testclient import TestClient

from mappy.api import create_app
from mappy.config import Settings
from mappy.embed import HashEmbedder
from test_api_static import NoLLM


def client(tmp_path):
    from conftest import SAMPLE

    return TestClient(create_app(Settings(mall_path=SAMPLE, cache_dir=tmp_path, log_dir=tmp_path),
                                 embedder=HashEmbedder(), llm=NoLLM()))


def test_mall_carries_a_version_for_client_caches(tmp_path):
    body = client(tmp_path).get("/api/mall").json()
    assert body["version"] and len(body["version"]) == 16


def test_client_errors_are_logged(tmp_path):
    r = client(tmp_path).post("/api/client-error", json={"message": "TypeError: x is undefined", "stack": "at boot", "ua": "Android"})
    assert r.status_code == 204
    assert "TypeError: x is undefined" in (tmp_path / "client-errors.log").read_text(encoding="utf-8")

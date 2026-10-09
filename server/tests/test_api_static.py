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


def test_print_redesign_keeps_https_qr_codes_and_http_fallback(tmp_path, monkeypatch):
    from conftest import SAMPLE
    import mappy.api as api

    payloads = []

    def capture_qr(data, scale=6):
        payloads.append(data)
        return "<svg></svg>"

    monkeypatch.setattr(api, "lan_ip", lambda: "192.168.1.20")
    monkeypatch.setattr(api, "_qr_svg", capture_qr)
    settings = Settings(mall_path=SAMPLE, cache_dir=tmp_path, port=8000, https_port=8443)
    client = TestClient(create_app(settings, embedder=HashEmbedder(), llm=NoLLM()))
    response = client.get("/print")

    assert response.status_code == 200
    assert "/css/print.css" in response.text and "Print codes" in response.text
    assert 'href="https://192.168.1.20:8443/"' in response.text
    assert 'href="http://192.168.1.20:8000/"' in response.text
    location_codes = [value for value in payloads if "/?at=" in value]
    assert location_codes
    assert all(value.startswith("https://192.168.1.20:8443/?at=") for value in location_codes)
    assert "https://192.168.1.20:8443/" in payloads
    assert any(value.startswith("WIFI:") for value in payloads)

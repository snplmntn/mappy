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


class CrashingLLM(NoLLM):
    async def health(self):
        raise RuntimeError("boom")


def _client(tmp_path, llm=None, **kwargs):
    from conftest import SAMPLE

    settings = Settings(mall_path=SAMPLE, cache_dir=tmp_path, log_dir=tmp_path / "logs")
    return TestClient(create_app(settings, embedder=HashEmbedder(), llm=llm or NoLLM()), **kwargs)


def test_too_long_message_gets_a_readable_error(tmp_path):
    r = _client(tmp_path).post("/api/chat", json={"message": "x" * 501, "now": "14:00"})
    assert r.status_code == 422 and r.json() == {"error": "That's too long. Keep it under 500 characters."}


def test_malformed_request_asks_to_reload(tmp_path):
    r = _client(tmp_path).post("/api/chat", json={"message": "hi", "now": "2pm"})
    assert r.status_code == 422 and "Reload" in r.json()["error"]


def test_server_crash_is_logged_and_readable(tmp_path):
    r = _client(tmp_path, CrashingLLM(), raise_server_exceptions=False).get("/api/health")
    assert r.status_code == 500 and "Try again" in r.json()["error"]
    assert "boom" in (tmp_path / "logs" / "server-errors.log").read_text(encoding="utf-8")


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

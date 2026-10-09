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


def test_shared_location_qr_is_a_standalone_svg(tmp_path):
    import xml.etree.ElementTree as ET
    from conftest import SAMPLE

    client = TestClient(create_app(Settings(mall_path=SAMPLE, cache_dir=tmp_path), embedder=HashEmbedder(), llm=NoLLM()))
    for location in ("gf-entrance", "node:gf-corridor"):
        response = client.get("/api/qr", params={"data": f"http://192.168.0.71:8000/?at={location}"})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/svg+xml")
        svg = ET.fromstring(response.content)
        assert svg.tag == "{http://www.w3.org/2000/svg}svg"
        assert int(svg.attrib["width"]) > 0
        assert svg.attrib["width"] == svg.attrib["height"]
        assert any(path.get("fill") in ("#fff", "#ffffff", "white")
                   for path in svg.iter("{http://www.w3.org/2000/svg}path"))

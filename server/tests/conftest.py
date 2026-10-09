import json
from pathlib import Path

import pytest

from mappy.mall import load_mall

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "data" / "sample" / "mall.json"


@pytest.fixture(scope="session")
def mall():
    return load_mall(SAMPLE)


@pytest.fixture
def sample_raw():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def write_mall(tmp_path, raw):
    p = tmp_path / "mall.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    return p

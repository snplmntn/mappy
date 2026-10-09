"""Settings from environment variables, then the .env file at the repo root."""

import os
import socket
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> dict[str, str]:
    env_file = ROOT / ".env"
    values: dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"')
    return values


def _get(name: str, default: str) -> str:
    return os.environ.get(name) or _load_dotenv().get(name) or default


def _default_mall() -> Path:
    real = ROOT / "data" / "sm-makati" / "mall.json"
    return real if real.exists() else ROOT / "data" / "sample" / "mall.json"


@dataclass
class Settings:
    mall_path: Path = field(default_factory=lambda: Path(_get("MAPPY_MALL", str(_default_mall()))))
    llm_base_url: str = field(default_factory=lambda: _get("MAPPY_LLM_URL", "http://127.0.0.1:11434"))
    llm_model: str = field(default_factory=lambda: _get("MAPPY_LLM_MODEL", "qwen3:1.7b"))
    llm_threads: int = field(default_factory=lambda: int(_get("MAPPY_LLM_THREADS", "4")))
    e5_dir: Path = field(default_factory=lambda: Path(_get("MAPPY_E5_DIR", str(ROOT / "models" / "e5"))))
    port: int = field(default_factory=lambda: int(_get("MAPPY_PORT", "8000")))
    wifi_ssid: str = field(default_factory=lambda: _get("MAPPY_WIFI_SSID", "mappy"))
    wifi_pass: str = field(default_factory=lambda: _get("MAPPY_WIFI_PASS", ""))
    cache_dir: Path = field(default_factory=lambda: ROOT / "server" / ".cache")
    log_dir: Path = field(default_factory=lambda: ROOT / "server" / ".logs")
    web_dir: Path = field(default_factory=lambda: ROOT / "web")


def lan_ip() -> str:
    """The address phones on the hotspot use to reach this machine. Sends no packets."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            if not ip.startswith("127."):
                return ip
    except OSError:
        pass
    for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
        if ip.startswith(("192.168.", "10.", "172.")):
            return ip
    return "127.0.0.1"

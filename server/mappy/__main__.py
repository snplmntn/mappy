"""Run Mappy: `python -m mappy`."""

import sys

import segno
import uvicorn

from .api import create_app
from .config import Settings, lan_ip


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    settings = Settings()
    url = f"http://{lan_ip()}:{settings.port}/"
    app = create_app(settings)
    print(f"\nMappy → {url}\nPrint QR codes → {url}print\nMall: {settings.mall_path}\n")
    try:
        segno.make(url).terminal(compact=True)
    except (UnicodeEncodeError, OSError):
        pass
    uvicorn.run(app, host="0.0.0.0", port=settings.port, log_level="warning")


if __name__ == "__main__":
    main()

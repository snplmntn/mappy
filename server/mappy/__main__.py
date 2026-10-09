"""Run Mappy: `python -m mappy`. Serves HTTPS (needed for the microphone) and plain HTTP as a fallback."""

import asyncio
import sys

import segno
import uvicorn

from .api import create_app
from .config import Settings, lan_ip
from .tls import ensure_cert


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    settings = Settings()
    ip = lan_ip()
    app = create_app(settings)
    configs = [uvicorn.Config(app, host="0.0.0.0", port=settings.port, log_level="warning")]
    url = f"http://{ip}:{settings.port}/"
    try:
        cert, key = ensure_cert(settings.cache_dir / "tls", ip)
        configs.append(uvicorn.Config(app, host="0.0.0.0", port=settings.https_port, log_level="warning",
                                      ssl_certfile=str(cert), ssl_keyfile=str(key)))
        url = f"https://{ip}:{settings.https_port}/"
    except Exception as exc:  # HTTPS only adds the microphone; plain HTTP keeps everything else working
        print(f"HTTPS disabled ({exc}); voice input falls back to the keyboard mic.")
    print(f"\nMappy → {url}\nAlso on → http://{ip}:{settings.port}/\nPrint QR codes → {url}print\nMall: {settings.mall_path}\n")
    try:
        segno.make(url).terminal(compact=True)
    except (UnicodeEncodeError, OSError):
        pass

    async def serve():
        await asyncio.gather(*(uvicorn.Server(c).serve() for c in configs))

    asyncio.run(serve())


if __name__ == "__main__":
    main()

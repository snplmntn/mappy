"""HTTP API and static web app. Thin wiring over ChatService; logic lives elsewhere."""

import html
from datetime import datetime
from typing import Annotated

import segno
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .chat import ChatService
from .config import Settings, lan_ip
from .embed import E5Embedder, HashEmbedder
from .llm import LLMClient
from .locator import locate
from .mall import load_mall
from .models import Edit, Trip
from .router import Router
from .search import Search

HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


class ChatReq(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    at: dict | None = None
    now: str = Field(pattern=HHMM)
    trip: Trip = Trip()


class PlanReq(BaseModel):
    at: dict | None = None
    now: str = Field(pattern=HHMM)
    trip: Trip
    edits: list[Edit] = []


class RouteReq(BaseModel):
    at: dict | None = None
    to: dict
    elevator_only: bool = False


class ClientErrorReq(BaseModel):
    message: str = Field(max_length=2000)
    stack: str = Field(default="", max_length=8000)
    ua: str = Field(default="", max_length=400)


class LocateReq(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    floor: str | None = None


class RevalidatingStaticFiles(StaticFiles):
    """Phones must never run a stale mix of old and new app files, so every load revalidates (cheap via ETag)."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


def _qr_svg(data: str, scale: int = 6) -> str:
    return segno.make(data, error="m").svg_inline(scale=scale, border=2, dark="#10213f")


def create_app(settings: Settings | None = None, embedder=None, llm=None) -> FastAPI:
    settings = settings or Settings()
    mall = load_mall(settings.mall_path)
    if embedder is None:
        embedder = E5Embedder(settings.e5_dir) if (settings.e5_dir / "tokenizer.json").exists() else HashEmbedder()
    search = Search(mall, embedder, settings.cache_dir)
    llm = llm or LLMClient(settings.llm_base_url, sorted(mall.category_defaults),
                           model=settings.llm_model, threads=settings.llm_threads)
    svc = ChatService(mall=mall, search=search, router=Router(mall), router_elev=Router(mall, True), llm=llm)
    app = FastAPI(title="Mappy", docs_url=None, redoc_url=None)

    @app.get("/api/mall")
    def get_mall(request: Request):
        etag = f'"{mall.hash}"'
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304)
        return JSONResponse({**mall.raw, "version": mall.hash}, headers={"ETag": etag, "Cache-Control": "no-cache"})

    @app.post("/api/chat")
    async def chat(req: ChatReq):
        return await svc.chat(req.message, req.at, req.now, req.trip)

    @app.post("/api/plan")
    def plan(req: PlanReq):
        return svc.plan(req.at, req.now, req.trip, req.edits)

    @app.post("/api/route")
    def route(req: RouteReq):
        return svc.route(req.at, req.to, req.elevator_only)

    @app.post("/api/locate")
    def do_locate(req: LocateReq):
        landmarks = search.names_in(req.text) or [req.text]
        cands, ask = locate(mall, search, landmarks, req.floor)
        return {"candidates": [c.model_dump() for c in cands], "ask": ask}

    @app.post("/api/client-error", status_code=204)
    def client_error(req: ClientErrorReq):
        """Phones report crashes here so they can be diagnosed from the laptop."""
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with (settings.log_dir / "client-errors.log").open("a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {req.ua}\n{req.message}\n{req.stack}\n\n")
        return Response(status_code=204)

    @app.get("/api/health")
    async def health():
        return {"ok": True, "mall": mall.name, "model": settings.llm_model,
                "embed_model": embedder.model_id, "llm_ok": await llm.health()}

    @app.get("/api/qr")
    def qr(data: Annotated[str, Query(max_length=400)]):
        return Response(_qr_svg(data), media_type="image/svg+xml")

    @app.get("/print", response_class=HTMLResponse)
    def print_page():
        base = f"http://{lan_ip()}:{settings.port}"
        wifi = f"WIFI:S:{settings.wifi_ssid};T:WPA;P:{settings.wifi_pass};;"
        cards = "".join(
            f'<div class="card">{_qr_svg(f"{base}/?at={a.id}", 5)}<b>{html.escape(a.label)}</b>'
            f'<small>{html.escape(mall.floors[a.floor].name)}</small></div>'
            for a in mall.anchors.values())
        return f"""<!doctype html><html><head><meta charset="utf-8"><title>Mappy · Print</title>
<style>body{{font-family:system-ui,sans-serif;margin:24px;color:#10213f}}h1{{margin:0 0 4px}}
.steps{{font-size:18px;margin:8px 0 20px}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}}
.card{{border:2px solid #10213f;border-radius:12px;padding:12px;text-align:center;break-inside:avoid}}
.card b{{display:block;font-size:16px}}.card small{{color:#555}}.hero{{display:flex;gap:24px;flex-wrap:wrap}}</style></head>
<body><h1>Mappy</h1><p class="steps">1) Scan Wi-Fi &nbsp; 2) Airplane mode ON, then Wi-Fi ON &nbsp; 3) Scan a location</p>
<div class="hero"><div class="card">{_qr_svg(wifi, 6)}<b>Wi-Fi: {html.escape(settings.wifi_ssid)}</b></div>
<div class="card">{_qr_svg(base + "/", 6)}<b>Open Mappy</b><small>{html.escape(base)}</small></div></div>
<h2>Location codes</h2><div class="grid">{cards}</div></body></html>"""

    if settings.web_dir.exists():
        app.mount("/", RevalidatingStaticFiles(directory=settings.web_dir, html=True), name="web")
    return app

"""HTTP API and static web app. Thin wiring over ChatService; logic lives elsewhere."""

import html
import io
import logging
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Annotated

import segno
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .chat import ChatService
from .config import Settings, lan_ip
from .edge import CpuMeter, EdgeMonitor, Probe, cpu_name, internet_reachable, memory
from .embed import E5Embedder, HashEmbedder
from .llm import LLMClient
from .locator import locate
from .mall import load_mall
from .models import Edit, Trip
from .router import Router
from .search import Search

HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"
TEXT_FIELDS = ("message", "text")
STALE_CLIENT = "Mappy couldn't read that request. Reload the page and try again."
SERVER_FAULT = "Something went wrong on the Mappy server. Try again."
log = logging.getLogger("mappy")


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


QR_STYLE = {"border": 2, "dark": "#10213f"}


def _error(status: int, message: str) -> JSONResponse:
    """Every API failure has this one shape, and `error` is always safe to show the user."""
    return JSONResponse({"error": message}, status_code=status)


def _validation_message(exc: RequestValidationError) -> str:
    for e in exc.errors():
        if e["loc"] and e["loc"][-1] in TEXT_FIELDS:
            if e["type"] == "string_too_long":
                return f"That's too long. Keep it under {e['ctx']['max_length']} characters."
            if e["type"] == "string_too_short":
                return "Type something first."
    return STALE_CLIENT


def _append_log(log_dir: Path, name: str, entry: str) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with (log_dir / name).open("a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {entry}\n\n")


def _qr_svg(data: str, scale: int = 6) -> str:
    """Inline SVG for embedding in HTML. Has no xmlns, so it can't be served as a standalone image."""
    return segno.make(data, error="m").svg_inline(scale=scale, **QR_STYLE)


def _qr_svg_file(data: str, scale: int = 6) -> bytes:
    """Standalone SVG document (with xmlns) that an <img src> can render."""
    buf = io.BytesIO()
    # Own white background and a full quiet zone, so a shared code still scans on a dark screen.
    segno.make(data, error="m").save(buf, kind="svg", scale=scale, **{**QR_STYLE, "border": 4, "light": "#ffffff"})
    return buf.getvalue()


async def _none() -> None:
    return None


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
    edge, cpu, cpu_label = EdgeMonitor(), CpuMeter(), cpu_name()
    online = Probe(internet_reachable)
    model_mb = Probe(lambda: llm.loaded_mb() if hasattr(llm, "loaded_mb") else _none())

    @app.exception_handler(RequestValidationError)
    async def bad_request(request: Request, exc: RequestValidationError):
        return _error(422, _validation_message(exc))

    @app.exception_handler(Exception)
    async def server_fault(request: Request, exc: Exception):
        """Crashes are written to the laptop's log so they can be diagnosed after the fact."""
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        trace = "".join(traceback.format_exception(exc))
        _append_log(settings.log_dir, "server-errors.log", f"{request.method} {request.url.path}\n{trace}")
        return _error(500, SERVER_FAULT)

    @app.get("/api/mall")
    def get_mall(request: Request):
        edge.seen(request.client.host if request.client else None)
        etag = f'"{mall.hash}"'
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304)
        return JSONResponse({**mall.raw, "version": mall.hash}, headers={"ETag": etag, "Cache-Control": "no-cache"})

    @app.post("/api/chat")
    async def chat(req: ChatReq, request: Request):
        started = time.perf_counter()
        out = await svc.chat(req.message, req.at, req.now, req.trip)
        ms = round((time.perf_counter() - started) * 1000)
        out["meta"] |= {"ms": ms, "model": settings.llm_model}
        edge.record(request.client.host if request.client else None, req.message,
                    out["meta"]["engine"], out["meta"]["intent"], ms)
        return out

    @app.get("/api/edge")
    async def edge_stats():
        """Everything the projector dashboard shows. All of it is measured on this machine."""
        return {**edge.stats(), "machine": {"cpu": cpu_label, "cpu_pct": cpu.read(), "memory": memory()},
                "model": settings.llm_model, "model_mb": await model_mb.get(),
                "embed_model": embedder.model_id, "internet": await online.get()}

    @app.get("/edge")
    def edge_page():
        return FileResponse(settings.web_dir / "edge.html", headers={"Cache-Control": "no-cache"})

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
        _append_log(settings.log_dir, "client-errors.log", f"{req.ua}\n{req.message}\n{req.stack}")
        return Response(status_code=204)

    @app.get("/api/health")
    async def health():
        return {"ok": True, "mall": mall.name, "model": settings.llm_model,
                "embed_model": embedder.model_id, "llm_ok": await llm.health()}

    @app.get("/api/qr")
    def qr(data: Annotated[str, Query(max_length=400)]):
        return Response(_qr_svg_file(data), media_type="image/svg+xml")

    @app.get("/print", response_class=HTMLResponse)
    def print_page():
        ip = lan_ip()
        base = f"https://{ip}:{settings.https_port}"
        fallback = f"http://{ip}:{settings.port}"
        wifi = f"WIFI:S:{settings.wifi_ssid};T:WPA;P:{settings.wifi_pass};;"
        cards = "".join(
            f'<article class="qr-card location-card"><div class="card-kicker"><span data-icon="pin"></span>'
            f'{html.escape(mall.floors[a.floor].name)}</div><div class="qr-code">{_qr_svg(f"{base}/?at={a.id}", 5)}</div>'
            f'<h3>{html.escape(a.label)}</h3><p>Scan to set your starting point</p></article>'
            for a in mall.anchors.values())
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#f7f4e9">
<title>Mappy &middot; QR codes</title><link rel="stylesheet" href="/css/print.css"></head>
<body>
<header class="topbar"><a class="brand" href="/" aria-label="Mappy home"><span class="brand-symbol" aria-hidden="true">m</span>mappy<span class="brand-period">.</span></a>
<div class="header-actions"><a class="button back" href="/"><span data-icon="back"></span>Back to app</a>
<button class="button print-button" id="printButton" type="button"><span data-icon="print"></span>Print codes</button></div></header>
<main>
<div class="page-heading"><span class="eyebrow">{html.escape(mall.name)} / QUICK START</span>
<h1>Scan. Connect.<br><span>You're on your way.</span></h1>
<p>Get Mappy on your phone. No app download needed.</p></div>
<ol class="steps"><li><span class="step-number">1</span><div><b>Join the Wi-Fi</b><span>Connect your phone to the laptop's network.</span></div></li>
<li><span class="step-number">2</span><div><b>Open Mappy</b><span>Scan the app code with your phone camera.</span></div></li>
<li><span class="step-number">3</span><div><b>Set your location</b><span>Scan the code for where you're standing.</span></div></li></ol>
<section aria-labelledby="connectTitle"><div class="section-heading"><h2 id="connectTitle">Get connected</h2><span>START HERE</span></div>
<div class="connect-grid">
<article class="qr-card connect-card"><div class="connect-copy"><span class="card-icon wifi-icon" data-icon="wifi"></span><h3>Join the Wi-Fi</h3>
<p>Network: <strong>{html.escape(settings.wifi_ssid)}</strong></p><p class="helper">Already on the same network?<br>Go straight to the app code.</p></div><div class="qr-code">{_qr_svg(wifi, 6)}</div></article>
<article class="qr-card connect-card app-card"><div class="connect-copy"><span class="card-icon" data-icon="phone"></span><h3>Open Mappy</h3>
<p>Your mall companion, in your browser.</p><a class="app-url" href="{html.escape(base, quote=True)}/">{html.escape(base)}</a></div><div class="qr-code">{_qr_svg(base + "/", 6)}</div></article>
</div><p class="connection-note">First visit on this laptop's local network: if your browser shows a certificate warning, select <b>Advanced &rarr; Proceed</b> to use HTTPS for microphone access. If it will not open, <a href="{html.escape(fallback, quote=True)}/">open Mappy over HTTP</a> and use typing or your keyboard's microphone.</p>
<p class="offline-note"><span data-icon="shield"></span>Trying the offline demo? Turn airplane mode on, then reconnect to Wi-Fi.</p></section>
<section aria-labelledby="locationsTitle"><div class="section-heading"><h2 id="locationsTitle">Start from your spot</h2><span>{len(mall.anchors)} LOCATION CODES</span></div>
<p class="section-description">Choose your current location. Print these cards to place around the mall.</p>
<div class="location-grid">{cards}</div></section>
<footer><span class="footer-brand">mappy.</span><span>Keep the laptop running and both devices on the same network.</span></footer>
</main><script type="module" src="/js/print.js"></script></body></html>"""

    if settings.web_dir.exists():
        app.mount("/", RevalidatingStaticFiles(directory=settings.web_dir, html=True), name="web")
    return app

# Mappy

**An errand isn't a point, it's a task with a duration.** Mappy plans your mall trip around waiting time, offline.

SM's directory kiosks have a queue, one screen, and no idea *why* you came. Mappy puts that kiosk in every phone: scan a QR code (no install), say what you need in Taglish, and a local AI on a laptop plans the whole trip, across floors.

Built for AppBuildersPH Hackathon 2026 (theme: Local AI).

## What it does

- **Ask by purpose, in Taglish.** *"sira screen ng phone ko"* finds the phone-repair stalls.
- **Plans around waiting.** *"papaayos ko phone ko, kakain, tapos bibili ng regalo"* becomes: drop off the phone → eat while it's being fixed → shop → pick up. Nothing hardcodes that order. Idle time is the cost the planner minimizes.
- **Steer by talking.** *"sabi ng technician 1 oras daw"*, *"kailangan ko umalis ng 5"*, *"wag na H&M"*, *"may stroller ako"*: each re-plans and shows what changed.
- **Multi-floor routes.** One-way escalators, an elevator-only mode, and step-by-step floor transfers ("Take Escalator B ↑ to 4th Floor").
- **Locate without GPS.** Scan a location QR (exact spot, like a kiosk), or describe what you see (*"nasa tabi ako ng Starbucks, katapat ng H&M"*) and confirm a pin.
- **Meet a friend.** Type what your friend sees; Mappy pins them and routes you there.

## Why local

- **Malls are connectivity dead zones.** Indoors, below ground, crowded towers, captive-portal Wi-Fi. Mappy works with **zero internet**: phones join a hotspot in airplane mode and talk only to the laptop.
- **The edge box replaces the kiosk.** One laptop serves every phone nearby. Nothing leaves the building, and each extra question costs nothing.
- **Private intent.** "Pharmacy for X" or "meeting someone" never reaches a cloud.
- **Fast.** Re-planning after every edit is instant. There's no round trip.

## Measured performance

From `tools/eval.py` on 50 Taglish messages. CPU only, Ollama `num_thread=4`, real map. Full table: [docs/eval-results.md](docs/eval-results.md).

| | Rules first, then LLM (shipped) | LLM only |
|---|---|---|
| Intent accuracy | 92% (46/50) | 82% (41/50) |
| Category F1 (find/plan) | 0.79 | 0.71 |
| Steering edits exact | 100% (12/12) | 25% (3/12) |
| Landmarks found | 100% (8/8) | 100% (8/8) |
| Latency (LLM calls) | median 270 ms, p95 329 ms | median 245 ms, p95 476 ms |

These numbers were measured on a Ryzen 7 5700X limited to 4 threads. The demo laptop (i3 12th gen, 8 GB, no GPU) is slower per core; re-run `tools/eval.py` there to get its own numbers.

## Run it

**One-time setup, on home internet:**
```powershell
powershell -ExecutionPolicy Bypass -File tools\setup.ps1
```
This installs Python 3.12 and Ollama, pulls `qwen3:1.7b`, downloads and checksums multilingual-e5-small, quantizes it to int8, creates `.env`, and runs the tests.

Then allow phones to reach the laptop (admin PowerShell, once):
```powershell
New-NetFirewallRule -DisplayName "Mappy" -Direction Inbound -Protocol TCP -LocalPort 8000,8443 -Action Allow -Profile Any
```

**Start:**
```powershell
powershell -ExecutionPolicy Bypass -File tools\run.ps1
```
The terminal prints the app URL and a QR code. Open `http://<laptop-ip>:8000/print` for the Wi-Fi QR, the app QR and the location QR cards.

**Tests:** `.venv\Scripts\python -m pytest -q` (123 tests, pure logic; no network).

## Demo network

1. Spare Android phone: hotspot `mappy`, WPA2, **mobile data off**. The laptop joins it.
2. Put the hotspot password in `.env` as `MAPPY_WIFI_PASS` so the print page's Wi-Fi QR works.
3. Judges: scan the Wi-Fi QR → **airplane mode on, then Wi-Fi on** → scan a location card.
4. Android hotspots may change subnet per session. Re-open `/print` after the hotspot is up; it always uses the current IP.
5. Mirror one phone to the projector with `scrcpy` over USB.
6. Open `http://localhost:8000/edge` on the laptop, next to the mirrored phone. It shows every phone's request live: which engine answered (rules, cache, local LLM or fallback), how long it took, CPU, memory, the model's RAM, and whether the laptop can reach the internet.
7. Send one message that needs the LLM before going on stage. The first LLM call after startup is slow (about 7 s measured); warm calls take about 0.3 s.

## How it works

```
Phone (Chrome, 13 KB gzipped)  ──HTTP──>  FastAPI on the laptop
  chat + SVG map, keeps its own trip         rules ─> Qwen3-1.7B (Ollama) ─> fallback
                                             e5-small embeddings (in-process)
                                             wait-aware planner, multi-floor router, locator
```

- **The LLM only extracts structure** (intents, errands, edits, landmarks) under a JSON schema. Planning, routing and edits are deterministic code with unit tests.
- **Rules handle chips, short searches and common steering without the LLM.** Measured: 28 of 50 eval messages.
- **The prompt is a fixed prefix**, so Ollama reuses its cache (437 of ~470 prompt tokens cached per call).
- **An 8-second timeout or busy model → deterministic fallback.** The app never hangs.

## Data honesty

**Store names come from public listings, with floors checked against a June 2026 walk-through video** ([Where In PH, "SM MAKATI Walking Tour 2026"](https://www.youtube.com/watch?v=3IVE7saCJUk)) and the SM Store directory pylons it shows. **The interior layout is our reconstruction** inside SM Makati's real building footprint. The video does not visit the Annex, the Lower Ground mall corridors or Cyberzone, so stores there are unconfirmed. The app says so on screen. Phone-repair stalls marked "demo" (FixHub Mobile, QuickFix Gadget Clinic, ScreenDoc) are fictional. Loading SM's real floor plans would be a data swap: edit the store table in `tools/build_sm_makati.py` or replace `data/sm-makati/mall.json`.

## Disclosures

| | |
|---|---|
| **Models** | Qwen3-1.7B via Ollama `qwen3:1.7b` (Q4_K_M, Apache 2.0). intfloat/multilingual-e5-small (MIT), int8-quantized by us with onnxruntime. |
| **Runtime and frameworks** | Ollama 0.40.1, onnxruntime, FastAPI, uvicorn, pydantic, numpy, tokenizers, rapidfuzz, httpx, segno. Vanilla JS + SVG (no frontend framework). |
| **Map data** | Building outlines © OpenStreetMap contributors (ODbL), ways 27831200 and 263667838. Store names from public listings; floors checked against a public walk-through video. Layout reconstructed. |
| **Cloud/APIs at runtime** | None. Internet is used only during setup to download software and models. |
| **Existing code/assets** | None. Built during the hackathon. |
| **AI development tools** | Claude Code. |
| **Why local** | See "Why local" above. |

## Team

Built by the Mappy team for AppBuildersPH Hackathon 2026.

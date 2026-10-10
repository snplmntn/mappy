"""Local map editor: watch a walk-through video next to the generated floor plan and name each storefront.

    .venv\\Scripts\\python tools\\map_editor.py        then open http://127.0.0.1:8765

Every save writes data/sm-makati/units.json (the hand-placed stores) and rebuilds data/sm-makati/mall.json.
Restart the app server to serve the new map. Needs the optional `data` dependency (shapely).
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_sm_makati as b  # noqa: E402

PAGE = Path(__file__).with_name("map_editor.html")
HOST, PORT = "127.0.0.1", 8765
CATEGORIES = sorted(b.CATEGORY_TAGS) + ["restroom"]


def state() -> dict:
    editor: dict = {}
    data = b.build(editor)
    floors = []
    for f in data["floors"]:
        ed = editor["floors"][f["id"]]
        floors.append({k: f[k] for k in ("id", "name", "level", "width", "height", "outline", "walk_path", "atria")}
                      | {"units": ed["units"], "stores": ed["stores"]})
    known = {(r[0], r[1]): {"name": r[0], "floor": r[1], "category": r[2], "tags": r[3]} for r in b.STORES}
    return {"floors": floors, "pins": b.load_pins(), "orphans": editor.get("orphans", []),
            "categories": CATEGORIES, "known": list(known.values())}


def validate(stores: list) -> str | None:
    floors = {fid for fid, _, _ in b.MAIN_FLOORS} | {"AX"}
    taken: dict[str, str] = {}
    for s in stores:
        name = str(s.get("name", "")).strip()
        if not name:
            return "Every store needs a name."
        if s.get("floor") not in floors:
            return f"{name}: unknown floor {s.get('floor')!r}."
        if s.get("category") not in CATEGORIES:
            return f"{name}: unknown category {s.get('category')!r}."
        if not s.get("units"):
            return f"{name}: pick at least one storefront."
        for u in s["units"]:
            if u in taken:
                return f"Storefront {u} is used by both {taken[u]} and {name}."
            taken[u] = name
    return None


def save(stores: list) -> None:
    keep = ("name", "floor", "category", "tags", "units", "service_min", "fictional", "seen", "note")
    clean = [{k: s[k] for k in keep if s.get(k) not in (None, "", [])} for s in stores]
    order = [f for f, _, _ in b.MAIN_FLOORS] + ["AX"]
    clean.sort(key=lambda s: (order.index(s["floor"]), min(s["units"])))  # stable diffs: by floor, then position
    tmp = b.PINS.with_suffix(".tmp")
    lines = ",\n".join("  " + json.dumps(s, ensure_ascii=False) for s in clean)  # one store per line: easy diffs
    tmp.write_text(f'{{"version": 1, "stores": [\n{lines}\n]}}\n', encoding="utf-8")
    tmp.replace(b.PINS)
    b.main()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json")

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/state":
            self._json(200, state())
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:
        if self.path != "/api/pins":
            return self._send(404, b"not found", "text/plain")
        try:
            stores = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))["stores"]
        except (ValueError, KeyError, TypeError):
            return self._json(400, {"error": "Bad request body."})
        if err := validate(stores):
            return self._json(400, {"error": err})
        save(stores)
        self._json(200, state())

    def log_message(self, fmt, *args) -> None:
        if not self.path.startswith("/api/state"):
            super().log_message(fmt, *args)


def main() -> None:
    print(f"Map editor on http://{HOST}:{PORT}  (Ctrl+C to stop)")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()

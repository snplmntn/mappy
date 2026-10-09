"""Generate data/sm-makati/mall.json: real SM Makati building outlines (OpenStreetMap),
real store names (public listings), reconstructed interior layout.

Edit STORES below to fix names, floors or categories, then re-run:
    python tools/build_sm_makati.py
"""

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sm-makati" / "mall.json"

# © OpenStreetMap contributors (ODbL). Way 27831200 (SM Makati), way 263667838 (SM Makati Annex).
MAIN_LATLON = [
    (14.5490282, 121.0269864), (14.5490825, 121.0269344), (14.5491233, 121.0268954), (14.5489869, 121.0267253),
    (14.5489981, 121.0266742), (14.5492449, 121.0264409), (14.5496963, 121.0260399), (14.5497369, 121.0260038),
    (14.5498367, 121.0259859), (14.5501274, 121.0263254), (14.5502147, 121.0264306), (14.5504984, 121.0267643),
    (14.5497175, 121.0274767), (14.5496261, 121.0274767), (14.549422, 121.0272495), (14.5493812, 121.027284),
    (14.5493204, 121.0273355), (14.5492631, 121.0272671), (14.5491192, 121.0270951),
]
ANNEX_LATLON = [
    (14.5493204, 121.0273355), (14.5495408, 121.0275988), (14.5494441, 121.0276872), (14.549375, 121.0277504),
    (14.5492975, 121.02774), (14.548985, 121.0273745), (14.5486725, 121.027009), (14.5486826, 121.0269084),
    (14.548844, 121.0267663), (14.5490282, 121.0269864), (14.5491192, 121.0270951), (14.5492631, 121.0272671),
]

WIDTH = 1000
MARGIN = 40
STEP = 64          # px between corridor nodes
SLOT_OFFSET = 58   # px from corridor centerline to store center
SLOT_W, SLOT_H = 56, 40

MAIN_FLOORS = [("LG", "Lower Ground", -1), ("GF", "Ground Floor", 0), ("2F", "2nd Floor", 1),
               ("3F", "3rd Floor", 2), ("4F", "4th Floor · Cyberzone", 3)]

CATEGORY_DEFAULTS = {
    "phone_repair": (45, True), "shoe_repair": (30, True), "food": (30, False), "cafe": (20, False),
    "clothing": (25, False), "shoes": (20, False), "accessories": (15, False), "gift": (15, False),
    "home": (15, False), "books_stationery": (15, False), "beauty": (15, False), "department_store": (30, False),
    "electronics": (20, False), "gaming": (20, False), "appliances": (20, False), "grocery": (30, False),
    "pharmacy": (5, False), "bank": (15, False), "atm": (3, False), "remittance": (10, False),
    "courier": (10, False), "pet": (15, False), "restroom": (5, False),
}

CATEGORY_TAGS = {
    "food": ["kain", "meal", "gutom", "pagkain", "lunch", "merienda"],
    "cafe": ["kape", "coffee", "drink", "drinks", "inumin", "juice", "pastry"],
    "clothing": ["damit", "clothes", "shirt", "fashion"],
    "shoes": ["sapatos", "shoes", "sandals", "tsinelas"],
    "accessories": ["relo", "watch", "alahas", "jewelry", "accessories"],
    "gift": ["regalo", "pasalubong", "souvenir", "gift"],
    "home": ["gamit sa bahay", "home", "kitchen"],
    "books_stationery": ["notebook", "ballpen", "school supplies", "books"],
    "beauty": ["skincare", "makeup", "beauty"],
    "department_store": ["department store", "clothes", "home"],
    "electronics": ["gadget", "laptop", "charger", "cellphone", "computer"],
    "gaming": ["games", "console", "arcade", "laro"],
    "appliances": ["appliance", "aircon", "ref", "electric fan"],
    "grocery": ["grocery", "supermarket", "groceries"],
    "pharmacy": ["gamot", "botika", "medicine", "drugstore"],
    "bank": ["bangko", "bank", "deposit", "withdraw"],
    "atm": ["atm", "withdraw", "cash", "pera"],
    "remittance": ["padala", "pera", "remittance", "money transfer"],
    "courier": ["package", "shipping", "courier", "padala"],
    "pet": ["pet", "aso", "pusa", "dog", "cat"],
    "restroom": ["cr", "banyo", "toilet", "comfort room"],
    "phone_repair": ["phone", "cellphone", "cellfone", "screen", "battery", "sira", "ayos", "paayos", "magpaayos", "ipaayos", "repair", "basag"],
    "shoe_repair": ["sapatos", "takong", "repair", "ayos", "paayos", "magpaayos", "ipaayos", "bag"],
}

# (name, floor, category, extra tags, service minutes or None, fictional)
STORES = [
    ("SM Supermarket", "LG", "grocery", [], None, False),
    ("Western Union", "LG", "remittance", [], None, False),
    ("DHL Express", "LG", "courier", [], None, False),
    ("Mr. Quickie", "LG", "shoe_repair", ["susi", "key", "takong"], 20, False),
    ("BDO ATM", "LG", "atm", [], None, False),
    ("Starbucks", "GF", "cafe", ["frappuccino"], None, False),
    ("BDO", "GF", "bank", [], None, False),
    ("BDO ATM", "GF", "atm", [], None, False),
    ("H&M", "GF", "clothing", [], None, False),
    ("Kultura Filipino", "GF", "gift", ["filipino", "barong"], None, False),
    ("Auntie Anne's", "GF", "food", ["pretzel"], None, False),
    ("La Botica", "GF", "pharmacy", [], None, False),
    ("The SM Store", "GF", "department_store", [], None, False),
    ("Seattle's Best Coffee", "GF", "cafe", [], None, False),
    ("SipYO Coco Fluff", "GF", "food", ["ice cream", "buko", "dessert"], None, False),
    ("Mary Grace Cafe", "GF", "cafe", ["ensaymada"], None, False),
    ("Sfera", "2F", "clothing", [], None, False),
    ("Dear Flora", "2F", "clothing", [], None, False),
    ("Uniqlo", "2F", "clothing", [], None, False),
    ("Crocs", "2F", "shoes", [], None, False),
    ("Tissot", "2F", "accessories", [], None, False),
    ("Wenger", "2F", "accessories", [], None, False),
    ("Broadway Gems", "2F", "accessories", [], None, False),
    ("Miniso", "2F", "home", ["cute", "gift"], None, False),
    ("PaperDollzCo", "2F", "books_stationery", [], None, False),
    ("Buttons & Wrap", "2F", "gift", ["gift wrap"], None, False),
    ("VMV Hypoallergenics", "2F", "beauty", [], None, False),
    ("SM Makati Foodcourt", "3F", "food", ["food court", "foodcourt"], None, False),
    ("Kyu Kyu Ramen 99", "3F", "food", ["ramen", "japanese"], None, False),
    ("Goldilocks", "3F", "food", ["cake", "bakery"], None, False),
    ("Delifrance", "3F", "cafe", ["bread", "sandwich"], None, False),
    ("Brownies Unlimited", "3F", "food", ["brownies", "dessert"], None, False),
    ("Sizzling Plate", "3F", "food", ["sizzling", "steak"], None, False),
    ("Cucina Norte", "3F", "food", ["pasta"], None, False),
    ("Fuel Burgers", "3F", "food", ["burger"], None, False),
    ("Gong Cha", "3F", "food", ["milk tea", "tea"], None, False),
    ("Yakiudon", "3F", "food", ["udon", "japanese"], None, False),
    ("Ssamjang Express", "3F", "food", ["korean"], None, False),
    ("Turks", "3F", "food", ["shawarma"], None, False),
    ("YoCoCo", "3F", "food", ["dessert"], None, False),
    ("DECS", "3F", "food", [], None, False),
    ("Kumori", "3F", "cafe", ["bakery", "japanese"], None, False),
    ("ASUS Concept Store", "4F", "electronics", ["laptop"], None, False),
    ("Lenovo Legion Store", "4F", "electronics", ["laptop", "gaming laptop"], None, False),
    ("Techno", "4F", "electronics", ["cellphone", "phone"], None, False),
    ("Mi Store", "4F", "electronics", ["xiaomi", "phone"], None, False),
    ("GameXtreme", "4F", "gaming", [], None, False),
    ("Nintendo Authorized Store", "4F", "gaming", ["switch"], None, False),
    ("FixHub Mobile", "4F", "phone_repair", [], 45, True),
    ("QuickFix Gadget Clinic", "4F", "phone_repair", ["tablet", "laptop repair"], 60, True),
    ("ScreenDoc", "4F", "phone_repair", ["screen replacement"], 30, True),
    ("SM Appliance Center", "AX", "appliances", [], None, False),
    ("Dyson", "AX", "appliances", ["vacuum"], None, False),
    ("Pet Express", "AX", "pet", [], None, False),
    ("BOS Shoes & Bags Repair", "AX", "shoe_repair", ["bag repair"], 30, False),
]


def project(latlon: list[tuple[float, float]], angle: float | None = None):
    lat0 = sum(p[0] for p in MAIN_LATLON) / len(MAIN_LATLON)
    lon0 = sum(p[1] for p in MAIN_LATLON) / len(MAIN_LATLON)
    kx = math.cos(math.radians(lat0)) * 111_320
    pts = [((lon - lon0) * kx, (lat0 - lat) * 110_540) for lat, lon in latlon]
    if angle is None:
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        sxx = sum((x - cx) ** 2 for x, _ in pts)
        syy = sum((y - cy) ** 2 for _, y in pts)
        sxy = sum((x - cx) * (y - cy) for x, y in pts)
        angle = 0.5 * math.atan2(2 * sxy, sxx - syy)
    c, s = math.cos(-angle), math.sin(-angle)
    return [(x * c - y * s, x * s + y * c) for x, y in pts], angle


def fit(pts):
    minx, maxx = min(p[0] for p in pts), max(p[0] for p in pts)
    miny, maxy = min(p[1] for p in pts), max(p[1] for p in pts)
    k = (WIDTH - 2 * MARGIN) / (maxx - minx)
    out = [(round((x - minx) * k + MARGIN, 1), round((y - miny) * k + MARGIN, 1)) for x, y in pts]
    height = round((maxy - miny) * k + 2 * MARGIN)
    return out, height, 1 / k


def inside(poly, x, y) -> bool:
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def rect_inside(poly, cx, cy, w, h) -> bool:
    return all(inside(poly, cx + dx, cy + dy) for dx in (-w / 2, w / 2) for dy in (-h / 2, h / 2))


class FloorLayout:
    """Corridor spine + two cross corridors; store slots on both sides."""

    def __init__(self, fid: str, poly, height: int):
        self.fid, self.poly, self.height = fid, poly, height
        self.nodes: list[dict] = []
        self.edges: list[list[str]] = []
        self.slots: list[tuple[float, float, str]] = []
        mid = self._best_spine_y()
        xs = [x for x in range(MARGIN, WIDTH - MARGIN + 1, STEP) if inside(poly, x, mid)]
        spine = [self._node(f"c{i}", x, mid) for i, x in enumerate(xs)]
        self.spine = spine
        for a, b in zip(spine, spine[1:]):
            self.edges.append([a, b])
        n = len(spine)
        self.junctions = [spine[n // 3], spine[(2 * n) // 3]] if n >= 6 else [spine[n // 2]]
        self.center = spine[n // 2]
        reserved = set(self.junctions) | {self.center}
        for j, junction in enumerate(self.junctions):
            jx = self._xy(junction)[0]
            for direction in (-1, 1):
                prev, k = junction, 1
                while inside(poly, jx, mid + direction * k * STEP) and inside(poly, jx, mid + direction * (k * STEP + 30)):
                    node = self._node(f"x{j}{'n' if direction < 0 else 's'}{k}", jx, mid + direction * k * STEP)
                    self.edges.append([prev, node])
                    for side in (-1, 1):
                        self._slot(jx + side * SLOT_OFFSET, mid + direction * k * STEP, node)
                    prev, k = node, k + 1
        for node in spine:
            if node in reserved:
                continue
            x, y = self._xy(node)
            for side in (-1, 1):
                self._slot(x, y + side * SLOT_OFFSET, node)

    def _best_spine_y(self) -> float:
        best, best_y = -1, self.height / 2
        for y in range(MARGIN + 60, self.height - MARGIN - 60, 4):
            count = sum(1 for x in range(MARGIN, WIDTH - MARGIN, STEP) if inside(self.poly, x, y))
            if count > best:
                best, best_y = count, y
        return best_y

    def _node(self, suffix: str, x: float, y: float) -> str:
        nid = f"{self.fid}-{suffix}"
        self.nodes.append({"id": nid, "floor": self.fid, "x": round(x, 1), "y": round(y, 1)})
        return nid

    def _xy(self, nid: str) -> tuple[float, float]:
        n = next(n for n in self.nodes if n["id"] == nid)
        return n["x"], n["y"]

    def _slot(self, cx: float, cy: float, node: str) -> None:
        overlaps = any(abs(cx - sx) < SLOT_W and abs(cy - sy) < SLOT_H for sx, sy, _ in self.slots)
        if not overlaps and rect_inside(self.poly, cx, cy, SLOT_W, SLOT_H):
            self.slots.append((cx, cy, node))

    def add_point(self, suffix: str, x: float, y: float, link: str) -> str:
        nid = self._node(suffix, x, y)
        self.edges.append([link, nid])
        return nid


def slug(name: str, floor: str) -> str:
    base = "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-")
    while "--" in base:
        base = base.replace("--", "-")
    return f"{base}-{floor.lower()}"


def build() -> dict:
    main_pts, angle = project(MAIN_LATLON)
    annex_pts, _ = project(ANNEX_LATLON, angle)
    # Fit both buildings in one frame so their scale matches, then split into floors.
    both, height, m_per_px = fit(main_pts + annex_pts)
    main_poly, annex_poly = both[:len(main_pts)], both[len(main_pts):]

    floors, nodes, edges, places, connectors, anchors = [], [], [], [], [], {}
    layouts: dict[str, FloorLayout] = {}
    for fid, name, level in MAIN_FLOORS:
        floors.append({"id": fid, "name": name, "level": level, "width": WIDTH, "height": height,
                       "scale_m_per_px": round(m_per_px, 4), "outline": [list(p) for p in main_poly]})
        layouts[fid] = FloorLayout(fid, main_poly, height)
    floors.append({"id": "AX", "name": "Annex", "level": 0, "width": WIDTH, "height": height,
                   "scale_m_per_px": round(m_per_px, 4), "outline": [list(p) for p in annex_poly]})
    layouts["AX"] = FloorLayout("AX", annex_poly, height)

    # Vertical connectors at the same spot on every main floor.
    stops: dict[str, dict[str, str]] = {k: {} for k in ("esc_a_up", "esc_a_dn", "esc_b_up", "esc_b_dn", "elev")}
    for fid, _, _ in MAIN_FLOORS:
        lay = layouts[fid]
        ja = lay.junctions[0]
        jb = lay.junctions[-1]
        ax, ay = lay._xy(ja)
        bx, by = lay._xy(jb)
        cx, cy = lay._xy(lay.center)
        stops["esc_a_up"][fid] = lay.add_point("esc-a-up", ax - 16, ay + 22, ja)
        stops["esc_a_dn"][fid] = lay.add_point("esc-a-dn", ax + 16, ay + 22, ja)
        stops["esc_b_up"][fid] = lay.add_point("esc-b-up", bx - 16, by + 22, jb)
        stops["esc_b_dn"][fid] = lay.add_point("esc-b-dn", bx + 16, by + 22, jb)
        stops["elev"][fid] = lay.add_point("el1", cx, cy - 22, lay.center)
    order = [f for f, _, _ in MAIN_FLOORS]
    connectors += [
        {"id": "esc-a-up", "name": "Escalator A", "kind": "escalator", "direction": "up",
         "stops": [stops["esc_a_up"][f] for f in order]},
        {"id": "esc-a-down", "name": "Escalator A", "kind": "escalator", "direction": "down",
         "stops": [stops["esc_a_dn"][f] for f in reversed(order)]},
        {"id": "esc-b-up", "name": "Escalator B", "kind": "escalator", "direction": "up",
         "stops": [stops["esc_b_up"][f] for f in order]},
        {"id": "esc-b-down", "name": "Escalator B", "kind": "escalator", "direction": "down",
         "stops": [stops["esc_b_dn"][f] for f in reversed(order)]},
        {"id": "elev-1", "name": "Elevator 1", "kind": "elevator", "direction": "both",
         "stops": [stops["elev"][f] for f in order]},
    ]
    # Annex walkway: from the GF spine end nearest the annex to the annex spine end nearest the main building.
    gf, ax_lay = layouts["GF"], layouts["AX"]
    acx = sum(p[0] for p in annex_poly) / len(annex_poly)
    gf_end = min((gf.spine[0], gf.spine[-1]), key=lambda n: abs(gf._xy(n)[0] - acx))
    mcx = sum(p[0] for p in main_poly) / len(main_poly)
    ax_end = min((ax_lay.spine[0], ax_lay.spine[-1]), key=lambda n: abs(ax_lay._xy(n)[0] - mcx))
    gx, gy = gf._xy(gf_end)
    gf_br = gf.add_point("br-annex", gx, gy - 24, gf_end)
    hx, hy = ax_lay._xy(ax_end)
    ax_br = ax_lay.add_point("br-main", hx, hy - 24, ax_end)
    connectors.append({"id": "walk-annex", "name": "Annex Walkway", "kind": "bridge", "direction": "both",
                       "stops": [gf_br, ax_br], "seconds": 90})

    # Restrooms first (west end of each floor), then stores in table order.
    by_floor: dict[str, list] = {f: [] for f in layouts}
    for fid in layouts:
        by_floor[fid].append(("Restroom", fid, "restroom", [], None, False))
    for row in STORES:
        by_floor[row[1]].append(row)
    used_ids: set[str] = set()
    for fid, rows in by_floor.items():
        slots = sorted(layouts[fid].slots, key=lambda s: (s[0], s[1]))
        if len(rows) > len(slots):
            sys.exit(f"{fid}: {len(rows)} places but only {len(slots)} slots")
        spread = len(slots) / len(rows)
        for i, (name, _, cat, extra, minutes, fictional) in enumerate(rows):
            cx, cy, node = slots[int(i * spread)]
            pid = slug(name, fid)
            while pid in used_ids:
                pid += "-2"
            used_ids.add(pid)
            place = {"id": pid, "name": name, "floor": fid,
                     "rect": [round(cx - SLOT_W / 2, 1), round(cy - SLOT_H / 2, 1), SLOT_W, SLOT_H],
                     "node": node, "category": cat, "tags": CATEGORY_TAGS[cat] + extra}
            if minutes:
                place["service"] = {"duration_min": minutes}
            if fictional:
                place["fictional"] = True
            places.append(place)

    for lay in layouts.values():
        nodes += lay.nodes
        edges += lay.edges

    def node_of(pid: str) -> str:
        return next(p["node"] for p in places if p["id"] == pid)

    east_gf = max(gf.spine, key=lambda n: gf._xy(n)[0])
    anchors = [
        {"id": "gf-mrt-entrance", "label": "GF · MRT/Ayala Entrance", "floor": "GF", "node": east_gf, "heading_deg": 270},
        {"id": "lg-supermarket", "label": "LG · SM Supermarket", "floor": "LG", "node": node_of("sm-supermarket-lg"), "heading_deg": 0},
        {"id": "2f-escalator-a", "label": "2F · Escalator A", "floor": "2F", "node": stops["esc_a_up"]["2F"], "heading_deg": 90},
        {"id": "3f-foodcourt", "label": "3F · Foodcourt", "floor": "3F", "node": node_of("sm-makati-foodcourt-3f"), "heading_deg": 0},
        {"id": "4f-cyberzone-entrance", "label": "4F · Cyberzone Entrance", "floor": "4F", "node": stops["esc_a_up"]["4F"], "heading_deg": 90},
        {"id": "ax-entrance", "label": "Annex · Walkway Entrance", "floor": "AX", "node": ax_br, "heading_deg": 90},
    ]
    return {
        "mall": {"id": "sm-makati", "name": "SM Makati",
                 "note": "Store names from public listings; layout reconstructed."},
        "floors": floors, "nodes": nodes, "edges": edges, "connectors": connectors, "places": places,
        "category_defaults": {k: {"duration_min": d, "async": a} for k, (d, a) in CATEGORY_DEFAULTS.items()},
        "anchors": anchors,
    }


def main() -> None:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.path.insert(0, str(ROOT / "server"))
    from mappy.mall import load_mall

    m = load_mall(OUT)
    per_floor = {f: sum(1 for p in m.places.values() if p.floor == f) for f in m.floor_order()}
    print(f"wrote {OUT.relative_to(ROOT)}: {len(m.places)} places {per_floor}, {len(m.nodes)} nodes, "
          f"{m.floors['GF'].height:.0f}px tall, {m.floors['GF'].scale:.3f} m/px")


if __name__ == "__main__":
    main()

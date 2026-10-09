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

MAIN_FLOORS = [("LG", "Lower Ground", -1), ("GF", "Ground Floor", 0), ("2F", "2nd Floor", 1),
               ("3F", "3rd Floor", 2), ("4F", "4th Floor (Cyberzone)", 3)]

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



# Stores that occupy several storefront units (anchor stores look big, like in a real mall).
UNITS = {
    "SM Supermarket": 3, "The SM Store": 3, "SM Makati Foodcourt": 3, "SM Appliance Center": 2,
    "H&M": 2, "Uniqlo": 2,
}


def project(latlon, angle=None):
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
    return out, round((maxy - miny) * k + 2 * MARGIN), 1 / k


def inside(poly, x, y) -> bool:
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def rect_inside(poly, x, y, w, h) -> bool:
    xs = (x + 2, x + w / 2, x + w - 2)
    ys = (y + 2, y + h / 2, y + h - 2)
    return all(inside(poly, px, py) for px in xs for py in ys)


CORRIDOR_HALF = 34      # corridor is 68 px wide
ATRIUM_HALF_W = 66
ATRIUM_HALF_H = 96
LIFT_HALF_W = 32
UNIT_W = 68
UNIT_GAP = 3
NODE_STEP = 60
MAX_DEPTH = 150
MIN_DEPTH = 44
WALL_GAP = 8


class MallFloor:
    """One floor: a long corridor with storefront units on both sides, escalator atriums, a lift lobby."""

    def __init__(self, fid: str, poly, height: int, atria=(0.28, 0.72), lift=0.5):
        self.fid, self.poly = fid, poly
        self.nodes: list[dict] = []
        self.edges: list[list[str]] = []
        self.mid = self._spine_y(height)
        self.x0, self.x1 = self._spine_extent()
        span = self.x1 - self.x0
        xs = [self.x0 + 20 + i * NODE_STEP for i in range(int((span - 40) // NODE_STEP) + 1)]
        self.spine = [self._node(f"c{i}", x, self.mid) for i, x in enumerate(xs)]
        for a, b in zip(self.spine, self.spine[1:]):
            self.edges.append([a, b])
        self.atria = [self._snap(self.x0 + f * span) for f in atria] if atria else []
        self.lift_x = self._snap(self.x0 + lift * span)
        self.walkways = [[self.x0, self.mid - CORRIDOR_HALF, span, 2 * CORRIDOR_HALF]]
        self.atrium_rects = []
        for ax in self.atria:
            r = [ax - ATRIUM_HALF_W, self.mid - ATRIUM_HALF_H, 2 * ATRIUM_HALF_W, 2 * ATRIUM_HALF_H]
            self.walkways.append(r)
            self.atrium_rects.append(r)
        self.lift_rect = [self.lift_x - LIFT_HALF_W, self.mid - CORRIDOR_HALF - 44, 2 * LIFT_HALF_W, 46]
        self.walkways.append(self.lift_rect)
        self.units = {-1: self._row(-1), 1: self._row(1)}

    def _spine_y(self, height) -> float:
        best, best_y = -1, height / 2
        for y in range(MARGIN + 80, height - MARGIN - 80, 4):
            count = sum(1 for x in range(MARGIN, WIDTH - MARGIN, 8) if inside(self.poly, x, y))
            room = sum(1 for x in range(MARGIN, WIDTH - MARGIN, 8)
                       if inside(self.poly, x, y - 110) and inside(self.poly, x, y + 110))
            score = count + room
            if score > best:
                best, best_y = score, y
        return best_y

    def _spine_extent(self):
        run, best, start = 0, (0, 0, 0), None
        for x in range(0, WIDTH + 1, 4):
            ok = all(inside(self.poly, x, self.mid + d) for d in (-CORRIDOR_HALF, 0, CORRIDOR_HALF))
            if ok:
                start = x if start is None else start
                if x - start > best[0]:
                    best = (x - start, start, x)
            else:
                start = None
        return best[1] + 6, best[2] - 6

    def _snap(self, x) -> float:
        return min((self._xy(n)[0] for n in self.spine), key=lambda sx: abs(sx - x))

    def _node(self, suffix, x, y) -> str:
        nid = f"{self.fid}-{suffix}"
        self.nodes.append({"id": nid, "floor": self.fid, "x": round(x, 1), "y": round(y, 1)})
        return nid

    def _xy(self, nid):
        n = next(n for n in self.nodes if n["id"] == nid)
        return n["x"], n["y"]

    def nearest_spine(self, x) -> str:
        return min(self.spine, key=lambda n: abs(self._xy(n)[0] - x))

    def add_point(self, suffix, x, y) -> str:
        nid = self._node(suffix, x, y)
        self.edges.append([self.nearest_spine(x), nid])
        return nid

    def _blocked(self, side: int) -> list[tuple[float, float]]:
        blocks = [(ax - ATRIUM_HALF_W, ax + ATRIUM_HALF_W) for ax in self.atria]
        if side < 0:
            blocks.append((self.lift_x - LIFT_HALF_W - 2, self.lift_x + LIFT_HALF_W + 2))
        return sorted(blocks)

    def _wall(self, x: float, side: int, edge: float | None = None) -> float:
        """Distance from a frontage line to the building wall, straight out at column x."""
        edge = self.mid + side * CORRIDOR_HALF if edge is None else edge
        d = 0
        while d < MAX_DEPTH + 40 and inside(self.poly, x, edge + side * (d + 3)):
            d += 3
        return d

    def _units_between(self, a: float, b: float, side: int, edge: float, n: int | None = None):
        length = b - a
        if length < UNIT_W * 0.6:
            return []
        n = n or max(1, round(length / UNIT_W))
        w = (length - (n - 1) * UNIT_GAP) / n
        out = []
        for i in range(n):
            ux = a + i * (w + UNIT_GAP)
            depth = min(self._wall(cx, side, edge) for cx in (ux + 4, ux + w / 2, ux + w - 4)) - WALL_GAP
            depth = min(depth, MAX_DEPTH)
            if depth >= MIN_DEPTH:
                y = edge - depth if side < 0 else edge
                out.append([round(ux, 1), round(y, 1), round(w, 1), round(depth, 1)])
        return out

    def _row(self, side: int) -> list[list[float]]:
        """Storefronts along one side: units lining the corridor between atria and the lift, plus
        units ringing each atrium. Each reaches back toward the building wall."""
        corridor_edge = self.mid + side * CORRIDOR_HALF
        atrium_edge = self.mid + side * ATRIUM_HALF_H
        units, x = [], self.x0
        for a, b in self._blocked(side):
            units += self._units_between(x, a - UNIT_GAP, side, corridor_edge)
            if any(abs((a + b) / 2 - ax) < 1 for ax in self.atria):
                units += self._units_between(a, b, side, atrium_edge, n=2)
            x = max(x, b + UNIT_GAP)
        units += self._units_between(x, self.x1, side, corridor_edge)
        return sorted(units, key=lambda u: u[0])

    def _in_atrium_band(self, x) -> bool:
        return any(abs(x - ax) < ATRIUM_HALF_W for ax in self.atria)

    def runs(self, side: int) -> list[list[list[float]]]:
        """Group a row's units into runs of physically adjacent storefronts."""
        out: list[list[list[float]]] = []
        for u in self.units[side]:
            prev = out[-1][-1] if out else None
            same_frontage = prev is not None and abs(frontage(prev, side) - frontage(u, side)) < 1
            if prev and same_frontage and abs(prev[0] + prev[2] + UNIT_GAP - u[0]) < 1.5:
                out[-1].append(u)
            else:
                out.append([u])
        return out


def frontage(u: list[float], side: int) -> float:
    """The y of the storefront's open side (the edge facing the walkway)."""
    return u[1] if side > 0 else u[1] + u[3]


def merge(units: list[list[float]], side: int) -> list[float]:
    x = units[0][0]
    w = units[-1][0] + units[-1][2] - x
    depth = min(u[3] for u in units)
    y = units[0][1] if side > 0 else units[0][1] + units[0][3] - depth
    return [x, y, w, depth]


def allocate(floor: MallFloor, rows: list[tuple]) -> tuple[list[tuple], list[list[float]]]:
    """Give each store adjacent units (anchors get several); leftover units become unnamed storefronts."""
    runs = [(side, run) for side in (-1, 1) for run in floor.runs(side)]
    free = [(side, list(run)) for side, run in runs]
    placed = []
    ordered = sorted(rows, key=lambda r: -UNITS.get(r[0], 1))
    for row in ordered:
        need = UNITS.get(row[0], 1)
        options = [(i, side, run) for i, (side, run) in enumerate(free) if len(run) >= need]
        if not options:
            sys.exit(f"{floor.fid}: no room for {row[0]} ({need} units)")
        # Spread stores out: take from the run with the most free units, preferring the north row for anchors.
        i, side, run = max(options, key=lambda o: (len(o[2]), -o[1] if need > 1 else 0))
        take, rest = run[:need], run[need:]
        free[i] = (side, rest)
        placed.append((row, merge(take, side), side))
    blanks = [u for _, run in free for u in run]
    return placed, blanks


def slug(name: str, floor: str) -> str:
    base = "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-")
    while "--" in base:
        base = base.replace("--", "-")
    return f"{base}-{floor.lower()}"


def build() -> dict:
    main_raw, angle = project(MAIN_LATLON)
    annex_raw, _ = project(ANNEX_LATLON, angle)
    main_poly, main_h, main_scale = fit(main_raw)
    annex_poly, annex_h, annex_scale = fit(annex_raw)

    floors, nodes, edges, places, connectors = [], [], [], [], []
    layouts: dict[str, MallFloor] = {}
    for fid, name, level in MAIN_FLOORS:
        layouts[fid] = MallFloor(fid, main_poly, main_h)
    layouts["AX"] = MallFloor("AX", annex_poly, annex_h, atria=(), lift=0.5)

    # Escalators sit in the two atria (A west, B east): up on the north side, down on the south side.
    stops = {k: {} for k in ("a_up", "a_dn", "b_up", "b_dn", "lift")}
    for fid, _, _ in MAIN_FLOORS:
        lay = layouts[fid]
        ax, bx = lay.atria
        stops["a_up"][fid] = lay.add_point("esc-a-up", ax, lay.mid - 64)
        stops["a_dn"][fid] = lay.add_point("esc-a-dn", ax, lay.mid + 64)
        stops["b_up"][fid] = lay.add_point("esc-b-up", bx, lay.mid - 64)
        stops["b_dn"][fid] = lay.add_point("esc-b-dn", bx, lay.mid + 64)
        stops["lift"][fid] = lay.add_point("lift", lay.lift_x, lay.mid - CORRIDOR_HALF - 22)
    order = [f for f, _, _ in MAIN_FLOORS]
    connectors += [
        {"id": "esc-a-up", "name": "Escalator A", "kind": "escalator", "direction": "up",
         "stops": [stops["a_up"][f] for f in order]},
        {"id": "esc-a-down", "name": "Escalator A", "kind": "escalator", "direction": "down",
         "stops": [stops["a_dn"][f] for f in reversed(order)]},
        {"id": "esc-b-up", "name": "Escalator B", "kind": "escalator", "direction": "up",
         "stops": [stops["b_up"][f] for f in order]},
        {"id": "esc-b-down", "name": "Escalator B", "kind": "escalator", "direction": "down",
         "stops": [stops["b_dn"][f] for f in reversed(order)]},
        {"id": "elev-1", "name": "Elevator", "kind": "elevator", "direction": "both",
         "stops": [stops["lift"][f] for f in order]},
    ]
    # Annex walkway from the GF corridor end nearest the annex.
    annex_cx = sum(p[0] for p in annex_raw) / len(annex_raw)
    main_cx = sum(p[0] for p in main_raw) / len(main_raw)
    gf, ax_lay = layouts["GF"], layouts["AX"]
    gf_end = gf.spine[-1] if annex_cx > main_cx else gf.spine[0]
    ax_end = ax_lay.spine[0] if annex_cx > main_cx else ax_lay.spine[-1]
    gx, gy = gf._xy(gf_end)
    gf_br = gf.add_point("walk-annex", gx + (14 if annex_cx > main_cx else -14), gy)
    hx, hy = ax_lay._xy(ax_end)
    ax_br = ax_lay.add_point("walk-main", hx + (-14 if annex_cx > main_cx else 14), hy)
    connectors.append({"id": "walk-annex", "name": "Annex Walkway", "kind": "bridge", "direction": "both",
                       "stops": [gf_br, ax_br], "seconds": 60})

    by_floor: dict[str, list] = {f: [("Restrooms", f, "restroom", [], None, False)] for f in layouts}
    for row in STORES:
        by_floor[row[1]].append(row)
    used: set[str] = set()
    for fid, rows in by_floor.items():
        lay = layouts[fid]
        placed, blanks = allocate(lay, rows)
        for k, ((name, _, cat, extra, minutes, fictional), rect, side) in enumerate(placed):
            pid = slug(name, fid)
            while pid in used:
                pid += "-2"
            used.add(pid)
            door_x = rect[0] + rect[2] / 2
            door_y = lay.mid + side * (CORRIDOR_HALF - 6)
            door = lay.add_point(f"door{k}", door_x, door_y)
            place = {"id": pid, "name": name, "floor": fid, "rect": rect, "node": door,
                     "category": cat, "tags": CATEGORY_TAGS[cat] + extra}
            if minutes:
                place["service"] = {"duration_min": minutes}
            if fictional:
                place["fictional"] = True
            places.append(place)
        poly, h, scale = (annex_poly, annex_h, annex_scale) if fid == "AX" else (main_poly, main_h, main_scale)
        name = "Annex" if fid == "AX" else next(n for f, n, _ in MAIN_FLOORS if f == fid)
        level = 0 if fid == "AX" else next(lv for f, _, lv in MAIN_FLOORS if f == fid)
        floors.append({"id": fid, "name": name, "level": level, "width": WIDTH, "height": h,
                       "scale_m_per_px": round(scale, 4), "outline": [list(p) for p in poly],
                       "walkways": lay.walkways, "atria": lay.atrium_rects, "blanks": blanks})
        nodes += lay.nodes
        edges += lay.edges

    def node_of(pid):
        return next(p["node"] for p in places if p["id"] == pid)

    gf_east = max(gf.spine, key=lambda n: gf._xy(n)[0])
    anchors = [
        {"id": "gf-mrt-entrance", "label": "Ground Floor, Ayala MRT entrance", "floor": "GF", "node": gf_east, "heading_deg": 270},
        {"id": "lg-supermarket", "label": "Lower Ground, SM Supermarket", "floor": "LG", "node": node_of("sm-supermarket-lg"), "heading_deg": 0},
        {"id": "2f-escalator-a", "label": "2nd Floor, Escalator A", "floor": "2F", "node": stops["a_up"]["2F"], "heading_deg": 90},
        {"id": "3f-foodcourt", "label": "3rd Floor, Foodcourt", "floor": "3F", "node": node_of("sm-makati-foodcourt-3f"), "heading_deg": 0},
        {"id": "4f-cyberzone-entrance", "label": "Cyberzone entrance, 4th Floor", "floor": "4F", "node": stops["a_up"]["4F"], "heading_deg": 90},
        {"id": "ax-entrance", "label": "Annex entrance", "floor": "AX", "node": ax_br, "heading_deg": 90},
    ]
    return portrait({
        "mall": {"id": "sm-makati", "name": "SM Makati",
                 "note": "Store names from public listings. Layout reconstructed for this demo."},
        "floors": floors, "nodes": nodes, "edges": edges, "connectors": connectors, "places": places,
        "category_defaults": {k: {"duration_min": d, "async": a} for k, (d, a) in CATEGORY_DEFAULTS.items()},
        "anchors": anchors,
    })


def portrait(data: dict) -> dict:
    """Turn every floor 90 degrees so the long walkway runs top to bottom, which fits phone screens
    and makes storefronts wide enough for their names."""
    heights = {f["id"]: f["height"] for f in data["floors"]}

    def pt(fid, x, y):
        return [round(heights[fid] - y, 1), round(x, 1)]

    def rect(fid, r):
        x, y, w, h = r
        return [round(heights[fid] - y - h, 1), round(x, 1), h, w]

    for f in data["floors"]:
        fid = f["id"]
        f["outline"] = [pt(fid, x, y) for x, y in f["outline"]]
        for key in ("walkways", "atria", "blanks"):
            f[key] = [rect(fid, r) for r in f[key]]
        f["width"], f["height"] = f["height"], f["width"]
    for n in data["nodes"]:
        n["x"], n["y"] = pt(n["floor"], n["x"], n["y"])
    for p in data["places"]:
        p["rect"] = rect(p["floor"], p["rect"])
    return data


def main() -> None:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.path.insert(0, str(ROOT / "server"))
    from mappy.mall import load_mall

    m = load_mall(OUT)
    per_floor = {f: sum(1 for p in m.places.values() if p.floor == f) for f in m.floor_order()}
    blanks = {f["id"]: len(f["blanks"]) for f in data["floors"]}
    print(f"wrote {OUT.relative_to(ROOT)}: {len(m.places)} places {per_floor}, blank units {blanks}, "
          f"{len(m.nodes)} nodes, GF {m.floors['GF'].height:.0f}px tall at {m.floors['GF'].scale:.3f} m/px")


if __name__ == "__main__":
    main()

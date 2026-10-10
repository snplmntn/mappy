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
# Floors checked against the "SM MAKATI Walking Tour 2026" video (Where In PH, uploaded 2026-06-04) and the
# SM Store directory pylons it shows. "Not seen" rows are unconfirmed, not known closed: the video never visits the
# Annex, the LG mall corridors or Cyberzone.
STORES = [
    # LG: supermarket and Market Food Hall, reached from GF by travelators.
    ("SM Supermarket", "LG", "grocery", [], None, False),
    ("Market Food Hall", "LG", "food", ["food court", "foodcourt", "food hall"], None, False),
    ("Goldilocks", "LG", "food", ["cake", "bakery"], None, False),
    ("Kumori", "LG", "cafe", ["bakery", "japanese"], None, False),
    ("Sizzling Plate", "LG", "food", ["sizzling", "steak"], None, False),
    ("Cucina Norte", "LG", "food", ["pasta"], None, False),
    ("Goto Pilipinas", "LG", "food", ["goto", "lugaw", "arroz caldo"], None, False),
    ("Dipping Dumpling", "LG", "food", ["dumplings", "chinese"], None, False),
    ("Ssamjang Express", "LG", "food", ["korean"], None, False),
    ("The Chinese Kitchen", "LG", "food", ["chinese"], None, False),
    ("Chooks-to-Go", "LG", "food", ["chicken", "manok", "lechon manok"], None, False),
    # Listed food tenants not seen in the video. No food court was seen on 3F, so they go with the LG food hall.
    ("Kyu Kyu Ramen 99", "LG", "food", ["ramen", "japanese"], None, False),
    ("Delifrance", "LG", "cafe", ["bread", "sandwich"], None, False),
    ("Brownies Unlimited", "LG", "food", ["brownies", "dessert"], None, False),
    ("Fuel Burgers", "LG", "food", ["burger"], None, False),
    ("Gong Cha", "LG", "food", ["milk tea", "tea"], None, False),
    ("Yakiudon", "LG", "food", ["udon", "japanese"], None, False),
    ("Turks", "LG", "food", ["shawarma"], None, False),
    ("DECS", "LG", "food", [], None, False),
    # Not seen: the video never enters the LG mall corridors.
    ("Western Union", "LG", "remittance", [], None, False),
    ("DHL Express", "LG", "courier", [], None, False),
    ("Mr. Quickie", "LG", "shoe_repair", ["susi", "key", "takong"], 20, False),
    ("BDO ATM", "LG", "atm", [], None, False),
    # GF
    ("The SM Store", "GF", "department_store", [], None, False),
    ("H&M", "GF", "clothing", [], None, False),
    ("Uniqlo", "GF", "clothing", [], None, False),
    ("Crate & Barrel", "GF", "home", ["kitchen", "furniture"], None, False),
    ("Pet Express", "GF", "pet", [], None, False),
    ("The Body Shop", "GF", "beauty", ["body wash", "lotion"], None, False),
    ("Sunnies Face", "GF", "beauty", [], None, False),
    ("Shiseido", "GF", "beauty", [], None, False),
    ("NARS", "GF", "beauty", [], None, False),
    ("MAC", "GF", "beauty", ["lipstick"], None, False),
    ("Clinique", "GF", "beauty", [], None, False),
    ("Innisfree", "GF", "beauty", ["korean skincare"], None, False),
    ("BreadTalk", "GF", "food", ["bread", "bakery"], None, False),
    ("Starbucks", "GF", "cafe", ["frappuccino"], None, False),
    ("BDO", "GF", "bank", [], None, False),
    ("BDO ATM", "GF", "atm", [], None, False),
    ("La Botica", "GF", "pharmacy", [], None, False),
    ("SipYO Coco Fluff", "GF", "food", ["ice cream", "buko", "dessert"], None, False),
    # 2F: loop around the central void; Cyberzone is on this level per the directory pylons.
    ("Sports Central", "2F", "clothing", ["sports", "adidas", "nike", "rubber shoes"], None, False),
    ("KLAD", "2F", "accessories", ["jewelry", "alahas"], None, False),
    ("@Tokyo", "2F", "accessories", ["bag", "japanese"], None, False),
    ("JINS", "2F", "accessories", ["eyeglasses", "salamin"], None, False),
    ("TW Steel", "2F", "accessories", ["watch", "relo"], None, False),
    ("Citizen", "2F", "accessories", ["watch", "relo"], None, False),
    ("Tissot", "2F", "accessories", [], None, False),
    ("ECCO", "2F", "shoes", [], None, False),
    ("Levi's", "2F", "clothing", ["jeans", "maong"], None, False),
    ("Kultura Filipino", "2F", "gift", ["filipino", "barong"], None, False),
    ("Seattle's Best Coffee", "2F", "cafe", [], None, False),
    ("Miniso", "2F", "home", ["cute", "gift"], None, False),
    ("Sfera", "2F", "clothing", [], None, False),
    ("Dear Flora", "2F", "clothing", [], None, False),
    ("Crocs", "2F", "shoes", [], None, False),
    ("Wenger", "2F", "accessories", [], None, False),
    ("Broadway Gems", "2F", "accessories", [], None, False),
    ("PaperDollzCo", "2F", "books_stationery", [], None, False),
    ("Buttons & Wrap", "2F", "gift", ["gift wrap"], None, False),
    ("VMV Hypoallergenics", "2F", "beauty", [], None, False),
    ("ASUS Concept Store", "2F", "electronics", ["laptop", "cyberzone"], None, False),
    ("Lenovo Legion Store", "2F", "electronics", ["laptop", "gaming laptop", "cyberzone"], None, False),
    ("Techno", "2F", "electronics", ["cellphone", "phone", "cyberzone"], None, False),
    ("GameXtreme", "2F", "gaming", ["cyberzone"], None, False),
    ("Nintendo Authorized Store", "2F", "gaming", ["switch", "cyberzone"], None, False),
    ("FixHub Mobile", "2F", "phone_repair", ["cyberzone"], 45, True),
    ("QuickFix Gadget Clinic", "2F", "phone_repair", ["tablet", "laptop repair", "cyberzone"], 60, True),
    ("ScreenDoc", "2F", "phone_repair", ["screen replacement", "cyberzone"], 30, True),
    # 3F
    ("ACE Hardware", "3F", "home", ["hardware", "tools", "pako"], None, False),
    ("Watsons", "3F", "pharmacy", ["skincare", "shampoo"], None, False),
    ("Alfamart", "3F", "grocery", ["convenience store", "snacks"], None, False),
    ("Mi Store", "3F", "electronics", ["xiaomi", "phone"], None, False),
    ("Decathlon", "3F", "clothing", ["sports", "gym", "bike"], None, False),
    ("Ideal Vision Center", "3F", "accessories", ["eyeglasses", "salamin", "optical"], None, False),
    ("Mary Grace Cafe", "3F", "cafe", ["ensaymada"], None, False),
    ("Auntie Anne's", "3F", "food", ["pretzel"], None, False),
    ("Zus Coffee", "3F", "cafe", [], None, False),
    ("Gotcha", "3F", "cafe", ["milk tea", "tea"], None, False),
    ("Carmen's Best", "3F", "food", ["ice cream", "dessert"], None, False),
    ("YoCoCo", "3F", "food", ["dessert"], None, False),
    ("Kiehl's", "3F", "beauty", [], None, False),
    ("Jo Malone London", "3F", "beauty", ["perfume", "pabango"], None, False),
    ("Lancome", "3F", "beauty", [], None, False),
    # 4F
    ("SM Appliance Center", "4F", "appliances", [], None, False),
    ("TCL", "4F", "appliances", ["tv", "television"], None, False),
    ("David's Salon", "4F", "beauty", ["haircut", "gupit", "salon"], None, False),
    ("Honey Graze Bakery + Kitchen", "4F", "food", ["bakery"], None, False),
    ("Lojel", "4F", "accessories", ["luggage", "maleta"], None, False),
    # 5F: SM Store home floor.
    ("SM Home", "5F", "home", ["bedding", "kitchen"], None, False),
    ("ACE Express", "5F", "home", ["hardware", "tools"], None, False),
    # Annex: not visited in the video.
    ("Dyson", "AX", "appliances", ["vacuum"], None, False),
    ("BOS Shoes & Bags Repair", "AX", "shoe_repair", ["bag repair"], 30, False),
]




from shapely.geometry import LineString, MultiPoint, Point, Polygon, box
from shapely.ops import nearest_points, polylabel, unary_union, voronoi_diagram

M_PER_PX = 0.15          # every floor uses the same scale, so distances are real
MARGIN = 40
MAIN_FLOORS = [("LG", "Lower Ground", -1), ("GF", "Ground Floor", 0), ("2F", "2nd Floor", 1),
               ("3F", "3rd Floor", 2), ("4F", "4th Floor", 3), ("5F", "5th Floor", 4)]
MAIN = dict(depth=110, corridor=56, unit_len=96)       # ~16 m deep stores, ~8 m walkways, ~10 m frontages
ANNEX = dict(depth=62, corridor=40, unit_len=80)
CROSSES = [(0.26, 58, "atrium"), (0.5, 26, "lift"), (0.74, 58, "atrium")]
# Main floors loop around one long central void (seen in the 2026 walk-through). Lower Ground sits under it.
VOID = dict(frac=0.62, width=110)              # ~60% of the core's length, ~16 m across
VOID_BANKS = (0.3, 0.72)                       # escalator banks A and B, as fractions along the void
VOID_TRAVELATOR = 0.1                          # travelators between GF and the LG supermarket entrance
ESCALATOR_FLOORS = {"GF", "2F", "3F", "4F", "5F"}
TRAVELATOR_FLOORS = {"LG", "GF"}
MITRE = dict(join_style="mitre", mitre_limit=3.0)
NODE_STEP = 30
# Stores that span several storefronts, and where they go.
PERIMETER_ANCHORS = {"SM Supermarket": 9, "The SM Store": 7, "SM Appliance Center": 5, "H&M": 2, "Uniqlo": 2,
                     "SM Home": 4, "ACE Hardware": 2}
ISLAND_ANCHORS = {"Market Food Hall"}


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


def portrait_px(pts_m):
    """Meters with the long axis horizontal -> pixels with the long axis vertical (fits phones)."""
    rot = [(-y, x) for x, y in pts_m]
    minx, miny = min(p[0] for p in rot), min(p[1] for p in rot)
    out = [(round((x - minx) / M_PER_PX + MARGIN, 1), round((y - miny) / M_PER_PX + MARGIN, 1)) for x, y in rot]
    w = max(p[0] for p in out) + MARGIN
    h = max(p[1] for p in out) + MARGIN
    return out, round(w), round(h), (minx, miny)


def largest(g):
    if g is None or g.is_empty:
        return None
    if g.geom_type == "Polygon":
        return g
    polys = [p for p in getattr(g, "geoms", []) if p.geom_type == "Polygon"]
    return max(polys, key=lambda p: p.area) if polys else None


def coords(poly, tol=0.6):
    return [[round(x, 1), round(y, 1)] for x, y in poly.simplify(tol).exterior.coords[:-1]]


def svg_path(geom):
    """Polygon/MultiPolygon (with holes) as an SVG path; render with fill-rule evenodd."""
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    parts = []
    for p in polys:
        for ring in [p.exterior, *p.interiors]:
            pts = list(ring.simplify(0.6).coords)[:-1]
            parts.append("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + "Z")
    return "".join(parts)


class Unit:
    def __init__(self, poly, door, zone, pos, island=None):
        self.poly, self.door, self.zone, self.pos, self.island = poly, door, zone, pos, island


class Plan:
    """A floor laid out from the building outline: storefronts along every exterior wall, a walkway loop
    following the outline, and (if there is room) a core with cross walkways, atria and island stores."""

    def __init__(self, fid, outline, depth, corridor, unit_len, crosses=(), entrances=(), void=None):
        self.fid = fid
        self.B = B = Polygon(outline).buffer(0)
        self.corridor = corridor
        ring_out = largest(B.buffer(-depth, **MITRE))
        core = largest(ring_out.buffer(-corridor, **MITRE))
        self.core = core if core is not None and core.area > 6000 else None
        self.ring_out = ring_out
        walk = ring_out if self.core is None else ring_out.difference(self.core)
        # Cross walkways through the core: atria with escalators, and a lift lobby.
        self.crosses = []
        self.void = None
        islands = []
        if self.core is not None and void is not None:
            # A long void down the middle with a balcony walkway around it, joined to the outer walkway
            # at both ends and both sides. The core left over becomes four blocks of stores.
            minx, miny, maxx, maxy = self.core.bounds
            cx, cy = self.core.centroid.x, self.core.centroid.y
            half_len, half_w = void["frac"] * (maxy - miny) / 2, void["width"] / 2
            self.void = box(cx - half_w, cy - half_len, cx + half_w, cy + half_len).buffer(-12).buffer(12)
            self.void_open = void.get("open", False)
            balcony = self.void.buffer(corridor, **MITRE)
            self.balcony_line = self.void.buffer(corridor / 2, **MITRE).exterior
            center = largest(ring_out.buffer(-corridor / 2, **MITRE))
            self.links = []
            for sx, sy, dx, dy in ((cx, cy - half_len - corridor / 2, 0, -1), (cx, cy + half_len + corridor / 2, 0, 1),
                                   (cx - half_w - corridor / 2, cy, -1, 0), (cx + half_w + corridor / 2, cy, 1, 0)):
                hit = LineString([(sx, sy), (sx + dx * 2000, sy + dy * 2000)]).intersection(center.exterior)
                end = nearest_points(hit, Point(sx, sy))[0]
                self.links.append(LineString([(sx, sy), (end.x, end.y)]))
            bands = unary_union([ln.buffer(corridor / 2, cap_style="flat") for ln in self.links])
            walk = walk.union(balcony.union(bands).intersection(ring_out))
            if not self.void_open:
                walk = walk.difference(self.void)
            rest = self.core.difference(balcony).difference(bands)
            islands = [g for g in getattr(rest, "geoms", [rest]) if g.geom_type == "Polygon" and g.area > 2500]
            self.center_line = center.exterior
        elif self.core is not None:
            minx, miny, maxx, maxy = self.core.bounds
            center = largest(ring_out.buffer(-corridor / 2, **MITRE))
            for frac, half, kind in crosses:
                y = miny + frac * (maxy - miny)
                cut = box(minx - 60, y - half, maxx + 60, y + half)
                band = cut.intersection(self.core)
                line = LineString([(B.bounds[0] - 50, y), (B.bounds[2] + 50, y)]).intersection(center)
                if line.geom_type != "LineString":
                    line = max(line.geoms, key=lambda g: g.length)
                self.crosses.append({"y": y, "half": half, "kind": kind, "band": band, "cut": cut, "line": line})
                walk = walk.union(band)
            rest = self.core.difference(unary_union([c["cut"] for c in self.crosses]))
            islands = [g for g in getattr(rest, "geoms", [rest]) if g.area > 2500]
            self.center_line = center.exterior
        else:
            minx, miny, maxx, maxy = ring_out.bounds
            spine = LineString([((minx + maxx) / 2, miny - 20), ((minx + maxx) / 2, maxy + 20)]).intersection(ring_out)
            self.center_line = spine if spine.geom_type == "LineString" else max(spine.geoms, key=lambda g: g.length)
        perimeter = B.difference(ring_out)
        # Entrances cut through the storefront band to the outside.
        self.entrances = []
        strips = []
        for name, target in entrances:
            pb = nearest_points(B.exterior, Point(target))[0]
            pr = nearest_points(ring_out.exterior, pb)[0]
            dx, dy = pb.x - pr.x, pb.y - pr.y
            n = math.hypot(dx, dy) or 1
            ux, uy = dx / n, dy / n
            strip = LineString([(pr.x - ux * 6, pr.y - uy * 6), (pb.x + ux * 30, pb.y + uy * 30)]).buffer(corridor / 2, cap_style="flat")
            strips.append(strip)
            perimeter = perimeter.difference(strip)
            walk = walk.union(strip.intersection(B))
            self.entrances.append((name, (pb.x - ux * 14, pb.y - uy * 14)))
        self.walk = walk
        # Storefront units: Voronoi cells around frontage points along each walkway edge.
        self.units: list[Unit] = []
        edge = ring_out.exterior
        count = max(4, int(edge.length // unit_len))
        seeds = []
        for i in range(count):
            d = i * edge.length / count
            p = edge.interpolate(d)
            if not any(st.buffer(8).contains(p) for st in strips):
                seeds.append((d, p))
        for d, p, cell in self._cells(seeds, perimeter):
            self.units.append(Unit(cell, (p.x, p.y), "perimeter", d))
        for k, isl in enumerate(islands):
            self.units += self._island_units(isl, k, unit_len)
        self.islands = islands
        # Space no storefront covered (corners, slivers) becomes plain unnamed storefront, never a hole.
        covered = unary_union([u.poly for u in self.units])
        spare = perimeter.union(unary_union(islands)) if islands else perimeter
        leftover = spare.difference(covered.buffer(0.3))
        self.leftovers = [g for g in getattr(leftover, "geoms", [leftover]) if g.geom_type == "Polygon" and g.area > 150]

    def _island_units(self, isl, k, unit_len):
        """Rectangular storefronts in a core island: columns across, and back-to-back rows when deep enough,
        each opening onto the walkway above or below it."""
        minx, miny, maxx, maxy = isl.bounds
        cols = max(1, round((maxx - minx) / unit_len))
        rows = 2 if maxy - miny > 110 else 1
        if self.void is not None:
            return self._block_units(isl, k, unit_len)
        out = []
        for c in range(cols):
            x0 = minx + c * (maxx - minx) / cols
            x1 = minx + (c + 1) * (maxx - minx) / cols
            for r in range(rows):
                y0 = miny + r * (maxy - miny) / rows
                y1 = miny + (r + 1) * (maxy - miny) / rows
                piece = largest(isl.intersection(box(x0, y0, x1, y1)))
                if piece is None or piece.area < 700 or piece.buffer(-8).is_empty:
                    continue
                door_y = y0 if r == 0 else y1
                door = nearest_points(piece.exterior, Point((x0 + x1) / 2, door_y))[0]
                out.append(Unit(piece, (door.x, door.y), "island", c * rows + r, island=k))
        return out

    def _block_units(self, isl, k, unit_len):
        """Grid storefronts in a block between walkways. Each opens onto the walkway it shares the longest
        edge with; cells that touch no walkway stay unnamed storefront."""
        minx, miny, maxx, maxy = isl.bounds
        cols = max(1, round((maxx - minx) / unit_len))
        rows = max(1, round((maxy - miny) / unit_len))
        edge_zone = self.walk.buffer(2)
        out = []
        for c in range(cols):
            for r in range(rows):
                x0, x1 = minx + c * (maxx - minx) / cols, minx + (c + 1) * (maxx - minx) / cols
                y0, y1 = miny + r * (maxy - miny) / rows, miny + (r + 1) * (maxy - miny) / rows
                piece = largest(isl.intersection(box(x0, y0, x1, y1)))
                if piece is None or piece.area < 2500 or piece.buffer(-18).is_empty:  # no slivers in the blocks
                    continue
                front = piece.exterior.intersection(edge_zone)
                parts = [g for g in getattr(front, "geoms", [front]) if g.geom_type == "LineString" and g.length > 20]
                if not parts:
                    continue
                door = max(parts, key=lambda g: g.length).interpolate(0.5, normalized=True)
                out.append(Unit(piece, (door.x, door.y), "island", c * rows + r, island=k))
        return out

    def _cells(self, seeds, region):
        if not seeds:
            return []
        if len(seeds) == 1:
            return [(seeds[0][0], seeds[0][1], region)]
        vor = voronoi_diagram(MultiPoint([p for _, p in seeds]), envelope=self.B.envelope.buffer(600))
        out = []
        for d, p in seeds:
            cell = next((c for c in vor.geoms if c.buffer(0.01).contains(p)), None)
            piece = largest(cell.intersection(region)) if cell is not None else None
            if piece is not None and piece.area > 700 and not piece.buffer(-8).is_empty:  # skip slivers
                out.append((d, p, piece))
        return out


class Graph:
    def __init__(self, fid):
        self.fid = fid
        self.nodes: dict[str, tuple[float, float]] = {}
        self.edges: list[list[str]] = []

    def add(self, suffix, xy):
        nid = f"{self.fid}-{suffix}"
        self.nodes[nid] = (round(xy[0], 1), round(xy[1], 1))
        return nid

    def link(self, a, b):
        self.edges.append([a, b])

    def nearest(self, xy, among):
        return min(among, key=lambda n: math.dist(self.nodes[n], xy))


def sample(line, step):
    n = max(1, int(line.length // step))
    return [line.interpolate(i * line.length / n) for i in range(n + (0 if line.is_ring else 1))]


def build_graph(plan: Plan) -> tuple[Graph, list[str], dict]:
    g = Graph(plan.fid)
    walk_nodes = []
    ring_pts = sample(plan.center_line, NODE_STEP)
    ring = [g.add(f"w{i}", (p.x, p.y)) for i, p in enumerate(ring_pts)]
    for a, b in zip(ring, ring[1:]):
        g.link(a, b)
    if plan.center_line.is_ring and len(ring) > 2:
        g.link(ring[-1], ring[0])
    walk_nodes += ring
    special = {}
    if plan.void is not None:
        balcony = [g.add(f"b{i}", (p.x, p.y)) for i, p in enumerate(sample(plan.balcony_line, NODE_STEP))]
        for a, b in zip(balcony, balcony[1:] + balcony[:1]):
            g.link(a, b)
        for k, line in enumerate(plan.links):
            ids = [g.add(f"x{k}-{j}", (p.x, p.y)) for j, p in enumerate(sample(line, NODE_STEP))]
            for a, b in zip(ids, ids[1:]):
                g.link(a, b)
            g.link(ids[0], g.nearest(g.nodes[ids[0]], balcony))
            g.link(ids[-1], g.nearest(g.nodes[ids[-1]], ring))
            walk_nodes += ids
        walk_nodes += balcony
        # Escalators, travelators and the glass elevator stand in the void, stepping off onto the balcony.
        minx, miny, maxx, maxy = plan.void.bounds
        cx = (minx + maxx) / 2

        def at(name, dx, frac):
            n = g.add(name, (cx + dx, miny + frac * (maxy - miny)))
            g.link(n, g.nearest(g.nodes[n], balcony))
            return n

        if plan.fid in ESCALATOR_FLOORS:
            special["banks"] = [(at(f"esc{k}-up", -22, f), at(f"esc{k}-dn", 22, f)) for k, f in enumerate(VOID_BANKS)]
        special["lift"] = at("lift", 0, 0.5)
        if plan.fid in TRAVELATOR_FLOORS:
            special["trav"] = (at("trav-up", -22, VOID_TRAVELATOR), at("trav-dn", 22, VOID_TRAVELATOR))
    for k, c in enumerate(plan.crosses):
        pts = sample(c["line"], NODE_STEP)
        ids = [g.add(f"x{k}-{j}", (p.x, p.y)) for j, p in enumerate(pts)]
        for a, b in zip(ids, ids[1:]):
            g.link(a, b)
        g.link(ids[0], g.nearest(g.nodes[ids[0]], ring))
        g.link(ids[-1], g.nearest(g.nodes[ids[-1]], ring))
        walk_nodes += ids
        cx = (c["line"].bounds[0] + c["line"].bounds[2]) / 2
        if c["kind"] == "atrium":
            up = g.add(f"esc{k}-up", (cx - 30, c["y"]))
            dn = g.add(f"esc{k}-dn", (cx + 30, c["y"]))
            g.link(up, g.nearest(g.nodes[up], ids))
            g.link(dn, g.nearest(g.nodes[dn], ids))
            special.setdefault("atria", []).append((k, up, dn, cx, c))
        else:
            lift = g.add("lift", (cx, c["y"]))
            g.link(lift, g.nearest(g.nodes[lift], ids))
            special["lift"] = lift
    for name, xy in plan.entrances:
        e = g.add(f"entrance-{name}", xy)
        g.link(e, g.nearest(xy, walk_nodes))
        special.setdefault("entrances", {})[name] = e
    return g, walk_nodes, special


def label_for(poly):
    p = polylabel(poly, tolerance=1.0)
    r = poly.exterior.distance(p)
    minx, _, maxx, _ = poly.bounds
    return [round(p.x, 1), round(p.y, 1), round(min(maxx - minx - 8, max(40.0, 2.6 * r)), 1)]


def allocate(plan: Plan, rows, lift_xy):
    """Assign stores to storefront units. Anchors take several adjacent units; the foodcourt takes an island."""
    perim = sorted([u for u in plan.units if u.zone == "perimeter"], key=lambda u: u.pos)
    island_units = [u for u in plan.units if u.zone == "island"]
    used: set[int] = set()
    placed = []
    spacing = (plan.ring_out.exterior.length / max(1, len(perim))) * 1.6

    def adjacent_run(k):
        best = None
        for i in range(len(perim)):
            run = [perim[(i + j) % len(perim)] for j in range(k)]
            if any(id(u) in used for u in run):
                continue
            gaps = [((run[j + 1].pos - run[j].pos) % plan.ring_out.exterior.length) for j in range(k - 1)]
            if any(gp > spacing for gp in gaps):
                continue
            area = sum(u.poly.area for u in run)
            if best is None or area > best[0]:
                best = (area, run)
        return best[1] if best else None

    for row in sorted([r for r in rows if r[0] in PERIMETER_ANCHORS], key=lambda r: -PERIMETER_ANCHORS[r[0]]):
        run = adjacent_run(PERIMETER_ANCHORS[row[0]]) or adjacent_run(1)
        used.update(id(u) for u in run)
        placed.append((row, run))
    for row in [r for r in rows if r[0] in ISLAND_ANCHORS]:
        best_island = max(range(len(plan.islands)), key=lambda k: plan.islands[k].area)
        run = [u for u in island_units if u.island == best_island and id(u) not in used]
        used.update(id(u) for u in run)
        placed.append((row, run))
    for row in [r for r in rows if r[0] == "Restrooms"]:
        pool = [u for u in island_units if id(u) not in used] or [u for u in perim if id(u) not in used]
        u = min(pool, key=lambda u: math.dist(u.door, lift_xy) if lift_xy else u.poly.area)
        used.add(id(u))
        placed.append((row, [u]))
    rest = [r for r in rows if r[0] not in PERIMETER_ANCHORS and r[0] not in ISLAND_ANCHORS and r[0] != "Restrooms"]
    free = [u for u in perim + island_units if id(u) not in used]
    if len(rest) > len(free):
        sys.exit(f"{plan.fid}: {len(rest)} stores but only {len(free)} free storefronts")
    picks = [free[int(i * len(free) / len(rest))] for i in range(len(rest))] if rest else []
    for row, u in zip(rest, picks):
        used.add(id(u))
        placed.append((row, [u]))
    blanks = [u for u in plan.units if id(u) not in used]
    return placed, blanks


def build() -> dict:
    main_m, angle = project(MAIN_LATLON)
    annex_m, _ = project(ANNEX_LATLON, angle)
    main_px, main_w, main_h, _ = portrait_px(main_m)
    annex_px, annex_w, annex_h, _ = portrait_px(annex_m)
    # Where the annex sits relative to the main building, in the main building's frame.
    rot_main = [(-y, x) for x, y in main_m]
    rot_annex = [(-y, x) for x, y in annex_m]
    mminx, mminy = min(p[0] for p in rot_main), min(p[1] for p in rot_main)
    acx = sum(p[0] for p in rot_annex) / len(rot_annex)
    acy = sum(p[1] for p in rot_annex) / len(rot_annex)
    annex_dir_px = ((acx - mminx) / M_PER_PX + MARGIN, (acy - mminy) / M_PER_PX + MARGIN)

    floors, nodes, edges, places, connectors = [], [], [], [], []
    plans, graphs, specials = {}, {}, {}
    main_poly = Polygon(main_px)
    far_end = (main_poly.centroid.x * 2 - annex_dir_px[0], main_poly.centroid.y * 2 - annex_dir_px[1])
    for fid, name, level in MAIN_FLOORS:
        entrances = [("main", far_end), ("annex", annex_dir_px)] if fid == "GF" else []
        plans[fid] = Plan(fid, main_px, entrances=entrances, void=dict(VOID, open=fid == "LG"), **MAIN)
    annex_poly = Polygon(annex_px)
    plans["AX"] = Plan("AX", annex_px, entrances=[("main", (annex_poly.centroid.x, 0))], **ANNEX)
    for fid, plan in plans.items():
        graphs[fid], _, specials[fid] = build_graph(plan)

    # Vertical connectors in the void: escalator banks A and B (GF up), travelators to LG, one glass elevator.
    order = [f for f, _, _ in MAIN_FLOORS]
    esc = [f for f in order if f in ESCALATOR_FLOORS]
    for idx, letter in ((0, "A"), (1, "B")):
        connectors.append({"id": f"esc-{letter.lower()}-up", "name": f"Escalator {letter}", "kind": "escalator",
                           "direction": "up", "stops": [specials[f]["banks"][idx][0] for f in esc]})
        connectors.append({"id": f"esc-{letter.lower()}-down", "name": f"Escalator {letter}", "kind": "escalator",
                           "direction": "down", "stops": [specials[f]["banks"][idx][1] for f in reversed(esc)]})
    trav = [f for f in order if f in TRAVELATOR_FLOORS]
    connectors.append({"id": "trav-up", "name": "Travelator", "kind": "escalator", "direction": "up",
                       "stops": [specials[f]["trav"][0] for f in trav]})
    connectors.append({"id": "trav-down", "name": "Travelator", "kind": "escalator", "direction": "down",
                       "stops": [specials[f]["trav"][1] for f in reversed(trav)]})
    connectors.append({"id": "elev-1", "name": "Elevator", "kind": "elevator", "direction": "both",
                       "stops": [specials[f]["lift"] for f in order]})
    connectors.append({"id": "walk-annex", "name": "Annex Walkway", "kind": "bridge", "direction": "both",
                       "stops": [specials["GF"]["entrances"]["annex"], specials["AX"]["entrances"]["main"]], "seconds": 60})

    by_floor = {f: [("Restrooms", f, "restroom", [], None, False)] for f in plans}
    for row in STORES:
        by_floor[row[1]].append(row)
    used_ids: set[str] = set()
    for fid, plan in plans.items():
        g = graphs[fid]
        lift = specials[fid].get("lift")
        lift_xy = g.nodes[lift] if lift else None
        placed, blanks = allocate(plan, by_floor[fid], lift_xy)
        walk_nodes = [n for n in g.nodes if "-w" in n or "-x" in n or "-b" in n]
        for k, ((name, _, cat, extra, minutes, fictional), units) in enumerate(placed):
            poly = largest(unary_union([u.poly for u in units]).buffer(0.5).buffer(-0.5)) or max((u.poly for u in units), key=lambda q: q.area)
            door_xy = units[len(units) // 2].door
            door = g.add(f"d{k}", door_xy)
            g.link(door, g.nearest(door_xy, walk_nodes))
            pid = slug(name, fid)
            while pid in used_ids:
                pid += "-2"
            used_ids.add(pid)
            minx, miny, maxx, maxy = poly.bounds
            place = {"id": pid, "name": name, "floor": fid,
                     "rect": [round(minx, 1), round(miny, 1), round(maxx - minx, 1), round(maxy - miny, 1)],
                     "shape": coords(poly), "label": label_for(poly), "node": door,
                     "category": cat, "tags": CATEGORY_TAGS[cat] + extra}
            if minutes:
                place["service"] = {"duration_min": minutes}
            if fictional:
                place["fictional"] = True
            places.append(place)
        rails = [coords(plan.void)] if plan.void is not None and not plan.void_open else []
        for _, up, dn, cx, c in specials[fid].get("atria", []):
            rail = box(cx - 62, c["y"] - c["half"] + 14, cx + 62, c["y"] + c["half"] - 14)
            rails.append(coords(rail))
        poly_px, w, h = (annex_px, annex_w, annex_h) if fid == "AX" else (main_px, main_w, main_h)
        name = "Annex" if fid == "AX" else next(n for f, n, _ in MAIN_FLOORS if f == fid)
        level = 0 if fid == "AX" else next(lv for f, _, lv in MAIN_FLOORS if f == fid)
        floors.append({"id": fid, "name": name, "level": level, "width": w, "height": h,
                       "scale_m_per_px": M_PER_PX, "outline": [list(p) for p in poly_px],
                       "walk_path": svg_path(plan.walk), "atria": rails,
                       "blanks": [coords(u.poly) for u in blanks] + [coords(g) for g in plan.leftovers]})
        nodes += [{"id": n, "floor": fid, "x": x, "y": y} for n, (x, y) in g.nodes.items()]
        edges += g.edges

    def node_of(pid):
        return next(p["node"] for p in places if p["id"] == pid)

    anchors = [
        {"id": "gf-mrt-entrance", "label": "Ground Floor, main entrance", "floor": "GF",
         "node": specials["GF"]["entrances"]["main"], "heading_deg": 0},
        {"id": "lg-supermarket", "label": "Lower Ground, SM Supermarket", "floor": "LG", "node": node_of("sm-supermarket-lg"), "heading_deg": 0},
        {"id": "2f-escalator-a", "label": "2nd Floor, Escalator A", "floor": "2F", "node": specials["2F"]["banks"][0][0], "heading_deg": 0},
        {"id": "lg-food-hall", "label": "Lower Ground, Market Food Hall", "floor": "LG", "node": node_of("market-food-hall-lg"), "heading_deg": 0},
        {"id": "3f-ace-hardware", "label": "3rd Floor, ACE Hardware", "floor": "3F", "node": node_of("ace-hardware-3f"), "heading_deg": 0},
        {"id": "4f-escalators", "label": "4th Floor, escalators", "floor": "4F", "node": specials["4F"]["banks"][0][0], "heading_deg": 0},
        {"id": "5f-sm-home", "label": "5th Floor, SM Home", "floor": "5F", "node": node_of("sm-home-5f"), "heading_deg": 0},
        {"id": "ax-entrance", "label": "Annex entrance", "floor": "AX", "node": specials["AX"]["entrances"]["main"], "heading_deg": 0},
    ]
    return {
        "mall": {"id": "sm-makati", "name": "SM Makati",
                 "note": "Store names and floors from public listings and a 2026 walk-through video. Layout reconstructed for this demo."},
        "floors": floors, "nodes": nodes, "edges": edges, "connectors": connectors, "places": places,
        "category_defaults": {k: {"duration_min": d, "async": a} for k, (d, a) in CATEGORY_DEFAULTS.items()},
        "anchors": anchors,
    }


def slug(name: str, floor: str) -> str:
    base = "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-")
    while "--" in base:
        base = base.replace("--", "-")
    return f"{base}-{floor.lower()}"


def main() -> None:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sys.path.insert(0, str(ROOT / "server"))
    from mappy.mall import load_mall

    m = load_mall(OUT)
    per_floor = {f: sum(1 for p in m.places.values() if p.floor == f) for f in m.floor_order()}
    blanks = {f["id"]: len(f["blanks"]) for f in data["floors"]}
    size_kb = OUT.stat().st_size // 1024
    print(f"wrote {OUT.relative_to(ROOT)} ({size_kb} KB): {len(m.places)} places {per_floor}, empty storefronts {blanks}, "
          f"{len(m.nodes)} nodes")


if __name__ == "__main__":
    main()

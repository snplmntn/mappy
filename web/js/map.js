import { h, s } from "./util.js";
import { atNode, state } from "./state.js";

const CAT_CLASS = {
  food: "m-food", cafe: "m-food",
  clothing: "m-shop", shoes: "m-shop", accessories: "m-shop", gift: "m-shop", home: "m-shop", pet: "m-shop",
  books_stationery: "m-shop", beauty: "m-shop", department_store: "m-shop", grocery: "m-shop",
  electronics: "m-tech", gaming: "m-tech", appliances: "m-tech",
  phone_repair: "m-service", shoe_repair: "m-service", pharmacy: "m-service", bank: "m-service",
  atm: "m-service", remittance: "m-service", courier: "m-service",
  restroom: "m-rest",
};
const LABEL_PX = 11;
const LABEL_MIN_PPU = 0.42; // screen px per map unit below which labels would overlap
const MIN_ZOOM = 0.6;
const MAX_ZOOM = 6;
const FIT_PAD = 70;

const points = (path) => path.map((p) => p.join(",")).join(" ");
const shortName = (name) => (name.length > 14 ? `${name.slice(0, 13)}…` : name);

function connectorGlyph(c) {
  if (c.kind === "escalator") return c.direction === "up" ? "▲" : "▼";
  return c.kind === "elevator" ? "⇅" : "⇄";
}

/** Draw one floor. opts: {legs, dimLegs, pins:[{floor,x,y,label}], targets:Set<placeId>, you:boolean} */
export function renderFloor(svgEl, floorId, opts = {}) {
  const { mall, index } = state;
  const floor = index.floors[floorId];
  const g = s("g");
  g.append(s("polygon", { class: "m-outline", points: points(floor.outline) }));
  for (const p of mall.places) {
    if (p.floor !== floorId) continue;
    const [x, y, w, hh] = p.rect;
    const target = opts.targets && opts.targets.has(p.id) ? " target" : "";
    g.append(s("rect", { class: `m-store ${CAT_CLASS[p.category] || "m-other"}${target}`, x, y, width: w, height: hh, rx: 4 }));
    g.append(s("text", { class: "m-label", x: x + w / 2, y: y + hh / 2 }, p.category === "restroom" ? "CR" : shortName(p.name)));
  }
  for (const c of mall.connectors) {
    for (const id of c.stops) {
      const n = index.nodes[id];
      if (n.floor !== floorId) continue;
      g.append(s("rect", { class: "m-icon-bg", x: n.x - 11, y: n.y - 11, width: 22, height: 22, rx: 5 }));
      g.append(s("text", { class: "m-icon", x: n.x, y: n.y + 1 }, connectorGlyph(c)));
    }
  }
  for (const leg of opts.dimLegs || []) {
    if (leg.floor === floorId && leg.path.length > 1) g.append(s("polyline", { class: "m-route-dim", points: points(leg.path) }));
  }
  for (const leg of opts.legs || []) {
    if (leg.floor !== floorId || leg.path.length < 2) continue;
    g.append(s("polyline", { class: "m-route-case", points: points(leg.path) }));
    g.append(s("polyline", { class: "m-route", points: points(leg.path) }));
  }
  const merged = new Map();
  for (const pin of opts.pins || []) {
    if (pin.floor !== floorId) continue;
    const key = `${pin.x},${pin.y}`;
    const prev = merged.get(key);
    merged.set(key, prev ? { ...prev, label: `${prev.label},${pin.label}` } : { ...pin, label: String(pin.label) });
  }
  for (const pin of merged.values()) {
    const r = pin.label.length > 2 ? 20 : 15;
    g.append(s("circle", { class: "m-pin", cx: pin.x, cy: pin.y, r }));
    g.append(s("text", { class: "m-pin-text", x: pin.x, y: pin.y + 1 }, pin.label));
  }
  const you = opts.you === false ? null : atNode();
  if (you && you.floor === floorId) {
    g.append(s("circle", { class: "m-you-halo", cx: you.x, cy: you.y, r: 14 }));
    g.append(s("circle", { class: "m-you", cx: you.x, cy: you.y, r: 10 }));
  }
  svgEl.replaceChildren(g);
}

/** Bounding box of points, padded and never smaller than minSize. */
export function bbox(pts, pad = FIT_PAD, minSize = 260) {
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  let [x0, x1, y0, y1] = [Math.min(...xs) - pad, Math.max(...xs) + pad, Math.min(...ys) - pad, Math.max(...ys) + pad];
  if (x1 - x0 < minSize) [x0, x1] = [(x0 + x1 - minSize) / 2, (x0 + x1 + minSize) / 2];
  if (y1 - y0 < minSize) [y0, y1] = [(y0 + y1 - minSize) / 2, (y0 + y1 + minSize) / 2];
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

export function pinForPlace(placeId, label) {
  const p = state.index.places[placeId];
  const [x, y, w, hh] = p.rect;
  return { floor: p.floor, x: x + w / 2, y: y + hh / 2, label };
}

export function pinForNode(nodeId, label) {
  const n = state.index.nodes[nodeId];
  return { floor: n.floor, x: n.x, y: n.y, label };
}

/** Full-screen map with steps, floor strip, pan and pinch-zoom. */
export class MapView {
  constructor() {
    this.root = document.getElementById("mapview");
    this.svg = document.getElementById("mapSvg");
    this.stepEl = document.getElementById("mapStep");
    this.instrEl = document.getElementById("mapInstruction");
    this.strip = document.getElementById("floorStrip");
    this.card = document.getElementById("mapCard");
    this.view = { x: 0, y: 0, w: 1000, h: 800 };
    this.pointers = new Map();
    document.getElementById("mapBack").addEventListener("click", () => this.close());
    this.bindGestures();
  }

  /** opts: {legs, pins, title, pick:fn(nodeId)} */
  open(opts = {}) {
    this.pins = opts.pins || [];
    this.legs = (opts.legs || []).map((leg, i, all) => {
      const pin = this.pins[leg.stop_index];
      const lastForStop = !all[i + 1] || all[i + 1].stop_index !== leg.stop_index;
      return lastForStop && !leg.connector && pin && pin.floor === leg.floor
        ? { ...leg, path: [...leg.path, [pin.x, pin.y]] } : leg;
    });
    this.title = opts.title || "Mapa";
    this.onPick = opts.pick || null;
    this.step = 0;
    this.preview = null;
    this.root.hidden = false;
    const you = atNode();
    this.floor = this.legs.length ? this.legs[0].floor : (you ? you.floor : state.index.floorOrder[0]);
    this.render(true);
  }

  close() {
    this.root.hidden = true;
  }

  currentFloor() {
    return this.preview || this.floor;
  }

  render(refit) {
    const { index } = state;
    const floorId = this.currentFloor();
    const leg = this.legs[this.step];
    renderFloor(this.svg, floorId, {
      legs: leg && !this.preview ? [leg] : [],
      dimLegs: this.legs.filter((l) => l !== leg || this.preview),
      pins: this.pins,
    });
    const floorName = index.floors[floorId].name;
    if (this.onPick) {
      this.stepEl.textContent = floorName;
      this.instrEl.textContent = "Pindutin kung nasaan ka";
    } else if (this.preview) {
      this.stepEl.textContent = "Tinitingnan lang";
      this.instrEl.textContent = floorName;
    } else if (leg) {
      this.stepEl.textContent = `Step ${this.step + 1} of ${this.legs.length}, ${floorName}`;
      this.instrEl.textContent = leg.instruction;
    } else {
      this.stepEl.textContent = this.title;
      this.instrEl.textContent = floorName;
    }
    this.renderStrip();
    this.renderCard();
    if (refit) this.fit();
    else this.applyView();
  }

  renderStrip() {
    const routeFloors = new Set(this.legs.map((l) => l.floor));
    const current = this.currentFloor();
    const buttons = [...state.index.floorOrder].reverse().map((fid) =>
      h("button", {
        class: `floor-btn${routeFloors.has(fid) ? " on-route" : ""}`,
        type: "button",
        "aria-current": fid === current ? "true" : "false",
        "aria-label": state.index.floors[fid].name,
        onclick: () => {
          this.preview = fid === this.floor ? null : fid;
          this.render(true);
        },
      }, fid));
    this.strip.replaceChildren(...buttons);
  }

  renderCard() {
    const leg = this.legs[this.step];
    if (this.preview) {
      this.card.replaceChildren(
        h("span", { class: "grow" }, "Hindi ito ang kasalukuyang hakbang."),
        h("button", { class: "primary", type: "button", onclick: () => { this.preview = null; this.render(true); } }, "Bumalik"));
      return;
    }
    if (!leg) {
      this.card.replaceChildren();
      return;
    }
    const last = this.step === this.legs.length - 1;
    const prev = this.step > 0
      ? h("button", { class: "chip-s", type: "button", onclick: () => this.go(-1) }, "Prev")
      : null;
    const text = leg.connector ? leg.instruction : last ? "Nandiyan na ang destinasyon mo." : "Sundan ang dilaw na linya.";
    const next = h("button", { class: "primary", type: "button", onclick: () => (last ? this.close() : this.go(1)) },
      last ? "Done" : leg.connector ? "Next floor" : "Next");
    this.card.replaceChildren(prev || "", h("span", { class: "grow" }, text), next);
  }

  go(delta) {
    this.step = Math.max(0, Math.min(this.legs.length - 1, this.step + delta));
    this.floor = this.legs[this.step].floor;
    this.preview = null;
    this.render(true);
  }

  fit() {
    const floorId = this.currentFloor();
    const leg = this.legs[this.step];
    let pts = [];
    if (leg && !this.preview && leg.floor === floorId) pts = [...leg.path];
    pts.push(...this.pins.filter((p) => p.floor === floorId).map((p) => [p.x, p.y]));
    const you = atNode();
    if (!pts.length && you && you.floor === floorId) pts.push([you.x, you.y]);
    const f = state.index.floors[floorId];
    const box = pts.length ? bbox(pts) : { x: 0, y: 0, w: f.width, h: f.height };
    this.setView(box);
  }

  setView(box) {
    const rect = this.svg.getBoundingClientRect();
    const aspect = rect.width && rect.height ? rect.width / rect.height : 0.7;
    const strip = this.strip.getBoundingClientRect().width + 16;
    const reserve = rect.width ? Math.min(0.4, strip / rect.width) : 0.2;
    let { x, y, w, h: hh } = box;
    w /= 1 - reserve; // keep the route clear of the floor buttons on the right
    if (w / hh > aspect) {
      const nh = w / aspect;
      y -= (nh - hh) / 2;
      hh = nh;
    } else {
      const nw = hh * aspect;
      x -= (nw - w) / 2;
      w = nw;
    }
    this.view = { x, y, w, h: hh };
    this.applyView();
  }

  applyView() {
    const { x, y, w, h: hh } = this.view;
    this.svg.setAttribute("viewBox", `${x} ${y} ${w} ${hh}`);
    const ppu = (this.svg.getBoundingClientRect().width || 360) / w;
    this.svg.style.setProperty("--lbl", `${LABEL_PX / ppu}px`);
    this.svg.classList.toggle("zoom-low", ppu < LABEL_MIN_PPU);
  }

  toSvg(clientX, clientY) {
    const rect = this.svg.getBoundingClientRect();
    return [this.view.x + ((clientX - rect.left) / rect.width) * this.view.w,
      this.view.y + ((clientY - rect.top) / rect.height) * this.view.h];
  }

  zoomAt(factor, clientX, clientY) {
    const floorW = state.index.floors[this.currentFloor()].width;
    const newW = Math.min(floorW / MIN_ZOOM, Math.max(floorW / MAX_ZOOM, this.view.w / factor));
    const k = newW / this.view.w;
    const [px, py] = this.toSvg(clientX, clientY);
    this.view = { x: px - (px - this.view.x) * k, y: py - (py - this.view.y) * k, w: this.view.w * k, h: this.view.h * k };
    this.applyView();
  }

  bindGestures() {
    const svg = this.svg;
    let last = null;
    let moved = 0;
    let lastTap = 0;
    svg.addEventListener("pointerdown", (e) => {
      svg.setPointerCapture(e.pointerId);
      this.pointers.set(e.pointerId, [e.clientX, e.clientY]);
      moved = 0;
      last = null;
    });
    svg.addEventListener("pointermove", (e) => {
      if (!this.pointers.has(e.pointerId)) return;
      const prev = this.pointers.get(e.pointerId);
      this.pointers.set(e.pointerId, [e.clientX, e.clientY]);
      const rect = svg.getBoundingClientRect();
      if (this.pointers.size === 1) {
        const dx = e.clientX - prev[0];
        const dy = e.clientY - prev[1];
        moved += Math.abs(dx) + Math.abs(dy);
        this.view.x -= (dx / rect.width) * this.view.w;
        this.view.y -= (dy / rect.height) * this.view.h;
        this.applyView();
      } else if (this.pointers.size === 2) {
        const [a, b] = [...this.pointers.values()];
        const dist = Math.hypot(a[0] - b[0], a[1] - b[1]);
        if (last) this.zoomAt(dist / last, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2);
        last = dist;
        moved += 10;
      }
    });
    const end = (e) => {
      this.pointers.delete(e.pointerId);
      if (this.pointers.size < 2) last = null;
      if (e.type !== "pointerup" || moved > 8) return;
      const now = Date.now();
      if (this.onPick) {
        this.pick(e.clientX, e.clientY);
      } else if (now - lastTap < 300) {
        this.zoomAt(2, e.clientX, e.clientY);
      }
      lastTap = now;
    };
    svg.addEventListener("pointerup", end);
    svg.addEventListener("pointercancel", end);
    svg.addEventListener("wheel", (e) => {
      e.preventDefault();
      this.zoomAt(e.deltaY < 0 ? 1.2 : 1 / 1.2, e.clientX, e.clientY);
    }, { passive: false });
  }

  pick(clientX, clientY) {
    const [x, y] = this.toSvg(clientX, clientY);
    const floorId = this.currentFloor();
    let best = null;
    for (const n of state.mall.nodes) {
      if (n.floor !== floorId) continue;
      const d = Math.hypot(n.x - x, n.y - y);
      if (!best || d < best.d) best = { id: n.id, d };
    }
    if (best) {
      const cb = this.onPick;
      this.onPick = null;
      this.close();
      cb(best.id);
    }
  }
}

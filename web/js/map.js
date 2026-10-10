import { h, s } from "./util.js";
import { atNode, state } from "./state.js";
import { icon } from "./icons.js";

const CAT_CLASS = {
  food: "m-food", cafe: "m-food",
  clothing: "m-shopping", shoes: "m-shopping", accessories: "m-shopping", gift: "m-shopping", home: "m-shopping",
  books_stationery: "m-shopping", beauty: "m-shopping", department_store: "m-shopping", grocery: "m-shopping", pet: "m-shopping",
  electronics: "m-tech", gaming: "m-tech", appliances: "m-tech",
  phone_repair: "m-service", shoe_repair: "m-service", pharmacy: "m-service", bank: "m-service",
  atm: "m-service", remittance: "m-service", courier: "m-service",
  restroom: "m-rest", nursing_room: "m-rest", chapel: "m-rest", clinic: "m-rest", services: "m-service",
};
export const CATEGORY_NAMES = {
  phone_repair: "Phone repair", shoe_repair: "Shoe repair", food: "Food", cafe: "Coffee", clothing: "Clothes",
  shoes: "Shoes", accessories: "Accessories", gift: "Gifts", home: "Home", books_stationery: "Books & stationery",
  beauty: "Beauty", department_store: "Department store", electronics: "Electronics", gaming: "Gaming",
  appliances: "Appliances", grocery: "Grocery", pharmacy: "Pharmacy", bank: "Bank", atm: "ATM",
  remittance: "Money transfer", courier: "Courier", pet: "Pets", restroom: "Restroom",
  services: "Customer service", nursing_room: "Nursing room", chapel: "Chapel", clinic: "Clinic",
};
const LABEL_UNITS = 13;
const MIN_PPU = 0.25;
const MAX_PPU = 4;
const TWEEN_MS = 420;
const WALK_MPS = 1.2;

const pts = (path) => path.map((p) => p.join(",")).join(" ");

function wrapLabel(name, width) {
  const max = Math.max(4, Math.floor(width / (LABEL_UNITS * 0.58)));
  const lines = [""];
  for (const w of name.split(" ")) {
    const cur = lines[lines.length - 1];
    if (!cur) lines[lines.length - 1] = w;
    else if ((cur + " " + w).length <= max) lines[lines.length - 1] = cur + " " + w;
    else lines.push(w);
  }
  const out = lines.slice(0, 2).map((l) => (l.length > max ? `${l.slice(0, max - 1)}…` : l));
  if (lines.length > 2) out[1] = `${out[1].slice(0, max - 1)}…`;
  return out;
}

function connectorGlyph(c, x, y) {
  if (c.kind === "escalator" && c.direction === "up") return `M${x} ${y + 6}V${y - 6}M${x - 5} ${y - 1}L${x} ${y - 6}L${x + 5} ${y - 1}`;
  if (c.kind === "escalator") return `M${x} ${y - 6}V${y + 6}M${x - 5} ${y + 1}L${x} ${y + 6}L${x + 5} ${y + 1}`;
  if (c.kind === "elevator") return `M${x - 5} ${y - 2}L${x} ${y - 7}L${x + 5} ${y - 2}M${x - 5} ${y + 2}L${x} ${y + 7}L${x + 5} ${y + 2}`;
  return `M${x - 6} ${y}H${x + 6}M${x + 1} ${y - 5}L${x + 6} ${y}L${x + 1} ${y + 5}`;
}

/**
 * Draw one floor like an indoor mall map: building, walkways, storefronts, escalators, route, pins.
 * opts: {route, otherRoutes, stops:[{floor,x,y,label,dest}], focus, focusLabel, candidates, hit, you}
 */
export function renderFloor(svgEl, floorId, opts = {}) {
  const { mall, index } = state;
  const floor = index.floors[floorId];
  const g = s("g");
  g.append(s("rect", { class: "m-outside", x: -3000, y: -3000, width: floor.width + 6000, height: floor.height + 6000 }));
  g.append(s("polygon", { class: "m-building", points: pts(floor.outline) }));
  if (floor.walk_path) g.append(s("path", { class: "m-walk", d: floor.walk_path, "fill-rule": "evenodd" }));
  for (const [x, y, w, hh] of floor.walkways || []) g.append(s("rect", { class: "m-walk", x, y, width: w, height: hh, rx: 10 }));
  for (const shape of floor.atria || []) {
    if (Array.isArray(shape[0])) g.append(s("polygon", { class: "m-atrium-rail", points: pts(shape) }));
    else g.append(s("rect", { class: "m-atrium-rail", x: shape[0] + 18, y: shape[1] + 18, width: shape[2] - 36, height: shape[3] - 36, rx: 14 }));
  }
  for (const shape of floor.blanks || []) {
    if (Array.isArray(shape[0])) g.append(s("polygon", { class: "m-unit", points: pts(shape) }));
    else g.append(s("rect", { class: "m-unit", x: shape[0], y: shape[1], width: shape[2], height: shape[3], rx: 3 }));
  }
  for (const p of mall.places) {
    if (p.floor !== floorId) continue;
    const [x, y, w, hh] = p.rect;
    const cls = `m-shop ${CAT_CLASS[p.category] || "m-other"}${opts.hit === p.id ? " hit" : ""}`;
    if (p.shape) g.append(s("polygon", { class: cls, points: pts(p.shape) }));
    else g.append(s("rect", { class: cls, x, y, width: w, height: hh, rx: 3 }));
    const [lx, ly, lw] = p.label || [x + w / 2, y + hh / 2, w - 6];
    const lines = wrapLabel(p.name, lw);
    const t = s("text", { class: "m-label", x: lx, y: ly, "data-w": lw, "data-chars": Math.max(...lines.map((l) => l.length)) });
    lines.forEach((line, i) => t.append(s("tspan", { x: lx, dy: i ? "1.15em" : `${-(lines.length - 1) * 0.575}em` }, line)));
    g.append(t);
  }
  for (const route of opts.otherRoutes || []) {
    if (route.floor === floorId && route.path.length > 1) g.append(s("polyline", { class: "m-route-other", points: pts(route.path) }));
  }
  if (opts.route && opts.route.floor === floorId && opts.route.path.length > 1) {
    g.append(s("polyline", { class: "m-route-case", points: pts(opts.route.path) }));
    g.append(s("polyline", { class: "m-route", points: pts(opts.route.path) }));
  }
  for (const c of mall.connectors) {
    for (const id of c.stops) {
      const n = index.nodes[id];
      if (n.floor !== floorId) continue;
      if (opts.focus === id) g.append(s("circle", { class: "m-conn-focus", cx: n.x, cy: n.y, r: 16 }));
      g.append(s("circle", { class: "m-conn", cx: n.x, cy: n.y, r: 12 }));
      g.append(s("path", { class: "m-conn-glyph", d: connectorGlyph(c, n.x, n.y) }));
      if (opts.focus === id && opts.focusLabel) g.append(s("text", { class: "m-conn-label", x: n.x, y: n.y - 24 }, opts.focusLabel));
    }
  }
  for (const c of opts.candidates || []) {
    if (c.floor !== floorId) continue;
    g.append(s("circle", { class: "m-cand", cx: c.x, cy: c.y, r: 15 }));
    g.append(s("text", { class: "m-cand-text", x: c.x, y: c.y + 1 }, String(c.label)));
  }
  const merged = new Map();
  for (const st of opts.stops || []) {
    if (st.floor !== floorId) continue;
    const key = `${st.x},${st.y}`;
    const prev = merged.get(key);
    merged.set(key, prev ? { ...prev, label: `${prev.label},${st.label}`, dest: prev.dest || st.dest } : { ...st, label: String(st.label) });
  }
  for (const st of merged.values()) {
    if (st.dest) {
      g.append(s("path", { class: "m-dest", d: `M${st.x} ${st.y}c-6-9-14-14-14-22a14 14 0 0 1 28 0c0 8-8 13-14 22z` }));
      g.append(s("text", { class: "m-stop-text", x: st.x, y: st.y - 22 }, st.label));
    } else {
      g.append(s("circle", { class: "m-stop", cx: st.x, cy: st.y, r: st.label.length > 2 ? 17 : 13 }));
      g.append(s("text", { class: "m-stop-text", x: st.x, y: st.y + 1 }, st.label));
    }
  }
  if (opts.dropped && opts.dropped.floor === floorId) {
    const { x, y } = opts.dropped;
    g.append(s("path", { class: "m-drop", d: `M${x} ${y}c-5-8-12-12-12-19a12 12 0 0 1 24 0c0 7-7 11-12 19z` }));
  }
  const you = opts.you === false ? null : atNode();
  if (you && you.floor === floorId) {
    g.append(s("circle", { class: "m-you-halo", cx: you.x, cy: you.y, r: 26 }));
    g.append(s("circle", { class: "m-you", cx: you.x, cy: you.y, r: 10 }));
  }
  svgEl.replaceChildren(g);
}

function insidePolygon(points, x, y) {
  let hit = false;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const [xi, yi] = points[i];
    const [xj, yj] = points[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) hit = !hit;
  }
  return hit;
}

function insidePlace(p, x, y) {
  if (p.shape) return insidePolygon(p.shape, x, y);
  const [rx, ry, w, hh] = p.rect;
  return x >= rx && x <= rx + w && y >= ry && y <= ry + hh;
}

const LABEL_PX = 11;
const CHAR_PX = 6.3;

/** Keep store names a readable size on screen and hide the ones that would not fit their store. */
export function fitLabels(svgEl, ppu) {
  svgEl.style.setProperty("--lbl", `${LABEL_PX / ppu}px`);
  for (const t of svgEl.querySelectorAll(".m-label")) {
    t.style.display = Number(t.dataset.w) * ppu >= Number(t.dataset.chars) * CHAR_PX ? "" : "none";
  }
}

export function bbox(points, pad = 60, minSize = 240) {
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  let [x0, x1, y0, y1] = [Math.min(...xs) - pad, Math.max(...xs) + pad, Math.min(...ys) - pad, Math.max(...ys) + pad];
  if (x1 - x0 < minSize) [x0, x1] = [(x0 + x1 - minSize) / 2, (x0 + x1 + minSize) / 2];
  if (y1 - y0 < minSize) [y0, y1] = [(y0 + y1 - minSize) / 2, (y0 + y1 + minSize) / 2];
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

/** The part of a floor people care about: walkways and storefronts, not back-of-house space. */
function floorContentBox(floor) {
  if (floor.walk_path) return bbox(floor.outline, 20, 200);
  const rects = [...(floor.walkways || []), ...(floor.blanks || []),
    ...state.mall.places.filter((p) => p.floor === floor.id).map((p) => p.rect)];
  if (!rects.length) return { x: 0, y: 0, w: floor.width, h: floor.height };
  const corners = rects.flatMap(([x, y, w, hh]) => [[x, y], [x + w, y + hh]]);
  return bbox(corners, 30, 200);
}

/** Where a route to a store ends: its door on the walkway. */
export function placePoint(placeId) {
  const p = state.index.places[placeId];
  const door = state.index.nodes[p.node];
  return { floor: p.floor, x: door.x, y: door.y };
}

export function nodePoint(nodeId) {
  const n = state.index.nodes[nodeId];
  return { floor: n.floor, x: n.x, y: n.y };
}

function pathMeters(leg) {
  const scale = state.index.floors[leg.floor].scale_m_per_px;
  let d = 0;
  for (let i = 1; i < leg.path.length; i++) d += Math.hypot(leg.path[i][0] - leg.path[i - 1][0], leg.path[i][1] - leg.path[i - 1][1]);
  return Math.round((d * scale) / 5) * 5;
}

function connectorNodeAt(floorId, [x, y]) {
  for (const c of state.mall.connectors) {
    for (const id of c.stops) {
      const n = state.index.nodes[id];
      if (n.floor === floorId && Math.hypot(n.x - x, n.y - y) < 2) return id;
    }
  }
  return null;
}

/** Turn API legs into navigation steps with explicit up/down guidance. */
function buildSteps(legs, stops) {
  const { floors } = state.index;
  return legs.map((leg, i) => {
    const meters = pathMeters(leg);
    const stop = stops[leg.stop_index];
    const c = leg.connector;
    if (c && c.to_floor) {
      const up = floors[c.to_floor].level > floors[leg.floor].level;
      const kind = c.kind === "escalator" ? (up ? "up" : "down") : c.kind === "elevator" ? "elevator" : "bridge";
      const to = floors[c.to_floor].name;
      const primary = c.kind === "bridge" ? `Cross the ${c.name} to the ${to}`
        : c.kind === "elevator" ? `Take the Elevator ${up ? "up" : "down"} to ${to}`
          : `Take ${c.name} ${up ? "up" : "down"} to ${to}`;
      return {
        leg, kind, primary,
        secondary: meters ? `Walk ${meters} m to ${c.name}` : `You're at ${c.name}`,
        floorChange: `${floors[leg.floor].name} → ${to}`,
        focus: leg.path.length ? connectorNodeAt(leg.floor, leg.path[leg.path.length - 1]) : null,
        focusLabel: `${c.name} ${up ? "↑" : c.kind === "bridge" ? "→" : "↓"} ${c.to_floor}`,
        target: c.to_floor,
      };
    }
    const last = !legs[i + 1] || legs[i + 1].stop_index !== leg.stop_index;
    const name = stop ? stop.name : "your destination";
    const where = meters ? `${meters} m on ${floors[leg.floor].name}` : floors[leg.floor].name;
    return { leg, kind: last ? "arrive" : "walk", primary: `Walk to ${name}`, secondary: [where, stop && stop.reason].filter(Boolean).join(" · ") };
  });
}

/** Full-screen navigation: route steps, floor switcher, pan/zoom, browse and pick modes. */
export class Navigator {
  constructor({ onClose, onDirections, onSetLocation }) {
    this.view = document.getElementById("navView");
    this.chat = document.getElementById("chatView");
    this.svg = document.getElementById("mapSvg");
    this.top = document.getElementById("navTop");
    this.floorsEl = document.getElementById("floors");
    this.sheet = document.getElementById("navSheet");
    this.onClose = onClose;
    this.onDirections = onDirections;
    this.onSetLocation = onSetLocation;
    this.camera = { x: 0, y: 0, w: 1000, h: 800 };
    this.pointers = new Map();
    this.reset("browse");
    this.bindGestures();
  }

  reset(mode) {
    Object.assign(this, { mode, steps: [], legs: [], stops: [], step: 0, preview: null, selected: null, dropped: null, summary: null });
  }

  /** opts: {legs, stops:[{floor,x,y,label,name,reason,dest}], summary:{finish}} */
  route(opts) {
    this.reset("route");
    this.stops = opts.stops || [];
    this.summary = opts.summary || null;
    this.legs = (opts.legs || []).map((leg, i, all) => {
      const st = this.stops[leg.stop_index];
      const last = !all[i + 1] || all[i + 1].stop_index !== leg.stop_index;
      return last && !leg.connector && st && st.floor === leg.floor ? { ...leg, path: [...leg.path, [st.x, st.y]] } : leg;
    });
    this.steps = buildSteps(this.legs, this.stops);
    this.show(this.steps.length ? this.steps[0].leg.floor : this.homeFloor());
  }

  browse(floorId) {
    this.reset("browse");
    this.show(floorId || this.homeFloor());
  }

  pick(callback) {
    this.reset("pick");
    this.onPick = callback;
    this.show(this.homeFloor());
  }

  homeFloor() {
    const you = atNode();
    if (you) return you.floor;
    return state.index.floorOrder.includes("GF") ? "GF" : state.index.floorOrder[0];
  }

  show(floorId) {
    this.floor = floorId;
    const opening = this.view.hidden;
    this.view.hidden = false;
    this.draw();
    this.fit(false);
    if (opening) {
      const anim = { duration: matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 280, easing: "cubic-bezier(.2,.8,.2,1)" };
      this.view.animate([{ opacity: 0, transform: "scale(1.04)" }, { opacity: 1, transform: "none" }], anim);
      this.chat.animate([{ opacity: 1 }, { opacity: 0, transform: "scale(.98)" }], anim).onfinish = () => { this.chat.hidden = true; };
    }
  }

  close() {
    this.chat.hidden = false;
    const anim = { duration: matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 240, easing: "cubic-bezier(.2,.8,.2,1)" };
    this.chat.animate([{ opacity: 0, transform: "scale(.98)" }, { opacity: 1, transform: "none" }], anim);
    this.view.animate([{ opacity: 1 }, { opacity: 0, transform: "scale(1.04)" }], anim).onfinish = () => { this.view.hidden = true; };
    this.onClose?.();
  }

  shownFloor() {
    return this.preview || this.floor;
  }

  draw() {
    const step = this.steps[this.step];
    renderFloor(this.svg, this.shownFloor(), {
      route: step && !this.preview ? step.leg : null,
      otherRoutes: this.legs.filter((l) => !step || l !== step.leg || this.preview),
      stops: this.stops,
      focus: step && !this.preview ? step.focus : null,
      focusLabel: step ? step.focusLabel : null,
      hit: this.selected,
      dropped: this.dropped,
    });
    this.applyCamera();
    this.drawTop(step);
    this.drawFloors(step);
    this.drawSheet(step);
  }

  drawTop(step) {
    const { floors } = state.index;
    let ic = "map";
    let primary;
    let secondary;
    let chip = null;
    if (this.mode === "pick") {
      ic = "locate";
      primary = "Tap where you are";
      secondary = floors[this.shownFloor()].name;
    } else if (this.mode === "browse" || !step) {
      primary = floors[this.shownFloor()].name;
      secondary = "Tap a store to get directions";
    } else if (this.preview) {
      primary = floors[this.preview].name;
      secondary = "Previewing another floor";
    } else {
      ic = step.kind === "arrive" ? "pin" : step.kind;
      primary = step.primary;
      secondary = step.secondary;
      chip = step.floorChange ? h("div", { class: "floor-change" }, step.floorChange) : null;
    }
    this.top.replaceChildren(
      h("div", { class: `maneuver${ic === "pin" ? " arrive" : ""}` }, icon(ic, 28)),
      h("div", { class: "nav-text" }, h("div", { class: "nav-primary" }, primary), h("div", { class: "nav-secondary" }, secondary), chip));
  }

  drawFloors(step) {
    const route = new Set(this.legs.map((l) => l.floor));
    const current = this.shownFloor();
    const target = step && !this.preview ? step.target : null;
    this.floorsEl.replaceChildren(...[...state.index.floorOrder].reverse().map((fid) =>
      h("button", {
        class: `floor-btn${route.has(fid) ? " on-route" : ""}${fid === target ? " target" : ""}`,
        type: "button", "aria-current": fid === current ? "true" : "false", "aria-label": state.index.floors[fid].name,
        onclick: () => this.switchFloor(fid),
      }, fid)));
  }

  drawSheet(step) {
    const closeBtn = h("button", { class: "back-to-chat", type: "button", onclick: () => this.close() }, icon("back"), "Back to chat");
    const row = (...children) => {
      const themeBtn = h("button", { class: "theme-toggle", type: "button", "data-theme-toggle": "", "aria-label": "Switch color theme" });
      this.sheet.replaceChildren(h("div", { class: "map-toolbar" }, closeBtn, themeBtn), h("div", { class: "sheet-row" }, ...children));
      window.dispatchEvent(new Event("mappy-theme-controls"));
    };
    if (this.mode === "pick") {
      row(h("div", { class: "eta" }, h("b", {}, "Set your location"), h("div", {}, "Tap the walkway where you're standing")));
      return;
    }
    if (this.mode === "browse" || !step) {
      const p = this.selected && state.index.places[this.selected];
      const imHere = (nodeId) => h("button", {
        class: "round", type: "button", "aria-label": "Set as my location", title: "I'm here",
        onclick: () => { this.onSetLocation(nodeId); this.selected = null; this.dropped = null; this.draw(); },
      }, icon("locate"));
      if (p) {
        row(h("div", { class: "eta" }, h("b", {}, p.name), h("div", {}, `${CATEGORY_NAMES[p.category] || p.category} · ${state.index.floors[p.floor].name}`)),
          imHere(p.node),
          h("button", { class: "next", type: "button", onclick: (e) => { e.currentTarget.classList.add("loading"); this.onDirections(p.id); } }, "Directions"));
      } else if (this.dropped) {
        row(h("div", { class: "eta" }, h("b", {}, "Dropped pin"), h("div", {}, `${state.index.floors[this.dropped.floor].name} · tap the button to set your location`)),
          h("button", { class: "next", type: "button", onclick: () => { this.onSetLocation(this.dropped.id); this.dropped = null; this.draw(); } }, "I'm here"));
      } else {
        row(h("div", { class: "eta" }, h("b", {}, state.mall.mall.name), h("div", {}, "Tap a store, or tap where you are")));
      }
      return;
    }
    const last = this.step === this.steps.length - 1;
    const meters = this.steps.slice(this.step).reduce((sum, st) => sum + pathMeters(st.leg), 0);
    const mins = Math.max(1, Math.round(meters / WALK_MPS / 60));
    const progress = `Step ${this.step + 1} of ${this.steps.length}`;
    const sub = this.summary ? `Done by ${this.summary.finish} · ${progress}` : progress;
    const prev = h("button", { class: "round", type: "button", "aria-label": "Previous step", disabled: this.step === 0, onclick: () => this.go(-1) }, icon("back"));
    const next = last
      ? h("button", { class: "end", type: "button", onclick: () => this.close() }, "End")
      : h("button", { class: "next", type: "button", onclick: () => this.go(1) }, step.leg.connector ? "I'm there" : "Next");
    row(h("div", { class: "eta" }, h("b", {}, `${mins} min walk`), h("div", {}, sub)), prev, next);
  }

  go(delta) {
    const from = this.shownFloor();
    this.step = Math.max(0, Math.min(this.steps.length - 1, this.step + delta));
    this.preview = null;
    this.floor = this.steps[this.step].leg.floor;
    this.transitionFloor(from, this.floor);
  }

  switchFloor(fid) {
    const from = this.shownFloor();
    if (this.mode === "route") this.preview = fid === this.floor ? null : fid;
    else this.floor = fid;
    this.selected = null;
    this.transitionFloor(from, this.shownFloor());
  }

  transitionFloor(from, to) {
    this.draw();
    this.fit(true);
    if (from === to) return;
    const dir = state.index.floors[to].level > state.index.floors[from].level ? -1 : 1;
    this.svg.animate([{ opacity: 0, transform: `translateY(${dir * 40}px)` }, { opacity: 1, transform: "none" }],
      { duration: matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 320, easing: "cubic-bezier(.2,.8,.2,1)" });
  }

  /** Frame the current step inside the area not covered by the floating panels. */
  fit(animate) {
    const floorId = this.shownFloor();
    const step = this.steps[this.step];
    const points = [];
    if (step && !this.preview && step.leg.floor === floorId) points.push(...step.leg.path);
    if (!points.length) {
      for (const st of this.stops) if (st.floor === floorId) points.push([st.x, st.y]);
      const you = atNode();
      if (you && you.floor === floorId) points.push([you.x, you.y]);
    }
    const f = state.index.floors[floorId];
    const whole = this.mode !== "route" || !points.length;
    const box = whole ? floorContentBox(f) : bbox(points, 90, 420);
    this.setCamera(this.cameraFor(box), animate);
  }

  cameraFor(box) {
    const r = this.svg.getBoundingClientRect();
    const W = r.width || 360;
    const H = r.height || 700;
    const top = this.top.getBoundingClientRect().bottom - r.top + 12;
    const bottom = r.bottom - this.sheet.getBoundingClientRect().top + 12;
    const right = this.floorsEl.getBoundingClientRect().width + 24;
    const inner = { x: 12, y: Math.max(top, 12), w: Math.max(80, W - right - 12), h: Math.max(80, H - top - bottom) };
    const ppu = Math.min(MAX_PPU, inner.w / box.w, inner.h / box.h);
    const cx = box.x + box.w / 2;
    const cy = box.y + box.h / 2;
    return { x: cx - (inner.x + inner.w / 2) / ppu, y: cy - (inner.y + inner.h / 2) / ppu, w: W / ppu, h: H / ppu };
  }

  setCamera(target, animate) {
    cancelAnimationFrame(this.raf);
    if (!animate || matchMedia("(prefers-reduced-motion: reduce)").matches) {
      this.camera = target;
      this.applyCamera();
      return;
    }
    const from = { ...this.camera };
    const t0 = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - t0) / TWEEN_MS);
      const e = 1 - Math.pow(1 - t, 3);
      this.camera = Object.fromEntries(["x", "y", "w", "h"].map((k) => [k, from[k] + (target[k] - from[k]) * e]));
      this.applyCamera();
      if (t < 1) this.raf = requestAnimationFrame(tick);
    };
    this.raf = requestAnimationFrame(tick);
  }

  applyCamera() {
    const { x, y, w, h: hh } = this.camera;
    this.svg.setAttribute("viewBox", `${x} ${y} ${w} ${hh}`);
    const ppu = (this.svg.getBoundingClientRect().width || 360) / w;
    fitLabels(this.svg, ppu);
  }

  toMap(clientX, clientY) {
    const r = this.svg.getBoundingClientRect();
    return [this.camera.x + ((clientX - r.left) / r.width) * this.camera.w, this.camera.y + ((clientY - r.top) / r.height) * this.camera.h];
  }

  zoomAt(factor, clientX, clientY) {
    const r = this.svg.getBoundingClientRect();
    const ppu = r.width / this.camera.w;
    const next = Math.min(MAX_PPU, Math.max(MIN_PPU, ppu * factor));
    const k = ppu / next;
    const [px, py] = this.toMap(clientX, clientY);
    this.camera = { x: px - (px - this.camera.x) * k, y: py - (py - this.camera.y) * k, w: this.camera.w * k, h: this.camera.h * k };
    this.applyCamera();
  }

  bindGestures() {
    const svg = this.svg;
    let pinch = null;
    let moved = 0;
    let lastTap = 0;
    svg.addEventListener("pointerdown", (e) => {
      cancelAnimationFrame(this.raf);
      svg.setPointerCapture(e.pointerId);
      this.pointers.set(e.pointerId, [e.clientX, e.clientY]);
      moved = 0;
      pinch = null;
    });
    svg.addEventListener("pointermove", (e) => {
      if (!this.pointers.has(e.pointerId)) return;
      const prev = this.pointers.get(e.pointerId);
      this.pointers.set(e.pointerId, [e.clientX, e.clientY]);
      const r = svg.getBoundingClientRect();
      if (this.pointers.size === 1) {
        const dx = e.clientX - prev[0];
        const dy = e.clientY - prev[1];
        moved += Math.abs(dx) + Math.abs(dy);
        if (moved < 6) return;
        this.camera.x -= (dx / r.width) * this.camera.w;
        this.camera.y -= (dy / r.height) * this.camera.h;
        this.applyCamera();
      } else if (this.pointers.size === 2) {
        const [a, b] = [...this.pointers.values()];
        const dist = Math.hypot(a[0] - b[0], a[1] - b[1]);
        if (pinch) this.zoomAt(dist / pinch, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2);
        pinch = dist;
        moved += 10;
      }
    });
    const end = (e) => {
      this.pointers.delete(e.pointerId);
      if (this.pointers.size < 2) pinch = null;
      if (e.type !== "pointerup" || moved > 8) return;
      const now = Date.now();
      if (now - lastTap < 280) this.zoomAt(2, e.clientX, e.clientY);
      else this.tap(e.clientX, e.clientY);
      lastTap = now;
    };
    svg.addEventListener("pointerup", end);
    svg.addEventListener("pointercancel", end);
    svg.addEventListener("wheel", (e) => {
      e.preventDefault();
      this.zoomAt(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX, e.clientY);
    }, { passive: false });
  }

  tap(clientX, clientY) {
    const [x, y] = this.toMap(clientX, clientY);
    const floorId = this.shownFloor();
    if (this.mode === "pick") {
      let best = null;
      for (const n of state.mall.nodes) {
        if (n.floor !== floorId) continue;
        const d = Math.hypot(n.x - x, n.y - y);
        if (!best || d < best.d) best = { id: n.id, d };
      }
      if (best) {
        const cb = this.onPick;
        this.close();
        cb(best.id);
      }
      return;
    }
    if (this.mode !== "browse") return;
    const hit = state.mall.places.find((p) => p.floor === floorId && insidePlace(p, x, y));
    this.selected = hit ? hit.id : null;
    this.dropped = null;
    if (!hit) {
      let best = null;
      for (const n of state.mall.nodes) {
        if (n.floor !== floorId) continue;
        const d = Math.hypot(n.x - x, n.y - y);
        if (!best || d < best.d) best = { ...n, d };
      }
      if (best && best.d < 80) this.dropped = best;
    }
    this.draw();
  }
}

/** Static mini map for chat cards. */
export function miniMap(floorId, candidates, placeIds = []) {
  const svgEl = s("svg", { class: "mini-map", role: "img", "aria-label": `Map of ${state.index.floors[floorId].name}` });
  renderFloor(svgEl, floorId, { candidates, you: false });
  const points = candidates.filter((c) => c.floor === floorId).map((c) => [c.x, c.y]);
  for (const pid of placeIds) {
    const p = state.index.places[pid];
    if (p && p.floor === floorId) points.push([p.rect[0] + p.rect[2] / 2, p.rect[1] + p.rect[3] / 2]);
  }
  const box = bbox(points, 70, 360);
  svgEl.setAttribute("viewBox", `${box.x} ${box.y} ${box.w} ${box.h}`);
  svgEl.setAttribute("preserveAspectRatio", "xMidYMid slice");
  requestAnimationFrame(() => fitLabels(svgEl, (svgEl.getBoundingClientRect().width || 340) / box.w));
  return svgEl;
}

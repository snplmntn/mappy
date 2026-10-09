import { h, s } from "./util.js";
import { state } from "./state.js";
import { bbox, pinForNode, renderFloor } from "./map.js";

const DURATIONS = [15, 30, 45, 60, 90];

function floorBadge(floorId) {
  return h("span", { class: "floor-badge", "aria-label": state.index.floors[floorId]?.name }, floorId);
}

function placesPanel(result, actions) {
  const rows = result.places.map((p) =>
    h("button", { class: "row", type: "button", onclick: () => actions.routeToPlace(p.id) },
      floorBadge(p.floor),
      h("span", { class: "row-main" },
        h("div", { class: "row-name" }, p.name, p.fictional ? h("span", { class: "demo-tag" }, "demo") : null),
        h("div", { class: "row-sub" }, p.walk_min ? `${p.walk_min} min lakad, ${p.floor_name}` : p.floor_name))));
  return h("div", { class: "panel" }, rows);
}

function stopTools(stop, errand, actions) {
  const tools = [];
  if (stop.kind !== "pick") {
    const options = DURATIONS.includes(errand.duration_min) ? DURATIONS : [...DURATIONS, errand.duration_min].sort((a, b) => a - b);
    for (const mins of options) {
      tools.push(h("button", {
        class: "chip-s", type: "button", "aria-pressed": mins === errand.duration_min ? "true" : "false",
        "aria-label": `${mins} minutes`,
        onclick: () => actions.applyEdits([{ op: "set_duration", errand: errand.id, minutes: mins }]),
      }, `${mins}m`));
    }
  }
  const status = stop.kind === "drop" ? ["dropped", "Naiwan ko na"] : stop.kind === "pick" ? ["done", "Nakuha ko na"] : ["done", "Tapos na"];
  tools.push(h("button", {
    class: "chip-s act", type: "button",
    onclick: () => actions.applyEdits([{ op: "status", errand: errand.id, status: status[0] }]),
  }, status[1]));
  return h("div", { class: "stop-tools" }, tools);
}

function planPanel(result, latest, actions) {
  const { plan, changes = [] } = result;
  if (!plan || !plan.stops.length) {
    const warnings = (plan?.warnings || []).map((w) => h("div", { class: "warn", role: "status" }, w));
    const empty = warnings.length ? "Walang ma-plano sa ngayon." : "Wala nang natitirang stops. Tapos ka na!";
    return h("div", { class: "panel" }, warnings, h("div", { class: "row" }, empty));
  }
  const errands = Object.fromEntries(state.trip.errands.map((e) => [e.id, e]));
  const changedText = changes.join(" ").toLowerCase();
  const items = plan.stops.map((stop, i) => {
    const place = state.index.places[stop.place];
    const errand = errands[stop.errand];
    const moved = errand && changedText.includes(errand.label.toLowerCase());
    return h("li", { class: `stop stop-kind-${stop.kind}${moved ? " moved" : ""}` },
      h("span", { class: "stop-num" }, String(i + 1)),
      h("span", { class: "row-name" }, place.name, place.fictional ? h("span", { class: "demo-tag" }, "demo") : null),
      h("span", { class: "stop-time" }, stop.arrive),
      h("span", { class: "stop-reason" }, `${state.index.floors[place.floor].name}. ${stop.reason}`),
      latest && errand ? stopTools(stop, errand, actions) : null);
  });
  const children = [];
  if (changes.length) children.push(h("div", { class: "changes" }, h("b", {}, "Binago"), h("ul", {}, changes.map((c) => h("li", {}, c)))));
  for (const w of plan.warnings) children.push(h("div", { class: "warn", role: "status" }, w));
  children.push(h("ol", { class: "stops" }, items));
  if (latest) {
    const elevator = h("input", {
      type: "checkbox", checked: state.trip.constraints.elevator_only,
      onchange: (e) => actions.applyEdits([{ op: "elevator_only", value: e.target.checked }]),
    });
    children.push(h("div", { class: "plan-foot" },
      h("span", { class: "plan-sum" }, "Tapos by ", h("b", {}, plan.finish_at), `, ${plan.walk_min} min lakad`),
      h("label", { class: "toggle" }, elevator, "Elevator lang"),
      h("button", { class: "primary", type: "button", onclick: () => actions.openPlan(plan) }, "Start")));
  }
  return h("div", { class: `panel${latest ? "" : " stale"}` }, children);
}

function miniMap(candidates) {
  const floor = candidates[0].floor;
  const pins = candidates.map((c, i) => ({ ...pinForNode(c.node, i + 1) })).filter((p) => p.floor === floor);
  const svgEl = s("svg", { class: "mini", role: "img", "aria-label": `Map of ${state.index.floors[floor].name}` });
  renderFloor(svgEl, floor, { pins, you: false });
  const box = bbox(pins.map((p) => [p.x, p.y]), 90, 320);
  svgEl.setAttribute("viewBox", `${box.x} ${box.y} ${box.w} ${box.h}`);
  return svgEl;
}

function locatePanel(result, latest, actions, text) {
  const { candidates, ask } = result;
  const friend = state.mode === "friend";
  const children = [miniMap(candidates)];
  if (latest) {
    const buttons = candidates.map((c, i) =>
      h("button", {
        class: "chip-s", type: "button",
        onclick: () => (friend ? actions.routeToNode(c.node) : actions.setAt({ node: c.node })),
      }, `${i + 1}: ${c.floor} ${friend ? "Puntahan" : "Ito ako"}`));
    children.push(h("div", { class: "loc-actions" }, buttons));
    if (ask === "floor") {
      const floors = [...new Set(state.index.floorOrder)];
      children.push(h("div", { class: "loc-actions" },
        floors.map((fid) => h("button", { class: "chip-s", type: "button", onclick: () => actions.relocate(text, fid) }, fid))));
    }
  }
  return h("div", { class: `panel${latest ? "" : " stale"}` }, children);
}

/** Render a chat result. latest: only the newest plan/locate panel stays interactive. */
export function renderResult(result, { latest, actions, text }) {
  if (!result) return null;
  if (result.type === "places") return placesPanel(result, actions);
  if (result.type === "plan") return planPanel(result, latest, actions);
  if (result.type === "locate" && result.candidates.length) return locatePanel(result, latest, actions, text);
  return null;
}

import { h } from "./util.js";
import { state } from "./state.js";
import { icon, categoryIcon } from "./icons.js";
import { CATEGORY_NAMES, miniMap, nodePoint } from "./map.js";

/** Class list for a control, adding the spinner when its action is running. */
const busyClass = (base, key) => (state.busy && state.pending === key ? `${base} loading` : base);

const DURATIONS = [15, 30, 45, 60, 90];

function placesCard(result, actions) {
  return h("div", { class: "card" }, result.places.map((p) =>
    h("button", { class: busyClass("row", `nav:${p.id}`), type: "button", onclick: () => actions.navigateToPlace(p.id) },
      h("span", { class: "row-icon" }, categoryIcon(p.category)),
      h("div", { class: "row-main" },
        h("div", { class: "row-title" }, p.name, p.fictional ? h("span", { class: "tag" }, "demo") : null),
        h("div", { class: "row-sub" }, [CATEGORY_NAMES[p.category] || p.category, p.floor_name, p.walk_min ? `${p.walk_min} min walk` : null]
          .filter(Boolean).join(" · "))),
      h("span", { class: "chev" }, icon("chevron")))));
}

function durationControl(errand, actions) {
  const wrap = h("div", { class: "stop-actions" });
  const collapsed = () => {
    wrap.replaceChildren(h("button", { class: busyClass("pill", `dur:${errand.id}`), type: "button", onclick: expanded }, `${errand.duration_min} min`));
    return wrap;
  };
  const expanded = () => {
    const options = DURATIONS.includes(errand.duration_min) ? DURATIONS : [...DURATIONS, errand.duration_min].sort((a, b) => a - b);
    wrap.replaceChildren(...options.map((m) => h("button", {
      class: "pill", type: "button", "aria-pressed": m === errand.duration_min ? "true" : "false",
      onclick: (e) => {
        if (m === errand.duration_min) return collapsed();
        e.currentTarget.classList.add("loading");
        return actions.applyEdits([{ op: "set_duration", errand: errand.id, minutes: m }], `dur:${errand.id}`);
      },
    }, `${m} min`)));
  };
  return collapsed();
}

function planCard(result, latest, actions) {
  const { plan, changes = [] } = result;
  const warnings = (plan?.warnings || []).map((w) => h("div", { class: "note warn", role: "status" }, w));
  if (!plan || !plan.stops.length) {
    return h("div", { class: "card" }, warnings,
      h("div", { class: "card-head" }, h("h3", {}, warnings.length ? "Nothing to plan right now" : "All done"),
        h("p", {}, warnings.length ? "Try a different request." : "You've finished every stop.")), h("div", { style: "height:12px" }));
  }
  const errands = Object.fromEntries(state.trip.errands.map((e) => [e.id, e]));
  const items = plan.stops.filter((stop) => state.index.places[stop.place]).map((stop, i) => {
    const place = state.index.places[stop.place];
    const errand = errands[stop.errand];
    const extra = [];
    if (latest && errand) {
      const status = stop.kind === "drop" ? ["dropped", "Dropped off"] : stop.kind === "pick" ? ["done", "Picked up"] : ["done", "Done"];
      const controls = stop.kind === "pick" ? h("div", { class: "stop-actions" }) : durationControl(errand, actions);
      controls.append(h("button", {
        class: busyClass("pill stop-complete", `status:${errand.id}`), type: "button",
        onclick: () => actions.applyEdits([{ op: "status", errand: errand.id, status: status[0] }], `status:${errand.id}`),
      }, icon("check", 14), status[1]));
      extra.push(controls);
    }
    return h("li", { class: `stop ${stop.kind}` },
      h("span", { class: "stop-dot" }, String(i + 1)),
      h("span", { class: "stop-title" }, place.name, place.fictional ? h("span", { class: "tag" }, "demo") : null),
      h("span", { class: "stop-time" }, stop.arrive),
      h("span", { class: "stop-why" }, `${stop.reason} · ${state.index.floors[place.floor].name}`),
      ...extra);
  });
  const children = [h("div", { class: "card-head" }, h("h3", {}, "Your plan"), h("p", {}, `Done by ${plan.finish_at} · ${plan.walk_min} min walking`))];
  if (changes.length) children.push(h("div", { class: "note changes" }, h("b", {}, "Changed"), h("ul", {}, changes.map((c) => h("li", {}, c)))));
  children.push(...warnings, h("ol", { class: "timeline" }, items));
  if (latest) {
    const elevator = h("input", {
      class: "switch", type: "checkbox", role: "switch", checked: state.trip.constraints.elevator_only,
      "aria-label": "Elevators only", disabled: state.busy,
      onchange: (e) => actions.applyEdits([{ op: "elevator_only", value: e.target.checked }], "elevator"),
    });
    children.push(h("div", { class: "card-foot" },
      h("label", { class: "switch-row" }, h("span", {}, "Elevators only"), elevator),
      h("button", { class: "primary", type: "button", onclick: () => actions.startPlan(plan) }, icon("walk"), "Start navigation")));
  }
  return h("div", { class: `card plan-card${latest ? "" : " stale"}` }, children);
}

function locateCard(result, latest, actions, text) {
  const friend = state.mode === "friend";
  const spots = result.candidates.map((c, i) => ({ ...nodePoint(c.node), label: i + 1, cand: c }));
  const children = [miniMap(spots[0].floor, spots, result.candidates[0].matched)];
  if (latest) {
    const near = (c) => c.matched.map((pid) => state.index.places[pid]?.name).filter(Boolean).join(", ");
    children.push(h("div", {}, spots.map((sp) =>
      h("button", { class: busyClass("row", `node:${sp.cand.node}`), type: "button", onclick: () => (friend ? actions.navigateToNode(sp.cand.node) : actions.setAt({ node: sp.cand.node })) },
        h("div", { class: "row-main" },
          h("div", { class: "row-title" }, `Spot ${sp.label}`),
          h("div", { class: "row-sub" }, [state.index.floors[sp.floor].name, near(sp.cand) ? `near ${near(sp.cand)}` : null].filter(Boolean).join(" · "))),
        h("span", { class: "row-sub" }, friend ? "Navigate" : "I'm here")))));
    if (result.ask === "floor") {
      children.push(h("div", { class: "stop-actions", style: "padding:0 16px 14px" },
        state.index.floorOrder.map((fid) => h("button", { class: busyClass("pill", `floor:${fid}`), type: "button", onclick: () => actions.relocate(text, fid) }, fid))));
    }
  }
  return h("div", { class: `card${latest ? "" : " stale"}` }, children);
}

export function renderResult(result, { latest, actions, text }) {
  if (!result) return null;
  if (result.type === "places") result = { ...result, places: result.places.filter((p) => state.index.places[p.id]) };
  if (result.type === "locate") result = { ...result, candidates: result.candidates.filter((c) => state.index.nodes[c.node]) };
  if (result.type === "places") return placesCard(result, actions);
  if (result.type === "plan") return planCard(result, latest, actions);
  if (result.type === "locate" && result.candidates.length) return locateCard(result, latest, actions, text);
  return null;
}

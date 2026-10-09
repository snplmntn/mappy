import { store } from "./util.js";

const KEY = "mappy.v1";
const MAX_MESSAGES = 40;
const EMPTY_TRIP = { errands: [], constraints: { deadline: null, order: [], elevator_only: false } };

const saved = store.get(KEY, {});

export const state = {
  mall: null,
  index: null,
  at: saved.at || null,
  trip: saved.trip || JSON.parse(JSON.stringify(EMPTY_TRIP)),
  messages: saved.messages || [],
  mode: "normal",
  busy: false,
  pending: null,
};

const listeners = new Set();

export function subscribe(fn) {
  listeners.add(fn);
}

export function update(patch) {
  Object.assign(state, patch);
  store.set(KEY, { at: state.at, trip: state.trip, messages: state.messages.slice(-MAX_MESSAGES) });
  listeners.forEach((fn) => fn(state));
}

export function pushMessage(msg) {
  update({ messages: [...state.messages, msg].slice(-MAX_MESSAGES) });
}

export function resetTrip() {
  update({ trip: JSON.parse(JSON.stringify(EMPTY_TRIP)) });
}

/** Lookup tables built once from mall.json. */
export function indexMall(mall) {
  const byId = (list) => Object.fromEntries(list.map((x) => [x.id, x]));
  const floorOrder = [...mall.floors].sort((a, b) => a.level - b.level || a.id.localeCompare(b.id)).map((f) => f.id);
  return {
    floors: byId(mall.floors),
    nodes: byId(mall.nodes),
    places: byId(mall.places),
    anchors: byId(mall.anchors || []),
    floorOrder,
  };
}

export function atLabel() {
  const { at, index } = state;
  if (!at || !index) return "Set your location";
  if (at.anchor && index.anchors[at.anchor]) return index.anchors[at.anchor].label;
  if (at.node && index.nodes[at.node]) {
    const n = index.nodes[at.node];
    let best = null;
    for (const p of Object.values(index.places)) {
      const door = index.nodes[p.node];
      if (!door || door.floor !== n.floor) continue;
      const d = Math.hypot(door.x - n.x, door.y - n.y);
      if (!best || d < best.d) best = { name: p.name, d };
    }
    const floor = index.floors[n.floor].name;
    return best ? `${floor}, near ${best.name}` : floor;
  }
  return "Set your location";
}

export function atNode() {
  const { at, index } = state;
  if (!at || !index) return null;
  if (at.anchor && index.anchors[at.anchor]) return index.nodes[index.anchors[at.anchor].node];
  return index.nodes[at.node] || null;
}

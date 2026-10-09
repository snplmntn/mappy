import { h, nowHHMM } from "./util.js";
import { atLabel, atNode, indexMall, pushMessage, resetTrip, state, subscribe, update } from "./state.js";
import { getJSON, OfflineError, post } from "./api.js";
import { renderChat } from "./chat.js";
import { MapView, pinForNode, pinForPlace } from "./map.js";

const OFFLINE = "Hindi ma-reach ang Mappy server. Naka-connect ka ba sa Wi-Fi na “mappy”, naka-airplane mode at naka-on ang Wi-Fi?";
const SERVER_ERROR = "May problema sa server. Subukan ulit.";
const WELCOME = "Hi! Ano ang gagawin mo sa mall? Halimbawa: “papaayos ko phone ko, kakain, tapos bibili ng regalo”.";
const FRIEND_PREFILL = "Sabi ng kaibigan ko, nasa tabi siya ng ";
const CHIPS = [["Kain", "kain"], ["CR", "CR"], ["ATM", "ATM"], ["Phone repair", "phone repair"], ["Pharmacy", "pharmacy"]];

const input = document.getElementById("input");
let map;

function botError(err) {
  pushMessage({ role: "bot", text: err instanceof OfflineError ? OFFLINE : SERVER_ERROR });
}

async function withBusy(fn) {
  if (state.busy) return;
  update({ busy: true });
  try {
    await fn();
  } catch (err) {
    botError(err);
  } finally {
    update({ busy: false });
  }
}

const actions = {
  send(text) {
    text = text.trim();
    if (!text || state.busy) return;
    pushMessage({ role: "user", text });
    return withBusy(async () => {
      const res = await post("/api/chat", { message: text, at: state.at, now: nowHHMM(), trip: state.trip });
      update({ trip: res.trip });
      pushMessage({ role: "bot", text: res.reply, result: res.result, query: text });
    });
  },

  applyEdits(edits) {
    return withBusy(async () => {
      const res = await post("/api/plan", { at: state.at, now: nowHHMM(), trip: state.trip, edits });
      if (res.question) {
        pushMessage({ role: "bot", text: res.question });
        return;
      }
      update({ trip: res.trip });
      const text = res.changes.length ? `Updated! ${res.changes.join("; ")}` : "Updated!";
      pushMessage({ role: "bot", text, result: { type: "plan", plan: res.plan, changes: res.changes } });
    });
  },

  routeToPlace(placeId) {
    const place = state.index.places[placeId];
    return this.route({ place: placeId }, pinForPlace(placeId, "★"), place.name);
  },

  routeToNode(nodeId) {
    update({ mode: "normal" });
    return this.route({ node: nodeId }, pinForNode(nodeId, "★"), "Meet-up");
  },

  route(to, pin, title) {
    return withBusy(async () => {
      const res = await post("/api/route", { at: state.at, to, elevator_only: state.trip.constraints.elevator_only });
      if (res.walk_min === null) {
        pushMessage({ role: "bot", text: "Hindi ko mahanap ang daan papunta diyan." });
      } else if (!res.legs.length) {
        pushMessage({ role: "bot", text: "Nandito ka na mismo." });
      } else {
        map.open({ legs: res.legs, pins: [pin], title });
      }
    });
  },

  openPlan(plan) {
    map.open({ legs: plan.legs, pins: plan.stops.map((st, i) => pinForPlace(st.place, i + 1)), title: "Your trip" });
  },

  setAt(at) {
    update({ at, mode: "normal" });
    pushMessage({ role: "bot", text: `Sige, nandito ka: ${atLabel()}.` });
  },

  relocate(text, floor) {
    return withBusy(async () => {
      const res = await post("/api/locate", { text, floor });
      pushMessage({ role: "bot", text: `Sa ${state.index.floors[floor].name}:`, result: { type: "locate", ...res }, query: text });
    });
  },
};

function renderChips() {
  const chips = CHIPS.map(([label, msg]) =>
    h("button", { class: "chip", type: "button", role: "listitem", onclick: () => actions.send(msg) }, label));
  chips.push(h("button", {
    class: "chip", type: "button", role: "listitem",
    onclick: () => {
      update({ mode: "friend" });
      input.value = FRIEND_PREFILL;
      input.focus();
    },
  }, "Find friend"));
  if (state.trip.errands.length) {
    chips.unshift(h("button", {
      class: "chip", type: "button", role: "listitem",
      onclick: () => {
        resetTrip();
        pushMessage({ role: "bot", text: "Bagong plano. Ano ang gagawin mo?" });
      },
    }, "Bagong plano"));
  }
  document.getElementById("chips").replaceChildren(...chips);
}

function closeSheet() {
  document.getElementById("sheet").hidden = true;
}

function openSheet() {
  const sheet = document.getElementById("sheet");
  const anchors = Object.values(state.index.anchors).map((a) =>
    h("button", { type: "button", onclick: () => { closeSheet(); actions.setAt({ anchor: a.id }); } }, a.label));
  const here = state.at ? (state.at.anchor || `node:${state.at.node}`) : null;
  const share = here
    ? [h("p", {}, "Ipa-scan sa kasama mo para makita niya kung nasaan ka:"),
      h("img", { class: "qr", alt: "QR code ng puwesto mo", src: `/api/qr?data=${encodeURIComponent(`${location.origin}/?at=${here}`)}` })]
    : [];
  const body = h("div", { class: "sheet-body" },
    h("h2", { id: "sheetTitle" }, "Nasaan ka?"),
    h("p", {}, "I-scan gamit ang camera ang location QR na malapit sa'yo, o pumili dito."),
    h("div", { class: "sheet-actions" },
      h("button", {
        type: "button",
        onclick: () => { closeSheet(); input.value = "Nasa tabi ako ng "; input.focus(); },
      }, "Sabihin ang nakikita mong store"),
      h("button", {
        type: "button",
        onclick: () => { closeSheet(); map.open({ pick: (node) => actions.setAt({ node }) }); },
      }, "Pindutin sa mapa"),
      ...anchors),
    ...share,
    h("div", { class: "sheet-actions" }, h("button", { type: "button", onclick: closeSheet }, "Isara")));
  sheet.replaceChildren(body);
  sheet.hidden = false;
}

function render() {
  document.getElementById("hereLabel").textContent = atLabel();
  document.getElementById("send").disabled = state.busy;
  renderChips();
  renderChat(actions);
}

function readAtParam() {
  const raw = new URLSearchParams(location.search).get("at");
  if (!raw) return;
  const at = raw.startsWith("node:") ? { node: raw.slice(5) } : { anchor: raw };
  if ((at.anchor && state.index.anchors[at.anchor]) || (at.node && state.index.nodes[at.node])) {
    update({ at });
  }
  history.replaceState(null, "", location.pathname);
}

async function checkHealth() {
  try {
    const health = await getJSON("/api/health", 4000);
    document.getElementById("aiBadge").classList.toggle("ok", Boolean(health.llm_ok));
  } catch {
    /* badge stays grey */
  }
}

async function boot() {
  try {
    const mall = await getJSON("/api/mall");
    update({ mall, index: indexMall(mall) });
  } catch (err) {
    document.getElementById("chat").replaceChildren(h("div", { class: "bubble" }, OFFLINE));
    return;
  }
  if (state.at && !atNode()) update({ at: null });
  readAtParam();
  document.getElementById("dataNote").textContent = state.mall.mall.note || "";
  map = new MapView();
  document.getElementById("here").addEventListener("click", openSheet);
  document.getElementById("mapBtn").addEventListener("click", () => map.open());
  document.getElementById("composer").addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value;
    input.value = "";
    actions.send(text);
  });
  subscribe(render);
  render();
  if (!state.messages.length) pushMessage({ role: "bot", text: WELCOME });
  if (!state.at) openSheet();
  checkHealth();
}

boot();

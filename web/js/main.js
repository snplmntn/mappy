import { h, nowHHMM } from "./util.js";
import { atLabel, atNode, indexMall, pushMessage, resetTrip, state, subscribe, update } from "./state.js";
import { getJSON, OfflineError, post } from "./api.js";
import { renderThread } from "./chat.js";
import { icon } from "./icons.js";
import { Navigator, nodePoint, placePoint } from "./map.js";

const OFFLINE = "Can't reach Mappy. Make sure you're on the “mappy” Wi-Fi with airplane mode on and Wi-Fi on.";
const SERVER_ERROR = "Something went wrong on the Mappy server. Try again.";

const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
let nav;

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

  prefill(text, mode = "normal") {
    update({ mode });
    input.value = text;
    autosize();
    input.focus();
  },

  applyEdits(edits) {
    return withBusy(async () => {
      const res = await post("/api/plan", { at: state.at, now: nowHHMM(), trip: state.trip, edits });
      if (res.question) {
        pushMessage({ role: "bot", text: res.question });
        return;
      }
      update({ trip: res.trip });
      pushMessage({ role: "bot", text: "Updated your plan.", result: { type: "plan", plan: res.plan, changes: res.changes } });
    });
  },

  navigateToPlace(placeId) {
    const p = state.index.places[placeId];
    return this.navigate({ place: placeId }, { ...placePoint(placeId), label: "", name: p.name, dest: true });
  },

  navigateToNode(nodeId) {
    update({ mode: "normal" });
    return this.navigate({ node: nodeId }, { ...nodePoint(nodeId), label: "", name: "your friend", dest: true });
  },

  navigate(to, stop) {
    return withBusy(async () => {
      const res = await post("/api/route", { at: state.at, to, elevator_only: state.trip.constraints.elevator_only });
      if (res.walk_min === null) pushMessage({ role: "bot", text: "I can't find a way there from where you are." });
      else if (!res.legs.length) pushMessage({ role: "bot", text: "You're already there." });
      else nav.route({ legs: res.legs, stops: [stop] });
    });
  },

  startPlan(plan) {
    const stops = plan.stops.map((st, i) => ({
      ...placePoint(st.place), label: i + 1, name: state.index.places[st.place].name, reason: st.reason,
      dest: i === plan.stops.length - 1,
    }));
    nav.route({ legs: plan.legs, stops, summary: { finish: plan.finish_at } });
  },

  setAt(at) {
    update({ at, mode: "normal" });
    pushMessage({ role: "bot", text: `Got it. You're at ${atLabel()}.` });
  },

  relocate(text, floor) {
    return withBusy(async () => {
      const res = await post("/api/locate", { text, floor });
      const msg = res.candidates.length ? `On the ${state.index.floors[floor].name}:` : `I couldn't find that on the ${state.index.floors[floor].name}.`;
      pushMessage({ role: "bot", text: msg, result: { type: "locate", ...res }, query: text });
    });
  },
};

function autosize() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
  sendBtn.disabled = !input.value.trim() || state.busy;
}

function closeModal() {
  document.getElementById("modal").hidden = true;
}

function openLocation() {
  const modal = document.getElementById("modal");
  const row = (title, sub, onclick) => h("button", { class: "row", type: "button", onclick },
    h("div", { class: "row-main" }, h("div", { class: "row-title" }, title), sub ? h("div", { class: "row-sub" }, sub) : null),
    h("span", { class: "chev" }, icon("chevron")));
  const anchors = Object.values(state.index.anchors).map((a) => row(a.label, null, () => { closeModal(); actions.setAt({ anchor: a.id }); }));
  const here = state.at ? (state.at.anchor || `node:${state.at.node}`) : null;
  const share = here
    ? [h("h2", {}, "Share your spot"), h("p", {}, "Let a friend scan this to see where you are."),
      h("img", { class: "qr", alt: "QR code for your location", src: `/api/qr?data=${encodeURIComponent(`${location.origin}/?at=${here}`)}` })]
    : [];
  modal.replaceChildren(h("div", { class: "modal-body" },
    h("div", { class: "grabber" }),
    h("h2", {}, "Where are you?"),
    h("p", {}, "Scan a Mappy location code with your camera, or choose below."),
    h("div", { class: "list" },
      row("Describe what you see", "e.g. “next to Starbucks, across from H&M”", () => { closeModal(); actions.prefill("I'm next to "); }),
      row("Tap on the map", "Pick your spot on the floor plan", () => { closeModal(); nav.pick((node) => actions.setAt({ node })); })),
    h("div", { class: "list" }, anchors),
    ...share));
  modal.hidden = false;
  modal.onclick = (e) => { if (e.target === modal) closeModal(); };
}

function render() {
  document.getElementById("placeText").textContent = atLabel();
  renderThread(actions);
  autosize();
}

function readAtParam() {
  const raw = new URLSearchParams(location.search).get("at");
  if (!raw) return;
  const at = raw.startsWith("node:") ? { node: raw.slice(5) } : { anchor: raw };
  if ((at.anchor && state.index.anchors[at.anchor]) || (at.node && state.index.nodes[at.node])) update({ at });
  history.replaceState(null, "", location.pathname);
}

async function boot() {
  document.getElementById("mapBtn").append(icon("map"));
  document.getElementById("newBtn").append(icon("compose"));
  sendBtn.append(icon("send", 18));
  try {
    const mall = await getJSON("/api/mall");
    update({ mall, index: indexMall(mall) });
  } catch {
    document.getElementById("thread").replaceChildren(h("div", { class: "empty" }, h("h1", {}, "Can't reach Mappy"), h("p", {}, OFFLINE)));
    return;
  }
  if (state.at && !atNode()) update({ at: null });
  readAtParam();
  document.getElementById("fineprint").textContent = state.mall.mall.note || "";
  nav = new Navigator({ onClose: render, onDirections: (pid) => actions.navigateToPlace(pid) });
  document.getElementById("placePill").addEventListener("click", openLocation);
  document.getElementById("mapBtn").addEventListener("click", () => nav.browse());
  document.getElementById("newBtn").addEventListener("click", () => {
    resetTrip();
    update({ messages: [], mode: "normal" });
  });
  input.addEventListener("input", autosize);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      document.getElementById("composer").requestSubmit();
    }
  });
  document.getElementById("composer").addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value;
    input.value = "";
    actions.send(text);
  });
  subscribe(render);
  render();
  if (!state.at) openLocation();
}

boot();

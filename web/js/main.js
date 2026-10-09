import { h, nowHHMM } from "./util.js";
import { atLabel, atNode, dropIfStale, indexMall, pushMessage, resetTrip, state, subscribe, update } from "./state.js";
import { getJSON, OfflineError, post } from "./api.js";
import { renderThread } from "./chat.js";
import { icon } from "./icons.js";
import { Navigator, nodePoint, placePoint } from "./map.js";

const OFFLINE = "Can't reach Mappy. Make sure you're on the “mappy” Wi-Fi with airplane mode on and Wi-Fi on.";
const SERVER_ERROR = "Something went wrong on the Mappy server. Try again.";

const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const micBtn = document.getElementById("mic");
const KEYBOARD_MIC_TIP = "Tap 🎤 on your keyboard to talk";
let nav;

function botError(err) {
  pushMessage({ role: "bot", text: err instanceof OfflineError ? OFFLINE : SERVER_ERROR });
}

/** Run an async action while the control that started it shows a spinner (state.pending = its key). */
async function withBusy(fn, pending = "send") {
  if (state.busy) return;
  update({ busy: true, pending });
  try {
    await fn();
  } catch (err) {
    botError(err);
  } finally {
    update({ busy: false, pending: null });
  }
}

let toastTimer;
function toast(text) {
  let el = document.getElementById("toast");
  if (!el) {
    el = h("div", { id: "toast", class: "toast", role: "status", "aria-live": "polite" });
    document.body.append(el);
  }
  el.textContent = text;
  el.hidden = false;
  el.animate([{ opacity: 0, transform: "translate(-50%, 8px)" }, { opacity: 1, transform: "translate(-50%, 0)" }], { duration: 180, easing: "ease-out" });
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 2200);
  if (navigator.vibrate) navigator.vibrate(10);
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

  applyEdits(edits, pending = "edit") {
    return withBusy(async () => {
      const res = await post("/api/plan", { at: state.at, now: nowHHMM(), trip: state.trip, edits });
      if (res.question) {
        pushMessage({ role: "bot", text: res.question });
        return;
      }
      update({ trip: res.trip });
      pushMessage({ role: "bot", text: "Updated your plan.", result: { type: "plan", plan: res.plan, changes: res.changes } });
    }, pending);
  },

  navigateToPlace(placeId) {
    const p = state.index.places[placeId];
    return this.navigate({ place: placeId }, { ...placePoint(placeId), label: "", name: p.name, dest: true }, `nav:${placeId}`);
  },

  navigateToNode(nodeId) {
    update({ mode: "normal" });
    return this.navigate({ node: nodeId }, { ...nodePoint(nodeId), label: "", name: "your friend", dest: true }, `node:${nodeId}`);
  },

  navigate(to, stop, pending) {
    return withBusy(async () => {
      const res = await post("/api/route", { at: state.at, to, elevator_only: state.trip.constraints.elevator_only });
      if (res.walk_min === null) pushMessage({ role: "bot", text: "I can't find a way there from where you are." });
      else if (!res.legs.length) pushMessage({ role: "bot", text: "You're already there." });
      else nav.route({ legs: res.legs, stops: [stop] });
    }, pending);
  },

  startPlan(plan) {
    const stops = plan.stops.map((st, i) => ({
      ...placePoint(st.place), label: i + 1, name: state.index.places[st.place].name, reason: st.reason,
      dest: i === plan.stops.length - 1,
    }));
    nav.route({ legs: plan.legs, stops, summary: { finish: plan.finish_at } });
  },

  setAt(at, { quiet = false } = {}) {
    update({ at, mode: "normal" });
    toast(`Location set: ${atLabel()}`);
    if (!quiet) pushMessage({ role: "bot", text: `Got it. You're at ${atLabel()}.` });
  },

  relocate(text, floor) {
    return withBusy(async () => {
      const res = await post("/api/locate", { text, floor });
      const msg = res.candidates.length ? `On the ${state.index.floors[floor].name}:` : `I couldn't find that on the ${state.index.floors[floor].name}.`;
      pushMessage({ role: "bot", text: msg, result: { type: "locate", ...res }, query: text });
    }, `floor:${floor}`);
  },
};

/** Voice input: the browser's speech recognition when allowed, otherwise the keyboard's own mic. */
let listening = null;
function startVoice() {
  if (listening) {
    listening.stop();
    return;
  }
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition || !window.isSecureContext) {
    input.focus();
    toast(KEYBOARD_MIC_TIP);
    return;
  }
  const rec = new Recognition();
  rec.lang = "en-PH";
  rec.interimResults = true;
  const before = input.value ? `${input.value.trim()} ` : "";
  rec.onresult = (e) => {
    input.value = before + [...e.results].map((r) => r[0].transcript).join("");
    autosize();
  };
  rec.onerror = () => {
    input.focus();
    toast(KEYBOARD_MIC_TIP);
  };
  rec.onend = () => {
    listening = null;
    micBtn.classList.remove("listening");
    micBtn.setAttribute("aria-label", "Speak");
    autosize();
  };
  listening = rec;
  micBtn.classList.add("listening");
  micBtn.setAttribute("aria-label", "Stop listening");
  rec.start();
}

function autosize() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
  micBtn.hidden = Boolean(input.value.trim()) && !listening;
  const sending = state.busy && state.pending === "send";
  sendBtn.classList.toggle("loading", sending);
  sendBtn.disabled = sending || !input.value.trim() || state.busy;
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
  micBtn.append(icon("mic"));
  micBtn.addEventListener("click", startVoice);
  try {
    const mall = await getJSON("/api/mall");
    dropIfStale(mall);
    update({ mall, index: indexMall(mall) });
  } catch {
    document.getElementById("thread").replaceChildren(h("div", { class: "empty" }, h("h1", {}, "Can't reach Mappy"), h("p", {}, OFFLINE)));
    return;
  }
  if (state.at && !atNode()) update({ at: null });
  readAtParam();
  document.getElementById("fineprint").textContent = state.mall.mall.note || "";
  nav = new Navigator({
    onClose: render,
    onDirections: (pid) => actions.navigateToPlace(pid),
    onSetLocation: (nodeId) => actions.setAt({ node: nodeId }, { quiet: true }),
    notify: toast,
  });
  document.getElementById("placePill").addEventListener("click", openLocation);
  document.getElementById("mapBtn").addEventListener("click", () => nav.browse());
  document.getElementById("newBtn").addEventListener("click", () => {
    resetTrip();
    update({ messages: [], mode: "normal" });
    toast("New trip");
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
  document.getElementById("thread").dataset.ok = "1";
  if (!state.at) openLocation();
}

boot();

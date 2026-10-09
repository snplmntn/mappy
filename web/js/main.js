import { h, nowHHMM } from "./util.js";
import { atLabel, atNode, dropIfStale, indexMall, pushMessage, resetTrip, savedInfo, state, subscribe, update } from "./state.js";
import { ApiError, getJSON, OfflineError, post, SERVER_ERROR, TimeoutError } from "./api.js";
import { renderThread } from "./chat.js";
import { icon } from "./icons.js";
import { Navigator, nodePoint, placePoint } from "./map.js";

const OFFLINE = "Can't reach Mappy. Make sure you're on the “mappy” Wi-Fi with airplane mode on and Wi-Fi on.";
const TIMEOUT = "Mappy is taking too long to answer. Try again.";
const ELEVATOR_BLOCKED = "There's no elevator route there. Turn off “Elevators only” in your plan to use escalators.";

const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const micBtn = document.getElementById("mic");
const KEYBOARD_MIC_TIP = "Tap 🎤 on your keyboard to talk";
let nav;

function errorText(err) {
  if (err instanceof OfflineError) return OFFLINE;
  if (err instanceof TimeoutError) return TIMEOUT;
  if (err instanceof ApiError) return err.message;
  return SERVER_ERROR;
}

function botError(err) {
  pushMessage({ role: "bot", text: errorText(err) });
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
  el.animate([{ opacity: 0, transform: "translate(-50%, 8px)" }, { opacity: 1, transform: "translate(-50%, 0)" }], { duration: matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 180, easing: "ease-out" });
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 2200);
  if (navigator.vibrate) navigator.vibrate(10);
}

const actions = {
  browse() { nav.browse(); },
  send(text) {
    text = text.trim();
    if (!text || state.busy) return;
    pushMessage({ role: "user", text });
    return withBusy(async () => {
      const res = await post("/api/chat", { message: text, at: state.at, now: nowHHMM(), trip: state.trip });
      update({ trip: res.trip });
      pushMessage({ role: "bot", text: res.reply, result: res.result, query: text, meta: res.meta });
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
      if (res.walk_min === null) {
        pushMessage({ role: "bot", text: res.reason === "elevator_only" ? ELEVATOR_BLOCKED : "I can't find a way there from where you are." });
      } else if (!res.legs.length) pushMessage({ role: "bot", text: "You're already there." });
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

let modalTrigger;
function closeModal() {
  document.getElementById("modal").hidden = true;
  document.getElementById("chatView").inert = false;
  modalTrigger?.focus();
}

function openLocation() {
  const modal = document.getElementById("modal");
  modalTrigger = document.activeElement;
  const row = (title, sub, onclick) => h("button", { class: "row", type: "button", onclick },
    h("span", { class: "row-icon" }, icon("pin")),
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
    h("button", { class: "icon-btn modal-close", type: "button", "aria-label": "Close location dialog", onclick: closeModal }, icon("close")),
    h("div", { class: "modal-emblem" }, icon("locate")),
    h("h2", { id: "locationTitle" }, "Where are you?"),
    h("p", {}, "Scan a Mappy location code with your camera, or choose below."),
    h("div", { class: "list" },
      row("Describe what you see", "e.g. “next to Starbucks, across from H&M”", () => { closeModal(); actions.prefill("I'm next to "); }),
      row("Tap on the map", "Pick your spot on the floor plan", () => { closeModal(); nav.pick((node) => actions.setAt({ node })); })),
    h("div", { class: "list" }, anchors),
    ...share));
  modal.hidden = false;
  modal.setAttribute("aria-labelledby", "locationTitle");
  document.getElementById("chatView").inert = true;
  modal.querySelector("button").focus();
  modal.onkeydown = (e) => {
    if (e.key === "Escape") closeModal();
    if (e.key === "Tab") {
      const buttons = [...modal.querySelectorAll("button")];
      const first = buttons[0], last = buttons[buttons.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  };
  modal.onclick = (e) => { if (e.target === modal) closeModal(); };
}

/** Keep the spot in the address too, so a reload finds it even where the browser drops saved data. */
function syncAtParam() {
  const at = state.at ? (state.at.anchor || `node:${state.at.node}`) : null;
  const params = new URLSearchParams(location.search);
  if (params.get("at") === at) return;
  if (at) params.set("at", at);
  else params.delete("at");
  const query = params.toString();
  history.replaceState(null, "", `${location.pathname}${query ? `?${query}` : ""}${location.hash}`);
}

function render() {
  syncAtParam();
  document.getElementById("placeText").textContent = atLabel();
  document.getElementById("newBtn").disabled = state.busy;
  renderThread(actions);
  autosize();
}

function readAtParam() {
  const raw = new URLSearchParams(location.search).get("at");
  if (!raw) return;
  const at = raw.startsWith("node:") ? { node: raw.slice(5) } : { anchor: raw };
  if ((at.anchor && state.index.anchors[at.anchor]) || (at.node && state.index.nodes[at.node])) update({ at });
}

async function boot() {
  document.getElementById("mapBtn").append(icon("map"), h("span", {}, "Map"));
  document.getElementById("newBtn").append(icon("compose"), h("span", {}, "New trip"));
  document.getElementById("locationIcon").append(icon("pin"));
  document.getElementById("composerIcon").append(icon("sparkle"));
  sendBtn.append(icon("send", 18));
  micBtn.append(icon("mic"));
  micBtn.addEventListener("click", startVoice);
  try {
    const mall = await getJSON("/api/mall");
    dropIfStale(mall);
    update({ mall, index: indexMall(mall) });
  } catch (err) {
    document.getElementById("thread").replaceChildren(h("div", { class: "empty" }, h("h1", {}, "Can't reach Mappy"), h("p", {}, errorText(err))));
    return;
  }
  if (state.at && !atNode()) update({ at: null });
  readAtParam();
  document.getElementById("fineprint").textContent = state.mall.mall.note || "";
  nav = new Navigator({
    onClose: render,
    onDirections: (pid) => actions.navigateToPlace(pid),
    onSetLocation: (nodeId) => actions.setAt({ node: nodeId }, { quiet: true }),
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
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      document.getElementById("composer").requestSubmit();
    }
  });
  document.getElementById("composer").addEventListener("submit", (e) => {
    e.preventDefault();
    if (state.busy || !input.value.trim()) return;
    const text = input.value;
    input.value = "";
    actions.send(text);
  });
  subscribe(render);
  render();
  document.getElementById("thread").dataset.ok = "1";
  if (!state.at) reportForgotSpot();
}

/** Tell the laptop why this phone asked "Where are you?" again, so lost storage can be diagnosed. */
function reportForgotSpot() {
  try {
    const nav = performance.getEntriesByType("navigation")[0];
    const info = { ...savedInfo, load: nav ? nav.type : "unknown", mallVersion: state.mall.version, url: location.href };
    const body = JSON.stringify({ message: `forgot spot: ${JSON.stringify(info)}`, stack: "", ua: navigator.userAgent });
    navigator.sendBeacon?.("/api/client-error", new Blob([body], { type: "application/json" }));
  } catch {
    /* diagnostics must never break the app */
  }
}

boot();

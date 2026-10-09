import { h, nowHHMM, store } from "./util.js";
import { atLabel, atNode, dropIfStale, indexMall, pushMessage, resetTrip, savedInfo, state, subscribe, update } from "./state.js";
import { ApiError, CancelledError, getJSON, OfflineError, post, SERVER_ERROR, TimeoutError } from "./api.js";
import { renderThread } from "./chat.js";
import { categoryIcon, icon } from "./icons.js";
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

/** The in-flight chat request, so the send button can stop it. */
let inflight = null;

/**
 * Run an async action while the control that started it shows a spinner (state.pending = its key).
 * `retry` is the message to resend from the error's "Try again" chip.
 */
async function withBusy(fn, pending = "send", retry = null) {
  if (state.busy) return;
  update({ busy: true, pending });
  try {
    await fn();
  } catch (err) {
    if (!(err instanceof CancelledError)) pushMessage({ role: "bot", text: errorText(err), ...(retry && { retry }) });
  } finally {
    inflight = null;
    update({ busy: false, pending: null });
  }
}

const RECENT_KEY = "mappy.recentSpots";
const atKey = (at) => (at ? at.anchor || `node:${at.node}` : null);

/** The last few spots the shopper set, newest first, so switching back is one tap. */
function rememberSpot(at) {
  const recent = store.get(RECENT_KEY, []).filter((r) => r.key !== atKey(at));
  store.set(RECENT_KEY, [{ key: atKey(at), at, label: atLabel() }, ...recent].slice(0, 4));
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
  /** Ask Mappy. `echo: false` resends without repeating the shopper's bubble (retry, new location). */
  send(text, { echo = true, prefix = "" } = {}) {
    text = text.trim();
    if (!text || state.busy) return;
    if (echo) pushMessage({ role: "user", text });
    const { signal } = (inflight = new AbortController());
    return withBusy(async () => {
      const res = await post("/api/chat", { message: text, at: state.at, now: nowHHMM(), trip: state.trip, prev: state.lastPlaces }, { signal });
      update({ trip: res.trip, ...(res.result?.type === "places" && { lastPlaces: res.result }) });
      pushMessage({ role: "bot", text: prefix + res.reply, result: res.result, query: text, meta: res.meta });
    }, "send", text);
  },

  stop() {
    inflight?.abort();
  },

  /** Drop a failed answer and ask the same thing again. */
  retry(index) {
    const msg = state.messages[index];
    update({ messages: state.messages.filter((_, i) => i !== index) });
    return this.send(msg.retry, { echo: false });
  },

  /** The shopper picked their spot after an answer that assumed the entrance: redo it from there. */
  locateAndRedo(at, msg) {
    this.setAt(at, { confirm: "none" });
    const prefix = `From ${atLabel()}: `;
    if (msg.result?.type === "plan") {
      return withBusy(async () => {
        const res = await post("/api/plan", { at: state.at, now: nowHHMM(), trip: state.trip, edits: [] });
        update({ trip: res.trip });
        pushMessage({ role: "bot", text: `${prefix}here's your updated plan.`, result: { type: "plan", plan: res.plan, changes: [] } });
      }, "edit");
    }
    return this.send(msg.query, { echo: false, prefix });
  },

  openLocation() { openLocation(); },

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

  /** Teach the laptop which stand-in shoppers pick for a missing store. Never blocks navigation. */
  pickAlternative(asked, place) {
    post("/api/pick", { asked, place }).catch(() => {});
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

  /** `confirm`: "chat" replies in the thread, "toast" when the thread is hidden (full-screen map), "none" when the caller says it. */
  setAt(at, { confirm = "chat" } = {}) {
    update({ at, mode: "normal" });
    rememberSpot(at);
    if (confirm === "toast") toast(`You're at ${atLabel()}`);
    if (confirm === "chat") pushMessage({ role: "bot", text: `Got it. You're at ${atLabel()}.` });
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
  // While Mappy thinks, the send button becomes a stop button, like ChatGPT.
  const sending = state.busy && state.pending === "send";
  if (sendBtn.classList.contains("stop") !== sending) {
    sendBtn.classList.toggle("stop", sending);
    sendBtn.replaceChildren(icon(sending ? "stop" : "send", 18));
    sendBtn.setAttribute("aria-label", sending ? "Stop answering" : "Send");
  }
  sendBtn.disabled = !sending && (!input.value.trim() || state.busy);
}

let modalTrigger;
function closeModal() {
  document.getElementById("modal").hidden = true;
  document.getElementById("chatView").inert = false;
  modalTrigger?.focus();
}

const MAX_SEARCH_RESULTS = 8;

/** Stores whose name matches what the shopper typed, names that start with it first. */
function searchPlaces(query) {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  return Object.values(state.index.places)
    .filter((p) => p.name.toLowerCase().includes(q))
    .sort((a, b) => Number(!a.name.toLowerCase().startsWith(q)) - Number(!b.name.toLowerCase().startsWith(q)) || a.name.localeCompare(b.name))
    .slice(0, MAX_SEARCH_RESULTS);
}

function openLocation() {
  const modal = document.getElementById("modal");
  modalTrigger = document.activeElement;
  const here = atKey(state.at);
  const choose = (at) => { closeModal(); actions.setAt(at); };
  const row = ({ badge, title, sub, current, onclick }) => h("button", { class: "row", type: "button", onclick, ...(current && { "aria-current": "true" }) },
    h("span", { class: "row-icon" }, badge),
    h("div", { class: "row-main" }, h("div", { class: "row-title" }, title), sub ? h("div", { class: "row-sub" }, sub) : null),
    h("span", { class: "chev" }, icon(current ? "check" : "chevron")));
  const floorBadge = (floorId) => h("span", { class: "floor-badge" }, floorId);
  const section = (title, rows) => (rows.length ? [h("h3", { class: "sheet-label" }, title), h("div", { class: "list" }, rows)] : []);

  const recent = store.get(RECENT_KEY, [])
    .filter((r) => r.key !== here && ((r.at.anchor && state.index.anchors[r.at.anchor]) || (r.at.node && state.index.nodes[r.at.node])))
    .slice(0, 3)
    .map((r) => row({ badge: icon("clock"), title: r.label, onclick: () => choose(r.at) }));
  const spots = Object.values(state.index.anchors).map((a) => row({
    badge: floorBadge(a.floor), title: a.label, current: here === a.id, onclick: () => choose({ anchor: a.id }),
  }));
  const other = [
    row({ badge: icon("compose"), title: "Describe what you see", sub: "e.g. “next to Starbucks, across from H&M”", onclick: () => { closeModal(); actions.prefill("I'm next to "); } }),
    row({ badge: icon("map"), title: "Tap on the map", sub: "Pick your spot on the floor plan", onclick: () => { closeModal(); nav.pick((node) => actions.setAt({ node })); } }),
  ];
  const share = here
    ? h("details", { class: "share" }, h("summary", {}, icon("friend"), "Share your spot with a friend"),
      h("img", { class: "qr", alt: "QR code for your location", src: `/api/qr?data=${encodeURIComponent(`${location.origin}/?at=${here}`)}` }))
    : null;

  const browse = h("div", {}, ...section("Recent", recent), ...section("Popular spots", spots), ...section("Other ways", other), share);
  const results = h("div", {});
  const search = h("input", {
    type: "search", placeholder: "Search a store you're next to", "aria-label": "Search a store you're next to", enterkeyhint: "search",
    oninput: () => {
      const found = searchPlaces(search.value);
      browse.hidden = Boolean(search.value.trim());
      results.replaceChildren(...(search.value.trim()
        ? found.length
          ? section("Stores", found.map((p) => row({ badge: categoryIcon(p.category), title: p.name, sub: state.index.floors[p.floor].name, onclick: () => choose({ node: p.node }) })))
          : [h("p", { class: "sheet-empty" }, `No store called “${search.value.trim()}”. Try describing what you see instead.`)]
        : []));
    },
  });

  modal.replaceChildren(h("div", { class: "modal-body" },
    h("div", { class: "grabber" }),
    h("div", { class: "sheet-head" },
      h("h2", { id: "locationTitle" }, "Where are you?"),
      h("button", { class: "icon-btn modal-close", type: "button", "aria-label": "Close location dialog", onclick: closeModal }, icon("close"))),
    h("label", { class: "sheet-search" }, icon("search", 18), search),
    results, browse));
  modal.hidden = false;
  modal.setAttribute("aria-labelledby", "locationTitle");
  document.getElementById("chatView").inert = true;
  // On phones, opening the keyboard would hide the list; let them tap the search box themselves.
  (matchMedia("(pointer: coarse)").matches ? modal.querySelector(".modal-close") : search).focus();
  modal.onkeydown = (e) => {
    if (e.key === "Escape") closeModal();
    if (e.key === "Tab") {
      const focusable = [...modal.querySelectorAll("button, input, summary")].filter((el) => el.offsetParent);
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  };
  modal.onclick = (e) => { if (e.target === modal) closeModal(); };
}

/** Keep the spot in the address too, so a reload finds it even where the browser drops saved data. */
function syncAtParam() {
  const at = atKey(state.at);
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
  const newBtn = document.getElementById("newBtn");
  newBtn.disabled = state.busy;
  newBtn.hidden = !state.messages.length; // nothing to start over from yet
  renderThread(actions);
  autosize();
}

function readAtParam() {
  const raw = new URLSearchParams(location.search).get("at");
  if (!raw) return;
  const at = raw.startsWith("node:") ? { node: raw.slice(5) } : { anchor: raw };
  if ((at.anchor && state.index.anchors[at.anchor]) || (at.node && state.index.nodes[at.node])) update({ at });
}

/** iOS slides the whole page up under the keyboard; size the app to the visible area instead. */
function fitAboveKeyboard() {
  const vv = window.visualViewport;
  if (!vv) return;
  const sync = () => {
    document.documentElement.style.setProperty("--app-height", `${vv.height}px`);
    if (window.scrollY) window.scrollTo(0, 0);
    // Keep the end of the chat (or the suggestion chips) next to the composer.
    const thread = document.getElementById("thread");
    thread.scrollTop = thread.scrollHeight;
  };
  vv.addEventListener("resize", sync);
  vv.addEventListener("scroll", sync);
  sync();
}

async function boot() {
  fitAboveKeyboard();
  document.getElementById("mapBtn").append(icon("map"), h("span", {}, "Map"));
  document.getElementById("newBtn").append(icon("compose"), h("span", {}, "New trip"));
  document.getElementById("locationIcon").append(icon("pin"));
  document.getElementById("placePill").append(h("span", { class: "place-chev", "aria-hidden": "true" }, icon("chevron", 16)));
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
    onSetLocation: (nodeId) => actions.setAt({ node: nodeId }, { confirm: "toast" }),
  });
  document.getElementById("placePill").addEventListener("click", openLocation);
  document.getElementById("mapBtn").addEventListener("click", () => nav.browse());
  document.getElementById("newBtn").addEventListener("click", () => {
    resetTrip();
    update({ messages: [], lastPlaces: null, mode: "normal" });
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
    if (e.submitter === sendBtn && sendBtn.classList.contains("stop")) return actions.stop();
    if (state.busy || !input.value.trim()) return;
    const text = input.value;
    input.value = "";
    actions.send(text);
  });
  document.getElementById("chatView").addEventListener("click", (e) => {
    if (!state.messages.length && !e.target.closest("button, a, summary, textarea, input, details")) input.focus();
  });
  subscribe(render);
  render();
  document.getElementById("thread").dataset.ok = "1";
  // Open ready to type, like a chat app. iOS ignores this until the first tap, which the listener above catches.
  input.focus();
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

import { h } from "./util.js";
import { state } from "./state.js";
import { icon } from "./icons.js";
import { renderResult } from "./cards.js";

const SUGGESTIONS = [
  { title: "Plan my errands", icon: "bag", hint: "Phone repair, lunch, a little shopping", send: "Fix my phone screen, eat, then buy a gift for mom" },
  { title: "Nearest restroom", icon: "restroom", hint: "Find the closest one", send: "restroom" },
  { title: "Find an ATM", icon: "cash", hint: "A quick stop for cash", send: "ATM" },
  { title: "Meet a friend", icon: "friend", hint: "Find your way to each other", prefill: "My friend is next to " },
];

function seconds(ms) {
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

/** One quiet line saying who understood the message and how fast, all on the local server. */
function receipt(meta) {
  if (!meta || typeof meta.ms !== "number") return null;
  const label = {
    llm: `On-device · ${meta.model} · ${seconds(meta.ms)} · nothing sent online`,
    cache: `On-device · remembered answer · ${seconds(meta.ms)}`,
    rules: `On-device · instant match · ${seconds(meta.ms)} · nothing sent online`,
    fallback: `On-device · quick parser (AI was busy) · ${seconds(meta.ms)}`,
  }[meta.engine];
  return label ? h("p", { class: "receipt" }, label) : null;
}

function latestIndex(type) {
  for (let i = state.messages.length - 1; i >= 0; i--) if (state.messages[i].result?.type === type) return i;
  return -1;
}

/** The wordmark from the QR sheet: the "m" tile starts "appy". */
function wordmark() {
  return h("span", { class: "wordmark" }, h("span", { class: "brand-symbol", "aria-hidden": "true" }, "m"), h("span", { class: "sr-only" }, "M"), "appy");
}

function emptyState(actions) {
  return h("div", { class: "empty" },
    h("h1", {}, "How can ", wordmark(), " help you today?"),
    h("p", {}, "Find a store, plan your stops, or meet a friend."),
    h("div", { class: "suggestions" }, SUGGESTIONS.map((sg) =>
      h("button", { class: "suggestion", type: "button", title: sg.hint,
        onclick: () => (sg.send ? actions.send(sg.send) : actions.prefill(sg.prefill, "friend")) },
        icon(sg.icon), h("span", {}, sg.title)))),
    h("button", { class: "browse-link", type: "button", onclick: actions.browse },
      icon("map"), `Explore ${state.mall.mall.name}`, icon("chevron")));
}

function chip(label, onclick, iconName = null) {
  return h("button", { class: "chip", type: "button", disabled: state.busy, onclick }, iconName ? icon(iconName, 16) : null, label);
}

/** Answers measured from the entrance (no spot set yet): ask where the shopper is, then redo the answer. */
function locationNudge(msg, actions) {
  return h("div", { class: "nudge" },
    h("p", {}, icon("pin", 16), "Walking times are from the main entrance. Where are you?"),
    h("div", { class: "chips" },
      Object.values(state.index.anchors).map((a) => chip(a.label, () => actions.locateAndRedo({ anchor: a.id }, msg))),
      chip("Somewhere else…", () => actions.openLocation(), "search")));
}

/** ChatGPT-style next steps under the newest answer. */
function followUps(msg, i, actions) {
  if (msg.retry) return [chip("Try again", () => actions.retry(i), "refresh")];
  const r = msg.result;
  if (r?.type === "places" && r.places.length) {
    const top = r.places.find((p) => state.index.places[p.id]);
    const more = Object.values(state.index.places).filter((p) => p.category === r.category).length > (r.shown || r.places).length;
    return [top && chip(`Take me to ${top.name}`, () => actions.navigateToPlace(top.id), "arrow"), more && chip("Show more", () => actions.send("Show more"))];
  }
  if (r?.type === "plan" && r.plan?.stops.length) return [chip("Add lunch", () => actions.send("Add lunch")), chip("Add coffee", () => actions.send("Add coffee"))];
  return [];
}

export function renderThread(actions) {
  const thread = document.getElementById("thread");
  document.getElementById("chatView").classList.toggle("is-empty", !state.messages.length && !state.busy);
  if (!state.messages.length && !state.busy) {
    thread.replaceChildren(emptyState(actions));
    thread.style.display = "flex";
    return;
  }
  thread.style.display = "";
  const latestPlan = latestIndex("plan");
  const latestLocate = latestIndex("locate");
  const nodes = state.messages.map((m, i) => {
    if (m.role === "user") return h("div", { class: "msg-user" }, m.text);
    const latest = i === latestPlan || i === latestLocate;
    const newest = i === state.messages.length - 1 && !state.busy;
    const measured = ["places", "plan"].includes(m.result?.type);
    const next = newest ? followUps(m, i, actions).filter(Boolean) : [];
    return h("div", { class: "msg-bot" }, m.text ? h("p", {}, m.text) : null, renderResult(m.result, { latest, actions, text: m.query }), receipt(m.meta),
      next.length ? h("div", { class: "chips" }, next) : null,
      newest && measured && !state.at ? locationNudge(m, actions) : null);
  });
  if (state.busy) nodes.push(h("div", { class: "msg-bot" }, h("div", { class: "typing", "aria-label": "Thinking" }, h("i"), h("i"), h("i"))));
  thread.replaceChildren(h("div", { class: "thread-inner" }, nodes));
  const lastBot = [...thread.querySelectorAll(".msg-bot")].pop();
  const tall = lastBot && lastBot.offsetHeight > thread.clientHeight * 0.75;
  thread.scrollTop = tall ? lastBot.offsetTop - thread.offsetTop - 12 : thread.scrollHeight;
}



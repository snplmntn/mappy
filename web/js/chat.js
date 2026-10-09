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
    llm: `Local AI · ${meta.model} · ${seconds(meta.ms)} · nothing sent online`,
    cache: `Local AI · remembered answer · ${seconds(meta.ms)}`,
    rules: `Instant match · ${seconds(meta.ms)} · no AI needed`,
    fallback: `Quick parser · AI was busy · ${seconds(meta.ms)}`,
  }[meta.engine];
  return label ? h("p", { class: "receipt" }, label) : null;
}

function latestIndex(type) {
  for (let i = state.messages.length - 1; i >= 0; i--) if (state.messages[i].result?.type === type) return i;
  return -1;
}

function emptyState(actions) {
  return h("div", { class: "empty" },
    h("h1", {}, "How can I help you today?"),
    h("p", {}, "Find a store, plan your stops, or meet a friend."),
    h("div", { class: "suggestions" }, SUGGESTIONS.map((sg) =>
      h("button", { class: "suggestion", type: "button", title: sg.hint,
        onclick: () => (sg.send ? actions.send(sg.send) : actions.prefill(sg.prefill, "friend")) },
        icon(sg.icon), h("span", {}, sg.title)))),
    h("button", { class: "browse-link", type: "button", onclick: actions.browse },
      icon("map"), `Explore ${state.mall.mall.name}`, icon("chevron")));
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
    return h("div", { class: "msg-bot" }, m.text ? h("p", {}, m.text) : null, renderResult(m.result, { latest, actions, text: m.query }), receipt(m.meta));
  });
  if (state.busy) nodes.push(h("div", { class: "msg-bot" }, h("div", { class: "typing", "aria-label": "Thinking" }, h("i"), h("i"), h("i"))));
  thread.replaceChildren(h("div", { class: "thread-inner" }, nodes));
  const lastBot = [...thread.querySelectorAll(".msg-bot")].pop();
  const tall = lastBot && lastBot.offsetHeight > thread.clientHeight * 0.75;
  thread.scrollTop = tall ? lastBot.offsetTop - thread.offsetTop - 12 : thread.scrollHeight;
}



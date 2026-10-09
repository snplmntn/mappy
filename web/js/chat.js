import { h } from "./util.js";
import { state } from "./state.js";
import { icon } from "./icons.js";
import { renderResult } from "./cards.js";

const SUGGESTIONS = [
  { title: "Fix my phone, eat, then buy a gift", hint: "Plans around repair time", send: "Fix my phone screen, eat, then buy a gift for mom" },
  { title: "Nearest restroom", hint: "Closest one to you", send: "restroom" },
  { title: "Find an ATM", hint: "Cash on this floor or nearby", send: "ATM" },
  { title: "Find my friend", hint: "Describe what they can see", prefill: "My friend is next to " },
];

function latestIndex(type) {
  for (let i = state.messages.length - 1; i >= 0; i--) if (state.messages[i].result?.type === type) return i;
  return -1;
}

function emptyState(actions) {
  return h("div", { class: "empty" },
    h("h1", {}, "Where to?"),
    h("p", {}, `${state.mall?.mall.name || "Mall"} · works offline`),
    h("div", { class: "suggestions" }, SUGGESTIONS.map((sg) =>
      h("button", { class: "suggestion", type: "button", onclick: () => (sg.send ? actions.send(sg.send) : actions.prefill(sg.prefill, "friend")) },
        h("b", {}, sg.title), h("span", {}, sg.hint)))));
}

export function renderThread(actions) {
  const thread = document.getElementById("thread");
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
    return h("div", { class: "msg-bot" }, m.text ? h("p", {}, m.text) : null, renderResult(m.result, { latest, actions, text: m.query }));
  });
  if (state.busy) nodes.push(h("div", { class: "msg-bot" }, h("div", { class: "typing", "aria-label": "Thinking" }, h("i"), h("i"), h("i"))));
  thread.replaceChildren(h("div", { class: "thread-inner" }, nodes));
  const lastBot = [...thread.querySelectorAll(".msg-bot")].pop();
  const tall = lastBot && lastBot.offsetHeight > thread.clientHeight * 0.75;
  thread.scrollTop = tall ? lastBot.offsetTop - thread.offsetTop - 12 : thread.scrollHeight;
}



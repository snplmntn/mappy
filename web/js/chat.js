import { h } from "./util.js";
import { state } from "./state.js";
import { renderResult } from "./cards.js";

const chatEl = () => document.getElementById("chat");

/** Index of the newest message carrying an interactive result type. */
function latestIndex(type) {
  for (let i = state.messages.length - 1; i >= 0; i--) {
    if (state.messages[i].result?.type === type) return i;
  }
  return -1;
}

export function renderChat(actions) {
  const latestPlan = latestIndex("plan");
  const latestLocate = latestIndex("locate");
  const nodes = state.messages.map((m, i) => {
    if (m.role === "user") return h("div", { class: "msg user" }, m.text);
    const latest = i === latestPlan || i === latestLocate;
    return h("div", { class: "msg bot" },
      m.text ? h("div", { class: "bubble" }, m.text) : null,
      renderResult(m.result, { latest, actions, text: m.query }));
  });
  if (state.busy) nodes.push(h("div", { class: "msg bot" }, h("div", { class: "bubble typing" }, "Nag-iisip…")));
  const el = chatEl();
  el.replaceChildren(...nodes);
  const lastBot = [...el.querySelectorAll(".msg.bot")].pop();
  const tall = lastBot && lastBot.offsetHeight > el.clientHeight * 0.8;
  el.scrollTop = tall ? lastBot.offsetTop - el.offsetTop - 8 : el.scrollHeight;
}

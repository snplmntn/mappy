import { icon } from "./icons.js";

document.querySelectorAll("[data-icon]").forEach((el) => {
  el.append(icon(el.dataset.icon));
});
document.getElementById("printButton").addEventListener("click", () => window.print());

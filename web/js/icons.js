import { s } from "./util.js";

const PATHS = {
  mic: ["M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z", "M5 11a7 7 0 0 0 14 0", "M12 18v3"],
  print: ["M6 9V3h12v6", "M6 18H3V9h18v9h-3", "M6 14h12v7H6z", "M17 11h.01"],
  wifi: ["M2 8a16 16 0 0 1 20 0", "M5 12a11 11 0 0 1 14 0", "M8 16a6 6 0 0 1 8 0", "M12 20h.01"],
  sparkle: ["M12 3l2.6 6.4L21 12l-6.4 2.6L12 21l-2.6-6.4L3 12l6.4-2.6L12 3z"],
  arrow: ["M4 12h16", "M14 6l6 6-6 6"],
  bag: ["M5 7h14l2 14H3L5 7z", "M8 8V6a4 4 0 0 1 8 0v2"],
  coffee: ["M4 8h12v7a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4V8z", "M16 9h2a3 3 0 0 1 0 6h-2", "M3 22h15", "M7 2v2", "M12 2v2"],
  food: ["M4 3v6a3 3 0 0 0 6 0V3", "M7 3v18", "M20 21V3c-4 2-5 6-5 10h5"],
  clock: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", "M12 7v5l3 2"],
  shield: ["M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3z", "M8 12l3 3 5-6"],
  layers: ["M12 3L2 8l10 5 10-5-10-5z", "M2 12l10 5 10-5", "M2 16l10 5 10-5"],
  check: ["M5 12l4 4L19 6"],
  phone: ["M7 2h10v20H7z", "M11 18h2"],
  send: ["M12 19V5", "M5 12l7-7 7 7"],
  map: ["M9 4L3 6v14l6-2 6 2 6-2V4l-6 2-6-2z", "M9 4v14", "M15 6v14"],
  compose: ["M12 20h9", "M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"],
  chevron: ["M9 6l6 6-6 6"],
  back: ["M15 18l-6-6 6-6"],
  close: ["M6 6l12 12", "M18 6L6 18"],
  walk: ["M12 20V5", "M6 11l6-6 6 6"],
  up: ["M4 19h5l9-12h2", "M15 5h5v5"],
  down: ["M4 7h5l9 12h2", "M15 21h5v-5"],
  elevator: ["M6 3h12v18H6z", "M9 10l3-3 3 3", "M9 14l3 3 3-3"],
  bridge: ["M4 12h16", "M14 6l6 6-6 6"],
  pin: ["M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z", "M12 9.5h.01"],
  locate: ["M12 2v3", "M12 19v3", "M2 12h3", "M19 12h3", "M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10z"],
  friend: ["M16 19v-1a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v1", "M9 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8z", "M22 19v-1a4 4 0 0 0-3-3.9", "M16 3.1a4 4 0 0 1 0 7.8"],
  restroom: ["M7 4a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z", "M17 4a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z", "M5 21v-6H4l1-6h4l1 6H9v6", "M15 21v-9h-1V9h6v3h-1v9", "M12 3v18"],
  cash: ["M3 6h18v12H3z", "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z", "M6 9v.01", "M18 15v.01"],
  stop: ["M7 7h10v10H7z"],
  search: ["M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z", "M20 20l-4-4"],
  refresh: ["M20 11a8 8 0 1 0-2.3 5.7", "M20 4v7h-7"],
  wrench: ["M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.8-.7-.7-2.8z"],
};

/** Inline stroke icon, 24x24 grid. */
export function icon(name, size = 20) {
  const el = s("svg", { class: "icon", viewBox: "0 0 24 24", width: size, height: size, "aria-hidden": "true", focusable: "false" });
  for (const d of PATHS[name] || []) el.append(s("path", { d }));
  return el;
}

export function categoryIcon(category) {
  return icon(({ food: "food", cafe: "coffee", phone_repair: "wrench", shoe_repair: "wrench", atm: "cash", bank: "cash", restroom: "restroom", electronics: "phone", pharmacy: "shield" })[category] || "bag");
}

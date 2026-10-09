(() => {
  let saved;
  try { saved = localStorage.getItem("mappy-theme"); } catch (_) {}
  let theme = saved === "dark" ? "dark" : "light";
  function apply() {
    document.documentElement.dataset.theme = theme;
    document.querySelectorAll('meta[name="theme-color"]').forEach(meta => {
      meta.removeAttribute("media");
      meta.content = theme === "dark" ? "#212121" : "#ffffff";
    });
    document.querySelectorAll("[data-theme-toggle]").forEach(button => {
      const next = theme === "dark" ? "light" : "dark";
      button.setAttribute("aria-label", `Switch to ${next} mode`);
      button.title = `Switch to ${next} mode`;
      button.innerHTML = `<svg class="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${next === "light" ? '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>' : '<path d="M20 15.5A9 9 0 0 1 8.5 4 9 9 0 1 0 20 15.5Z"/>'}</svg><span>${next === "light" ? "Light" : "Dark"} mode</span>`;
    });
  }
  apply();
  document.addEventListener("DOMContentLoaded", apply);
  document.addEventListener("click", event => {
    if (!event.target.closest("[data-theme-toggle]")) return;
    theme = theme === "dark" ? "light" : "dark";
    saved = theme;
    try { localStorage.setItem("mappy-theme", theme); } catch (_) {}
    apply();
  });
  window.addEventListener("mappy-theme-controls", apply);
  function syncSavedTheme() {
    try { saved = localStorage.getItem("mappy-theme"); } catch (_) {}
    theme = saved === "dark" ? "dark" : "light";
    apply();
  }
  window.addEventListener("storage", event => {
    if (event.key === "mappy-theme" || event.key === null) syncSavedTheme();
  });
  window.addEventListener("pageshow", syncSavedTheme);
})();

// Appearance panel (M8): theme + palette live on <html>, saved in the osfl_appearance cookie.
(function () {
  "use strict";
  const root = document.documentElement;
  const toggle = document.querySelector('[data-testid="appearance-toggle"]');
  const panel = document.querySelector('[data-testid="appearance-panel"]');
  if (!toggle || !panel) return;

  function save() {
    const value = `${root.dataset.theme}:${root.dataset.palette}`;
    document.cookie = `osfl_appearance=${value}; path=/; max-age=31536000; samesite=lax`;
    panel.querySelectorAll("[data-theme-choice]").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.themeChoice === root.dataset.theme)));
    panel.querySelectorAll("[data-palette-choice]").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.paletteChoice === root.dataset.palette)));
    window.dispatchEvent(new CustomEvent("osfl:appearance"));
  }

  toggle.addEventListener("click", (e) => {
    e.stopPropagation();
    panel.hidden = !panel.hidden;
    toggle.setAttribute("aria-expanded", String(!panel.hidden));
  });
  document.addEventListener("click", (e) => {
    if (!panel.hidden && !panel.contains(e.target)) { panel.hidden = true; toggle.setAttribute("aria-expanded", "false"); }
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") panel.hidden = true; });
  panel.querySelectorAll("[data-theme-choice]").forEach((b) => b.addEventListener("click", () => {
    root.dataset.theme = b.dataset.themeChoice; save();
  }));
  panel.querySelectorAll("[data-palette-choice]").forEach((b) => b.addEventListener("click", () => {
    root.dataset.palette = b.dataset.paletteChoice; save();
  }));
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () =>
    window.dispatchEvent(new CustomEvent("osfl:appearance")));
})();

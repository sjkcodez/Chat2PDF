(() => {
  const KEY = "chat-to-pdf-theme";
  const root = document.documentElement;
  const saved = localStorage.getItem(KEY);
  const prefersLight = window.matchMedia("(prefers-color-scheme: light)").matches;
  const initial = saved || (prefersLight ? "light" : "dark");
  root.setAttribute("data-theme", initial);

  function updateIcon() {
    const btn = document.getElementById("theme-toggle");
    if (!btn) return;
    btn.textContent = root.getAttribute("data-theme") === "dark" ? "🌙" : "☀️";
  }
  window.addEventListener("DOMContentLoaded", () => {
    updateIcon();
    const btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.addEventListener("click", () => {
        const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
        root.setAttribute("data-theme", next);
        localStorage.setItem(KEY, next);
        updateIcon();
      });
    }
  });
})();

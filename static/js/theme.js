/* ============================================================
   theme.js — Dark / Light mode toggle with localStorage
   ============================================================ */
(function () {
  const KEY = 'campus-theme';
  const root = document.documentElement;

  function apply(theme) {
    root.setAttribute('data-theme', theme);
    const icon = theme === 'dark' ? '☀' : '◑';
    // Update any button with id="theme-toggle" OR class="theme-toggle"
    document.querySelectorAll('#theme-toggle, .theme-toggle').forEach(btn => {
      btn.textContent = icon;
    });
  }

  // On load: restore saved or detect preference
  const saved = localStorage.getItem(KEY);
  if (saved) {
    apply(saved);
  } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    apply('dark');
  } else {
    apply('light');
  }

  window.toggleTheme = function () {
    const current = root.getAttribute('data-theme') || 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    localStorage.setItem(KEY, next);
    apply(next);
  };
})();

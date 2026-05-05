/* ============================================================
   toast.js — Lightweight toast notification system
   Usage: window.showToast('Message', 'success' | 'error' | 'warning' | '')
   ============================================================ */
(function () {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  window.showToast = function (message, type = '', duration = 3500) {
    const toast = document.createElement('div');
    toast.className = 'toast' + (type ? ` toast--${type}` : '');

    const icons = { success: '✓', error: '✕', warning: '⚠' };
    const icon = icons[type] || '●';
    toast.innerHTML = `<span style="font-weight:700;flex-shrink:0">${icon}</span><span>${message}</span>`;

    container.appendChild(toast);
    requestAnimationFrame(() => {
      requestAnimationFrame(() => toast.classList.add('show'));
    });

    setTimeout(() => {
      toast.classList.add('hide');
      toast.addEventListener('transitionend', () => toast.remove(), { once: true });
    }, duration);
  };
})();

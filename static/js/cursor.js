// ── Global Cursor Glow Effect ──────────────────────────────────
// Cyan radial spotlight that follows the cursor on blank space.
// Automatically hides over buttons, links, inputs, etc.
// Injected globally via _partials/head.html

document.addEventListener('DOMContentLoaded', function () {
  const glow = document.createElement('div');
  glow.id = 'global-cursor-glow';
  Object.assign(glow.style, {
    position:      'fixed',
    pointerEvents: 'none',
    zIndex:        '9999',
    width:         '76px',
    height:        '76px',
    borderRadius:  '50%',
    background:    'radial-gradient(circle, oklch(0.85 0.28 195 / 0.55) 0%, oklch(0.75 0.22 195 / 0.15) 60%, transparent 100%)',
    transform:     'translate(-50%, -50%)',
    left:          '-999px',
    top:           '-999px',
    opacity:       '0',
    transition:    'opacity 0.25s ease',
    willChange:    'left, top',
  });
  document.body.appendChild(glow);

  const INTERACTIVE = new Set(['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA', 'LABEL', 'NAV']);
  let mx = -999, my = -999, cx = -999, cy = -999, visible = false;

  document.addEventListener('mousemove', function(e) {
    mx = e.clientX;
    my = e.clientY;
    const hit = document.elementFromPoint(mx, my);
    const isInteractive = hit && (
      INTERACTIVE.has(hit.tagName) ||
      hit.closest('button, a, input, select, textarea, nav, [role="button"]')
    );
    visible = !isInteractive;
  });

  document.addEventListener('mouseleave', function() { visible = false; });

  (function loop() {
    cx += (mx - cx) * 0.10;
    cy += (my - cy) * 0.10;
    glow.style.left    = cx + 'px';
    glow.style.top     = cy + 'px';
    glow.style.opacity = visible ? '1' : '0';
    requestAnimationFrame(loop);
  })();
});


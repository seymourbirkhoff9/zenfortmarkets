/**
 * Adds a Show/Hide button inside every password field under `root`.
 * The button is a real <button type="button"> with aria-pressed, so it works
 * with keyboard and screen readers and never submits the form.
 */
export function passwordToggles(root = document) {
  root.querySelectorAll('input[type="password"]:not([data-reveal-ready])').forEach((input) => {
    input.dataset.revealReady = '1';
    const wrap = document.createElement('div');
    wrap.className = 'relative';
    input.replaceWith(wrap);
    wrap.append(input);
    input.classList.add('pr-16');

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'absolute inset-y-0 right-0 my-1 mr-1 rounded px-3 text-xs font-semibold text-muted hover:bg-sunken hover:text-ink';
    btn.textContent = 'Show';
    btn.setAttribute('aria-pressed', 'false');
    btn.setAttribute('aria-label', `Show ${input.labels?.[0]?.textContent?.trim().toLowerCase() || 'password'}`);
    btn.addEventListener('click', () => {
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.textContent = show ? 'Hide' : 'Show';
      btn.setAttribute('aria-pressed', String(show));
      input.focus({ preventScroll: true });
      const end = input.value.length; try { input.setSelectionRange(end, end); } catch { /* some types disallow */ }
    });
    wrap.append(btn);
  });
}

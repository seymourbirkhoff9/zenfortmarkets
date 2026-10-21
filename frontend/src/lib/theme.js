// Theme is applied before first paint by an inline script in each HTML file
// (see <head>); this module only handles toggling and persistence.
const KEY = 'zf-theme';

export function currentTheme() {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
}

export function toggleTheme() {
  const next = currentTheme() === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem(KEY, next); } catch { /* private mode */ }
  return next;
}

// ── A ready-made switch for pages outside the app shell (public site, sign-in pages) ──
import { html, render } from './dom.js';
import { icon } from './icons.js';

const label = () => (currentTheme() === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');

/** Markup for the switch. Call wireThemeButton() after it's in the page. */
export const themeButton = () => html`<button type="button" data-theme-toggle
  class="rounded p-2 text-muted hover:bg-sunken hover:text-ink" aria-label="${label()}" title="${label()}">
  ${icon(currentTheme() === 'dark' ? 'sun' : 'moon')}</button>`;

export function wireThemeButton(root = document) {
  root.querySelectorAll('[data-theme-toggle]').forEach((btn) => btn.addEventListener('click', () => {
    toggleTheme();
    render(btn, icon(currentTheme() === 'dark' ? 'sun' : 'moon'));
    btn.setAttribute('aria-label', label()); btn.title = label();
  }));
}

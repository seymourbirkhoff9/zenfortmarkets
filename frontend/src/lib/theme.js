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

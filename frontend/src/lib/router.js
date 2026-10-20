/**
 * Hash router for the two signed-in apps (app.html, admin.html).
 * Routes: { '/': view, '/customers/:id': view }. A view is
 *   async (outlet, params, query) => cleanup?
 * Its returned cleanup runs before the next route renders (clear timers etc.).
 */
export function createRouter(routes, { onRoute } = {}) {
  const table = Object.entries(routes).map(([pattern, view]) => {
    if (pattern === '*') return { pattern, rx: /^$^/, keys: [], view };   // fallback, never matched directly
    const keys = [];
    const rx = new RegExp('^' + pattern.replace(/\/:(\w+)/g, (_, k) => { keys.push(k); return '/([^/]+)'; }) + '/?$');
    return { pattern, rx, keys, view };
  });
  let cleanup = null;
  let token = 0;

  async function resolve() {
    const hash = location.hash.replace(/^#/, '') || '/';
    const [path, qs] = hash.split('?');
    const query = Object.fromEntries(new URLSearchParams(qs || ''));
    const match = table.find((r) => r.rx.test(path)) || table.find((r) => r.pattern === '*');
    const params = {};
    if (match && match.keys.length) {
      const m = path.match(match.rx);
      match.keys.forEach((k, i) => { params[k] = decodeURIComponent(m[i + 1]); });
    }
    if (typeof cleanup === 'function') cleanup();
    cleanup = null;
    const mine = ++token;
    onRoute?.(match?.pattern, path);
    // Fresh element per route: drops every listener the previous view attached.
    const old = document.getElementById('outlet');
    const outlet = old.cloneNode(false);
    old.replaceWith(outlet);
    window.scrollTo(0, 0);
    let result;
    try {
      result = await match.view(outlet, params, query);
    } catch (err) {
      if (err?.status === 401) return;   // already redirecting to sign in
      console.error(err);
      outlet.innerHTML = '<div class="panel px-6 py-10 text-center" role="alert"><p class="font-semibold">This page didn’t load</p>' +
        '<p class="mt-1 text-sm text-muted">Check your connection, then reload the page.</p></div>';
    }
    if (mine === token) cleanup = result;   // ignore views that finished after navigation
  }

  window.addEventListener('hashchange', resolve);
  return { start: resolve, go: (path) => { location.hash = path; } };
}

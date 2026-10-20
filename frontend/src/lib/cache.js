/**
 * Stale-while-revalidate cache for screen data.
 *
 *   swr('dashboard', () => api.users.dashboard(), (data, { stale }) => draw(data))
 *
 * If we've loaded this screen before, `draw` runs immediately with the last
 * data (stale: true), then again when fresh data arrives. Revisiting a page
 * is therefore instant, and the network only decides how *current* it is.
 * Kept in memory for the tab's lifetime; cleared on sign-out.
 */
const store = new Map();
const inflight = new Map();

export const peek = (key) => store.get(key)?.value;

export function invalidate(prefix = '') {
  [...store.keys()].forEach((k) => { if (k.startsWith(prefix)) store.delete(k); });
}

/** Fetch once even if several callers ask at the same time. */
export function load(key, fetcher) {
  if (inflight.has(key)) return inflight.get(key);
  const p = fetcher()
    .then((value) => { store.set(key, { value, at: Date.now() }); return value; })
    .finally(() => inflight.delete(key));
  inflight.set(key, p);
  return p;
}

export async function swr(key, fetcher, onData) {
  const hit = store.get(key);
  if (hit) onData(hit.value, { stale: true });
  const value = await load(key, fetcher);
  onData(value, { stale: false });
  return value;
}

/** Fire-and-forget warm-up, e.g. when the app is idle. Errors are ignored. */
export function prefetch(key, fetcher, maxAgeMs = 60_000) {
  const hit = store.get(key);
  if (hit && Date.now() - hit.at < maxAgeMs) return;
  load(key, fetcher).catch(() => {});
}

export const whenIdle = (fn) => (window.requestIdleCallback || ((f) => setTimeout(f, 300)))(fn);

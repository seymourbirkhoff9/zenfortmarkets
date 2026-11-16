/**
 * tracker.js — Real-time visitor & page view tracker for Zenfort Markets.
 * Generates an anonymous, persistent visitor ID and reports page visits and heartbeats.
 * Credentials ('include') are used so the backend can automatically associate visits
 * with authenticated customer accounts.
 */

function getVisitorId() {
  const KEY = 'zf_vid';
  let vid = null;
  try {
    vid = localStorage.getItem(KEY);
    if (!vid) {
      if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        vid = 'v_' + crypto.randomUUID();
      } else {
        vid = 'v_' + Math.random().toString(36).substring(2, 10) + Date.now().toString(36);
      }
      localStorage.setItem(KEY, vid);
    }
  } catch {
    vid = 'v_temp_' + Math.random().toString(36).substring(2, 10);
  }
  return vid;
}

const visitorId = getVisitorId();
let lastTrackedPath = null;
let lastTrackedTime = 0;

export function trackPageView(customPath) {
  const path = customPath || (location.pathname + (location.hash || ''));
  const now = Date.now();

  // Avoid spamming if the exact same path is fired twice within 1 second
  if (path === lastTrackedPath && now - lastTrackedTime < 1000) return;
  lastTrackedPath = path;
  lastTrackedTime = now;

  const payload = {
    visitor_id: visitorId,
    path: path.substring(0, 255),
    referrer: document.referrer ? document.referrer.substring(0, 500) : null,
  };

  try {
    fetch('/api/public/track', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(payload),
    }).catch(() => {});
  } catch {
    // Non-blocking fail-safe
  }
}

// ── Auto-tracking ──────────────────────────
if (typeof window !== 'undefined') {
  // Track initial page view
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => trackPageView());
  } else {
    trackPageView();
  }

  // Track hash or history state changes
  window.addEventListener('hashchange', () => trackPageView());
  window.addEventListener('popstate', () => trackPageView());

  // Heartbeat every 45 seconds while tab is focused/visible
  setInterval(() => {
    if (!document.hidden) {
      trackPageView();
    }
  }, 45_000);

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      trackPageView();
    }
  });
}


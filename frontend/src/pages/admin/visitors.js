import { api } from '../../lib/api.js';
import { html, on, render } from '../../lib/dom.js';
import { ago, dateTime } from '../../lib/format.js';
import { icon } from '../../lib/icons.js';
import { emptyState, errorState, skeletonRows } from '../../lib/ui.js';
import { pageHeader } from '../common.js';

export default async function visitors(outlet) {
  let timer = null;

  render(outlet, html`
    ${pageHeader('Live Traffic & Visitors', 'Real-time visibility into who is browsing the site, their current location, device, and customer account.')}
    <div id="stats-area" class="mb-6 grid gap-4 sm:grid-cols-3">
      <div class="panel p-5"><div class="text-sm font-medium text-muted">Active Now</div><div class="mt-2 text-3xl font-bold">—</div></div>
      <div class="panel p-5"><div class="text-sm font-medium text-muted">Unique Visitors (Today)</div><div class="mt-2 text-3xl font-bold">—</div></div>
      <div class="panel p-5"><div class="text-sm font-medium text-muted">Page Views (Today)</div><div class="mt-2 text-3xl font-bold">—</div></div>
    </div>
    <div id="top-pages-area" class="mb-6"></div>
    <section class="panel">
      <div class="flex items-center justify-between border-b border-line px-6 py-4">
        <h2 class="font-serif text-xl">Recent & Live Visitors</h2>
        <button id="refresh-btn" class="btn-quiet btn-sm flex items-center gap-1.5">${icon('swap', 'h-4 w-4')} Refresh</button>
      </div>
      <div id="rows">${skeletonRows(8)}</div>
    </section>
  `);

  const statsEl = outlet.querySelector('#stats-area');
  const topPagesEl = outlet.querySelector('#top-pages-area');
  const rowsEl = outlet.querySelector('#rows');

  async function load(showSkeleton = false) {
    if (showSkeleton) render(rowsEl, skeletonRows(6));
    try {
      const data = await api.admin.visitors();

      // Render top metric cards
      render(statsEl, html`
        <div class="panel p-5 border-l-4 border-l-settled">
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium text-muted">Active Right Now</span>
            <span class="relative flex h-3 w-3">
              <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-settled opacity-75"></span>
              <span class="relative inline-flex h-3 w-3 rounded-full bg-settled"></span>
            </span>
          </div>
          <div class="mt-2 text-3xl font-bold text-foreground">${data.active_now}</div>
          <div class="mt-1 text-xs text-muted">Browsing within the last 5 minutes</div>
        </div>

        <div class="panel p-5">
          <div class="text-sm font-medium text-muted">Unique Visitors Today</div>
          <div class="mt-2 text-3xl font-bold text-foreground">${data.today_visitors}</div>
          <div class="mt-1 text-xs text-muted">Individual browser sessions</div>
        </div>

        <div class="panel p-5">
          <div class="text-sm font-medium text-muted">Total Page Views Today</div>
          <div class="mt-2 text-3xl font-bold text-foreground">${data.today_page_views}</div>
          <div class="mt-1 text-xs text-muted">Page hits and route changes</div>
        </div>
      `);

      // Render top pages
      if (data.top_pages && data.top_pages.length) {
        render(topPagesEl, html`
          <div class="panel p-5">
            <h3 class="mb-3 text-sm font-medium text-muted uppercase tracking-wider">Top Pages Viewed Today</h3>
            <div class="flex flex-wrap gap-2">
              ${data.top_pages.map((p) => html`
                <div class="flex items-center gap-2 rounded bg-sunken px-3 py-1.5 text-xs">
                  <span class="font-mono font-medium text-foreground">${p.path}</span>
                  <span class="rounded bg-line px-1.5 py-0.5 font-bold">${p.views}</span>
                </div>
              `)}
            </div>
          </div>
        `);
      } else {
        render(topPagesEl, '');
      }

      // Render visitors table
      const list = data.recent_visitors || [];
      if (!list.length) {
        render(rowsEl, emptyState('No visitors recorded yet', 'Visits will appear here in real-time as users browse.'));
        return;
      }

      render(rowsEl, html`
        <div class="overflow-x-auto">
          <table class="table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Identity</th>
                <th>Current Page</th>
                <th>Location / IP</th>
                <th>Device</th>
                <th>Views</th>
                <th>Last Active</th>
              </tr>
            </thead>
            <tbody>
              ${list.map((v) => html`
                <tr>
                  <td class="whitespace-nowrap">
                    ${v.is_online
                      ? html`<span class="inline-flex items-center gap-1.5 rounded-full bg-settled/10 px-2.5 py-0.5 text-xs font-medium text-settled">
                          <span class="h-1.5 w-1.5 rounded-full bg-settled"></span> Online
                        </span>`
                      : html`<span class="inline-flex items-center rounded-full bg-sunken px-2 py-0.5 text-xs text-muted">Offline</span>`}
                  </td>
                  <td>
                    ${v.user_id
                      ? html`
                        <div>
                          <a href="#/customers/${v.user_id}" class="font-medium text-accent hover:underline">${v.user_name || 'Customer'}</a>
                          <div class="text-xs text-muted">${v.user_email}</div>
                        </div>`
                      : html`<span class="rounded bg-sunken px-2 py-0.5 text-xs text-muted">Guest / Anonymous</span>`}
                  </td>
                  <td class="max-w-[16rem] truncate font-mono text-xs">
                    <span title="${v.current_path}">${v.current_path}</span>
                  </td>
                  <td class="text-xs">
                    <div class="font-medium">${v.country || 'Unknown'}</div>
                    <div class="text-muted">${v.ip_address || '—'}</div>
                  </td>
                  <td class="text-xs text-muted">
                    <span class="capitalize">${v.device_type || 'Desktop'}</span>
                  </td>
                  <td class="text-xs font-semibold">
                    ${v.page_views}
                  </td>
                  <td class="whitespace-nowrap text-xs text-muted" title="${dateTime(v.last_seen_at)}">
                    ${ago(v.last_seen_at)}
                  </td>
                </tr>
              `)}
            </tbody>
          </table>
        </div>
      `);
    } catch (err) {
      render(rowsEl, errorState(err));
    }
  }

  on(outlet, 'click', '#refresh-btn', () => load(false));
  on(outlet, 'click', '[data-action="retry"]', () => load(true));

  // Initial load
  await load(true);

  // Auto-refresh every 15 seconds while viewing this page
  timer = setInterval(() => {
    if (!document.hidden && document.body.contains(outlet)) {
      load(false);
    }
  }, 15_000);

  // Clean up interval when navigating away
  const cleanTimer = () => {
    clearInterval(timer);
    window.removeEventListener('hashchange', cleanTimer);
  };
  window.addEventListener('hashchange', cleanTimer, { once: true });
}


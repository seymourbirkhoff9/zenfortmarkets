import { api } from '../../lib/api.js';
import { html, on, render } from '../../lib/dom.js';
import { dateTime, money, txLabel, waited } from '../../lib/format.js';
import { icon } from '../../lib/icons.js';
import { errorState, skeletonRows } from '../../lib/ui.js';
import { swr } from '../../lib/cache.js';
import { pageHeader, pill } from '../common.js';

export default async function overview(outlet) {
  render(outlet, html`${pageHeader('Overview')}<div class="panel">${skeletonRows(6)}</div>`);
  let drawn = false;
  on(outlet, 'click', 'tr[data-href]', (_, tr) => { location.hash = tr.dataset.href; });
  try {
    // One request; instant from cache when coming back to this page.
    await swr('admin:overview', api.admin.overview, (d) => { drawn = true; draw(d); });
  } catch (err) {
    if (!drawn) render(outlet, html`${pageHeader('Overview')}<div class="panel">${errorState(err)}</div>`);
    on(outlet, 'click', '[data-action="retry"]', () => window.dispatchEvent(new HashChangeEvent('hashchange')));
  }

  function draw({ stats: s, oldest, recent }) {
    const queues = [
      { href: '#/deposits', icon: 'down', name: 'Deposits to confirm', n: s.pending_deposits, amount: s.pending_deposits_amount, oldest: oldest.deposit,
        idle: 'No deposits waiting.' },
      { href: '#/withdrawals', icon: 'up', name: 'Withdrawals to pay out', n: s.pending_withdrawals, amount: s.pending_withdrawals_amount, oldest: oldest.withdrawal,
        idle: 'No payouts waiting.' },
      { href: '#/kyc', icon: 'id', name: 'Identity checks', n: s.pending_kyc, oldest: oldest.kyc,
        idle: 'No documents waiting.' },
    ];
    const totalWaiting = queues.reduce((a, q) => a + q.n, 0);

    render(outlet, html`
      ${pageHeader('Overview')}
      <section aria-labelledby="queue-h" class="panel overflow-hidden">
        <div class="flex flex-wrap items-baseline justify-between gap-2 border-b border-line px-6 py-5">
          <h2 id="queue-h" class="font-serif text-2xl">${totalWaiting === 0 ? 'Nothing needs review' : totalWaiting === 1 ? '1 item needs review' : `${totalWaiting} items need review`}</h2>
          <p class="text-sm text-muted">Oldest first in each queue.</p>
        </div>
        <ul class="divide-y divide-line">
          ${queues.map((q) => html`<li>
            <a href="${q.href}" class="grid items-center gap-4 px-6 py-4 hover:bg-sunken sm:grid-cols-[2.5rem_1fr_auto_auto]">
              <span class="hidden h-10 w-10 place-items-center rounded-full ${q.n ? 'bg-pending/10 text-pending' : 'bg-sunken text-muted'} sm:grid">${icon(q.icon)}</span>
              <span><span class="block font-semibold">${q.name}</span>
                <span class="block text-sm text-muted">${q.n ? `Oldest has waited ${waited(q.oldest)}` : q.idle}</span></span>
              <span class="text-right">${q.amount !== undefined && q.n ? html`<span class="figure text-lg">${money(q.amount)}</span>` : ''}</span>
              <span class="figure min-w-[3ch] text-right text-4xl ${q.n ? '' : 'text-muted'}">${q.n}</span>
            </a></li>`)}
        </ul>
      </section>

      <section aria-labelledby="book-h" class="mt-6">
        <h2 id="book-h" class="mb-3 text-sm font-semibold text-muted">Customer money on the books</h2>
        <div class="panel grid gap-px overflow-hidden bg-line sm:grid-cols-2 lg:grid-cols-4">
          ${[
            ['Main wallets', money(s.total_main_balance), 'Withdrawable on request'],
            ['Profit wallets', money(s.total_profit_balance), 'Returns and credits'],
            ['Invested', money(s.active_investment_capital), `${s.active_investments} active investment${s.active_investments === 1 ? '' : 's'}`],
            ['Net flow, 30 days', money(Number(s.deposits_completed_30d) - Number(s.withdrawals_completed_30d)),
              `${money(s.deposits_completed_30d)} in, ${money(s.withdrawals_completed_30d)} out`],
          ].map(([label, value, note]) => html`<div class="bg-surface p-5">
            <p class="text-sm text-muted">${label}</p><p class="figure mt-1 text-2xl">${value}</p><p class="mt-1 text-xs text-muted">${note}</p></div>`)}
        </div>
        <p class="mt-3 text-sm text-muted">${s.users_total} customer${s.users_total === 1 ? '' : 's'}. ${s.users_new_7d} joined this week. ${s.users_blocked} restricted.
          <a class="btn-link ml-1" href="#/customers">Customers</a></p>
      </section>

      <section class="panel mt-6" aria-labelledby="recent-h">
        <div class="panel-head"><h2 id="recent-h" class="panel-title">Latest ledger entries</h2><a class="btn-link" href="#/ledger">Full ledger</a></div>
        <div class="overflow-x-auto"><table class="table">
          <thead><tr><th>When</th><th>Customer</th><th>Type</th><th>Status</th><th class="text-right">Amount</th></tr></thead>
          <tbody>${recent.map((t) => html`<tr ${t.user_id ? html`data-href="#/customers/${t.user_id}"` : ''}>
            <td class="whitespace-nowrap text-muted">${dateTime(t.created_at)}</td>
            <td>${t.user_email || '—'}</td><td>${txLabel(t.tx_type)}</td><td>${pill(t.status)}</td>
            <td class="text-right figure">${money(t.amount)}</td></tr>`)}</tbody>
        </table></div>
      </section>`);
  }
}

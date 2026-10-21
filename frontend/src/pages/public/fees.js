import { contentPage } from './layout.js';
import { html, render } from '../../lib/dom.js';
import { money, pct } from '../../lib/format.js';

const API = (import.meta.env.VITE_API_BASE || '/api').replace(/\/$/, '');
const getJSON = (p) => fetch(API + p).then((r) => (r.ok ? r.json() : null)).catch(() => null);

contentPage({
  title: 'Fees and limits',
  intro: 'What it costs and what the limits are, taken live from the operator’s settings.',
  body: html`
    <section class="grid gap-6 md:grid-cols-3" data-reveal>
      ${[['No deposit fee', 'You pay only your own wallet’s network fee when you send.'],
         ['Free transfers', 'Moving money between your wallets or to another customer costs nothing.'],
         ['Withdrawal fee per network', 'A flat dollar fee, shown before you confirm, covers the payout network fee.']]
        .map(([t, d]) => html`<div class="panel p-5"><p class="font-semibold">${t}</p><p class="mt-1.5 text-sm text-muted">${d}</p></div>`)}
    </section>
    <section id="networks" class="mt-14 scroll-mt-6" data-reveal>
      <h2 class="font-serif text-2xl">Supported networks</h2>
      <div id="methods" class="panel mt-5"><p class="p-5 text-sm text-muted">Loading…</p></div>
    </section>
    <section id="plans" class="mt-14 scroll-mt-6" data-reveal>
      <h2 class="font-serif text-2xl">Investment plans</h2>
      <p class="mt-2 max-w-prose text-muted">Total over the term assumes every daily return is paid. Returns are not guaranteed.</p>
      <div id="plan-table" class="panel mt-5"><p class="p-5 text-sm text-muted">Loading…</p></div>
    </section>`,
});

const empty = (t) => html`<p class="p-5 text-sm text-muted">${t}</p>`;
getJSON('/public/payment-methods').then((ms) => render('#methods', !ms ? empty('Couldn’t load the list. Refresh to try again.')
  : !ms.length ? empty('No networks are open yet.') : html`<div class="overflow-x-auto"><table class="table">
    <thead><tr><th>Asset</th><th>Network</th><th>Minimum deposit</th><th>Minimum withdrawal</th><th>Withdrawal fee</th><th>Available for</th></tr></thead>
    <tbody>${ms.map((m) => html`<tr><td class="font-semibold">${m.asset}</td><td>${m.network}</td>
      <td class="figure">${money(m.min_deposit)}</td><td class="figure">${money(m.min_withdrawal)}</td><td class="figure">${money(m.withdrawal_fee)}</td>
      <td>${[m.deposits && 'Deposits', m.withdrawals && 'Withdrawals'].filter(Boolean).join(' and ') || 'Paused'}</td></tr>`)}</tbody></table></div>`));

getJSON('/public/plans').then((ps) => render('#plan-table', !ps ? empty('Couldn’t load the plans. Refresh to try again.')
  : !ps.length ? empty('No plans are open at the moment.') : html`<div class="overflow-x-auto"><table class="table">
    <thead><tr><th>Plan</th><th>Daily rate</th><th>Term</th><th>Amount</th><th class="text-right">Total over the term</th></tr></thead>
    <tbody>${ps.map((p) => html`<tr><td class="font-semibold">${p.name}</td><td class="figure">${pct(p.daily_roi_percent)}</td>
      <td>${p.duration_days} days</td><td class="figure">${money(p.min_amount)} to ${money(p.max_amount)}</td>
      <td class="figure text-right">${pct((Number(p.daily_roi_percent) * p.duration_days).toFixed(2))}</td></tr>`)}</tbody></table></div>`));

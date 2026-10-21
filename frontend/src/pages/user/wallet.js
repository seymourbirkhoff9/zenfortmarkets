import { api } from '../../lib/api.js';
import { html, on, render } from '../../lib/dom.js';
import { dateTime, money, shorten } from '../../lib/format.js';
import { icon } from '../../lib/icons.js';
import { copy, emptyState, errorState, skeletonRows, toastError } from '../../lib/ui.js';
import { refreshUser } from '../../session.js';
import { pageHeader, pill } from '../common.js';
import { depositDialog, withdrawDialog } from './actions.js';

export default async function wallet(outlet, _params, query) {
  let tab = query.tab === 'withdrawal' ? 'withdrawal' : 'deposit';
  let main = 0;

  const header = pageHeader('Deposits & withdrawals',
    'Crypto in and out. Each request is reviewed by an operator before money moves.',
    html`<button class="btn-primary" data-action="deposit">${icon('down', 'h-4 w-4')}Deposit</button>
         <button class="btn-quiet" data-action="withdraw">${icon('up', 'h-4 w-4')}Withdraw</button>`);

  async function load() {
    render(outlet, html`${header}<div class="panel">${skeletonRows(5)}</div>`);
    try {
      const [wallets, rows] = await Promise.all([api.wallets.list(), api.wallets.transactions({ tx_type: tab, limit: 100 }), refreshUser()]);
      main = Number(wallets.find((w) => w.wallet_type === 'main')?.balance || 0);
      render(outlet, html`${header}
        <section class="panel">
          <div class="panel-head">
            <div class="segmented" role="group" aria-label="Show">
              <button data-tab="deposit" aria-pressed="${tab === 'deposit'}">Deposits</button>
              <button data-tab="withdrawal" aria-pressed="${tab === 'withdrawal'}">Withdrawals</button>
            </div>
            <p class="text-sm text-muted">Main wallet <span class="figure ml-1 text-ink">${money(main)}</span></p>
          </div>
          ${rows.length ? html`<div class="overflow-x-auto"><table class="table">
            <thead><tr><th>Submitted</th><th>Method</th><th>${tab === 'deposit' ? 'Transaction hash' : 'Paid to'}</th><th>Status</th><th class="text-right">Amount</th></tr></thead>
            <tbody>${rows.map((t) => html`<tr>
              <td class="whitespace-nowrap text-muted">${dateTime(t.created_at)}</td>
              <td>${t.gateway_name || '—'}</td>
              <td class="font-mono text-xs">
                ${tab === 'deposit' ? (t.tx_hash ? html`<button class="hover:underline" data-copy="${t.tx_hash}" title="Copy">${shorten(t.tx_hash)}</button>` : (t.has_proof ? 'Screenshot attached' : '—'))
                  : html`<button class="hover:underline" data-copy="${t.withdrawal_address}" title="Copy">${shorten(t.withdrawal_address)}</button>
                    ${t.payout_tx_hash ? html`<span class="mt-1 block font-sans text-muted">Payout ref <button class="font-mono hover:underline" data-copy="${t.payout_tx_hash}">${shorten(t.payout_tx_hash)}</button></span>` : ''}`}
              </td>
              <td>${pill(t.status)}${t.rejection_reason ? html`<span class="mt-1 block max-w-[16rem] text-xs text-rejected">${t.rejection_reason}</span>` : ''}</td>
              <td class="text-right"><span class="figure">${money(t.amount)}</span>
                ${t.fee && Number(t.fee) ? html`<span class="block text-xs text-muted">fee ${money(t.fee)}</span>` : ''}</td>
            </tr>`)}</tbody></table></div>`
          : emptyState(tab === 'deposit' ? 'No deposits yet' : 'No withdrawals yet',
              tab === 'deposit' ? 'Send crypto to a published address, then report it here.' : 'Withdrawals you request will be listed here with their payout reference.')}
        </section>`);
    } catch (err) {
      render(outlet, html`${header}<div class="panel">${errorState(err)}</div>`);
    }
  }

  on(outlet, 'click', '[data-tab]', (_, el) => { tab = el.dataset.tab; history.replaceState(null, '', `#/wallet?tab=${tab}`); load(); });
  on(outlet, 'click', '[data-copy]', (_, el) => copy(el.dataset.copy));
  on(outlet, 'click', '[data-action]', async (_, el) => {
    try {
      const a = el.dataset.action;
      const done = a === 'deposit' ? await depositDialog() : a === 'withdraw' ? await withdrawDialog() : a === 'retry';
      if (done) load();
    } catch (err) { toastError(err); }
  });
  await load();
}

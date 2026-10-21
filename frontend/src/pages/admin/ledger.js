import { api } from '../../lib/api.js';
import { html, on, render } from '../../lib/dom.js';
import { TX_LABEL, dateTime, money, shorten, txLabel } from '../../lib/format.js';
import { copy, emptyState, errorState, skeletonRows } from '../../lib/ui.js';
import { pageHeader, pill } from '../common.js';

const PAGE = 50;

export default async function ledger(outlet, _p, query) {
  const state = { tx_type: '', status: '', q: query.q || '', skip: 0 };
  render(outlet, html`
    ${pageHeader('Ledger', 'Every balance change on the platform, newest first.')}
    <section class="panel">
      <div class="panel-head">
        <form id="f" class="flex flex-wrap gap-2" role="search">
          <label class="sr-only" for="lq">Customer email</label>
          <input class="input w-56 py-1.5 text-sm" id="lq" name="q" type="search" placeholder="Customer email" value="${state.q}" />
          <label class="sr-only" for="lt">Type</label>
          <select class="input w-auto py-1.5 text-sm" id="lt" name="tx_type"><option value="">All types</option>
            ${Object.entries(TX_LABEL).map(([v, l]) => html`<option value="${v}">${l}</option>`)}</select>
          <label class="sr-only" for="ls">Status</label>
          <select class="input w-auto py-1.5 text-sm" id="ls" name="status"><option value="">Any status</option>
            <option value="completed">Settled</option><option value="pending">Pending</option><option value="rejected">Rejected</option></select>
          <button class="btn-quiet btn-sm">Apply</button>
        </form>
        <span id="total" class="text-sm text-muted"></span>
      </div>
      <div id="rows">${skeletonRows(10)}</div>
      <div class="flex items-center justify-between border-t border-line px-5 py-3">
        <button class="btn-quiet btn-sm" data-page="-1">Newer</button><span id="range" class="text-xs text-muted"></span>
        <button class="btn-quiet btn-sm" data-page="1">Older</button></div>
    </section>`);

  const rowsEl = outlet.querySelector('#rows');
  async function load() {
    render(rowsEl, skeletonRows(8));
    try {
      const { data, headers } = await api.admin.transactions({ ...state, limit: PAGE });
      const total = Number(headers.get('X-Total-Count') || data.length);
      outlet.querySelector('#total').textContent = `${total} entr${total === 1 ? 'y' : 'ies'}`;
      outlet.querySelector('#range').textContent = total ? `${state.skip + 1}–${Math.min(state.skip + PAGE, total)}` : '';
      outlet.querySelector('[data-page="-1"]').disabled = state.skip === 0;
      outlet.querySelector('[data-page="1"]').disabled = state.skip + PAGE >= total;
      render(rowsEl, data.length ? html`<div class="overflow-x-auto"><table class="table">
        <thead><tr><th>When</th><th>Customer</th><th>Type</th><th>Detail</th><th>Status</th><th class="text-right">Amount</th></tr></thead>
        <tbody>${data.map((t) => html`<tr>
          <td class="whitespace-nowrap text-muted">${dateTime(t.created_at)}</td>
          <td>${t.user_id ? html`<a class="hover:underline" href="#/customers/${t.user_id}">${t.user_email}</a>` : '—'}</td>
          <td>${txLabel(t.tx_type)}</td>
          <td class="max-w-[22rem] text-xs text-muted">${t.description || ''}
            ${t.tx_hash ? html`<button class="block font-mono hover:underline" data-copy="${t.tx_hash}">hash ${shorten(t.tx_hash)}</button>` : ''}
            ${t.payout_tx_hash ? html`<button class="block font-mono hover:underline" data-copy="${t.payout_tx_hash}">payout ${shorten(t.payout_tx_hash)}</button>` : ''}
            ${t.rejection_reason ? html`<span class="block text-rejected">${t.rejection_reason}</span>` : ''}</td>
          <td>${pill(t.status)}</td>
          <td class="text-right figure">${money(t.amount)}</td></tr>`)}</tbody></table></div>`
        : emptyState('No entries match', 'Change the filters to see more.'));
    } catch (err) { render(rowsEl, errorState(err)); }
  }
  outlet.querySelector('#f').addEventListener('submit', (e) => {
    e.preventDefault();
    Object.assign(state, { q: e.target.q.value.trim(), tx_type: e.target.tx_type.value, status: e.target.status.value, skip: 0 });
    load();
  });
  on(outlet, 'click', '[data-page]', (_, el) => { state.skip = Math.max(0, state.skip + Number(el.dataset.page) * PAGE); load(); });
  on(outlet, 'click', '[data-copy]', (_, el) => copy(el.dataset.copy));
  on(outlet, 'click', '[data-action="retry"]', load);
  await load();
}

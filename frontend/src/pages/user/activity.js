import { api } from '../../lib/api.js';
import { html, on, render } from '../../lib/dom.js';
import { TX_LABEL } from '../../lib/format.js';
import { emptyState, errorState, skeletonRows } from '../../lib/ui.js';
import { pageHeader, txTable } from '../common.js';

const PAGE = 25;

export default async function activity(outlet) {
  const state = { tx_type: '', status: '', offset: 0 };
  render(outlet, html`
    ${pageHeader('Activity', 'Every movement on your wallets, newest first.')}
    <section class="panel">
      <div class="panel-head">
        <div class="flex flex-wrap gap-3">
          <label class="sr-only" for="f-type">Type</label>
          <select id="f-type" class="input w-auto py-1.5 text-sm">
            <option value="">All types</option>
            ${Object.entries(TX_LABEL).map(([v, l]) => html`<option value="${v}">${l}</option>`)}
          </select>
          <label class="sr-only" for="f-status">Status</label>
          <select id="f-status" class="input w-auto py-1.5 text-sm">
            <option value="">Any status</option><option value="completed">Settled</option>
            <option value="pending">Pending review</option><option value="rejected">Rejected</option>
          </select>
        </div>
      </div>
      <div id="rows">${skeletonRows(8)}</div>
      <div class="flex items-center justify-between gap-3 border-t border-line px-5 py-3">
        <button class="btn-quiet btn-sm" data-page="-1">Newer</button>
        <span id="page-label" class="text-xs text-muted"></span>
        <button class="btn-quiet btn-sm" data-page="1">Older</button>
      </div>
    </section>`);

  const rowsEl = outlet.querySelector('#rows');
  async function load() {
    render(rowsEl, skeletonRows(6));
    try {
      // Ask for one extra row to know whether an older page exists.
      const rows = await api.wallets.transactions({ tx_type: state.tx_type, status: state.status, limit: PAGE + 1, offset: state.offset });
      const hasMore = rows.length > PAGE;
      render(rowsEl, rows.length ? txTable(rows.slice(0, PAGE)) : emptyState('Nothing matches', 'Try a different type or status.'));
      outlet.querySelector('[data-page="-1"]').disabled = state.offset === 0;
      outlet.querySelector('[data-page="1"]').disabled = !hasMore;
      outlet.querySelector('#page-label').textContent = rows.length ? `Showing ${state.offset + 1}–${state.offset + Math.min(rows.length, PAGE)}` : '';
    } catch (err) { render(rowsEl, errorState(err)); }
  }
  outlet.querySelector('#f-type').addEventListener('change', (e) => { state.tx_type = e.target.value; state.offset = 0; load(); });
  outlet.querySelector('#f-status').addEventListener('change', (e) => { state.status = e.target.value; state.offset = 0; load(); });
  on(outlet, 'click', '[data-page]', (_, el) => { state.offset = Math.max(0, state.offset + Number(el.dataset.page) * PAGE); load(); });
  on(outlet, 'click', '[data-action="retry"]', load);
  await load();
}

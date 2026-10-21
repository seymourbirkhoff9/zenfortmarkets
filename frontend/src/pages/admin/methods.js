import { api } from '../../lib/api.js';
import { html, on, render } from '../../lib/dom.js';
import { money, shorten } from '../../lib/format.js';
import { confirmDialog, copy, emptyState, errorState, openDialog, skeletonRows, toast, toastError } from '../../lib/ui.js';
import { pageHeader } from '../common.js';

const num = (v) => (v === undefined || v === null || v === '' ? '' : Number(v));

function methodForm(m = {}) {
  const on_ = (k, d = true) => ((m[k] ?? d) ? 'checked' : '');
  return html`
    <div class="grid gap-4 sm:grid-cols-2">
      <div class="field"><label class="label" for="pm-asset">Asset</label>
        <input class="input uppercase" id="pm-asset" name="asset" required maxlength="20" placeholder="USDT" value="${m.asset || ''}" /></div>
      <div class="field"><label class="label" for="pm-net">Network</label>
        <input class="input" id="pm-net" name="network" required maxlength="50" placeholder="TRC20" value="${m.network || ''}" /></div>
    </div>
    <div class="field"><label class="label" for="pm-addr">Your deposit address</label>
      <input class="input font-mono text-sm" id="pm-addr" name="deposit_address" maxlength="255" autocomplete="off" spellcheck="false" value="${m.deposit_address || ''}" />
      <p class="hint">Customers send funds here. Check it carefully: a wrong address means lost deposits.</p></div>
    <div class="field"><label class="label" for="pm-memo">Memo or tag <span class="font-normal text-muted">(only for chains that need one)</span></label>
      <input class="input font-mono text-sm" id="pm-memo" name="deposit_memo" maxlength="255" value="${m.deposit_memo || ''}" /></div>
    <div class="grid gap-4 sm:grid-cols-3">
      <div class="field"><label class="label" for="pm-mind">Min deposit, USD</label><input class="input figure" id="pm-mind" name="min_deposit" type="number" min="0" step="0.01" value="${num(m.min_deposit ?? 0)}" /></div>
      <div class="field"><label class="label" for="pm-minw">Min withdrawal, USD</label><input class="input figure" id="pm-minw" name="min_withdrawal" type="number" min="0" step="0.01" value="${num(m.min_withdrawal ?? 0)}" /></div>
      <div class="field"><label class="label" for="pm-fee">Withdrawal fee, USD</label><input class="input figure" id="pm-fee" name="withdrawal_fee" type="number" min="0" step="0.01" value="${num(m.withdrawal_fee ?? 0)}" /></div>
    </div>
    <fieldset class="grid gap-2 sm:grid-cols-3"><legend class="label mb-1.5">Availability</legend>
      <label class="choice"><input type="checkbox" name="deposit_enabled" ${on_('deposit_enabled')} /><span>Deposits</span></label>
      <label class="choice"><input type="checkbox" name="withdraw_enabled" ${on_('withdraw_enabled')} /><span>Withdrawals</span></label>
      <label class="choice"><input type="checkbox" name="is_active" ${on_('is_active')} /><span>Listed</span></label>
    </fieldset>`;
}

// Unchecked checkboxes are absent from FormData, so booleans are read explicitly.
const toPayload = (v) => ({
  asset: v.asset.toUpperCase(), network: v.network,
  deposit_address: v.deposit_address || null, deposit_memo: v.deposit_memo || null,
  min_deposit: v.min_deposit || '0', min_withdrawal: v.min_withdrawal || '0', withdrawal_fee: v.withdrawal_fee || '0',
  deposit_enabled: v.deposit_enabled === 'on', withdraw_enabled: v.withdraw_enabled === 'on', is_active: v.is_active === 'on',
});

export default async function methods(outlet) {
  let list = [];
  const head = pageHeader('Payment methods',
    'The crypto rails customers can use. Deposits go to the address you publish; withdrawals are paid from your own wallet on the chosen network.',
    html`<button class="btn-primary" data-action="new">Add method</button>`);
  const state = (m) => !m.is_active ? html`<span class="pill-neutral">Hidden</span>`
    : html`${m.deposit_enabled ? html`<span class="pill-settled">Deposits</span>` : html`<span class="pill-neutral">No deposits</span>`}
           ${m.withdraw_enabled ? html`<span class="pill-settled">Withdrawals</span>` : html`<span class="pill-neutral">No withdrawals</span>`}`;

  async function load() {
    render(outlet, html`${head}<div class="panel">${skeletonRows(4)}</div>`);
    try {
      list = await api.admin.methods();
      render(outlet, html`${head}<section class="panel">
        ${list.length ? html`<div class="overflow-x-auto"><table class="table">
          <thead><tr><th>Asset</th><th>Deposit address</th><th>Limits and fee</th><th>Status</th><th><span class="sr-only">Actions</span></th></tr></thead>
          <tbody>${list.map((m) => html`<tr>
            <td><span class="font-semibold">${m.asset}</span><span class="block text-xs text-muted">${m.network}</span></td>
            <td>${m.deposit_address ? html`<button class="font-mono text-xs hover:underline" data-copy="${m.deposit_address}">${shorten(m.deposit_address, 12, 8)}</button>` : html`<span class="text-muted">—</span>`}
              ${m.deposit_memo ? html`<span class="block text-xs text-muted">Memo ${m.deposit_memo}</span>` : ''}</td>
            <td class="text-sm">Deposit from ${money(m.min_deposit)}<span class="block">Withdraw from ${money(m.min_withdrawal)}, fee ${money(m.withdrawal_fee)}</span></td>
            <td><div class="flex flex-wrap gap-1">${state(m)}</div></td>
            <td><div class="flex justify-end gap-2"><button class="btn-quiet btn-sm" data-edit="${m.id}">Edit</button>
              <button class="btn-quiet btn-sm text-rejected" data-delete="${m.id}">Remove</button></div></td>
          </tr>`)}</tbody></table></div>`
          : emptyState('No payment methods', 'Customers can’t deposit until you add at least one.', html`<button class="btn-primary" data-action="new">Add method</button>`)}
      </section>`);
    } catch (err) { render(outlet, html`${head}<div class="panel">${errorState(err)}</div>`); }
  }

  on(outlet, 'click', '[data-copy]', (_, el) => copy(el.dataset.copy, 'Address copied'));
  on(outlet, 'click', '[data-action]', async (_, el) => {
    if (el.dataset.action === 'retry') return load();
    const done = await openDialog({ title: 'Add payment method', submitLabel: 'Add method', body: methodForm(),
      onSubmit: (v) => api.admin.createMethod(toPayload(v)) });
    if (done) { toast(`${done.asset} on ${done.network} added.`); load(); }
  });
  on(outlet, 'click', '[data-edit]', async (_, el) => {
    const m = list.find((x) => x.id === el.dataset.edit);
    const done = await openDialog({ title: `Edit ${m.asset} (${m.network})`, submitLabel: 'Save changes', body: methodForm(m),
      onSubmit: (v) => api.admin.updateMethod(m.id, toPayload(v)) });
    if (done) { toast('Saved.'); load(); }
  });
  on(outlet, 'click', '[data-delete]', async (_, el) => {
    const m = list.find((x) => x.id === el.dataset.delete);
    if (!(await confirmDialog({ title: `Remove ${m.asset} (${m.network})?`, danger: true, confirmLabel: 'Remove',
      message: 'If any transaction used this method it can’t be removed; untick “Listed” instead to hide it.' }))) return;
    try { await api.admin.deleteMethod(m.id); toast('Removed.'); load(); } catch (err) { toastError(err); }
  });
  await load();
}

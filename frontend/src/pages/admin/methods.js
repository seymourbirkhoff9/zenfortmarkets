import { api } from '../../lib/api.js';
import { html, on, render } from '../../lib/dom.js';
import { money, shorten } from '../../lib/format.js';
import { confirmDialog, copy, emptyState, errorState, openDialog, skeletonRows, toast, toastError } from '../../lib/ui.js';
import { pageHeader } from '../common.js';

const num = (v) => (v === undefined || v === null || v === '' ? '' : Number(v));

// ── Crypto form ───────────────────────────────
function cryptoMethodForm(m = {}) {
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

// ── Bank transfer form ────────────────────────
function bankMethodForm(m = {}, bd = {}) {
  const on_ = (k, d = true) => ((m[k] ?? d) ? 'checked' : '');
  return html`
    <p class="mb-4 rounded border border-line bg-sunken px-3 py-2 text-sm text-muted">
      Customers will see all these details when they choose this method for a deposit. Fill in whichever fields apply to your bank.
    </p>
    <div class="grid gap-4 sm:grid-cols-2">
      <div class="field"><label class="label" for="bk-name">Bank name <span class="text-rejected">*</span></label>
        <input class="input" id="bk-name" name="bk_bank_name" required maxlength="100" placeholder="Chase, Barclays, Zenith..." value="${bd.bank_name || ''}" /></div>
      <div class="field"><label class="label" for="bk-holder">Account holder name <span class="text-rejected">*</span></label>
        <input class="input" id="bk-holder" name="bk_account_holder" required maxlength="100" placeholder="Acme Corp Ltd" value="${bd.account_holder || ''}" /></div>
    </div>
    <div class="grid gap-4 sm:grid-cols-2">
      <div class="field"><label class="label" for="bk-acct">Account number <span class="text-rejected">*</span></label>
        <input class="input font-mono" id="bk-acct" name="bk_account_number" required maxlength="50" placeholder="0123456789" value="${bd.account_number || ''}" /></div>
      <div class="field"><label class="label" for="bk-sort">Sort code / Routing number</label>
        <input class="input font-mono" id="bk-sort" name="bk_sort_code" maxlength="30" placeholder="20-00-00 or 021000021" value="${bd.sort_code || ''}" /></div>
    </div>
    <div class="grid gap-4 sm:grid-cols-2">
      <div class="field"><label class="label" for="bk-iban">IBAN <span class="font-normal text-muted">(optional)</span></label>
        <input class="input font-mono text-sm" id="bk-iban" name="bk_iban" maxlength="40" placeholder="GB29 NWBK 6016 1331 9268 19" value="${bd.iban || ''}" /></div>
      <div class="field"><label class="label" for="bk-swift">SWIFT / BIC <span class="font-normal text-muted">(optional)</span></label>
        <input class="input font-mono text-sm" id="bk-swift" name="bk_swift" maxlength="12" placeholder="CHASUS33" value="${bd.swift || ''}" /></div>
    </div>
    <div class="grid gap-4 sm:grid-cols-2">
      <div class="field"><label class="label" for="bk-cvu">CVU <span class="font-normal text-muted">(Argentina, optional)</span></label>
        <input class="input font-mono text-sm" id="bk-cvu" name="bk_cvu" maxlength="50" placeholder="0000003100012345678901" value="${bd.cvu || ''}" /></div>
      <div class="field"><label class="label" for="bk-alias">Alias <span class="font-normal text-muted">(Argentina / CBU alias, optional)</span></label>
        <input class="input" id="bk-alias" name="bk_alias" maxlength="50" placeholder="empresa.pagos.banco" value="${bd.alias || ''}" /></div>
    </div>
    <div class="field"><label class="label" for="bk-ref">Reference / notes for customer <span class="font-normal text-muted">(optional)</span></label>
      <input class="input" id="bk-ref" name="bk_reference_notes" maxlength="200"
        placeholder="Use your registered email as the payment reference" value="${bd.reference_notes || ''}" />
      <p class="hint">Shown to the customer when they select this method.</p></div>
    <div class="grid gap-4 sm:grid-cols-3">
      <div class="field"><label class="label" for="bk-mind">Min deposit, USD</label><input class="input figure" id="bk-mind" name="min_deposit" type="number" min="0" step="0.01" value="${num(m.min_deposit ?? 0)}" /></div>
      <div class="field"><label class="label" for="bk-minw">Min withdrawal, USD</label><input class="input figure" id="bk-minw" name="min_withdrawal" type="number" min="0" step="0.01" value="${num(m.min_withdrawal ?? 0)}" /></div>
      <div class="field"><label class="label" for="bk-fee">Withdrawal fee, USD</label><input class="input figure" id="bk-fee" name="withdrawal_fee" type="number" min="0" step="0.01" value="${num(m.withdrawal_fee ?? 0)}" /></div>
    </div>
    <fieldset class="grid gap-2 sm:grid-cols-3"><legend class="label mb-1.5">Availability</legend>
      <label class="choice"><input type="checkbox" name="deposit_enabled" ${on_('deposit_enabled')} /><span>Deposits</span></label>
      <label class="choice"><input type="checkbox" name="withdraw_enabled" ${on_('withdraw_enabled')} /><span>Withdrawals</span></label>
      <label class="choice"><input type="checkbox" name="is_active" ${on_('is_active')} /><span>Listed</span></label>
    </fieldset>`;
}

// ── Payload builders ──────────────────────────
const toCryptoPayload = (v) => ({
  method_type: 'crypto',
  asset: v.asset.toUpperCase(), network: v.network,
  deposit_address: v.deposit_address || null, deposit_memo: v.deposit_memo || null,
  bank_details: null,
  min_deposit: v.min_deposit || '0', min_withdrawal: v.min_withdrawal || '0', withdrawal_fee: v.withdrawal_fee || '0',
  deposit_enabled: v.deposit_enabled === 'on', withdraw_enabled: v.withdraw_enabled === 'on', is_active: v.is_active === 'on',
});

const toBankPayload = (v) => {
  const bd = {
    bank_name: v.bk_bank_name || '',
    account_holder: v.bk_account_holder || '',
    account_number: v.bk_account_number || '',
    sort_code: v.bk_sort_code || '',
    iban: v.bk_iban || '',
    swift: v.bk_swift || '',
    cvu: v.bk_cvu || '',
    alias: v.bk_alias || '',
    reference_notes: v.bk_reference_notes || '',
  };
  return {
    method_type: 'bank',
    asset: 'BANK',
    network: bd.bank_name || 'Bank Transfer',
    deposit_address: null, deposit_memo: null,
    bank_details: JSON.stringify(bd),
    min_deposit: v.min_deposit || '0', min_withdrawal: v.min_withdrawal || '0', withdrawal_fee: v.withdrawal_fee || '0',
    deposit_enabled: v.deposit_enabled === 'on', withdraw_enabled: v.withdraw_enabled === 'on', is_active: v.is_active === 'on',
  };
};

// ── Type picker dialog ────────────────────────
function openTypePicker() {
  return new Promise((resolve) => {
    const dlg = document.createElement('dialog');
    dlg.className = 'modal';
    dlg.innerHTML = `
      <div class="border-b border-line px-6 py-4 flex items-center justify-between">
        <h2 class="font-semibold text-base">Add payment method</h2>
        <button type="button" class="rounded p-1 text-muted hover:text-ink" data-close aria-label="Cancel">
          <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
      </div>
      <div class="p-6">
        <p class="mb-4 text-sm text-muted">What kind of payment method are you adding?</p>
        <div class="grid gap-3 sm:grid-cols-2">
          <button type="button" data-pick="crypto"
            class="flex flex-col items-start gap-2 rounded-lg border border-line bg-surface p-4 text-left hover:border-brass hover:bg-sunken transition-colors">
            <span class="rounded-full bg-navy/10 p-2">
              <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path stroke-linecap="round" d="M9 9.5C9 8.1 10.1 7 11.5 7h1C13.9 7 15 8.1 15 9.5S13.9 12 12.5 12h-1C10.1 12 9 13.1 9 14.5S10.1 17 11.5 17h1c1.4 0 2.5-1.1 2.5-2.5M12 6v2M12 16v2"/></svg>
            </span>
            <span class="font-semibold">Crypto</span>
            <span class="text-xs text-muted">Bitcoin, USDT, ETH and other blockchain assets. Customers send to a wallet address.</span>
          </button>
          <button type="button" data-pick="bank"
            class="flex flex-col items-start gap-2 rounded-lg border border-line bg-surface p-4 text-left hover:border-brass hover:bg-sunken transition-colors">
            <span class="rounded-full bg-navy/10 p-2">
              <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 14v3M12 14v3M16 14v3"/></svg>
            </span>
            <span class="font-semibold">Bank Transfer</span>
            <span class="text-xs text-muted">Wire, ACH, SEPA, CVU/alias. Customers transfer directly to your bank account.</span>
          </button>
        </div>
      </div>`;
    document.body.append(dlg);
    dlg.showModal();
    dlg.addEventListener('click', (e) => {
      if (e.target.closest('[data-close]') || e.target === dlg) { dlg.close(); document.body.removeChild(dlg); resolve(null); }
      const pick = e.target.closest('[data-pick]');
      if (pick) { dlg.close(); document.body.removeChild(dlg); resolve(pick.dataset.pick); }
    });
    dlg.addEventListener('cancel', () => { document.body.removeChild(dlg); resolve(null); });
  });
}

// ── Main page ─────────────────────────────────
export default async function methods(outlet) {
  let list = [];
  const head = pageHeader('Payment methods',
    'The crypto rails and bank accounts customers can use. Deposits go to the address or account you publish; withdrawals are paid from your own account.',
    html`<button class="btn-primary" data-action="new">Add method</button>`);

  const typeBadge = (m) => m.method_type === 'bank'
    ? html`<span class="pill-neutral">Bank</span>`
    : html`<span class="pill bg-sunken text-muted">Crypto</span>`;

  const addressCell = (m) => {
    if (m.method_type === 'bank') {
      try {
        const bd = JSON.parse(m.bank_details || '{}');
        return html`<span class="block font-medium text-sm">${bd.bank_name || '\u2014'}</span>
          <span class="block text-xs text-muted">${bd.account_number ? 'Acct: ' + bd.account_number : ''}</span>`;
      } catch { return html`<span class="text-muted">Bank details set</span>`; }
    }
    return m.deposit_address
      ? html`<button class="font-mono text-xs hover:underline" data-copy="${m.deposit_address}">${shorten(m.deposit_address, 12, 8)}</button>
             ${m.deposit_memo ? html`<span class="block text-xs text-muted">Memo ${m.deposit_memo}</span>` : ''}`
      : html`<span class="text-muted">\u2014</span>`;
  };

  const state = (m) => !m.is_active ? html`<span class="pill-neutral">Hidden</span>`
    : html`${m.deposit_enabled ? html`<span class="pill-settled">Deposits</span>` : html`<span class="pill-neutral">No deposits</span>`}
           ${m.withdraw_enabled ? html`<span class="pill-settled">Withdrawals</span>` : html`<span class="pill-neutral">No withdrawals</span>`}`;

  async function load() {
    render(outlet, html`${head}<div class="panel">${skeletonRows(4)}</div>`);
    try {
      list = await api.admin.methods();
      render(outlet, html`${head}<section class="panel">
        ${list.length ? html`<div class="overflow-x-auto"><table class="table">
          <thead><tr><th>Asset</th><th>Type</th><th>Account / Address</th><th>Limits and fee</th><th>Status</th><th><span class="sr-only">Actions</span></th></tr></thead>
          <tbody>${list.map((m) => html`<tr>
            <td><span class="font-semibold">${m.asset}</span><span class="block text-xs text-muted">${m.network}</span></td>
            <td>${typeBadge(m)}</td>
            <td>${addressCell(m)}</td>
            <td class="text-sm">Deposit from ${money(m.min_deposit)}<span class="block">Withdraw from ${money(m.min_withdrawal)}, fee ${money(m.withdrawal_fee)}</span></td>
            <td><div class="flex flex-wrap gap-1">${state(m)}</div></td>
            <td><div class="flex justify-end gap-2"><button class="btn-quiet btn-sm" data-edit="${m.id}">Edit</button>
              <button class="btn-quiet btn-sm text-rejected" data-delete="${m.id}">Remove</button></div></td>
          </tr>`)}</tbody></table></div>`
          : emptyState('No payment methods', 'Customers cannot deposit until you add at least one.', html`<button class="btn-primary" data-action="new">Add method</button>`)}\
      </section>`);
    } catch (err) { render(outlet, html`${head}<div class="panel">${errorState(err)}</div>`); }
  }

  on(outlet, 'click', '[data-copy]', (_, el) => copy(el.dataset.copy, 'Address copied'));

  on(outlet, 'click', '[data-action]', async (_, el) => {
    if (el.dataset.action === 'retry') return load();
    const type = await openTypePicker();
    if (!type) return;

    if (type === 'crypto') {
      const done = await openDialog({
        title: 'Add crypto method', submitLabel: 'Add method', body: cryptoMethodForm(),
        onSubmit: (v) => api.admin.createMethod(toCryptoPayload(v)),
      });
      if (done) { toast(done.asset + ' on ' + done.network + ' added.'); load(); }
    } else {
      const done = await openDialog({
        title: 'Add bank transfer', submitLabel: 'Add bank account', body: bankMethodForm(),
        onSubmit: (v) => api.admin.createMethod(toBankPayload(v)),
      });
      if (done) {
        try { const bd = JSON.parse(done.bank_details || '{}'); toast((bd.bank_name || 'Bank account') + ' added.'); }
        catch { toast('Bank transfer method added.'); }
        load();
      }
    }
  });

  on(outlet, 'click', '[data-edit]', async (_, el) => {
    const m = list.find((x) => x.id === el.dataset.edit);
    if (m.method_type === 'bank') {
      let bd = {};
      try { bd = JSON.parse(m.bank_details || '{}'); } catch { /* ignore */ }
      const done = await openDialog({
        title: 'Edit bank method (' + m.network + ')', submitLabel: 'Save changes',
        body: bankMethodForm(m, bd),
        onSubmit: (v) => api.admin.updateMethod(m.id, toBankPayload(v)),
      });
      if (done) { toast('Saved.'); load(); }
    } else {
      const done = await openDialog({
        title: 'Edit ' + m.asset + ' (' + m.network + ')', submitLabel: 'Save changes',
        body: cryptoMethodForm(m),
        onSubmit: (v) => api.admin.updateMethod(m.id, toCryptoPayload(v)),
      });
      if (done) { toast('Saved.'); load(); }
    }
  });

  on(outlet, 'click', '[data-delete]', async (_, el) => {
    const m = list.find((x) => x.id === el.dataset.delete);
    const label = m.method_type === 'bank' ? m.network + ' bank account' : m.asset + ' (' + m.network + ')';
    if (!(await confirmDialog({
      title: 'Remove ' + label + '?', danger: true, confirmLabel: 'Remove',
      message: 'If any transaction used this method it cannot be removed; untick "Listed" instead to hide it.',
    }))) return;
    try { await api.admin.deleteMethod(m.id); toast('Removed.'); load(); } catch (err) { toastError(err); }
  });

  await load();
}

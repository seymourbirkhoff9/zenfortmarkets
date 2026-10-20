import { api } from '../../lib/api.js';
import { html, on, render } from '../../lib/dom.js';
import { money, shorten, waited } from '../../lib/format.js';
import { icon } from '../../lib/icons.js';
import { copy, emptyState, errorState, openDialog, skeletonRows, toast, toastError } from '../../lib/ui.js';
import { pageHeader } from '../common.js';

const changed = () => window.dispatchEvent(new Event('zf:queues-changed'));

const customerCell = (t) => (t.user_id
  ? html`<a class="font-medium hover:underline" href="#/customers/${t.user_id}">${t.user_name || 'Customer'}</a>
    <span class="block text-xs text-muted">${t.user_email}</span>`
  : html`<span class="font-medium text-pending">Legacy record</span>
    <span class="block max-w-[14rem] text-xs text-muted">Not linked to any wallet, so it can’t be paid, credited or refunded.</span>`);

const copyable = (value, label) => value ? html`<button class="inline-flex items-center gap-1 font-mono text-xs hover:underline" data-copy="${value}" title="Copy ${label}">
  ${shorten(value, 10, 8)}${icon('copy', 'h-3.5 w-3.5 text-muted')}</button>` : html`<span class="text-muted">—</span>`;

/* ── Deposits ──────────────────────────────────────────────────────── */
export async function depositsQueue(outlet) {
  const head = pageHeader('Deposits', 'Check each payment on-chain against the hash or screenshot, then confirm or reject it. Confirming credits the customer’s Main wallet immediately.');
  async function load() {
    render(outlet, html`${head}<div class="panel">${skeletonRows(5)}</div>`);
    try {
      const rows = await api.admin.pendingDeposits();
      render(outlet, html`${head}<section class="panel">
        ${rows.length ? html`<div class="overflow-x-auto"><table class="table">
          <thead><tr><th>Waiting</th><th>Customer</th><th>Method</th><th>Evidence</th><th class="text-right">Reported amount</th><th><span class="sr-only">Actions</span></th></tr></thead>
          <tbody>${rows.map((t) => html`<tr>
            <td class="whitespace-nowrap text-muted">${waited(t.created_at)}</td>
            <td>${customerCell(t)}</td>
            <td>${t.asset}<span class="block text-xs text-muted">${t.network}</span></td>
            <td class="grid gap-1">${t.tx_hash ? copyable(t.tx_hash, 'hash') : ''}
              ${t.has_proof ? html`<button class="btn-link text-xs justify-self-start" data-proof="${t.id}">View screenshot</button>` : ''}</td>
            <td class="text-right figure text-lg">${money(t.amount)}</td>
            <td>${t.user_id ? html`<div class="flex justify-end gap-2">
              <button class="btn-quiet btn-sm" data-reject="${t.id}">Reject</button>
              <button class="btn-primary btn-sm" data-approve="${t.id}">Confirm</button></div>` : ''}</td>
          </tr>`)}</tbody></table></div>`
          : emptyState('Queue is clear', 'New deposit reports appear here, and you’ll get a notification for each one.')}
      </section>`);
      thisRows = rows;
    } catch (err) { render(outlet, html`${head}<div class="panel">${errorState(err)}</div>`); }
  }
  let thisRows = [];
  const find = (id) => thisRows.find((r) => r.id === id);

  on(outlet, 'click', '[data-copy]', (_, el) => copy(el.dataset.copy));
  on(outlet, 'click', '[data-proof]', async (_, el) => {
    try {
      const t = await api.admin.transaction(el.dataset.proof);
      openDialog({ title: `Screenshot from ${t.user_email}`, wide: true,
        body: html`<img src="${t.proof_image_url}" alt="Payment screenshot" class="mx-auto max-h-[70vh] rounded border border-line" />` });
    } catch (err) { toastError(err); }
  });
  on(outlet, 'click', '[data-approve]', async (_, el) => {
    const t = find(el.dataset.approve);
    const done = await openDialog({
      title: 'Confirm this deposit?', submitLabel: `Credit ${money(t.amount)}`,
      body: html`<p class="text-muted">${t.user_email} reported <strong class="figure text-ink">${money(t.amount)}</strong> in ${t.asset} on ${t.network}.</p>
        <p class="text-sm">Only confirm once you’ve seen the funds arrive at your ${t.asset} address. This can’t be undone from here; you’d need a manual debit.</p>`,
      onSubmit: () => api.admin.reviewDeposit(t.id, { status: 'approved' }),
    });
    if (done) { toast(`Credited ${money(t.amount)} to ${t.user_email}.`); changed(); load(); }
  });
  on(outlet, 'click', '[data-reject]', async (_, el) => {
    const t = find(el.dataset.reject);
    const done = await openDialog({
      title: 'Reject this deposit', submitLabel: 'Reject deposit', danger: true,
      body: html`<p class="text-muted">${t.user_email} will see this reason.</p>
        <div class="field"><label class="label" for="rej">Reason</label>
          <textarea class="input" id="rej" name="rejection_reason" rows="3" required maxlength="500" placeholder="e.g. No matching payment found for this hash."></textarea></div>`,
      onSubmit: (v) => api.admin.reviewDeposit(t.id, { status: 'rejected', rejection_reason: v.rejection_reason }),
    });
    if (done) { toast('Deposit rejected. The customer has been notified.'); changed(); load(); }
  });
  on(outlet, 'click', '[data-action="retry"]', load);
  await load();
}

/* ── Withdrawals ───────────────────────────────────────────────────── */
export async function withdrawalsQueue(outlet) {
  const head = pageHeader('Withdrawals', 'Funds are already held from the customer’s Main wallet. Send the payout from your own wallet, then record the payout hash. Rejecting returns the full amount.');
  let rows = [];
  async function load() {
    render(outlet, html`${head}<div class="panel">${skeletonRows(5)}</div>`);
    try {
      rows = await api.admin.pendingWithdrawals();
      render(outlet, html`${head}<section class="panel">
        ${rows.length ? html`<div class="overflow-x-auto"><table class="table">
          <thead><tr><th>Waiting</th><th>Customer</th><th>Pay out</th><th>To address</th><th class="text-right">Send</th><th><span class="sr-only">Actions</span></th></tr></thead>
          <tbody>${rows.map((t) => html`<tr>
            <td class="whitespace-nowrap text-muted">${waited(t.created_at)}</td>
            <td>${customerCell(t)}</td>
            <td>${t.asset}<span class="block text-xs text-muted">${t.network}</span></td>
            <td>${copyable(t.withdrawal_address, 'address')}
              ${t.withdrawal_details ? html`<span class="mt-1 block max-w-[16rem] text-xs">Note: ${t.withdrawal_details}</span>` : ''}</td>
            <td class="text-right"><span class="figure text-lg">${money(Number(t.amount) - Number(t.fee || 0))}</span>
              <span class="block text-xs text-muted">${money(t.amount)} held, ${money(t.fee || 0)} fee</span></td>
            <td>${t.user_id ? html`<div class="flex justify-end gap-2">
              <button class="btn-quiet btn-sm" data-reject="${t.id}">Reject</button>
              <button class="btn-primary btn-sm" data-pay="${t.id}">Mark paid</button></div>` : ''}</td>
          </tr>`)}</tbody></table></div>`
          : emptyState('Queue is clear', 'Withdrawal requests appear here, and you’ll get a notification for each one.')}
      </section>`);
    } catch (err) { render(outlet, html`${head}<div class="panel">${errorState(err)}</div>`); }
  }
  const find = (id) => rows.find((r) => r.id === id);

  on(outlet, 'click', '[data-copy]', (_, el) => copy(el.dataset.copy));
  on(outlet, 'click', '[data-pay]', async (_, el) => {
    const t = find(el.dataset.pay);
    const sendAmt = money(Number(t.amount) - Number(t.fee || 0));
    const done = await openDialog({
      title: 'Record the payout', submitLabel: 'Mark as paid',
      body: html`
        <dl class="grid grid-cols-[8rem_1fr] gap-x-4 gap-y-2 rounded border border-line bg-sunken p-4 text-sm">
          <dt class="text-muted">Customer</dt><dd>${t.user_email}</dd>
          <dt class="text-muted">Send</dt><dd class="figure">${sendAmt} worth of ${t.asset}</dd>
          <dt class="text-muted">Network</dt><dd>${t.network}</dd>
          <dt class="text-muted">Address</dt><dd class="break-all font-mono text-xs">${t.withdrawal_address}</dd>
          ${t.withdrawal_details ? html`<dt class="text-muted">Note</dt><dd>${t.withdrawal_details}</dd>` : ''}
        </dl>
        <div class="field"><label class="label" for="ph">Payout transaction hash</label>
          <input class="input font-mono text-sm" id="ph" name="payout_tx_hash" required autocomplete="off" spellcheck="false" />
          <p class="hint">The customer sees this so they can track the payment.</p></div>`,
      onSubmit: (v) => api.admin.reviewWithdrawal(t.id, { status: 'approved', payout_tx_hash: v.payout_tx_hash }),
    });
    if (done) { toast(`Withdrawal for ${t.user_email} marked as paid.`); changed(); load(); }
  });
  on(outlet, 'click', '[data-reject]', async (_, el) => {
    const t = find(el.dataset.reject);
    const done = await openDialog({
      title: 'Reject this withdrawal', submitLabel: `Reject and return ${money(t.amount)}`, danger: true,
      body: html`<p class="text-muted">The held ${money(t.amount)} goes back to ${t.user_email}’s Main wallet.</p>
        <div class="field"><label class="label" for="rej">Reason the customer will see</label>
          <textarea class="input" id="rej" name="rejection_reason" rows="3" required maxlength="500" placeholder="e.g. The address isn’t a valid ${t.network} address."></textarea></div>`,
      onSubmit: (v) => api.admin.reviewWithdrawal(t.id, { status: 'rejected', rejection_reason: v.rejection_reason }),
    });
    if (done) { toast('Withdrawal rejected and funds returned.'); changed(); load(); }
  });
  on(outlet, 'click', '[data-action="retry"]', load);
  await load();
}

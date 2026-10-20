import { api } from '../../lib/api.js';
import { html, on, render } from '../../lib/dom.js';
import { date, dateTime, money, pct, txLabel } from '../../lib/format.js';
import { icon } from '../../lib/icons.js';
import { confirmDialog, errorState, openDialog, skeletonRows, toast, toastError } from '../../lib/ui.js';
import { session } from '../../session.js';
import { pageHeader, pill, signedAmount } from '../common.js';
import { setAdmin, viewAsCustomer } from './customer-actions.js';

const FLAGS = [
  ['is_blocked', 'Restricted', 'Blocks deposits, withdrawals, transfers and new investments.', true],
  ['can_deposit', 'Can deposit', 'Allow new deposit reports.', false],
  ['can_withdraw', 'Can withdraw', 'Allow new withdrawal requests.', false],
  ['is_active', 'Account open', 'Closed accounts can’t sign in.', false],
];
const KYC_TEXT = { UNVERIFIED: ['pill-neutral', 'Not verified'], PENDING: ['pill-pending', 'In review'], VERIFIED: ['pill-settled', 'Verified'], REJECTED: ['pill-rejected', 'Rejected'] };

export default async function customer(outlet, { id }) {
  let d;
  async function load() {
    render(outlet, html`<div class="panel">${skeletonRows(8)}</div>`);
    try { d = await api.admin.user(id); draw(); }
    catch (err) { render(outlet, html`<div class="panel">${errorState(err)}</div>`); }
  }

  function draw() {
    const { user: u, wallets, investments, transactions, referred_by_email } = d;
    const [kc, kt] = KYC_TEXT[u.kyc_status];
    const self = u.id === session.user.id;
    render(outlet, html`
      <a href="#/customers" class="btn-link mb-4 inline-block text-xs">All customers</a>
      ${pageHeader(u.full_name, '', html`
        ${!u.is_admin && u.is_active ? html`<button class="btn-quiet" data-action="view-as" title="Opens their account read-only for 30 minutes">View as customer</button>` : ''}
        <button class="btn-quiet" data-action="email">${icon('mail', 'h-4 w-4')}Email</button>
        <button class="btn-quiet" data-action="debit">Debit</button>
        <button class="btn-primary" data-action="credit">Credit wallet</button>`)}

      <div class="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <div class="grid content-start gap-6">
          <section class="panel grid gap-px overflow-hidden bg-line sm:grid-cols-2" aria-label="Balances">
            ${wallets.map((w) => html`<div class="bg-surface p-5">
              <p class="text-sm text-muted">${w.wallet_type === 'main' ? 'Main wallet' : 'Profit wallet'}</p>
              <p class="figure mt-1 text-3xl">${money(w.balance)}</p></div>`)}
          </section>

          <section class="panel">
            <div class="panel-head"><h2 class="panel-title">Investments</h2></div>
            ${investments.length ? html`<div class="overflow-x-auto"><table class="table">
              <thead><tr><th>Plan</th><th>Started</th><th>Paid days</th><th>Status</th><th class="text-right">Invested</th><th class="text-right">Earned</th></tr></thead>
              <tbody>${investments.map((i) => html`<tr>
                <td>${i.plan_name}<span class="block text-xs text-muted">${pct(i.daily_roi_percent)} per day</span></td>
                <td class="text-muted">${date(i.start_date)}</td><td class="num">${i.days_paid} / ${i.duration_days}</td>
                <td>${pill(i.status)}</td><td class="text-right figure">${money(i.amount_invested)}</td>
                <td class="text-right figure">${money(i.total_earned)}</td></tr>`)}</tbody></table></div>`
              : html`<p class="px-5 py-6 text-sm text-muted">No investments.</p>`}
          </section>

          <section class="panel">
            <div class="panel-head"><h2 class="panel-title">Recent ledger</h2>
              <a class="btn-link" href="#/ledger?q=${encodeURIComponent(u.email)}">Full history</a></div>
            ${transactions.length ? html`<div class="overflow-x-auto"><table class="table">
              <thead><tr><th>When</th><th>What</th><th>Status</th><th class="text-right">Amount</th></tr></thead>
              <tbody>${transactions.map((t) => html`<tr>
                <td class="whitespace-nowrap text-muted">${dateTime(t.created_at)}</td>
                <td>${txLabel(t.tx_type)}<span class="block text-xs text-muted">${t.description || ''}</span></td>
                <td>${pill(t.status)}</td><td class="text-right">${signedAmount(t)}</td></tr>`)}</tbody></table></div>`
              : html`<p class="px-5 py-6 text-sm text-muted">No transactions yet.</p>`}
          </section>
        </div>

        <aside class="grid content-start gap-6">
          <section class="panel p-5">
            <h2 class="panel-title">Profile</h2>
            <dl class="mt-3 grid grid-cols-[6rem_1fr] gap-y-2 text-sm">
              <dt class="text-muted">Email</dt><dd class="break-all">${u.email}
                ${u.email_verified ? html`<span class="pill-settled mt-1">Confirmed</span>` : html`<span class="pill-neutral mt-1">Unconfirmed</span>`}</dd>
              <dt class="text-muted">Identity</dt><dd><span class="${kc}">${kt}</span>
                ${u.kyc_status === 'PENDING' ? html`<a class="btn-link mt-1 block text-xs" href="#/kyc">Review</a>` : ''}</dd>
              <dt class="text-muted">Country</dt><dd>${u.country || '—'}</dd>
              <dt class="text-muted">Phone</dt><dd>${u.phone || '—'}</dd>
              <dt class="text-muted">Joined</dt><dd>${date(u.created_at)}</dd>
              <dt class="text-muted">Referral</dt><dd class="font-mono">${u.referral_code}
                <span class="block font-sans text-xs text-muted">${u.referral_count} referred${referred_by_email ? `, referred by ${referred_by_email}` : ''}</span></dd>
            </dl>
          </section>

          <section class="panel p-5">
            <h2 class="panel-title">Access</h2>
            <p class="mt-2 text-sm">${u.is_admin ? html`<span class="pill-pending">Admin</span> Full access to the operations console.`
              : html`<span class="pill-neutral">Customer</span> No console access.`}</p>
            ${self ? html`<p class="mt-2 text-xs text-muted">You can’t change your own role.</p>`
              : html`<button class="${u.is_admin ? 'btn-quiet text-rejected' : 'btn-quiet'} btn-sm mt-3" data-action="${u.is_admin ? 'demote' : 'promote'}">
                  ${u.is_admin ? 'Remove admin access' : 'Make admin'}</button>`}
          </section>

          <section class="panel p-5">
            <h2 class="panel-title">Standing</h2>
            ${self ? html`<p class="mt-2 text-sm text-muted">This is your own account.</p>` : ''}
            <ul class="mt-3 grid gap-3">
              ${FLAGS.map(([key, label, hint, danger]) => html`<li class="flex items-start justify-between gap-3">
                <label for="flag-${key}" class="text-sm"><span class="font-medium">${label}</span><span class="block text-xs text-muted">${hint}</span></label>
                <input id="flag-${key}" type="checkbox" class="mt-1 h-5 w-5 ${danger ? 'accent-rejected' : 'accent-settled'}"
                  data-flag="${key}" ${u[key] ? 'checked' : ''} ${self ? 'disabled' : ''} /></li>`)}
            </ul>
          </section>
        </aside>
      </div>`);
  }

  const adjust = (kind) => openDialog({
    title: kind === 'credit' ? `Credit ${d.user.full_name}` : `Debit ${d.user.full_name}`,
    submitLabel: kind === 'credit' ? 'Credit wallet' : 'Debit wallet', danger: kind === 'debit',
    body: html`
      <fieldset class="grid grid-cols-2 gap-2"><legend class="label mb-1.5">Wallet</legend>
        ${d.wallets.map((w, i) => html`<label class="choice"><input type="radio" name="wallet_type" value="${w.wallet_type}" ${i === 0 ? 'checked' : ''} />
          <span>${w.wallet_type === 'main' ? 'Main' : 'Profit'}<span class="block text-xs text-muted">${money(w.balance)}</span></span></label>`)}
      </fieldset>
      <div class="field"><label class="label" for="adj-amt">Amount, in US dollars</label>
        <input class="input figure" id="adj-amt" name="amount" type="number" min="0.01" step="0.01" required /></div>
      <div class="field"><label class="label" for="adj-note">Note the customer will see</label>
        <input class="input" id="adj-note" name="description" maxlength="200" required placeholder="${kind === 'credit' ? 'e.g. Bank transfer received 12 Oct' : 'e.g. Correction for duplicate credit'}" />
        <p class="hint">Recorded in the audit log with your name.</p></div>`,
    onSubmit: (v) => (kind === 'credit' ? api.admin.credit : api.admin.debit)({ user_id: d.user.id, ...v }),
  });

  on(outlet, 'click', '[data-action]', async (_, el) => {
    const a = el.dataset.action;
    try {
      if (a === 'retry') return load();
      if (a === 'view-as') return viewAsCustomer(d.user);
      if (a === 'promote' || a === 'demote') {
        if (await setAdmin(d.user, a === 'promote')) load();
        return;
      }
      if (a === 'credit' || a === 'debit') {
        const tx = await adjust(a);
        if (tx) { toast(`${a === 'credit' ? 'Credited' : 'Debited'} ${money(tx.amount)}.`); load(); }
      }
      if (a === 'email') {
        const sent = await openDialog({
          title: `Email ${d.user.full_name}`, submitLabel: 'Send email',
          body: html`<div class="field"><label class="label" for="em-s">Subject</label><input class="input" id="em-s" name="subject" required maxlength="200" /></div>
            <div class="field"><label class="label" for="em-b">Message</label><textarea class="input" id="em-b" name="body" rows="6" required></textarea>
            <p class="hint">Sent as plain text. Also appears in their notifications.</p></div>`,
          onSubmit: (v) => api.admin.emailUser({ user_id: d.user.id, ...v }),
        });
        if (sent) toast('Email sent.');
      }
    } catch (err) { toastError(err); }
  });

  on(outlet, 'change', '[data-flag]', async (_, el) => {
    const key = el.dataset.flag;
    const value = el.checked;
    const risky = (key === 'is_blocked' && value) || (key === 'is_active' && !value);
    if (risky) {
      const ok = await confirmDialog({ title: key === 'is_blocked' ? 'Restrict this customer?' : 'Close this account?', danger: true,
        confirmLabel: key === 'is_blocked' ? 'Restrict' : 'Close account',
        message: key === 'is_blocked' ? 'They keep their balance but can’t move money until you lift the restriction. They’ll be notified.'
          : 'They won’t be able to sign in. You can reopen it later.' });
      if (!ok) { el.checked = !value; return; }
    }
    el.disabled = true;
    try { d.user = await api.admin.setUserFlags(id, { [key]: value }); toast('Saved.'); }
    catch (err) { el.checked = !value; toastError(err); }
    finally { el.disabled = false; }
  });

  await load();
}

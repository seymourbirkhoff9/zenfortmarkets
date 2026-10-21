import { api } from '../../lib/api.js';
import { html, on, render } from '../../lib/dom.js';
import { dateTime } from '../../lib/format.js';
import { emptyState, errorState, skeletonRows } from '../../lib/ui.js';
import { pageHeader } from '../common.js';

const ACTION = {
  CREDIT_WALLET: 'Credited a wallet', DEBIT_WALLET: 'Debited a wallet', APPROVE_DEPOSIT: 'Confirmed a deposit',
  REJECT_DEPOSIT: 'Rejected a deposit', APPROVE_WITHDRAWAL: 'Paid a withdrawal', REJECT_WITHDRAWAL: 'Rejected a withdrawal',
  APPROVE_KYC: 'Verified an identity', REJECT_KYC: 'Rejected an ID document', REVIEW_KYC: 'Reviewed an identity',
  BLOCK_USER: 'Restricted a customer', UNBLOCK_USER: 'Lifted a restriction', UPDATE_USER_FLAGS: 'Changed account permissions',
  CREATE_PLAN: 'Created a plan', UPDATE_PLAN: 'Edited a plan', DELETE_PLAN: 'Deleted a plan', RUN_ROI: 'Ran return accrual',
  IMPERSONATE_START: 'Viewed an account as the customer', IMPERSONATE_END: 'Stopped viewing as the customer',
  PROMOTE_ADMIN: 'Gave admin access', DEMOTE_ADMIN: 'Removed admin access', RESET_2FA: 'Reset two-factor sign-in',
  CREATE_PAYMENT_METHOD: 'Added a payment method', UPDATE_PAYMENT_METHOD: 'Edited a payment method', DELETE_PAYMENT_METHOD: 'Removed a payment method',
};
const PAGE = 100;

export default async function audit(outlet) {
  let skip = 0;
  render(outlet, html`${pageHeader('Audit log', 'Who did what, and when. Entries are written in the same database transaction as the change they describe.')}
    <section class="panel"><div id="rows">${skeletonRows(10)}</div>
      <div class="flex justify-between border-t border-line px-5 py-3"><button class="btn-quiet btn-sm" data-page="-1">Newer</button><button class="btn-quiet btn-sm" data-page="1">Older</button></div>
    </section>`);
  const rowsEl = outlet.querySelector('#rows');
  async function load() {
    render(rowsEl, skeletonRows(8));
    try {
      const rows = await api.admin.audit({ skip, limit: PAGE });
      outlet.querySelector('[data-page="-1"]').disabled = skip === 0;
      outlet.querySelector('[data-page="1"]').disabled = rows.length < PAGE;
      render(rowsEl, rows.length ? html`<div class="overflow-x-auto"><table class="table">
        <thead><tr><th>When</th><th>Admin</th><th>Action</th><th>Customer</th><th>Detail</th></tr></thead>
        <tbody>${rows.map((r) => html`<tr>
          <td class="whitespace-nowrap text-muted">${dateTime(r.created_at)}</td>
          <td>${r.admin_email || '—'}</td>
          <td class="font-medium">${ACTION[r.action] || r.action}</td>
          <td>${r.target_user_id ? html`<a class="hover:underline" href="#/customers/${r.target_user_id}">${r.target_email || 'Customer'}</a>` : '—'}</td>
          <td class="max-w-[24rem] text-xs text-muted">${r.details || ''}</td></tr>`)}</tbody></table></div>`
        : emptyState('No admin actions yet', 'Approvals, credits and configuration changes are recorded here.'));
    } catch (err) { render(rowsEl, errorState(err)); }
  }
  on(outlet, 'click', '[data-page]', (_, el) => { skip = Math.max(0, skip + Number(el.dataset.page) * PAGE); load(); });
  on(outlet, 'click', '[data-action="retry"]', load);
  await load();
}

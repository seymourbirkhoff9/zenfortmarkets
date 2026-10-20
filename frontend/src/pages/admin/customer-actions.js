/**
 * Account actions shared by the Customers list (row menu) and a customer's page.
 * Each returns the updated user, or undefined if cancelled. The server enforces
 * every rule (audit log, can't change your own role, keep at least one admin).
 */
import { api } from '../../lib/api.js';
import { confirmDialog, toast, toastError } from '../../lib/ui.js';
import { invalidate } from '../../lib/cache.js';

export async function viewAsCustomer(u) {
  try {
    const { redirect } = await api.admin.impersonate(u.id);
    invalidate();                       // cached admin data shouldn't leak into the customer view
    location.href = redirect;
  } catch (err) { toastError(err); }
}

const FLAG_COPY = {
  is_blocked: {
    on: ['Restrict this customer?', 'They keep their balance but can’t deposit, withdraw, transfer or invest until you lift it. They’ll be notified.', 'Restrict', true, 'Customer restricted.'],
    off: ['Lift the restriction?', 'They’ll be able to use their account normally again, and will be notified.', 'Lift restriction', false, 'Restriction lifted.'],
  },
  can_deposit: {
    on: ['Turn deposits back on?', 'They’ll be able to report deposits again.', 'Turn on', false, 'Deposits turned on.'],
    off: ['Turn off deposits?', 'They won’t be able to report new deposits. Pending ones are unaffected.', 'Turn off deposits', true, 'Deposits turned off.'],
  },
  can_withdraw: {
    on: ['Turn withdrawals back on?', 'They’ll be able to request withdrawals again.', 'Turn on', false, 'Withdrawals turned on.'],
    off: ['Turn off withdrawals?', 'They won’t be able to request new withdrawals. Pending ones stay in your queue.', 'Turn off withdrawals', true, 'Withdrawals turned off.'],
  },
  is_active: {
    on: ['Reopen this account?', 'They’ll be able to sign in again.', 'Reopen', false, 'Account reopened.'],
    off: ['Close this account?', 'They won’t be able to sign in. Their balance and history are kept, and you can reopen it later.', 'Close account', true, 'Account closed.'],
  },
};

/** Set one standing flag (with confirmation). */
export async function setFlag(u, key, value, { confirm = true } = {}) {
  const [title, message, label, danger, done] = FLAG_COPY[key][value ? 'on' : 'off'];
  if (confirm && !(await confirmDialog({ title, message, confirmLabel: label, danger }))) return undefined;
  try {
    const updated = await api.admin.setUserFlags(u.id, { [key]: value });
    toast(done);
    return updated;
  } catch (err) { toastError(err); return undefined; }
}

export async function setAdmin(u, makeAdmin) {
  const ok = await confirmDialog(makeAdmin
    ? { title: `Make ${u.full_name} an admin?`, confirmLabel: 'Make admin', danger: true,
        message: 'They’ll get full access to the operations console: approving deposits and withdrawals, crediting wallets and managing customers. This is recorded in the audit log.' }
    : { title: `Remove admin access from ${u.full_name}?`, confirmLabel: 'Remove admin access', danger: true,
        message: 'They’ll go back to being a regular customer. This is recorded in the audit log.' });
  if (!ok) return undefined;
  try {
    const updated = await api.admin.setRole(u.id, makeAdmin);
    toast(makeAdmin ? `${u.full_name} is now an admin.` : `${u.full_name} is no longer an admin.`);
    return updated;
  } catch (err) { toastError(err); return undefined; }
}

/** Menu entries for a user, as [label, handlerKey, danger] rows. */
export function menuItems(u, selfId) {
  const items = [['Open customer page', 'open']];
  if (!u.is_admin && u.is_active) items.push(['View as customer', 'view-as']);
  if (u.id !== selfId) {
    items.push(u.is_blocked ? ['Lift restriction', 'unblock'] : ['Restrict account', 'block', true]);
    items.push(u.can_deposit ? ['Turn off deposits', 'deposits-off'] : ['Turn on deposits', 'deposits-on']);
    items.push(u.can_withdraw ? ['Turn off withdrawals', 'withdrawals-off'] : ['Turn on withdrawals', 'withdrawals-on']);
    items.push(u.is_admin ? ['Remove admin access', 'demote', true] : ['Make admin', 'promote', true]);
  }
  return items;
}

export async function runMenuAction(action, u) {
  switch (action) {
    case 'open': location.hash = `#/customers/${u.id}`; return undefined;
    case 'view-as': return viewAsCustomer(u);
    case 'block': return setFlag(u, 'is_blocked', true);
    case 'unblock': return setFlag(u, 'is_blocked', false);
    case 'deposits-off': return setFlag(u, 'can_deposit', false);
    case 'deposits-on': return setFlag(u, 'can_deposit', true);
    case 'withdrawals-off': return setFlag(u, 'can_withdraw', false);
    case 'withdrawals-on': return setFlag(u, 'can_withdraw', true);
    case 'promote': return setAdmin(u, true);
    case 'demote': return setAdmin(u, false);
    default: return undefined;
  }
}

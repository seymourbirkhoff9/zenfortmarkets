import { api } from '../../lib/api.js';
import { html, on, render } from '../../lib/dom.js';
import { dateTime } from '../../lib/format.js';
import { confirmDialog, emptyState, setBusy, toast, toastError } from '../../lib/ui.js';
import { pageHeader } from '../common.js';

const AUDIENCE = { all: 'Every customer', verified_kyc: 'Verified customers', unverified_kyc: 'Customers who haven’t verified', active_investors: 'Customers with an active investment' };

// A send still unfinished after an hour never will (older versions could stop without recording why).
const stale = (r) => Date.now() - new Date(r.created_at).getTime() > 60 * 60 * 1000;

// Entries saved before errors were reworded hold the email service's raw "422: …" text.
const friendly = (err) => {
  if (!/^\d{3}: /.test(err)) return err;
  if (/`to`|testing email/i.test(err)) return 'Nothing was sent: the list included test addresses (like example.com) and the email service refused the whole send. Test addresses are now skipped automatically, so please send it again.';
  if (/own email|verify/i.test(err)) return 'Nothing was sent: the sending domain wasn’t verified with the email service.';
  return 'Nothing was sent: the email service refused it. Please try again.';
};

export default async function broadcast(outlet) {
  render(outlet, html`
    ${pageHeader('Email customers', 'Each recipient gets an email and an in-app notification. Text is sent as plain paragraphs; leave a blank line between them.')}
    <div class="grid gap-6 lg:grid-cols-[1fr_22rem]">
      <form id="compose" class="panel grid gap-4 self-start p-6">
        <div class="field"><label class="label" for="b-aud">Send to</label>
          <select class="input" id="b-aud" name="target_filter">${Object.entries(AUDIENCE).map(([v, l]) => html`<option value="${v}">${l}</option>`)}</select></div>
        <div class="field"><label class="label" for="b-sub">Subject</label><input class="input" id="b-sub" name="subject" required maxlength="200" /></div>
        <div class="field"><label class="label" for="b-body">Message</label><textarea class="input" id="b-body" name="body" rows="10" required></textarea></div>
        <button class="btn-primary justify-self-start">Send email</button>
      </form>
      <section class="panel" aria-labelledby="hist-h"><div class="panel-head"><h2 id="hist-h" class="panel-title">Sent</h2></div><div id="history"></div></section>
    </div>`);

  async function history() {
    try {
      const rows = await api.admin.broadcastHistory();
      render(outlet.querySelector('#history'), rows.length ? html`<ul class="divide-y divide-line">${rows.map((r) => html`
        <li class="px-5 py-3"><p class="font-medium">${r.subject}</p>
          <p class="text-xs text-muted">${AUDIENCE[r.target_filter] || r.target_filter}. ${dateTime(r.created_at)}</p>
          <p class="mt-1 text-xs">${r.delivered_count == null
            ? (stale(r) ? html`<span class="pill-rejected">Not sent</span>` : html`<span class="pill-pending">Sending…</span>`)
            : r.failed_count ? html`<span class="pill-rejected">${r.delivered_count} of ${r.recipient_count} delivered</span>`
            : html`<span class="pill-settled">Delivered to ${r.delivered_count}</span>`}</p>
          ${r.delivered_count == null && stale(r) ? html`<p class="mt-1 text-xs text-rejected">This send didn’t finish because of an earlier fault. Please send it again.</p>` : ''}
          ${r.failed_count && r.last_error ? html`<p class="mt-1 break-words text-xs text-rejected">${friendly(r.last_error)}</p>` : ''}</li>`)}</ul>`
        : emptyState('Nothing sent yet', 'Your broadcasts will be listed here.'));
    } catch (err) { toastError(err); }
  }

  on(outlet, 'submit', '#compose', async (e) => {
    e.preventDefault();
    const f = e.target;
    const v = { target_filter: f.target_filter.value, subject: f.subject.value.trim(), body: f.body.value.trim() };
    if (!(await confirmDialog({ title: 'Send this email?', confirmLabel: 'Send', message: `“${v.subject}” goes to: ${AUDIENCE[v.target_filter]}. It can’t be recalled.` }))) return;
    const btn = f.querySelector('button');
    setBusy(btn, true, 'Sending…');
    try { await api.admin.broadcast(v); f.reset(); toast('Sending now. Delivery results appear in the list when it finishes.'); setTimeout(history, 2500); setTimeout(history, 8000); }
    catch (err) { toastError(err); } finally { setBusy(btn, false); }
  });
  await history();
}

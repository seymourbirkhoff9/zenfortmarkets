import { api } from '../../lib/api.js';
import { html, on, render } from '../../lib/dom.js';
import { dateTime } from '../../lib/format.js';
import { confirmDialog, emptyState, setBusy, toast, toastError } from '../../lib/ui.js';
import { pageHeader } from '../common.js';

const AUDIENCE = { all: 'Every customer', verified_kyc: 'Verified customers', unverified_kyc: 'Customers who haven’t verified', active_investors: 'Customers with an active investment' };

export default async function broadcast(outlet) {
  render(outlet, html`
    ${pageHeader('Email customers', 'Each recipient gets an email and an in-app notification. Text is sent as plain paragraphs; leave a blank line between them.')}
    <div class="grid gap-6 lg:grid-cols-[1fr_22rem]">
      <form id="compose" class="panel grid gap-4 p-6">
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
          <p class="text-xs text-muted">${AUDIENCE[r.target_filter] || r.target_filter}. ${r.recipient_count} recipient${r.recipient_count === 1 ? '' : 's'}. ${dateTime(r.created_at)}</p></li>`)}</ul>`
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
    try { await api.admin.broadcast(v); f.reset(); toast('Sending. Recipient count updates when delivery finishes.'); setTimeout(history, 1500); }
    catch (err) { toastError(err); } finally { setBusy(btn, false); }
  });
  await history();
}

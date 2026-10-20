import { api } from '../../lib/api.js';
import { html, on, render } from '../../lib/dom.js';
import { date, waited } from '../../lib/format.js';
import { emptyState, errorState, openDialog, skeletonRows, toast, toastError } from '../../lib/ui.js';
import { pageHeader } from '../common.js';

export default async function kyc(outlet) {
  const head = pageHeader('Identity checks', 'Open each document, compare it with the account name, then verify or ask for a new one. Verified customers can withdraw.');
  let rows = [];
  async function load() {
    render(outlet, html`${head}<div class="panel">${skeletonRows(4)}</div>`);
    try {
      rows = await api.admin.pendingKyc();
      render(outlet, html`${head}<section class="panel">
        ${rows.length ? html`<table class="table">
          <thead><tr><th>Waiting</th><th>Customer</th><th>Country</th><th>Joined</th><th><span class="sr-only">Actions</span></th></tr></thead>
          <tbody>${rows.map((u) => html`<tr>
            <td class="text-muted">${waited(u.updated_at || u.created_at)}</td>
            <td><a class="font-medium hover:underline" href="#/customers/${u.id}">${u.full_name}</a><span class="block text-xs text-muted">${u.email}</span></td>
            <td>${u.country || '—'}</td><td class="text-muted">${date(u.created_at)}</td>
            <td class="text-right"><button class="btn-primary btn-sm" data-review="${u.id}">Review document</button></td>
          </tr>`)}</tbody></table>`
          : emptyState('No documents waiting', 'Submissions appear here and you’ll get a notification for each one.')}
      </section>`);
    } catch (err) { render(outlet, html`${head}<div class="panel">${errorState(err)}</div>`); }
  }

  on(outlet, 'click', '[data-review]', async (_, el) => {
    const u = rows.find((r) => r.id === el.dataset.review);
    let doc, type;
    try { ({ document: doc, content_type: type } = await api.admin.kycDocument(u.id)); } catch (err) { return toastError(err); }
    // Files arrive as short-lived links (or, for old records, data: URLs). Browsers won't frame a
    // data: PDF, so those are converted to a blob: URL; a linked PDF can be framed directly.
    const isPdf = type === 'application/pdf';
    let blobUrl = null;
    if (isPdf && doc.startsWith('data:')) blobUrl = URL.createObjectURL(await (await fetch(doc)).blob());

    const done = await openDialog({
      title: `${u.full_name}`, wide: true, submitLabel: 'Save decision',
      body: html`
        <div class="grid gap-5 md:grid-cols-[1.4fr_1fr]">
          <div class="rounded border border-line bg-sunken p-2">
            ${isPdf ? html`<iframe src="${blobUrl || doc}" title="ID document" class="h-[60vh] w-full rounded"></iframe>`
              : html`<img src="${doc}" alt="ID document for ${u.full_name}" class="mx-auto max-h-[60vh] rounded object-contain" />`}
          </div>
          <div class="grid content-start gap-4">
            <dl class="grid grid-cols-[5.5rem_1fr] gap-y-1.5 text-sm">
              <dt class="text-muted">Name</dt><dd>${u.full_name}</dd><dt class="text-muted">Email</dt><dd class="break-all">${u.email}</dd>
              <dt class="text-muted">Country</dt><dd>${u.country || '—'}</dd><dt class="text-muted">Phone</dt><dd>${u.phone || '—'}</dd>
            </dl>
            <fieldset class="grid gap-2"><legend class="label mb-1.5">Decision</legend>
              <label class="choice"><input type="radio" name="status" value="VERIFIED" required /><span>Verified. Name and photo match.</span></label>
              <label class="choice"><input type="radio" name="status" value="REJECTED" /><span>Ask for a new document</span></label>
            </fieldset>
            <div class="field" data-reason hidden><label class="label" for="kr">What should they fix?</label>
              <textarea class="input" id="kr" name="rejection_reason" rows="3" maxlength="500" placeholder="e.g. The photo is blurred. Upload a sharper image with all corners visible."></textarea></div>
          </div>
        </div>`,
      onMount: (dlg) => dlg.addEventListener('change', (e) => {
        if (e.target.name !== 'status') return;
        const box = dlg.querySelector('[data-reason]');
        box.hidden = e.target.value !== 'REJECTED';
        box.querySelector('textarea').required = e.target.value === 'REJECTED';
      }),
      onSubmit: (v) => api.admin.reviewKyc(u.id, { status: v.status, rejection_reason: v.rejection_reason || null }).then(() => v.status),
    });
    if (blobUrl) URL.revokeObjectURL(blobUrl);
    if (done) {
      toast(done === 'VERIFIED' ? `${u.full_name} is verified.` : `${u.full_name} was asked for a new document.`);
      window.dispatchEvent(new Event('zf:queues-changed'));
      load();
    }
  });
  on(outlet, 'click', '[data-action="retry"]', load);
  await load();
}

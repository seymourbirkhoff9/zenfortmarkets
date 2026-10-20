import { $, html, render } from './dom.js';
import { ApiError } from './api.js';

/* ── Toasts ─────────────────────────────────────────────────────────── */
let region;
export function toast(message, tone = 'ok') {
  if (!region) {
    region = document.createElement('div');
    region.setAttribute('role', 'status');
    region.setAttribute('aria-live', 'polite');
    region.className = 'fixed bottom-4 right-4 z-[60] grid gap-2 w-[min(24rem,calc(100vw-2rem))]';
    document.body.append(region);
  }
  const el = document.createElement('div');
  const bar = tone === 'error' ? 'bg-rejected' : tone === 'warn' ? 'bg-pending' : 'bg-settled';
  el.className = 'panel flex items-stretch overflow-hidden shadow-lg';
  render(el, html`<span class="w-1 ${bar}"></span><p class="px-4 py-3 text-sm">${message}</p>`);
  region.append(el);
  setTimeout(() => el.remove(), tone === 'error' ? 7000 : 4000);
}

export const toastError = (err) => toast(err instanceof ApiError ? err.message : 'Something went wrong. Try again.', 'error');

/* ── Modal dialogs ──────────────────────────────────────────────────── */
/**
 * openDialog({ title, body, submitLabel, onSubmit, danger, wide, onMount })
 *   or, to open instantly and fill in when data arrives:
 * openDialog({ title, load: async () => ({ body, title?, submitLabel?, onSubmit?, onMount?, danger? }) })
 *
 * - body: html`` content; form fields need name="…".
 * - onSubmit(values, dialogEl) may throw ApiError: its message shows in the
 *   dialog and fields named in err.fields are highlighted. The returned value
 *   resolves the promise (return false to keep the dialog open).
 * - No onSubmit → an information dialog with only a close button.
 */
export function openDialog(spec) {
  return new Promise((resolve) => {
    const dlg = document.createElement('dialog');
    dlg.className = `modal ${spec.wide ? 'w-[min(52rem,calc(100vw-2rem))]' : ''}`;
    const titleId = `dlg-${Math.random().toString(36).slice(2)}`;
    dlg.setAttribute('aria-labelledby', titleId);
    render(dlg, html`
      <form method="dialog" novalidate class="flex max-h-[85vh] flex-col">
        <header class="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <h2 id="${titleId}" class="font-serif text-xl">${spec.title}</h2>
          <button type="button" data-close class="-mr-1 rounded p-1 text-muted hover:text-ink" aria-label="Close">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18"/></svg>
          </button>
        </header>
        <div class="grid gap-4 overflow-y-auto px-5 py-5">
          <div data-body class="grid gap-4"></div>
          <p data-error class="error-text" role="alert" hidden></p>
        </div>
        <footer data-footer class="flex justify-end gap-2 border-t border-line px-5 py-3.5"></footer>
      </form>`);
    document.body.append(dlg);
    const form = dlg.querySelector('form');
    const bodyEl = dlg.querySelector('[data-body]');
    const errorEl = dlg.querySelector('[data-error]');
    const footer = dlg.querySelector('[data-footer]');
    let current = spec;
    let result;

    const drawFooter = (s, ready) => render(footer, s.onSubmit || !ready ? html`
      <button type="button" data-close class="btn-quiet">${s.cancelLabel || 'Cancel'}</button>
      <button type="submit" class="${s.danger ? 'btn-danger' : 'btn-primary'}" ${ready ? '' : 'disabled'}>${s.submitLabel || 'Save'}</button>`
      : html`<button type="button" data-close class="btn-quiet">Close</button>`);

    const show = (s) => {
      current = { ...spec, ...s };
      if (s.title) dlg.querySelector(`#${titleId}`).textContent = s.title;
      render(bodyEl, current.body);
      drawFooter(current, true);
      current.onMount?.(dlg);
      dlg.querySelector('[data-body] input:not([type=hidden]):not([type=radio]):not([type=checkbox]):not([type=file]), [data-body] textarea, [data-body] select')?.focus();
    };

    dlg.addEventListener('close', () => { dlg.remove(); resolve(result); });
    dlg.addEventListener('click', (e) => {
      if (e.target === dlg || e.target.closest('[data-close]')) dlg.close();
      else if (e.target.closest('a[href]')) dlg.close();      // following a link leaves the dialog
    });

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!current.onSubmit) return;
      errorEl.hidden = true;
      form.querySelectorAll('[aria-invalid]').forEach((el) => el.removeAttribute('aria-invalid'));
      if (!form.reportValidity()) return;
      const btn = form.querySelector('button[type=submit]');
      const label = btn.textContent;
      btn.disabled = true; btn.textContent = 'Working…';
      try {
        const values = Object.fromEntries([...new FormData(form).entries()].map(([k, v]) => [k, typeof v === 'string' ? v.trim() : v]));
        result = await current.onSubmit(values, dlg);
        if (result !== false) dlg.close();
      } catch (err) {
        errorEl.textContent = err?.message || 'Something went wrong.';
        errorEl.hidden = false;
        Object.keys(err?.fields || {}).forEach((f) => form.querySelector(`[name="${f.split('.').pop()}"]`)?.setAttribute('aria-invalid', 'true'));
      } finally {
        btn.disabled = false; btn.textContent = label;
      }
    });

    dlg.showModal();
    if (spec.load) {
      render(bodyEl, html`<div class="grid gap-3" aria-busy="true" aria-label="Loading">
        <div class="skeleton h-4 w-2/3"></div><div class="skeleton h-11"></div><div class="skeleton h-11"></div><div class="skeleton h-4 w-1/2"></div></div>`);
      drawFooter(spec, false);
      spec.load().then((s) => { if (dlg.open) show(s); }).catch((err) => {
        if (!dlg.open) return;
        render(bodyEl, html`<p class="text-muted">${err?.message || 'This couldn’t load. Close and try again.'}</p>`);
        drawFooter({}, true);
      });
    } else {
      show(spec);
    }
  });
}

export function confirmDialog({ title, message, confirmLabel = 'Confirm', danger = false }) {
  return openDialog({ title, body: html`<p class="max-w-prose text-muted">${message}</p>`, submitLabel: confirmLabel,
    danger, onSubmit: () => true }).then(Boolean);
}

/* ── Files ──────────────────────────────────────────────────────────── */
const MAX_BYTES = 1_900_000;

/**
 * Read an image or PDF into a data URL the API accepts.
 * Photos are downscaled (longest side 1600px, JPEG) so phone screenshots fit
 * under the server's 2 MB limit without the user doing anything.
 */
export async function fileToDataUrl(file, { allowPdf = false } = {}) {
  const okImage = ['image/png', 'image/jpeg', 'image/webp'].includes(file.type);
  if (allowPdf && file.type === 'application/pdf') {
    if (file.size > MAX_BYTES * 0.74) throw new Error('PDF must be smaller than 1.4 MB. Upload a photo instead.');
    return readAsDataUrl(file);
  }
  if (!okImage) throw new Error(allowPdf ? 'Upload a PNG, JPG, WebP or PDF.' : 'Upload a PNG, JPG or WebP image.');

  const bitmap = await createImageBitmap(file).catch(() => null);
  if (!bitmap) throw new Error('That image couldn’t be read. Try another file.');
  const scale = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  for (const q of [0.85, 0.7, 0.55]) {
    const url = canvas.toDataURL('image/jpeg', q);
    if (url.length * 0.75 < MAX_BYTES) return url;
  }
  throw new Error('That image is too large even after compression. Crop it and try again.');
}

const readAsDataUrl = (file) => new Promise((resolve, reject) => {
  const r = new FileReader();
  r.onload = () => resolve(r.result);
  r.onerror = () => reject(new Error('The file couldn’t be read.'));
  r.readAsDataURL(file);
});

/** Wire a file input + preview area. Returns a getter for the current data URL. */
export function filePicker(root, { inputSel, previewSel, allowPdf = false }) {
  let value = null;
  const input = $(inputSel, root);
  const preview = $(previewSel, root);
  input.addEventListener('change', async () => {
    value = null;
    preview.hidden = true;
    const file = input.files?.[0];
    if (!file) return;
    try {
      value = await fileToDataUrl(file, { allowPdf });
      preview.hidden = false;
      render(preview, value.startsWith('data:application/pdf')
        ? html`<p class="text-sm">${file.name} attached.</p>`
        : html`<img src="${value}" alt="Preview of ${file.name}" class="max-h-48 rounded border border-line object-contain" />`);
    } catch (err) {
      input.value = '';
      toast(err.message, 'error');
    }
  });
  return () => value;
}

/* ── Misc ───────────────────────────────────────────────────────────── */
export async function copy(text, label = 'Copied') {
  try { await navigator.clipboard.writeText(text); toast(label); }
  catch { toast('Copy failed. Select the text and copy it manually.', 'warn'); }
}

export function setBusy(button, busy, busyLabel = 'Working…') {
  if (busy) { button.dataset.label = button.textContent; button.textContent = busyLabel; button.disabled = true; }
  else { button.textContent = button.dataset.label || button.textContent; button.disabled = false; }
}

export const emptyState = (title, text, action = '') => html`
  <div class="px-6 py-12 text-center">
    <p class="font-semibold">${title}</p>
    <p class="mx-auto mt-1 max-w-sm text-sm text-muted">${text}</p>
    ${action ? html`<div class="mt-4">${action}</div>` : ''}
  </div>`;

export const errorState = (err, retryAction = 'retry') => html`
  <div class="px-6 py-10 text-center" role="alert">
    <p class="font-semibold">This section didn’t load</p>
    <p class="mx-auto mt-1 max-w-sm text-sm text-muted">${err?.message || 'Unknown error.'}</p>
    <button class="btn-quiet btn-sm mt-4" data-action="${retryAction}">Try again</button>
  </div>`;

export const skeletonRows = (n = 4) => html`<div class="grid gap-3 p-5">${Array.from({ length: n }, () => html`<div class="skeleton h-5"></div>`)}</div>`;

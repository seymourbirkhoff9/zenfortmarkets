/**
 * Tiny, safe templating.
 *
 *   html`<p>${user.full_name}</p>`   → interpolations are HTML-escaped
 *   html`<ul>${items.map(i => html`<li>${i}</li>`)}</ul>`  → nested templates pass through
 *   raw(trustedString)               → explicit opt-out, only for markup we generated
 *
 * Every view renders through this, so customer-supplied text (names, notes,
 * rejection reasons) can never inject markup.
 */
const SAFE = Symbol('safe-html');

class SafeHTML {
  constructor(value) { this.value = value; this[SAFE] = true; }
  toString() { return this.value; }
}

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const escapeHTML = (s) => String(s).replace(/[&<>"']/g, (c) => ESC[c]);

function toHTML(value) {
  if (value == null || value === false) return '';
  if (Array.isArray(value)) return value.map(toHTML).join('');
  if (value && value[SAFE]) return value.value;
  return escapeHTML(value);
}

export function html(strings, ...values) {
  let out = strings[0];
  values.forEach((v, i) => { out += toHTML(v) + strings[i + 1]; });
  return new SafeHTML(out);
}

export const raw = (s) => new SafeHTML(String(s));

export function render(target, template) {
  const el = typeof target === 'string' ? document.querySelector(target) : target;
  el.innerHTML = toHTML(template);
  labelTables(el);
  // Translation tools must never alter amounts, addresses or hashes.
  el.querySelectorAll('.figure, .num, .font-mono, .copy-row').forEach((n) => { n.classList.add('notranslate'); n.setAttribute('translate', 'no'); });
  return el;
}

/** Copy column headers onto cells (data-label) so tables can stack into cards on phones. */
function labelTables(root) {
  root.querySelectorAll('table.table').forEach((table) => {
    // Headers that are screen-reader-only (e.g. an Actions column) don't get a visible label.
    const heads = [...table.querySelectorAll('thead th')].map((th) => (th.querySelector('.sr-only') ? '' : th.textContent.trim()));
    table.querySelectorAll('tbody tr').forEach((tr) => {
      [...tr.children].forEach((td, i) => {
        if (heads[i]) td.setAttribute('data-label', heads[i]);
        // Keep multi-part cells (e.g. title + description) together as one block when stacked.
        const parts = [...td.childNodes].filter((n) => n.nodeType === 1 || n.textContent.trim());
        if (parts.length > 1) {
          const cell = document.createElement('div');
          cell.append(...td.childNodes);
          td.append(cell);
        }
      });
    });
  });
}

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

/** Delegate events: on(root, 'click', '[data-action=approve]', (e, el) => …) */
export function on(root, type, selector, handler) {
  root.addEventListener(type, (e) => {
    const el = e.target.closest(selector);
    if (el && root.contains(el)) handler(e, el);
  });
}

export function formData(form) {
  const data = {};
  for (const [k, v] of new FormData(form).entries()) data[k] = typeof v === 'string' ? v.trim() : v;
  return data;
}

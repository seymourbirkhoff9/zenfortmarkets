import { api } from '../../lib/api.js';
import { html, on, render } from '../../lib/dom.js';
import { date } from '../../lib/format.js';
import { emptyState, errorState, skeletonRows } from '../../lib/ui.js';
import { pageHeader } from '../common.js';
import { session } from '../../session.js';
import { menuItems, runMenuAction } from './customer-actions.js';

const PAGE = 25;
const FILTERS = [['', 'Everyone'], ['kyc_pending', 'ID in review'], ['blocked', 'Restricted'], ['inactive', 'Closed or deactivated'], ['admins', 'Admins']];
const KYC = { UNVERIFIED: 'pill-neutral', PENDING: 'pill-pending', VERIFIED: 'pill-settled', REJECTED: 'pill-rejected' };
const KYC_TEXT = { UNVERIFIED: 'Not verified', PENDING: 'In review', VERIFIED: 'Verified', REJECTED: 'Rejected' };

export default async function customers(outlet, _p, query) {
  const state = { q: query.q || '', filter: query.filter || '', skip: 0 };
  render(outlet, html`
    ${pageHeader('Customers')}
    <section class="panel">
      <div class="panel-head">
        <form id="search" class="flex w-full max-w-md gap-2" role="search">
          <label class="sr-only" for="q">Search by name or email</label>
          <input class="input py-1.5" id="q" name="q" type="search" placeholder="Search by name or email" value="${state.q}" />
          <button class="btn-quiet">Search</button>
        </form>
        <div class="segmented flex-wrap" role="group" aria-label="Filter">
          ${FILTERS.map(([v, l]) => html`<button data-filter="${v}" aria-pressed="${state.filter === v}">${l}</button>`)}
        </div>
      </div>
      <div id="rows">${skeletonRows(8)}</div>
      <div class="flex items-center justify-between gap-3 border-t border-line px-5 py-3">
        <button class="btn-quiet btn-sm" data-page="-1">Previous</button>
        <span id="count" class="text-xs text-muted"></span>
        <button class="btn-quiet btn-sm" data-page="1">Next</button>
      </div>
    </section>`);

  const rowsEl = outlet.querySelector('#rows');
  let rows = [];
  async function load() {
    render(rowsEl, skeletonRows(6));
    try {
      const { total, items } = await api.admin.users({ q: state.q, filter: state.filter, skip: state.skip, limit: PAGE });
      render(rowsEl, items.length ? html`<div class="overflow-x-auto"><table class="table">
        <thead><tr><th>Customer</th><th>Country</th><th>Identity</th><th>Standing</th><th>Joined</th><th><span class="sr-only">Actions</span></th></tr></thead>
        <tbody>${items.map((u) => html`<tr data-href="#/customers/${u.id}">
          <td><a class="font-medium hover:underline" href="#/customers/${u.id}">${u.full_name}</a>${u.is_admin ? html` <span class="pill-neutral ml-1">Admin</span>` : ''}
            <span class="block text-xs text-muted">${u.email}</span></td>
          <td>${u.country || '—'}</td>
          <td><span class="${KYC[u.kyc_status]}">${KYC_TEXT[u.kyc_status]}</span></td>
          <td>${!u.is_active ? html`<span class="pill-neutral">Closed</span>` : u.is_blocked ? html`<span class="pill-rejected">Restricted</span>`
            : (!u.can_deposit || !u.can_withdraw) ? html`<span class="pill-pending">Limited</span>` : html`<span class="pill-settled">Good</span>`}</td>
          <td class="whitespace-nowrap text-muted">${date(u.created_at)}</td>
          <td class="text-right"><button class="rounded px-2 py-1 text-muted hover:bg-sunken hover:text-ink" data-menu="${u.id}"
            aria-haspopup="menu" aria-expanded="false" aria-label="Actions for ${u.full_name}">
            <svg class="h-5 w-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="5" cy="12" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="19" cy="12" r="1.8"/></svg></button></td>
        </tr>`)}</tbody></table></div>` : emptyState('No customers match', 'Try another search or filter.'));
      rows = items;
      outlet.querySelector('#count').textContent = total ? `${state.skip + 1}–${Math.min(state.skip + PAGE, total)} of ${total}` : '';
      outlet.querySelector('[data-page="-1"]').disabled = state.skip === 0;
      outlet.querySelector('[data-page="1"]').disabled = state.skip + PAGE >= total;
    } catch (err) { render(rowsEl, errorState(err)); }
  }

  outlet.querySelector('#search').addEventListener('submit', (e) => { e.preventDefault(); state.q = e.target.q.value.trim(); state.skip = 0; load(); });
  on(outlet, 'click', '[data-filter]', (_, el) => {
    state.filter = el.dataset.filter; state.skip = 0;
    outlet.querySelectorAll('[data-filter]').forEach((b) => b.setAttribute('aria-pressed', String(b === el)));
    load();
  });
  on(outlet, 'click', '[data-page]', (_, el) => { state.skip = Math.max(0, state.skip + Number(el.dataset.page) * PAGE); load(); });
  on(outlet, 'click', 'tr[data-href]', (e, tr) => { if (!e.target.closest('a, button')) location.hash = tr.dataset.href; });

  // ── Row actions menu: one floating menu, positioned next to the button that opened it ──
  const menu = document.createElement('div');
  menu.className = 'panel fixed z-40 w-56 p-1.5 shadow-xl';
  menu.setAttribute('role', 'menu');
  menu.hidden = true;
  outlet.append(menu);
  let opener = null;
  const closeMenu = () => { menu.hidden = true; opener?.setAttribute('aria-expanded', 'false'); opener = null; };

  on(outlet, 'click', '[data-menu]', (e, btn) => {
    e.stopPropagation();
    if (opener === btn) return closeMenu();
    closeMenu();
    const u = rows.find((r) => r.id === btn.dataset.menu);
    render(menu, html`${menuItems(u, session.user.id).map(([label, action, danger]) => html`
      <button role="menuitem" class="nav-link w-full ${danger ? 'text-rejected hover:text-rejected' : ''}" data-act="${action}" data-id="${u.id}">${label}</button>`)}`);
    const r = btn.getBoundingClientRect();
    menu.hidden = false;
    const top = r.bottom + 4 + menu.offsetHeight > innerHeight ? r.top - menu.offsetHeight - 4 : r.bottom + 4;
    menu.style.top = `${Math.max(8, top)}px`;
    menu.style.left = `${Math.max(8, Math.min(r.right - menu.offsetWidth, innerWidth - menu.offsetWidth - 8))}px`;
    btn.setAttribute('aria-expanded', 'true');
    opener = btn;
    menu.querySelector('button')?.focus();
  });
  on(menu, 'click', '[data-act]', async (_, el) => {
    const u = rows.find((r) => r.id === el.dataset.id);
    closeMenu();
    if (await runMenuAction(el.dataset.act, u)) load();
  });
  const outside = (e) => { if (!menu.hidden && !menu.contains(e.target)) closeMenu(); };
  document.addEventListener('click', outside);
  menu.addEventListener('keydown', (e) => {
    const items = [...menu.querySelectorAll('button')];
    const i = items.indexOf(document.activeElement);
    if (e.key === 'Escape') { const b = opener; closeMenu(); b?.focus(); }
    if (e.key === 'ArrowDown') { e.preventDefault(); items[(i + 1) % items.length].focus(); }
    if (e.key === 'ArrowUp') { e.preventDefault(); items[(i - 1 + items.length) % items.length].focus(); }
  });
  window.addEventListener('scroll', closeMenu, { passive: true });
  on(outlet, 'click', '[data-action="retry"]', load);
  await load();
  return () => { document.removeEventListener('click', outside); window.removeEventListener('scroll', closeMenu); };
}

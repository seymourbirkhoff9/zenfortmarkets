import { api } from './lib/api.js';
import { $, $$, html, on, render } from './lib/dom.js';
import { ago } from './lib/format.js';
import { icon } from './lib/icons.js';
import { avatar } from './lib/avatar.js';
import { initTranslation, languageButton, wireLanguageButtons } from './lib/translate.js';
import { mountAssistant } from './lib/assistant/widget.js';
import { currentTheme, toggleTheme } from './lib/theme.js';
import { openDialog, toastError } from './lib/ui.js';
import { invalidate } from './lib/cache.js';
import { session } from './session.js';

/**
 * Mounts the signed-in chrome around #outlet.
 *   area: 'user' | 'admin'
 *   nav:  [{ href:'#/wallet', label:'Wallet', icon:'wallet', match:'/wallet', badge:'deposits' }]
 */
export function mountShell({ area, user, nav }) {
  const root = document.getElementById('root');
  const isAdmin = area === 'admin';
  render(root, html`
    <div id="progress" class="pointer-events-none fixed inset-x-0 top-0 z-[70] h-0.5 overflow-hidden" hidden aria-hidden="true">
      <div class="h-full w-1/3 animate-[zf-progress_1.1s_ease-in-out_infinite] bg-brass"></div></div>
    <a href="#outlet" class="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 btn-primary">Skip to content</a>
    ${user.impersonated_by ? html`
    <div class="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 bg-pending px-4 py-2 text-center text-sm font-medium text-white" role="status">
      <span>Viewing as <strong>${user.full_name}</strong> (${user.email}). View only: nothing can be changed.</span>
      <span id="imp-left" class="num opacity-90" aria-hidden="true"></span><span id="imp-left-sr" class="sr-only"></span>
      <button id="imp-exit" class="rounded bg-white/20 px-3 py-1 text-xs font-semibold hover:bg-white/30">Exit to console</button>
    </div>` : html`
    <p class="border-b border-line bg-sunken px-4 py-1.5 text-center text-xs text-muted">
      Demo environment. Balances are simulated and nothing here is investment advice.
    </p>`}
    <div class="lg:grid lg:min-h-[calc(100vh-29px)] lg:grid-cols-[15.5rem_1fr]">
      <aside id="sidebar" class="fixed inset-y-0 left-0 z-40 w-64 -translate-x-full border-r border-line bg-surface transition-transform lg:static lg:w-auto lg:translate-x-0" aria-label="Main">
        <div class="flex h-16 items-center gap-2.5 border-b border-line px-5">
          <span class="grid h-8 w-8 place-items-center rounded bg-navy font-serif text-lg font-semibold text-navy-fg">Z</span>
          <span class="leading-tight">
            <span class="block font-semibold">Zenfort Markets</span>
            <span class="block text-xs text-muted">${isAdmin ? 'Operations console' : 'Customer account'}</span>
          </span>
        </div>
        <nav class="grid gap-0.5 p-3 pl-3">
          ${nav.map((item) => item.section
            ? html`<p class="mt-4 px-3 pb-1 text-xs font-semibold text-muted">${item.section}</p>`
            : html`<a class="nav-link" href="${item.href}" data-match="${item.match}">
                ${icon(item.icon)}<span>${item.label}</span>
                ${item.badge ? html`<span class="badge" data-badge="${item.badge}" hidden></span>` : ''}
              </a>`)}
        </nav>
        ${user.is_admin && !isAdmin && !user.impersonated_by ? html`<div class="border-t border-line p-3">
          <a class="nav-link" href="/admin.html">${icon('shield')}<span>Operations console</span></a></div>` : ''}
      </aside>
      <div id="scrim" class="fixed inset-0 z-30 bg-black/40 lg:hidden" hidden></div>

      <div class="min-w-0">
        <header class="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-line bg-paper/90 px-4 backdrop-blur sm:px-6">
          <button id="menu-btn" class="rounded p-2 text-muted hover:bg-sunken lg:hidden" aria-label="Open menu" aria-controls="sidebar" aria-expanded="false">${icon('menu')}</button>
          <div class="ml-auto flex items-center gap-1">
            ${languageButton()}
            <button id="theme-btn" class="rounded p-2 text-muted hover:bg-sunken hover:text-ink" aria-label="Switch colour theme">
              ${icon(currentTheme() === 'dark' ? 'sun' : 'moon')}
            </button>
            <div class="relative">
              <button id="bell-btn" class="relative rounded p-2 text-muted hover:bg-sunken hover:text-ink" aria-label="Notifications" aria-expanded="false" aria-controls="bell-panel">
                ${icon('bell')}
                <span id="bell-count" class="absolute right-1 top-1 grid h-4 min-w-4 place-items-center rounded-full bg-rejected px-1 text-[10px] font-bold text-white num" hidden></span>
              </button>
              <div id="bell-panel" class="panel fixed inset-x-2 z-30 flex flex-col overflow-hidden shadow-xl sm:absolute sm:inset-x-auto sm:right-0 sm:top-11 sm:w-[24rem]" hidden></div>
            </div>
            <div class="relative">
              <button id="account-btn" class="flex items-center gap-2 rounded py-1.5 pl-2 pr-2.5 hover:bg-sunken" aria-expanded="false" aria-controls="account-menu">
                <span id="account-avatar">${avatar(user)}</span>
                <span class="hidden text-left text-sm leading-tight sm:block">
                  <span class="block font-medium">${user.full_name}</span>
                  <span class="block text-xs text-muted">${user.email}</span>
                </span>
              </button>
              <div id="account-menu" class="panel absolute right-0 top-12 z-30 w-56 p-1.5 shadow-xl" hidden>
                ${!isAdmin ? html`<a href="#/settings" class="nav-link">${icon('gear')}Settings</a>` : ''}
                <button id="logout-btn" class="nav-link w-full">${icon('out')}Sign out</button>
              </div>
            </div>
          </div>
        </header>
        <main id="outlet" tabindex="-1" class="mx-auto w-full max-w-6xl px-4 py-6 focus:outline-none sm:px-6 lg:py-8"></main>
      </div>
    </div>`);

  wireChrome();
  wireProgress();
  wireLanguageButtons(root);
  initTranslation();
  // Customers get the support assistant (not admins, and not while an admin is viewing as them).
  if (!isAdmin && !user.impersonated_by) mountAssistant({ user });
  if (user.impersonated_by) wireImpersonation(user);
  else if (!user.terms_current) askForTerms();
  // Settings broadcasts profile changes (e.g. a new photo) so the header updates immediately.
  window.addEventListener('zf:user-updated', (e) => render('#account-avatar', avatar(e.detail)));
  const stopPolling = startNotifications(area);
  return {
    setActive(path) {
      $$('#sidebar [data-match]').forEach((a) => {
        const m = a.dataset.match;
        const active = m === '/' ? path === '/' : path === m || path.startsWith(m + '/');
        a.toggleAttribute('aria-current', active);
        if (active) a.setAttribute('aria-current', 'page');
      });
      closeMenu();
    },
    setBadges(counts) {
      Object.entries(counts).forEach(([k, n]) => {
        const el = $(`[data-badge="${k}"]`);
        if (!el) return;
        el.textContent = n > 99 ? '99+' : n;
        el.hidden = !n;
      });
    },
    stopPolling,
  };
}


function closeMenu() {
  $('#sidebar').classList.add('-translate-x-full');
  $('#scrim').hidden = true;
  $('#menu-btn').setAttribute('aria-expanded', 'false');
}

function wireChrome() {
  $('#menu-btn').addEventListener('click', () => {
    $('#sidebar').classList.remove('-translate-x-full');
    $('#scrim').hidden = false;
    $('#menu-btn').setAttribute('aria-expanded', 'true');
  });
  $('#scrim').addEventListener('click', closeMenu);

  $('#theme-btn').addEventListener('click', (e) => {
    const t = toggleTheme();
    render(e.currentTarget, icon(t === 'dark' ? 'sun' : 'moon'));
  });

  popover('#account-btn', '#account-menu');
  $('#logout-btn').addEventListener('click', async () => {
    invalidate();
    try { await api.auth.logout(); } catch { /* cookie may already be gone */ }
    location.href = '/login.html';
  });
}

function popover(btnSel, panelSel, onOpen) {
  const btn = $(btnSel), panel = $(panelSel);
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = panel.hidden;
    $$('[aria-expanded="true"]').forEach((b) => { if (b !== btn && b.id !== 'menu-btn') { b.setAttribute('aria-expanded', 'false'); $('#' + b.getAttribute('aria-controls')).hidden = true; } });
    panel.hidden = !open;
    btn.setAttribute('aria-expanded', String(open));
    if (open) onOpen?.();
  });
  document.addEventListener('click', (e) => {
    if (!panel.hidden && !panel.contains(e.target)) { panel.hidden = true; btn.setAttribute('aria-expanded', 'false'); }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !panel.hidden) { panel.hidden = true; btn.setAttribute('aria-expanded', 'false'); btn.focus(); }
  });
}

/* ── Terms acceptance ─────────────────────────────────────────────── */
async function askForTerms() {
  const accepted = await openDialog({
    title: 'We’ve updated our terms', dismissable: false,
    submitLabel: 'Accept and continue', cancelLabel: 'Sign out',
    body: html`
      <p class="text-muted">Please review the updated documents before continuing:</p>
      <ul class="grid gap-1.5 text-sm">
        <li><a class="btn-link" href="/terms.html" target="_blank" rel="noopener">Terms of Service</a></li>
        <li><a class="btn-link" href="/privacy.html" target="_blank" rel="noopener">Privacy Policy</a></li>
        <li><a class="btn-link" href="/risk.html" target="_blank" rel="noopener">Risk Disclosure</a></li>
      </ul>
      <label class="flex items-start gap-2 text-sm"><input type="checkbox" name="agree" required class="mt-1 h-4 w-4 accent-settled" />
        <span>I’ve read and agree to the Terms of Service and Privacy Policy.</span></label>`,
    onSubmit: async () => { session.user = await api.auth.acceptTerms(); return true; },
  });
  if (!accepted) { try { await api.auth.logout(); } finally { location.href = '/login.html'; } }
}

/* ── View-only impersonation ───────────────────────────────────────── */
function wireImpersonation(user) {
  const left = $('#imp-left');
  const exit = async () => {
    try { const { redirect } = await api.auth.exitImpersonation(); invalidate(); location.href = redirect; }
    catch { location.href = '/admin.html'; }
  };
  const srLeft = $('#imp-left-sr');
  let lastMinute = null;
  const tick = () => {
    const ms = new Date(user.impersonation_expires_at).getTime() - Date.now();
    if (ms <= 0) { clearInterval(timer); exit(); return; }       // session over: back to the console
    const m = Math.floor(ms / 60000), sec = Math.floor((ms % 60000) / 1000);
    left.textContent = `Ends in ${m}:${String(sec).padStart(2, '0')}`;
    if (m !== lastMinute) {                                      // screen readers: once a minute, not every second
      lastMinute = m;
      srLeft.textContent = m ? `View-only session ends in ${m + 1} minutes.` : 'View-only session ends in under a minute.';
    }
  };
  const timer = setInterval(tick, 1000);
  tick();
  $('#imp-exit').addEventListener('click', exit);
}

/* ── Request progress bar ───────────────────────────────────────────── */
function wireProgress() {
  const bar = $('#progress');
  let timer;
  window.addEventListener('zf:busy', (e) => {
    clearTimeout(timer);
    // Only show for requests that take a noticeable time, to avoid flicker.
    if (e.detail > 0) timer = setTimeout(() => { bar.hidden = false; }, 150);
    else bar.hidden = true;
  });
}

/* ── Notifications ──────────────────────────────────────────────────── */
// Where a notification leads, by type and app area.
const LINKS = {
  user: { deposit: '#/wallet', withdrawal: '#/wallet?tab=withdrawal', kyc: '#/settings', referral: '#/referrals', account: '#/' },
  admin: { deposit: '#/deposits', withdrawal: '#/withdrawals', kyc: '#/kyc' },
};

function startNotifications(area) {
  const viewOnly = Boolean(session.user?.impersonated_by);
  const countEl = $('#bell-count');
  const panel = $('#bell-panel');
  const btn = $('#bell-btn');
  let items = null;      // last known list: the panel opens with it instantly
  let unread = 0;

  const setCount = (n) => {
    unread = Math.max(0, n);
    countEl.textContent = unread > 9 ? '9+' : unread;
    countEl.hidden = !unread;
  };

  async function fetchList() {
    try { items = await api.notifications.list(); setCount(items.filter((n) => !n.is_read).length); }
    catch { /* keep the old list */ }
    if (!panel.hidden) draw();
  }

  async function refreshCount() {
    if (document.hidden) return;
    try {
      const { unread: n } = await api.notifications.unread();
      if (n !== unread || items === null) { setCount(n); fetchList(); }   // prefetch so opening is instant
    } catch { /* polling failures stay silent */ }
  }

  function place() {
    // Phones: a full-width sheet just under the header (which may have scrolled).
    if (matchMedia('(min-width: 640px)').matches) { panel.style.top = ''; panel.style.maxHeight = '70vh'; return; }
    const top = document.querySelector('header').getBoundingClientRect().bottom + 6;
    panel.style.top = `${top}px`;
    panel.style.maxHeight = `calc(100dvh - ${top + 12}px)`;
  }

  function draw() {
    if (items === null) { render(panel, html`<div class="grid gap-3 p-4"><div class="skeleton h-4"></div><div class="skeleton h-4 w-2/3"></div><div class="skeleton h-4"></div></div>`); return; }
    const links = LINKS[area] || {};
    render(panel, html`
      <div class="flex shrink-0 items-center justify-between border-b border-line px-4 py-3">
        <p class="font-semibold">Notifications</p>
        ${unread && !viewOnly ? html`<button class="btn-link text-xs" data-action="read-all">Mark all as read</button>` : ''}
      </div>
      <ul class="overflow-y-auto overscroll-contain">
        ${items.length ? items.map((n) => html`
          <li class="flex items-start gap-2 border-b border-line/60 px-4 py-3 last:border-0 ${n.is_read ? '' : 'bg-brass/5'}">
            <span class="mt-2 h-1.5 w-1.5 shrink-0 rounded-full ${n.is_read ? '' : 'bg-brass'}" ${n.is_read ? '' : html`aria-label="Unread"`}></span>
            <a class="min-w-0 flex-1" href="${links[n.type] || '#/'}" data-open="${n.id}">
              <span class="block text-sm font-medium">${n.title}</span>
              <span class="block text-sm text-muted">${n.message}</span>
              <span class="mt-1 block text-xs text-muted">${ago(n.created_at)}</span>
            </a>
            ${n.is_read || viewOnly ? '' : html`<button class="shrink-0 rounded px-2 py-1 text-xs font-medium text-muted hover:bg-sunken hover:text-ink" data-read="${n.id}">Mark read</button>`}
          </li>`)
          : html`<li class="px-4 py-8 text-center text-sm text-muted">You’re all caught up.</li>`}
      </ul>`);
  }

  async function markRead(id) {
    const n = items?.find((x) => x.id === id);
    if (!n || n.is_read) return;
    n.is_read = true; setCount(unread - 1); draw();          // optimistic
    try { await api.notifications.read(id); } catch { n.is_read = false; setCount(unread + 1); draw(); }
  }

  popover('#bell-btn', '#bell-panel', () => { place(); draw(); fetchList(); });
  window.addEventListener('resize', () => { if (!panel.hidden) place(); });
  on(panel, 'click', '[data-read]', (e, el) => { e.preventDefault(); markRead(el.dataset.read); });
  on(panel, 'click', '[data-open]', (_, el) => {
    if (!viewOnly) markRead(el.dataset.open);
    panel.hidden = true; btn.setAttribute('aria-expanded', 'false');
  });
  on(panel, 'click', '[data-action="read-all"]', async () => {
    const before = items.map((n) => n.is_read);
    items.forEach((n) => { n.is_read = true; }); setCount(0); draw();
    try { await api.notifications.readAll(); } catch (err) { items.forEach((n, i) => { n.is_read = before[i]; }); fetchList(); toastError(err); }
  });

  refreshCount();
  const timer = setInterval(refreshCount, 30_000);
  document.addEventListener('visibilitychange', refreshCount);
  return () => clearInterval(timer);
}

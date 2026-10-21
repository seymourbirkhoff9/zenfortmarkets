import '../../styles.css';
import { html, raw, render } from '../../lib/dom.js';
import { SITE } from '../../site.js';
import { api } from '../../lib/api.js';
import { themeButton, wireThemeButton } from '../../lib/theme.js';
import { initTranslation, languageButton, wireLanguageButtons } from '../../lib/translate.js';
import { mountAssistant } from '../../lib/assistant/widget.js';

const NAV = [
  ['How it works', '/how-it-works.html'], ['Fees & limits', '/fees.html'], ['Security', '/security.html'],
  ['FAQ', '/faq.html'], ['About', '/about.html'],
];

export const footer = () => html`
  <footer class="border-t border-line bg-surface">
    <div class="mx-auto grid max-w-6xl gap-10 px-6 py-12 sm:grid-cols-2 lg:grid-cols-[1.4fr_1fr_1fr_1fr]">
      <div>
        <a href="/" class="flex items-center gap-2.5 font-semibold">
          <span class="grid h-8 w-8 place-items-center rounded bg-navy font-serif text-lg text-navy-fg">Z</span>${SITE.name}</a>
        <p class="mt-3 max-w-xs text-sm text-muted">Your trusted platform for cryptocurrency trading and investment management.</p>
      </div>
      ${[
        ['Product', [['How it works', '/how-it-works.html'], ['Fees & limits', '/fees.html'], ['Supported networks', '/fees.html#networks'], ['Security', '/security.html']]],
        ['Company', [['About', '/about.html'], ['FAQ', '/faq.html'], ['Contact', '/contact.html']]],
        ['Legal', [['Terms of Service', '/terms.html'], ['Privacy Policy', '/privacy.html'], ['Risk Disclosure', '/risk.html']]],
      ].map(([h, links]) => html`<nav aria-label="${h}"><p class="text-sm font-semibold">${h}</p>
        <ul class="mt-3 grid gap-2 text-sm text-muted">${links.map(([l, u]) => html`<li><a class="hover:text-ink hover:underline" href="${u}">${l}</a></li>`)}</ul></nav>`)}
    </div>
    <p class="border-t border-line px-6 py-5 text-center text-xs text-muted">© ${new Date().getFullYear()} ${SITE.name}. All rights reserved.</p>
  </footer>`;

export const header = () => html`
  <header class="relative z-30 mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-5">
    <a href="/" class="flex shrink-0 items-center gap-2.5 font-semibold">
      <span class="grid h-8 w-8 place-items-center rounded bg-navy font-serif text-lg text-navy-fg">Z</span>${SITE.name}</a>
    <nav aria-label="Main" class="hidden items-center gap-6 text-sm lg:flex">
      ${NAV.map(([l, u]) => html`<a class="text-muted hover:text-ink ${location.pathname === u ? 'font-semibold text-ink' : ''}" href="${u}"
        ${location.pathname === u ? html`aria-current="page"` : ''}>${l}</a>`)}
    </nav>
    <div class="flex items-center gap-1 sm:gap-2" id="auth-links">
      ${languageButton()}
      ${themeButton()}
      <span id="auth-cta" class="hidden items-center gap-2 sm:flex"><a class="btn-quiet" href="/login.html">Sign in</a>
      <a class="btn-primary" href="/signup.html">Create account</a></span>
      <button id="pub-menu" class="rounded p-2 text-muted hover:bg-sunken lg:hidden" aria-expanded="false" aria-controls="pub-nav" aria-label="Menu">
        <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg></button>
    </div>
    <nav id="pub-nav" aria-label="Main" class="panel absolute inset-x-4 top-[4.5rem] grid gap-1 p-2 shadow-xl lg:hidden" hidden>
      ${NAV.map(([l, u]) => html`<a class="nav-link" href="${u}">${l}</a>`)}
      <div id="auth-cta-mobile" class="mt-1 grid gap-2 border-t border-line p-2 pt-3 sm:hidden">
        <a class="btn-primary" href="/signup.html">Create account</a><a class="btn-quiet" href="/login.html">Sign in</a></div>
    </nav>
  </header>`;

export const cryptoTicker = () => html`
  <div class="border-b border-line bg-sunken overflow-hidden">
    <div class="flex animate-marquee whitespace-nowrap py-2">
      ${[
        { symbol: 'BTC', name: 'Bitcoin', price: '$67,245.00', change: '+2.34%', up: true },
        { symbol: 'ETH', name: 'Ethereum', price: '$3,456.78', change: '+1.89%', up: true },
        { symbol: 'BNB', name: 'BNB', price: '$598.45', change: '-0.45%', up: false },
        { symbol: 'SOL', name: 'Solana', price: '$178.23', change: '+5.67%', up: true },
        { symbol: 'XRP', name: 'XRP', price: '$0.5234', change: '-1.23%', up: false },
        { symbol: 'ADA', name: 'Cardano', price: '$0.4567', change: '+0.89%', up: true },
        { symbol: 'DOGE', name: 'Dogecoin', price: '$0.1234', change: '+3.45%', up: true },
        { symbol: 'DOT', name: 'Polkadot', price: '$7.89', change: '-0.67%', up: false },
      ].map(coin => html`
        <div class="flex items-center gap-3 px-6 text-sm">
          <span class="font-semibold text-ink">${coin.symbol}</span>
          <span class="text-muted">${coin.name}</span>
          <span class="font-medium text-ink">${coin.price}</span>
          <span class="${coin.up ? 'text-success' : 'text-danger'}">${coin.change}</span>
        </div>
      `)}
      ${[
        { symbol: 'BTC', name: 'Bitcoin', price: '$67,245.00', change: '+2.34%', up: true },
        { symbol: 'ETH', name: 'Ethereum', price: '$3,456.78', change: '+1.89%', up: true },
        { symbol: 'BNB', name: 'BNB', price: '$598.45', change: '-0.45%', up: false },
        { symbol: 'SOL', name: 'Solana', price: '$178.23', change: '+5.67%', up: true },
        { symbol: 'XRP', name: 'XRP', price: '$0.5234', change: '-1.23%', up: false },
        { symbol: 'ADA', name: 'Cardano', price: '$0.4567', change: '+0.89%', up: true },
        { symbol: 'DOGE', name: 'Dogecoin', price: '$0.1234', change: '+3.45%', up: true },
        { symbol: 'DOT', name: 'Polkadot', price: '$7.89', change: '-0.67%', up: false },
      ].map(coin => html`
        <div class="flex items-center gap-3 px-6 text-sm">
          <span class="font-semibold text-ink">${coin.symbol}</span>
          <span class="text-muted">${coin.name}</span>
          <span class="font-medium text-ink">${coin.price}</span>
          <span class="${coin.up ? 'text-success' : 'text-danger'}">${coin.change}</span>
        </div>
      `)}
    </div>
  </div>`;

/** Wire the header menu, the “Go to your account” link for signed-in visitors, and scroll reveals. */
export function enhance() {
  wireThemeButton();
  wireLanguageButtons();
  initTranslation();
  mountAssistant();
  // Signed-in visitors get a direct way back in instead of "Sign in / Create account".
  api.auth.me({ quiet401: true }).then((u) => {
    const link = html`<a class="btn-primary" href="${u.is_admin ? '/admin.html' : '/app.html'}">${u.is_admin ? 'Open the console' : 'Go to your account'}</a>`;
    render('#auth-cta', link);
    render('#auth-cta-mobile', link);
  }).catch(() => {});
  const btn = document.getElementById('pub-menu'), nav = document.getElementById('pub-nav');
  btn?.addEventListener('click', () => { nav.hidden = !nav.hidden; btn.setAttribute('aria-expanded', String(!nav.hidden)); });
  // Elements marked data-reveal fade up as they scroll into view (instantly with reduced motion).
  const els = document.querySelectorAll('[data-reveal]');
  if (!('IntersectionObserver' in window) || matchMedia('(prefers-reduced-motion: reduce)').matches) {
    els.forEach((el) => el.classList.add('is-visible')); return;
  }
  const io = new IntersectionObserver((entries) => entries.forEach((en) => {
    if (en.isIntersecting) { en.target.classList.add('is-visible'); io.unobserve(en.target); }
  }), { rootMargin: '0px 0px -8% 0px' });
  els.forEach((el) => io.observe(el));
}

/** A simple content page: header, title, body sections, footer. */
export function contentPage({ title, intro, body }) {
  document.title = `${title} — ${SITE.name}`;
  render('#root', html`${cryptoTicker()}${header()}
    <main>
      <section class="ledger-bg border-b border-line">
        <div class="mx-auto max-w-6xl px-6 pb-14 pt-10">
          <h1 class="max-w-3xl font-serif text-4xl leading-tight sm:text-5xl">${title}</h1>
          <p class="mt-4 max-w-2xl text-lg text-muted">${intro}</p>
        </div>
      </section>
      <div class="mx-auto max-w-6xl px-6 py-14">${body}</div>
    </main>
    ${footer()}`);
  enhance();
}

/**
 * A legal document page. `sections` is [[heading, [paragraph, …]], …]; paragraphs are plain text,
 * except entries wrapped in raw() which may contain our own trusted markup (links, lists).
 */
export function legalPage({ title, intro, sections }) {
  document.title = `${title} — ${SITE.name}`;
  render('#root', html`
    ${cryptoTicker()}
    ${header()}
    <main class="mx-auto max-w-3xl px-6 pb-20 pt-6">
      <p class="text-sm text-muted">Last updated ${SITE.termsUpdated} (version ${SITE.termsVersion})</p>
      <h1 class="mt-2 font-serif text-4xl">${title}</h1>
      <p class="mt-4 text-lg text-muted">${intro}</p>
      <nav aria-label="On this page" class="mt-8 rounded border border-line bg-surface p-4 text-sm">
        <p class="font-semibold">On this page</p>
        <ol class="mt-2 grid gap-1 sm:grid-cols-2">${sections.map(([h], i) => html`<li><a class="text-muted hover:text-ink hover:underline" href="#s${i + 1}">${i + 1}. ${h}</a></li>`)}</ol>
      </nav>
      ${sections.map(([h, paras], i) => html`
        <section id="s${i + 1}" class="mt-10 scroll-mt-6">
          <h2 class="font-serif text-2xl">${i + 1}. ${h}</h2>
          ${paras.map((p) => html`<p class="mt-3 leading-relaxed">${p}</p>`)}
        </section>`)}
    </main>
    ${footer()}`);
  enhance();
}

export { raw, SITE };

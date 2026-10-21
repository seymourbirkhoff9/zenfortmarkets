import { cryptoTicker, enhance, footer, header, SITE } from './public/layout.js';
import { html, render } from '../lib/dom.js';
import { money, pct } from '../lib/format.js';
import { icon } from '../lib/icons.js';

const API = (import.meta.env.VITE_API_BASE || '/api').replace(/\/$/, '');
const getJSON = (path) => fetch(API + path).then((r) => (r.ok ? r.json() : [])).catch(() => []);

// The hero statement: a sample that plays out the one thing this product is about.
const ROWS = [
  { id: 'dep', what: 'Deposit via USDT (TRC20)', note: 'Hash 0x7c1e…a94d submitted', amt: '+$250.00', status: 'pending' },
  { id: 'roi', what: 'Investment return, Starter 30', note: 'Day 12 of 30', amt: '+$1.60', status: 'settled' },
  { id: 'move', what: 'Profit wallet to Main', note: 'Instant', amt: '$18.40', status: 'settled' },
  { id: 'wd', what: 'Withdrawal to BTC (Bitcoin)', note: 'Held until paid out', amt: '−$120.00', status: 'pending' },
];
const pill = (st) => (st === 'pending' ? html`<span class="pill-pending">Pending review</span>` : html`<span class="pill-settled">Settled</span>`);

const statement = html`
  <figure class="panel overflow-hidden shadow-sm" aria-label="Sample account statement (animated)">
    <div class="flex items-end justify-between border-b border-line px-6 py-5">
      <div><p class="text-sm text-muted">Main wallet</p><p id="st-balance" class="figure text-4xl">$998.40</p></div>
      <p class="text-right text-xs text-muted">Sample statement</p>
    </div>
    <ol class="divide-y divide-line">
      ${ROWS.map((r) => html`<li class="st-row grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 px-6 py-3.5" data-row="${r.id}">
        <span class="font-medium">${r.what}</span><span class="figure text-right">${r.amt}</span>
        <span class="text-xs text-muted" data-note>${r.note}</span><span class="text-right" data-pill>${pill(r.status)}</span></li>`)}
    </ol>
    <p class="border-t border-line bg-sunken px-6 py-3 text-xs text-muted" data-caption aria-live="polite">An operator is checking the deposit…</p>
  </figure>`;

function playStatement() {
  const rows = [...document.querySelectorAll('.st-row')];
  const bal = document.getElementById('st-balance');
  const caption = document.querySelector('[data-caption]');
  const settle = () => {
    const dep = document.querySelector('[data-row="dep"]');
    dep.querySelector('[data-pill]').innerHTML = '<span class="pill-settled">Settled</span>';
    dep.querySelector('[data-note]').textContent = 'Confirmed by an operator';
    dep.classList.add('st-flash');
    caption.textContent = 'Confirmed. $250.00 credited to Main and written to the audit log.';
  };
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
    rows.forEach((r) => r.classList.add('in')); settle(); bal.textContent = '$1,248.40'; return;
  }
  rows.forEach((r, i) => setTimeout(() => r.classList.add('in'), 250 + i * 160));
  setTimeout(() => {
    settle();
    const from = 998.40, to = 1248.40, t0 = performance.now();
    const step = (t) => {
      const k = Math.min(1, (t - t0) / 900);
      bal.textContent = money(from + (to - from) * (1 - (1 - k) ** 3));
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, 2200);
}

const steps = [
  ['down', 'Send crypto, report it', 'Pick an asset and network from the list, send from your own wallet, then report the dollar value with the transaction hash or a screenshot.'],
  ['shield', 'A person checks it', 'An operator matches your payment on-chain and credits your Main wallet. Every decision is recorded with who made it and when.'],
  ['up', 'Withdraw to your address', 'Request a payout to your own wallet. The amount is held while it’s reviewed and returned in full if it can’t be paid.'],
];

const backOffice = [
  ['Review queue, oldest first', 'Deposits, payouts and identity checks wait in one queue, with how long each has been waiting.'],
  ['Audit log for every action', 'Credits, approvals and role changes are written in the same database transaction as the change itself.'],
  ['Private documents', 'ID documents and payment screenshots sit in private storage and open only through links that expire in minutes.'],
  ['View-only support access', 'Support can see your account exactly as you do, but can’t move money or change anything while doing so.'],
  ['One dollar ledger', 'Every balance is kept in US dollars. Crypto is only the rail money arrives and leaves on.'],
  ['You’re told about everything', 'Each review outcome reaches you in the app and by email, with the amount, method and reference.'],
];

const faqs = [
  ['Is this a real investment platform?', 'Yes. Zenfort Markets is a cryptocurrency trading and investment platform with secure wallet management and professional trading services.'],
  ['How long does a deposit take?', 'As long as it takes an operator to see your payment arrive on-chain. You’re notified as soon as it’s confirmed or if something needs fixing.'],
  ['Why do I need to verify my identity?', 'Withdrawals go to external addresses and can’t be reversed, so an identity check is required before the first one.'],
];

render('#root', html`
  ${cryptoTicker()}
  <div class="ledger-bg">
    ${header()}
    <section class="mx-auto grid max-w-6xl items-center gap-12 px-6 pb-20 pt-8 lg:grid-cols-[1fr_1.05fr] lg:pt-14">
      <div data-reveal>
        <h1 class="font-serif text-4xl leading-[1.1] sm:text-5xl">Crypto comes in. Dollars go on the books. A person checks every move.</h1>
        <p class="mt-5 max-w-prose text-lg text-muted">${SITE.name} is a professional cryptocurrency trading platform: customers report deposits
          and request payouts, operators review each one, and every balance change lands in an audited dollar ledger.</p>
        <div class="mt-8 flex flex-wrap gap-3">
          <a class="btn-primary px-5 py-3 text-base" href="/signup.html">Create account</a>
          <a class="btn-quiet px-5 py-3 text-base" href="/how-it-works.html">See how it works</a>
        </div>
      </div>
      <div data-reveal data-reveal-delay="2">${statement}</div>
    </section>
  </div>

  <!-- Trusted Partners Ticker -->
  <section class="border-y border-line bg-surface overflow-hidden">
    <div class="flex animate-marquee whitespace-nowrap py-8">
      ${[
        { name: 'Coinbase', logo: '🪙' },
        { name: 'Binance', logo: '🔷' },
        { name: 'Ethereum', logo: '💎' },
        { name: 'Bitcoin', logo: '₿' },
        { name: 'Solana', logo: '⚡' },
        { name: 'Cardano', logo: '🔵' },
        { name: 'Polkadot', logo: '🔴' },
        { name: 'Chainlink', logo: '🔗' },
      ].map(partner => html`
        <div class="flex items-center gap-3 px-8">
          <span class="text-2xl">${partner.logo}</span>
          <span class="text-lg font-semibold text-muted">${partner.name}</span>
        </div>
      `)}
      ${[
        { name: 'Coinbase', logo: '🪙' },
        { name: 'Binance', logo: '🔷' },
        { name: 'Ethereum', logo: '💎' },
        { name: 'Bitcoin', logo: '₿' },
        { name: 'Solana', logo: '⚡' },
        { name: 'Cardano', logo: '🔵' },
        { name: 'Polkadot', logo: '🔴' },
        { name: 'Chainlink', logo: '🔗' },
      ].map(partner => html`
        <div class="flex items-center gap-3 px-8">
          <span class="text-2xl">${partner.logo}</span>
          <span class="text-lg font-semibold text-muted">${partner.name}</span>
        </div>
      `)}
    </div>
  </section>

  <section id="networks" class="border-y border-line bg-surface" hidden>
    <div class="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-4 px-6 py-6">
      <p class="text-sm font-semibold text-muted">Fund your account with</p>
      <ul id="network-list" class="flex flex-wrap gap-2"></ul>
    </div>
  </section>

  <section class="mx-auto max-w-6xl px-6 py-20">
    <h2 class="max-w-2xl font-serif text-3xl" data-reveal>How money moves</h2>
    <ol class="mt-10 grid gap-10 md:grid-cols-3">
      ${steps.map(([ic, t, d], i) => html`<li data-reveal data-reveal-delay="${i + 1}">
        <span class="grid h-11 w-11 place-items-center rounded-full border border-line bg-surface text-brass">${icon(ic)}</span>
        <h3 class="mt-4 text-lg font-semibold"><span class="figure mr-2 text-muted">${i + 1}.</span>${t}</h3>
        <p class="mt-2 text-muted">${d}</p></li>`)}
    </ol>
    <a class="btn-link mt-10 inline-block" href="/how-it-works.html" data-reveal>The full walkthrough</a>
  </section>

  <section id="plans" class="border-y border-line bg-surface" hidden>
    <div class="mx-auto max-w-6xl px-6 py-20">
      <div class="flex flex-wrap items-end justify-between gap-4" data-reveal>
        <div><h2 class="font-serif text-3xl">Plans set by the operator</h2>
          <p class="mt-2 max-w-xl text-muted">Returns are paid daily into your Profit wallet and your principal comes back at the end of the term.
            Returns vary based on market conditions and plan performance.</p></div>
        <a class="btn-quiet" href="/fees.html#plans">All plans and fees</a>
      </div>
      <ul id="plan-list" class="mt-10 grid gap-5 md:grid-cols-3"></ul>
      <p class="mt-6 text-sm text-muted" data-reveal>Read the <a class="btn-link" href="/risk.html">Risk Disclosure</a> before investing.</p>
    </div>
  </section>

  <section class="mx-auto grid max-w-6xl gap-12 px-6 py-20 lg:grid-cols-[0.9fr_1.1fr]">
    <div data-reveal>
      <h2 class="font-serif text-3xl">Built like a back office, not a slot machine</h2>
      <p class="mt-4 text-muted">Nothing is credited automatically and nothing disappears without a record. Here is what that means in practice.</p>
      <a class="btn-link mt-6 inline-block" href="/security.html">How accounts are protected</a>
    </div>
    <dl class="grid gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-2">
      ${backOffice.map(([t, d], i) => html`<div class="bg-surface p-5" data-reveal data-reveal-delay="${(i % 2) + 1}">
        <dt class="font-semibold">${t}</dt><dd class="mt-1.5 text-sm text-muted">${d}</dd></div>`)}
    </dl>
  </section>

  <section class="border-t border-line bg-surface">
    <div class="mx-auto max-w-3xl px-6 py-20">
      <h2 class="font-serif text-3xl" data-reveal>Common questions</h2>
      <div class="mt-8 divide-y divide-line border-y border-line">
        ${faqs.map(([q, a]) => html`<details class="group py-4" data-reveal>
          <summary class="flex cursor-pointer list-none items-center justify-between gap-4 font-medium">${q}
            <span class="text-muted transition-transform group-open:rotate-45" aria-hidden="true">+</span></summary>
          <p class="mt-3 text-muted">${a}</p></details>`)}
      </div>
      <a class="btn-link mt-6 inline-block" href="/faq.html">All questions</a>
    </div>
  </section>

  <section class="bg-navy text-navy-fg">
    <div class="mx-auto flex max-w-6xl flex-col items-start justify-between gap-6 px-6 py-16 md:flex-row md:items-center" data-reveal>
      <div><h2 class="font-serif text-3xl">See the whole flow for yourself</h2>
        <p class="mt-2 opacity-80">Create an account, report a deposit, and watch it move through review.</p></div>
      <a class="btn rounded bg-brass px-5 py-3 text-base text-navy hover:opacity-90" href="/signup.html">Create account</a>
    </div>
  </section>
  ${footer()}`);

enhance();
// Start the statement once it's on screen (it usually is, on load).
new IntersectionObserver((e, o) => { if (e[0].isIntersecting) { o.disconnect(); playStatement(); } })
  .observe(document.querySelector('figure[aria-label^="Sample"]'));

// Live data from the console: supported networks and open plans.
getJSON('/public/payment-methods').then((methods) => {
  const seen = methods.filter((m) => m.deposits);
  if (!seen.length) return;
  render('#network-list', html`${seen.map((m) => html`<li class="flex items-center gap-2 rounded-full border border-line bg-paper px-3 py-1.5 text-sm">
    <span class="grid h-6 min-w-[1.5rem] place-items-center rounded-full bg-navy px-1.5 text-[10px] font-bold text-navy-fg">${m.asset.slice(0, 4)}</span>
    <span><strong>${m.asset}</strong> <span class="text-muted">on ${m.network}</span></span></li>`)}`);
  document.getElementById('networks').hidden = false;
});
getJSON('/public/plans').then((plans) => {
  if (!plans.length) return;
  render('#plan-list', html`${plans.slice(0, 3).map((p) => html`<li class="panel bg-paper p-6">
    <h3 class="font-serif text-xl">${p.name}</h3>
    <p class="mt-3 flex items-baseline gap-2"><span class="figure text-4xl">${pct(p.daily_roi_percent)}</span><span class="text-sm text-muted">per day</span></p>
    <p class="mt-3 text-sm text-muted">${p.duration_days} days, from ${money(p.min_amount)} to ${money(p.max_amount)}</p></li>`)}`);
  document.getElementById('plans').hidden = false;
});

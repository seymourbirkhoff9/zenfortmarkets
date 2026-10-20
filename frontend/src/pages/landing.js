import '../styles.css';
import { footer } from './public/layout.js';
import { api } from '../lib/api.js';
import { html, render } from '../lib/dom.js';

const rows = [
  ['Deposit via USDT (TRC20)', 'Pending review', 'pill-pending', '+$250.00', 'Hash 0x7c1e…a94d submitted'],
  ['Deposit via USDT (TRC20)', 'Settled', 'pill-settled', '+$250.00', 'Confirmed by an operator'],
  ['Wallet move, Profit to Main', 'Settled', 'pill-settled', '$18.40', 'Instant'],
  ['Withdrawal to BTC (Bitcoin)', 'Pending review', 'pill-pending', '−$120.00', 'Held until paid out'],
];

render('#root', html`
  <p class="border-b border-line bg-sunken px-4 py-1.5 text-center text-xs text-muted">
    Educational demo. Balances are simulated, no real funds are held, and nothing here is investment advice.
  </p>
  <header class="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
    <a href="/" class="flex items-center gap-2.5 font-semibold">
      <span class="grid h-8 w-8 place-items-center rounded bg-navy font-serif text-lg text-navy-fg">Z</span>Zenfort Markets</a>
    <nav class="flex items-center gap-2" id="auth-links">
      <a class="btn-quiet" href="/login.html">Sign in</a>
      <a class="btn-primary" href="/signup.html">Create account</a>
    </nav>
  </header>

  <main>
    <section class="mx-auto grid max-w-6xl items-center gap-12 px-6 pb-20 pt-10 lg:grid-cols-[1fr_1.05fr] lg:pt-16">
      <div>
        <h1 class="font-serif text-4xl leading-tight sm:text-5xl">Crypto comes in. Dollars go on the books. A person checks every move.</h1>
        <p class="mt-5 max-w-prose text-lg text-muted">
          Zenfort is a brokerage back office you can study end to end: customers report deposits and request payouts,
          operators review each one, and every balance change lands in an audited USD ledger.
        </p>
        <div class="mt-8 flex flex-wrap gap-3">
          <a class="btn-primary px-5 py-2.5" href="/signup.html">Open a demo account</a>
          <a class="btn-quiet px-5 py-2.5" href="/login.html">Sign in</a>
        </div>
      </div>

      <figure class="panel overflow-hidden shadow-sm" aria-label="Example account statement">
        <div class="flex items-end justify-between border-b border-line px-6 py-5">
          <div><p class="text-sm text-muted">Main wallet</p><p class="figure text-4xl">$1,248.40</p></div>
          <p class="text-right text-xs text-muted">Sample statement</p>
        </div>
        <ol class="divide-y divide-line">
          ${rows.map(([what, st, cls, amt, note]) => html`<li class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 px-6 py-3.5">
            <span class="font-medium">${what}</span><span class="figure text-right">${amt}</span>
            <span class="text-xs text-muted">${note}</span><span class="text-right"><span class="${cls}">${st}</span></span></li>`)}
        </ol>
      </figure>
    </section>

    <section class="border-t border-line bg-surface">
      <div class="mx-auto grid max-w-6xl gap-10 px-6 py-16 md:grid-cols-3">
        ${[
          ['For customers', 'Deposit with the asset and network the operator publishes, track every request until it settles, move funds between wallets, and withdraw to your own address once your ID is verified.'],
          ['For operators', 'One queue for deposits, payouts and identity checks, oldest first. Full view of any customer, manual credits and debits with a note, and configurable plans and payment rails.'],
          ['On the record', 'Each approval stores who did it and when, inside the same database transaction as the balance change. Rejections always carry a reason the customer can read.'],
        ].map(([t, d]) => html`<div><h2 class="text-lg font-semibold">${t}</h2><p class="mt-2 text-muted">${d}</p></div>`)}
      </div>
    </section>
  </main>

  ${footer()}`);

// Signed-in visitors get a direct way back in.
api.auth.me({ quiet401: true }).then((u) => {
  render('#auth-links', html`<a class="btn-primary" href="${u.is_admin ? '/admin.html' : '/app.html'}">Go to ${u.is_admin ? 'the console' : 'your account'}</a>`);
}).catch(() => {});

import { contentPage, SITE } from './layout.js';
import { html } from '../../lib/dom.js';

contentPage({
  title: `About ${SITE.name}`,
  intro: 'A working model of the part of a broker most people never see: the back office where every dollar is checked and recorded.',
  body: html`<div class="grid gap-12 lg:grid-cols-2">
    <div class="grid max-w-prose gap-4 text-lg" data-reveal>
      <p>Most finance apps show you the front: a balance and a button. ${SITE.name} shows the whole path a payment takes, from the moment a customer
        reports it to the moment an operator confirms it and the ledger records it.</p>
      <p>It’s built as an educational project. Balances are simulated, and nothing here is an offer to invest or financial advice.</p>
    </div>
    <dl class="grid gap-6" data-reveal data-reveal-delay="2">
      ${[['People check money, not scripts', 'Every deposit and payout is reviewed by an operator, and every decision is recorded.'],
         ['Plain about risk', 'Returns are never presented as guaranteed. The Risk Disclosure is linked wherever money is committed.'],
         ['Private by default', 'Identity documents are stored privately and opened only through short-lived links.']]
        .map(([t, d]) => html`<div class="border-l-2 border-brass pl-4"><dt class="font-semibold">${t}</dt><dd class="mt-1 text-muted">${d}</dd></div>`)}
    </dl></div>`,
});

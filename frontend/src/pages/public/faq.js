import { contentPage, SITE } from './layout.js';
import { html } from '../../lib/dom.js';

const groups = [
  ['The basics', [
    ['What is Zenfort Markets?', `${SITE.name} is a cryptocurrency trading and investment platform that provides secure wallet management, investment plans, and professional trading services.`],
    ['Why are balances in US dollars?', 'Keeping one currency makes every balance and fee easy to follow. Crypto is only how money arrives and leaves.'],
    ['What are the Main and Profit wallets?', 'Main is spendable: deposits arrive there and withdrawals and investments come from it. Profit collects investment returns; move them to Main any time.']]],
  ['Deposits', [
    ['How long does a deposit take?', 'As long as it takes an operator to see your payment arrive on-chain. You’re notified when it’s confirmed or rejected.'],
    ['I sent on the wrong network. Can it be recovered?', 'Usually not. Always check the asset and network shown before you send.'],
    ['Why was my deposit rejected?', 'The reason is shown on the deposit and in your notification, for example a hash that doesn’t match a payment.']]],
  ['Withdrawals', [
    ['Why do I need to verify my identity?', 'Payouts go to external addresses and can’t be reversed, so an identity check is required before the first one.'],
    ['What fee will I pay?', 'A flat fee per network, shown before you confirm. The fee is deducted from the amount sent.'],
    ['Where is my money while a withdrawal is pending?', 'Held from your Main wallet. If the request is rejected, the full amount comes back.']]],
  ['Investments', [
    ['Are returns guaranteed?', 'No. Read the Risk Disclosure. Investment returns vary based on market conditions and plan performance.'],
    ['Can I end an investment early?', 'No. The amount is locked for the full term, then returned to Main.']]],
];

contentPage({
  title: 'Frequently asked questions',
  intro: html`Can’t find your answer? <a class="btn-link" href="/contact.html">Contact us</a>.`,
  body: html`<div class="grid gap-12 lg:grid-cols-[14rem_1fr]">
    <nav aria-label="Topics" class="hidden lg:block"><ul class="sticky top-6 grid gap-2 text-sm">
      ${groups.map(([g], i) => html`<li><a class="text-muted hover:text-ink" href="#g${i}">${g}</a></li>`)}</ul></nav>
    <div class="grid gap-12">${groups.map(([g, qs], i) => html`<section id="g${i}" class="scroll-mt-6" data-reveal>
      <h2 class="font-serif text-2xl">${g}</h2>
      <div class="mt-4 divide-y divide-line border-y border-line">${qs.map(([q, a]) => html`<details class="group py-4">
        <summary class="flex cursor-pointer list-none items-center justify-between gap-4 font-medium">${q}
          <span class="text-muted transition-transform group-open:rotate-45" aria-hidden="true">+</span></summary>
        <p class="mt-3 max-w-prose text-muted">${a}</p></details>`)}</div></section>`)}</div></div>`,
});

import { contentPage, SITE } from './layout.js';
import { html } from '../../lib/dom.js';

const stage = (n, title, points) => html`
  <li class="grid gap-4 border-t border-line py-10 md:grid-cols-[14rem_1fr]" data-reveal>
    <div><span class="figure text-4xl text-brass">${n}</span><h2 class="mt-2 font-serif text-2xl">${title}</h2></div>
    <ul class="grid gap-3 text-muted">${points.map((p) => html`<li class="max-w-prose">${p}</li>`)}</ul>
  </li>`;

contentPage({
  title: 'How it works',
  intro: `Every movement of money in ${SITE.name} follows the same pattern: you ask, a person checks, the ledger records it.`,
  body: html`<ol>
    ${stage('01', 'Open an account', [
      'Sign up with your name, email and country, and confirm your email from the link we send.',
      'Every balance is kept in US dollars in two wallets: Main (spendable) and Profit (investment returns).'])}
    ${stage('02', 'Report a deposit', [
      'Choose an asset and network from the published list. The deposit address is shown only once you’re signed in.',
      'Send from your own wallet, then report the dollar value you sent with the transaction hash, a screenshot, or both.',
      'Only send the asset on the network shown. Funds sent on another network can be lost permanently.'])}
    ${stage('03', 'An operator reviews it', [
      'The deposit waits in a review queue, oldest first. An operator matches it on-chain and credits your Main wallet, or rejects it with a reason you can read.',
      'You’re notified in the app and by email either way, with the amount, method and reference.'])}
    ${stage('04', 'Invest, if you choose to', [
      'Plans are set by the operator: a daily rate, a term and an amount range. The amount comes from your Main wallet and is locked for the term.',
      'Returns are paid daily into Profit; your principal returns to Main at the end. Returns are never guaranteed. Read the Risk Disclosure first.'])}
    ${stage('05', 'Withdraw to your own address', [
      'Withdrawals need a verified identity. Upload an ID document once from Settings.',
      'Choose a payout method, enter your address and amount. The amount is held right away so it can’t be spent twice.',
      'An operator sends the payout and records the transaction hash, which you can check yourself. If it’s rejected, the full amount returns to Main.'])}
  </ol>
  <div class="mt-6 flex flex-wrap gap-3" data-reveal>
    <a class="btn-primary" href="/signup.html">Create account</a><a class="btn-quiet" href="/fees.html">Fees and limits</a></div>`,
});

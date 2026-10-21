import { contentPage } from './layout.js';
import { html } from '../../lib/dom.js';

const block = (title, items) => html`<section class="border-t border-line py-10" data-reveal>
  <h2 class="font-serif text-2xl">${title}</h2>
  <dl class="mt-6 grid gap-6 md:grid-cols-2">${items.map(([t, d]) => html`<div><dt class="font-semibold">${t}</dt><dd class="mt-1.5 text-muted">${d}</dd></div>`)}</dl>
</section>`;

contentPage({
  title: 'Security',
  intro: 'How accounts, money and documents are protected, and what isn’t in place yet.',
  body: html`
    ${block('Your account', [
      ['Passwords are never stored', 'Only a one-way bcrypt hash is kept. Nobody, including operators, can read your password.'],
      ['Sign-in session', 'Your session lives in a secure, httpOnly cookie that page scripts can’t read, and changes require a request header other sites can’t send.'],
      ['Identity before payouts', 'Withdrawals need a verified identity, and each payout goes only to the address you entered.'],
      ['Closing your account', 'Closing deactivates sign-in and deletes your photo and ID document. Financial records are kept for accounting.']])}
    ${block('Money', [
      ['A person reviews every deposit and payout', 'Nothing is credited or paid automatically. Each decision records who made it and when.'],
      ['Held, not lost', 'A requested withdrawal is held from your balance at once and returned in full if it’s rejected.'],
      ['No double spending', 'Balance changes lock the affected wallets, so two requests at the same moment can’t both spend the same dollars.'],
      ['Audit log', 'Credits, debits, approvals, role changes and support access are written in the same database transaction as the change.']])}
    ${block('Documents and support access', [
      ['Private storage', 'ID documents and payment screenshots are stored privately and open only through links that expire within minutes.'],
      ['View-only support', 'When support views your account to help, it’s read-only, time-limited and logged. They can’t move money or change settings.']])}
    ${block('Not yet available', [
      ['Two-factor sign-in', 'Not offered yet. Use a long, unique password.'],
      ['Password reset by email', 'Not offered yet. Contact support if you’re locked out.']])}`,
});

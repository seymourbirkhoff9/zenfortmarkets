import { contentPage, SITE } from './layout.js';
import { html } from '../../lib/dom.js';

contentPage({
  title: 'Contact',
  intro: 'We read every message.',
  body: html`<div class="grid gap-10 lg:grid-cols-[1fr_1fr]">
    <section class="panel p-6" data-reveal>
      <h2 class="font-serif text-2xl">Email support</h2>
      <p class="mt-2 text-muted">For account questions, deposits, withdrawals or identity checks.</p>
      <a class="btn-primary mt-5" href="mailto:${SITE.contactEmail}">${SITE.contactEmail}</a>
      <ul class="mt-6 grid gap-2 text-sm text-muted">
        <li>Write from the email address registered to your account.</li>
        <li>For a deposit or withdrawal, include the amount and the transaction hash.</li>
        <li>Never send your password. We will never ask for it.</li>
      </ul>
    </section>
    <section data-reveal data-reveal-delay="2">
      <h2 class="font-serif text-2xl">Before you write</h2>
      <p class="mt-2 text-muted">Many questions are answered in the <a class="btn-link" href="/faq.html">FAQ</a>.
        If you’re signed in, the status and reason for every request are shown under Deposits &amp; withdrawals.</p>
    </section></div>`,
});

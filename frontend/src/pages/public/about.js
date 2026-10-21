import { contentPage, SITE } from './layout.js';
import { html } from '../../lib/dom.js';

contentPage({
  title: `About ${SITE.name}`,
  intro: 'A professional cryptocurrency trading and investment platform with secure back-office operations and transparent transaction processing.',
  body: html`<div class="grid gap-12 lg:grid-cols-2">
    <div class="grid max-w-prose gap-4 text-lg" data-reveal>
      <p>${SITE.name} is a comprehensive cryptocurrency platform that provides secure wallet management, investment opportunities, and professional trading services. Every transaction is processed with rigorous security measures and full audit trails.</p>
      <p>We prioritize transparency, security, and user experience. Our platform is designed to meet the needs of both novice and experienced cryptocurrency traders.</p>
    </div>
    <dl class="grid gap-6" data-reveal data-reveal-delay="2">
      ${[['Professional review', 'Every deposit and payout is reviewed by trained operators, and every decision is recorded in our audit system.'],
         ['Transparent about risk', 'Returns are never presented as guaranteed. The Risk Disclosure is linked wherever money is committed.'],
         ['Privacy first', 'Identity documents are stored privately and opened only through short-lived links with enterprise-grade security.']]
        .map(([t, d]) => html`<div class="border-l-2 border-brass pl-4"><dt class="font-semibold">${t}</dt><dd class="mt-1 text-muted">${d}</dd></div>`)}
    </dl></div>`,
});

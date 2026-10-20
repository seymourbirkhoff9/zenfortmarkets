import { api } from '../../lib/api.js';
import { html, on, render } from '../../lib/dom.js';
import { date, money } from '../../lib/format.js';
import { icon } from '../../lib/icons.js';
import { copy, emptyState, errorState, skeletonRows } from '../../lib/ui.js';
import { pageHeader } from '../common.js';

export default async function referrals(outlet) {
  const head = pageHeader('Referrals', 'Share your code. When someone you referred makes their first approved deposit or investment, you receive a one-time bonus in your Main wallet.');
  render(outlet, html`${head}<div class="panel">${skeletonRows(4)}</div>`);
  try {
    const r = await api.referrals.stats();
    render(outlet, html`${head}
      <section class="panel grid gap-px overflow-hidden bg-line md:grid-cols-[1.5fr_1fr_1fr]">
        <div class="bg-surface p-6">
          <p class="text-sm text-muted">Your code</p>
          <p class="figure mt-1 text-4xl tracking-wider">${r.referral_code}</p>
          <div class="mt-4 flex flex-wrap gap-2">
            <button class="btn-primary btn-sm" data-copy="${r.referral_code}" data-label="Code copied">${icon('copy', 'h-4 w-4')}Copy code</button>
            <button class="btn-quiet btn-sm" data-copy="${r.referral_link}" data-label="Link copied">${icon('copy', 'h-4 w-4')}Copy sign-up link</button>
          </div>
        </div>
        <div class="bg-surface p-6"><p class="text-sm text-muted">People referred</p><p class="figure mt-1 text-3xl">${r.total_referrals}</p></div>
        <div class="bg-surface p-6"><p class="text-sm text-muted">Bonuses earned</p><p class="figure mt-1 text-3xl">${money(r.total_earned)}</p></div>
      </section>
      <section class="panel mt-6">
        <div class="panel-head"><h2 class="panel-title">People you referred</h2></div>
        ${r.referred_users.length ? html`<table class="table"><thead><tr><th>Name</th><th>Email</th><th>Joined</th></tr></thead>
          <tbody>${r.referred_users.map((u) => html`<tr><td>${u.full_name}</td><td class="text-muted">${u.email}</td><td class="text-muted">${date(u.created_at)}</td></tr>`)}</tbody></table>`
          : emptyState('No one yet', 'People who sign up with your code will be listed here.')}
      </section>`);
    on(outlet, 'click', '[data-copy]', (_, el) => copy(el.dataset.copy, el.dataset.label));
  } catch (err) {
    render(outlet, html`${head}<div class="panel">${errorState(err)}</div>`);
    on(outlet, 'click', '[data-action="retry"]', () => window.dispatchEvent(new HashChangeEvent('hashchange')));
  }
}

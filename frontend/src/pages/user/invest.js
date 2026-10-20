import { api } from '../../lib/api.js';
import { $, html, on, render } from '../../lib/dom.js';
import { date, money, pct } from '../../lib/format.js';
import { emptyState, errorState, openDialog, skeletonRows, toast, toastError } from '../../lib/ui.js';
import { session } from '../../session.js';
import { pageHeader, pill } from '../common.js';
import { viewOnly } from './actions.js';

const totalReturn = (amount, plan) => amount * (Number(plan.daily_roi_percent) / 100) * plan.duration_days;

/** A round example amount inside the plan's range, for the worked example on each card. */
function exampleAmount(plan) {
  const min = Number(plan.min_amount), max = Number(plan.max_amount);
  const nice = [100, 250, 500, 1000, 2500, 5000, 10000].find((n) => n >= min && n <= max);
  return nice ?? min;
}

const planCard = (p) => {
  const ex = exampleAmount(p);
  const termPct = Number(p.daily_roi_percent) * p.duration_days;
  return html`
  <li class="panel flex flex-col p-6">
    <h3 class="font-serif text-2xl">${p.name}</h3>
    ${p.description ? html`<p class="mt-1 text-sm text-muted">${p.description}</p>` : ''}
    <p class="mt-5 flex items-baseline gap-2"><span class="figure text-5xl">${pct(p.daily_roi_percent)}</span>
      <span class="text-sm text-muted">per day</span></p>
    <span class="mt-3 block h-0.5 w-12 bg-brass" aria-hidden="true"></span>
    <dl class="mt-4 grid grid-cols-3 gap-3 text-sm">
      <div><dt class="text-xs text-muted">Term</dt><dd class="figure text-base">${p.duration_days} days</dd></div>
      <div><dt class="text-xs text-muted">From</dt><dd class="figure text-base">${money(p.min_amount)}</dd></div>
      <div><dt class="text-xs text-muted">Up to</dt><dd class="figure text-base">${money(p.max_amount)}</dd></div>
    </dl>
    <p class="mt-5 rounded border border-line bg-sunken p-3 text-sm">
      <span class="block text-xs font-semibold text-muted">Example</span>
      ${money(ex)} earns <strong class="figure">${money(totalReturn(ex, p))}</strong> over ${p.duration_days} days
      (${termPct.toLocaleString('en-US', { maximumFractionDigits: 2 })}% in total), then the ${money(ex)} comes back to Main.</p>
    <div class="mt-auto pt-6"><button class="btn-primary w-full py-2.5" data-invest="${p.id}" ${session.user.is_blocked ? 'disabled' : ''}>Invest in ${p.name}</button></div>
  </li>`;
};

export default async function invest(outlet) {
  let state;
  async function load() {
    render(outlet, html`${pageHeader('Invest')}<div class="panel">${skeletonRows(5)}</div>`);
    try {
      const [plans, mine, wallets] = await Promise.all([api.investments.plans(), api.investments.mine(), api.wallets.list()]);
      state = { plans, mine, main: Number(wallets.find((w) => w.wallet_type === 'main')?.balance || 0) };
      draw();
    } catch (err) { render(outlet, html`${pageHeader('Invest')}<div class="panel">${errorState(err)}</div>`); }
  }

  function draw() {
    const { plans, mine, main } = state;
    render(outlet, html`
      ${pageHeader('Invest', 'Plans are set by the operator. Returns are paid daily into your Profit wallet and your principal comes back to Main at the end of the term. In this demo, returns are simulated.')}
      <section aria-labelledby="plans-h">
        <div class="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="plans-h" class="panel-title">Available plans</h2>
          <p class="text-sm text-muted">Main wallet <span class="figure ml-1 text-ink">${money(main)}</span></p>
        </div>
        ${plans.length ? html`<ul class="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">${plans.map(planCard)}</ul>`
          : html`<div class="panel">${emptyState('No plans are open', 'The operator hasn’t published any plans yet.')}</div>`}
      </section>

      <section class="panel mt-6" aria-labelledby="mine-h">
        <div class="panel-head"><h2 id="mine-h" class="panel-title">Your investments</h2></div>
        ${mine.length ? html`<div class="overflow-x-auto"><table class="table">
          <thead><tr><th>Plan</th><th>Started</th><th>Progress</th><th>Status</th><th class="text-right">Invested</th><th class="text-right">Earned</th></tr></thead>
          <tbody>${mine.map((i) => html`<tr>
            <td class="font-medium">${i.plan_name || 'Plan'}<span class="block text-xs text-muted">${pct(i.daily_roi_percent)} per day</span></td>
            <td class="whitespace-nowrap text-muted">${date(i.start_date)}<span class="block text-xs">Ends ${date(i.maturity_date)}</span></td>
            <td class="min-w-[9rem]">
              <div class="h-1.5 w-full overflow-hidden rounded-full bg-sunken" role="progressbar" aria-valuemin="0" aria-valuemax="${i.duration_days}" aria-valuenow="${i.days_paid}" aria-label="Days paid">
                <div class="h-full bg-brass" style="width:${Math.min(100, (i.days_paid / i.duration_days) * 100)}%"></div></div>
              <span class="mt-1 block text-xs text-muted">${i.days_paid} of ${i.duration_days} days paid</span></td>
            <td>${pill(i.status)}</td>
            <td class="text-right figure">${money(i.amount_invested)}</td>
            <td class="text-right figure text-settled">${money(i.total_earned)}</td>
          </tr>`)}</tbody></table></div>`
          : emptyState('No investments yet', 'Choose a plan above. The amount comes from your Main wallet.')}
      </section>`);
  }

  on(outlet, 'click', '[data-invest]', async (_, el) => {
    const plan = state.plans.find((p) => p.id === el.dataset.invest);
    if (viewOnly()) return openDialog({ title: 'View only', body: html`<p class="text-muted">You’re viewing this account as an admin. Exit to the console to make changes.</p>` });
    try {
      const done = await openDialog({
        title: `Invest in ${plan.name}`,
        submitLabel: 'Confirm investment', wide: false,
        body: html`
          <p class="text-sm text-muted">${pct(plan.daily_roi_percent)} per day for ${plan.duration_days} days. Available in Main: <strong class="figure text-ink">${money(state.main)}</strong></p>
          <div class="field"><label class="label" for="inv-amount">Amount, in US dollars</label>
            <input class="input figure" id="inv-amount" name="amount" type="number" inputmode="decimal" step="0.01"
              min="${plan.min_amount}" max="${Math.min(Number(plan.max_amount), state.main)}" required />
            <p class="hint">Between ${money(plan.min_amount)} and ${money(plan.max_amount)}.</p></div>
          <dl id="inv-preview" class="grid grid-cols-2 gap-3 rounded border border-line bg-sunken p-4 text-sm">
            <div><dt class="text-muted">Paid to Profit over the term</dt><dd class="figure text-lg">—</dd></div>
            <div><dt class="text-muted">Principal back to Main on</dt><dd class="figure text-lg">${date(Date.now() + plan.duration_days * 864e5)}</dd></div>
          </dl>
          <p class="hint">The amount is locked for the full term and can’t be withdrawn early.</p>
          <label class="flex items-start gap-2 text-sm"><input type="checkbox" name="accept_risk" required class="mt-1 h-4 w-4 accent-settled" />
            <span>I’ve read the <a class="btn-link" href="/risk.html" target="_blank" rel="noopener">Risk Disclosure</a>.
              I understand returns aren’t guaranteed and I could lose money.</span></label>`,
        onMount: (dlg) => $('#inv-amount', dlg).addEventListener('input', (e) => {
          const v = Number(e.target.value || 0);
          $('#inv-preview dd', dlg).textContent = v ? money(totalReturn(v, plan)) : '—';
        }),
        onSubmit: async (v) => {
          await api.investments.create(plan.id, v.amount);
          toast(`You invested ${money(v.amount)} in ${plan.name}.`);
          return true;
        },
      });
      if (done) load();
    } catch (err) { toastError(err); }
  });
  on(outlet, 'click', '[data-action="retry"]', load);
  await load();
}

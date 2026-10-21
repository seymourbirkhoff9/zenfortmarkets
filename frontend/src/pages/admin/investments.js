import { api } from '../../lib/api.js';
import { $$, html, on, render } from '../../lib/dom.js';
import { date, money, pct } from '../../lib/format.js';
import { emptyState, errorState, skeletonRows } from '../../lib/ui.js';
import { pageHeader, pill } from '../common.js';

const DAY = 864e5;
const reduceMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Everything shown is derived from ledger fields (days_paid, total_earned); nothing is invented client-side. */
function derive(i, now = Date.now()) {
  const amount = Number(i.amount_invested);
  const daily = amount * Number(i.daily_roi_percent) / 100;
  const start = new Date(i.start_date).getTime();
  const elapsedDays = Math.min((now - start) / DAY, i.duration_days);          // fractional
  const accruing = i.status === 'active' ? Math.max(0, Math.min(elapsedDays - i.days_paid, 1)) : 0;
  const nextDue = start + (i.days_paid + 1) * DAY;
  return {
    amount, daily, projected: daily * i.duration_days, earned: Number(i.total_earned),
    remaining: daily * (i.duration_days - i.days_paid),
    paidPct: (i.days_paid / i.duration_days) * 100,
    accruingPct: (accruing / i.duration_days) * 100,
    nextDue, maturity: new Date(i.maturity_date).getTime(),
  };
}

function nextLabel(i, d, now = Date.now()) {
  if (i.status !== 'active') return `Completed. Principal returned ${date(i.maturity_date)}.`;
  if (i.days_paid >= i.duration_days) return 'Final return paid. Principal returns at the next run.';
  const ms = d.nextDue - now;
  if (ms <= 0) return 'Next return is due now. It’s paid at the next hourly run.';
  const h = Math.floor(ms / 36e5), m = Math.floor((ms % 36e5) / 6e4);
  return `Next return of ${money(d.daily)} in ${h ? `${h} h ` : ''}${m} min`;
}

/** Count a number up from 0 when it first appears. */
function countUp(root) {
  $$('[data-count]', root).forEach((el) => {
    const target = Number(el.dataset.count);
    if (reduceMotion() || !target) { el.textContent = money(target); return; }
    const t0 = performance.now(), dur = 1100;
    const step = (t) => {
      const k = Math.min(1, (t - t0) / dur);
      el.textContent = money(target * (1 - (1 - k) ** 3));          // ease-out cubic
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
}

/** Grow progress bars from zero to their real width. */
function growBars(root) {
  const bars = $$('[data-w]', root);
  requestAnimationFrame(() => requestAnimationFrame(() => bars.forEach((b) => { b.style.width = `${b.dataset.w}%`; })));
}

const card = (i) => {
  const d = derive(i);
  return html`
  <article class="panel flex flex-col gap-4 p-5" data-inv="${i.id}">
    <header class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h3 class="truncate font-serif text-xl">${i.plan_name}</h3>
        <a class="block truncate text-sm text-muted hover:text-ink hover:underline" href="#/customers/${i.user_id}">${i.user_name || i.user_email}</a>
      </div>
      ${pill(i.status)}
    </header>

    <dl class="grid grid-cols-2 gap-3 text-sm">
      <div><dt class="text-xs text-muted">Invested</dt><dd class="figure text-lg">${money(d.amount)}</dd></div>
      <div><dt class="text-xs text-muted">Rate</dt><dd class="figure text-lg">${pct(i.daily_roi_percent)}<span class="font-sans text-xs text-muted"> per day</span></dd></div>
    </dl>

    <div>
      <div class="relative h-2.5 overflow-hidden rounded-full bg-sunken" role="progressbar" aria-label="Days paid"
           aria-valuemin="0" aria-valuemax="${i.duration_days}" aria-valuenow="${i.days_paid}">
        <div class="zf-bar absolute inset-y-0 left-0 rounded-full bg-brass" style="width:0" data-w="${d.paidPct.toFixed(2)}"></div>
        ${i.status === 'active' ? html`<div class="zf-bar zf-accruing absolute inset-y-0 rounded-full bg-brass/40" data-accrue
          style="left:${d.paidPct.toFixed(2)}%;width:0" data-w="${d.accruingPct.toFixed(3)}"></div>` : ''}
      </div>
      <p class="mt-1.5 flex justify-between text-xs text-muted">
        <span>Day ${i.days_paid} of ${i.duration_days} paid</span><span class="num">${Math.round(d.paidPct)}%</span></p>
    </div>

    <div class="flex items-end justify-between gap-3 border-t border-line pt-3">
      <div><p class="text-xs text-muted">Paid to customer so far</p>
        <p class="figure text-2xl text-settled" data-count="${d.earned}">${money(0)}</p></div>
      <p class="text-right text-xs text-muted">of ${money(d.projected)}<br/>over the term</p>
    </div>

    <footer class="grid gap-1 text-xs text-muted">
      <p data-next>${nextLabel(i, d)}</p>
      <p>Principal ${money(d.amount)} back on ${date(i.maturity_date)}</p>
    </footer>
  </article>`;
};

export default async function investments(outlet) {
  let filter = 'active', list = [];
  const head = pageHeader('Investments',
    'Every customer investment and where it stands. Bars show days already paid; the lighter part is today’s return building up until the next hourly payout run.');

  async function load() {
    render(outlet, html`${head}<div class="panel">${skeletonRows(6)}</div>`);
    try {
      list = await api.admin.investments({ status: filter === 'all' ? undefined : filter, limit: 200 });
      list.sort((a, b) => (a.status === b.status ? new Date(a.maturity_date) - new Date(b.maturity_date) : a.status === 'active' ? -1 : 1));
      draw();
    } catch (err) { render(outlet, html`${head}<div class="panel">${errorState(err)}</div>`); }
  }

  function draw() {
    const active = list.filter((i) => i.status === 'active').map((i) => [i, derive(i)]);
    const sum = (f) => active.reduce((s, [i, d]) => s + f(i, d), 0);
    const week = Date.now() + 7 * DAY;
    const maturing = active.filter(([, d]) => d.maturity <= week);
    render(outlet, html`${head}
      <section class="panel mb-6 grid gap-px overflow-hidden bg-line sm:grid-cols-2 lg:grid-cols-4" aria-label="Totals for active investments">
        ${[
          ['Active capital', sum((i, d) => d.amount), `${active.length} active investment${active.length === 1 ? '' : 's'}`],
          ['Returns paid so far', sum((i, d) => d.earned), 'Across active investments'],
          ['Returns still to pay', sum((i, d) => d.remaining), 'If every plan runs to term'],
          ['Principal due in 7 days', maturing.reduce((s, [, d]) => s + d.amount, 0), `${maturing.length} maturing`],
        ].map(([label, value, note]) => html`<div class="bg-surface p-5">
          <p class="text-sm text-muted">${label}</p><p class="figure mt-1 text-2xl" data-count="${value}">${money(0)}</p>
          <p class="mt-1 text-xs text-muted">${note}</p></div>`)}
      </section>
      <div class="mb-4 flex justify-end">
        <div class="segmented" role="group" aria-label="Show">
          ${[['active', 'Active'], ['completed', 'Completed'], ['all', 'All']].map(([v, l]) => html`<button data-filter="${v}" aria-pressed="${filter === v}">${l}</button>`)}
        </div>
      </div>
      ${list.length ? html`<div class="grid gap-5 md:grid-cols-2 xl:grid-cols-3">${list.map(card)}</div>`
        : html`<div class="panel">${emptyState(filter === 'active' ? 'No active investments' : 'Nothing here yet', 'Customer investments appear here as soon as they’re made.')}</div>`}`);
    countUp(outlet);
    growBars(outlet);
  }

  // Live: today's accruing segment and the countdown move without reloading.
  const timer = setInterval(() => {
    const now = Date.now();
    list.forEach((i) => {
      const el = outlet.querySelector(`[data-inv="${i.id}"]`);
      if (!el || i.status !== 'active') return;
      const d = derive(i, now);
      const acc = el.querySelector('[data-accrue]');
      if (acc) acc.style.width = `${d.accruingPct.toFixed(3)}%`;
      el.querySelector('[data-next]').textContent = nextLabel(i, d, now);
    });
  }, 30_000);

  on(outlet, 'click', '[data-filter]', (_, el) => { filter = el.dataset.filter; load(); });
  on(outlet, 'click', '[data-action="retry"]', load);
  await load();
  return () => clearInterval(timer);
}

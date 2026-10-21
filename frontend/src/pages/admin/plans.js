import { api } from '../../lib/api.js';
import { $, html, on, render } from '../../lib/dom.js';
import { date, money, pct } from '../../lib/format.js';
import { confirmDialog, emptyState, errorState, openDialog, skeletonRows, toast, toastError } from '../../lib/ui.js';
import { pageHeader, pill } from '../common.js';

/** What a plan pays on a given amount, so the operator sees the obligation they're creating. */
const payout = (amount, rate, days) => amount * (rate / 100) * days;

function planForm(p = {}) {
  return html`
    <div class="field"><label class="label" for="pl-name">Name</label>
      <input class="input" id="pl-name" name="name" required maxlength="100" value="${p.name || ''}" /></div>
    <div class="field"><label class="label" for="pl-desc">Description customers see <span class="font-normal text-muted">(optional)</span></label>
      <textarea class="input" id="pl-desc" name="description" rows="2" maxlength="500">${p.description || ''}</textarea></div>
    <div class="grid gap-4 sm:grid-cols-2">
      <div class="field"><label class="label" for="pl-min">Minimum, USD</label>
        <input class="input figure" id="pl-min" name="min_amount" type="number" min="0.01" step="0.01" required value="${p.min_amount ? Number(p.min_amount) : ''}" /></div>
      <div class="field"><label class="label" for="pl-max">Maximum, USD</label>
        <input class="input figure" id="pl-max" name="max_amount" type="number" min="0.01" step="0.01" required value="${p.max_amount ? Number(p.max_amount) : ''}" /></div>
      <div class="field"><label class="label" for="pl-rate">Daily rate, %</label>
        <input class="input figure" id="pl-rate" name="daily_roi_percent" type="number" min="0.0001" max="100" step="0.0001" required value="${p.daily_roi_percent ? Number(p.daily_roi_percent) : ''}" /></div>
      <div class="field"><label class="label" for="pl-days">Term, days</label>
        <input class="input figure" id="pl-days" name="duration_days" type="number" min="1" max="3650" step="1" required value="${p.duration_days || ''}" /></div>
    </div>
    <p id="pl-preview" class="rounded border border-line bg-sunken p-3 text-sm text-muted">Fill in the rate and term to see what the plan pays.</p>
    ${p.id ? html`<p class="hint">Changes apply to new investments only. Existing investments keep the rate and term they started with.</p>` : ''}`;
}

function wirePreview(dlg) {
  const update = () => {
    const rate = Number($('#pl-rate', dlg).value), days = Number($('#pl-days', dlg).value);
    const max = Number($('#pl-max', dlg).value) || 1000;
    if (!rate || !days) return;
    const total = rate * days;
    $('#pl-preview', dlg).textContent =
      `Pays ${total.toLocaleString('en-US', { maximumFractionDigits: 2 })}% of the principal over the term. ` +
      `A ${money(max)} investment earns ${money(payout(max, rate, days))}, and you return the ${money(max)} principal at the end.`;
  };
  dlg.addEventListener('input', update);
  update();
}

export default async function plans(outlet) {
  let list = [], lastRun = null;
  const head = pageHeader('Investment plans',
    'Plans you publish here appear on the customer Invest page. Returns accrue daily into Profit wallets; the principal returns to Main at the end of the term.',
    html`<button class="btn-quiet" data-action="run">Run accrual now</button><button class="btn-primary" data-action="new">New plan</button>`);

  async function load() {
    render(outlet, html`${head}<div class="panel">${skeletonRows(5)}</div>`);
    try {
      const [plansRes, invs] = await Promise.all([
        api.admin.plans(),
        api.admin.investments({ status: 'active', limit: 200 }).catch(() => []),
      ]);

      list = plansRes;
      const byPlan = {};
      invs.forEach((i) => { const b = (byPlan[i.plan_name] ||= { n: 0, capital: 0 }); b.n += 1; b.capital += Number(i.amount_invested); });
      render(outlet, html`${head}
        ${lastRun ? html`<p class="mb-4 rounded border border-line bg-surface px-4 py-3 text-sm" role="status">
          Accrual checked ${lastRun.investments_checked} investments: ${lastRun.days_paid} day(s) paid, totalling ${money(lastRun.amount_paid)}. ${lastRun.matured} matured.
          It also runs automatically every hour, and never pays the same day twice.</p>` : ''}
        <section class="panel">
          ${list.length ? html`<div class="overflow-x-auto"><table class="table">
            <thead><tr><th>Plan</th><th>Rate</th><th>Term</th><th>Amount range</th><th>Active investments</th><th>Visible</th><th><span class="sr-only">Actions</span></th></tr></thead>
            <tbody>${list.map((p) => {
        const b = byPlan[p.name] || { n: 0, capital: 0 }; return html`<tr>
              <td><span class="font-medium">${p.name}</span><span class="block text-xs text-muted">Created ${date(p.created_at)}</span></td>
              <td class="figure">${pct(p.daily_roi_percent)}<span class="block font-sans text-xs text-muted">per day</span></td>
              <td class="num">${p.duration_days} days</td>
              <td class="figure whitespace-nowrap">${money(p.min_amount)} – ${money(p.max_amount)}</td>
              <td class="num">${b.n}${b.n ? html`<span class="block text-xs text-muted">${money(b.capital)}</span>` : ''}</td>
              <td><label class="inline-flex items-center gap-2 text-sm"><input type="checkbox" class="h-4 w-4 accent-settled" data-toggle="${p.id}" ${p.is_active ? 'checked' : ''} />
                ${p.is_active ? 'Open' : 'Paused'}</label></td>
              <td><div class="flex justify-end gap-2"><button class="btn-quiet btn-sm" data-edit="${p.id}">Edit</button>
                ${b.n ? '' : html`<button class="btn-quiet btn-sm text-rejected" data-delete="${p.id}">Delete</button>`}</div></td>
            </tr>`;
      })}</tbody></table></div>`
          : emptyState('No plans yet', 'Create a plan to let customers invest.', html`<button class="btn-primary" data-action="new">New plan</button>`)}
        </section>`);
    } catch (err) { render(outlet, html`${head}<div class="panel">${errorState(err)}</div>`); }
  }

  const find = (id) => list.find((p) => p.id === id);
  const clean = (v) => ({ ...v, description: v.description || null, duration_days: Number(v.duration_days) });

  on(outlet, 'click', '[data-action]', async (_, el) => {
    const a = el.dataset.action;
    if (a === 'retry') return load();
    if (a === 'new') {
      const done = await openDialog({
        title: 'New plan', submitLabel: 'Publish plan', body: planForm(), onMount: wirePreview,
        onSubmit: (v) => api.admin.createPlan(clean(v))
      });
      if (done) { toast(`${done.name} is live.`); load(); }
    }
    if (a === 'run') {
      el.disabled = true;
      try { lastRun = await api.admin.runRoi(); toast('Accrual finished.'); load(); }
      catch (err) { toastError(err); } finally { el.disabled = false; }
    }
  });
  on(outlet, 'click', '[data-edit]', async (_, el) => {
    const p = find(el.dataset.edit);
    const done = await openDialog({
      title: `Edit ${p.name}`, submitLabel: 'Save changes', body: planForm(p), onMount: wirePreview,
      onSubmit: (v) => api.admin.updatePlan(p.id, clean(v))
    });
    if (done) { toast('Plan saved.'); load(); }
  });
  on(outlet, 'change', '[data-toggle]', async (_, el) => {
    el.disabled = true;
    try { await api.admin.updatePlan(el.dataset.toggle, { is_active: el.checked }); toast(el.checked ? 'Plan reopened.' : 'Plan paused. Existing investments continue.'); load(); }
    catch (err) { el.checked = !el.checked; el.disabled = false; toastError(err); }
  });
  on(outlet, 'click', '[data-delete]', async (_, el) => {
    const p = find(el.dataset.delete);
    if (!(await confirmDialog({ title: `Delete ${p.name}?`, danger: true, confirmLabel: 'Delete plan', message: 'Nobody has invested in it, so it can be removed completely.' }))) return;
    try { await api.admin.deletePlan(p.id); toast('Plan deleted.'); load(); } catch (err) { toastError(err); }
  });
  await load();
}

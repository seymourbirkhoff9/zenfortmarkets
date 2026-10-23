import { api } from '../../lib/api.js';
import { $, html, on, render } from '../../lib/dom.js';
import { dateTime, money } from '../../lib/format.js';
import { icon } from '../../lib/icons.js';
import { confirmDialog, emptyState, errorState, setBusy, skeletonRows, toast, toastError } from '../../lib/ui.js';
import { pageHeader, pill } from '../common.js';

export default async function fx(outlet) {
  render(outlet, html`${pageHeader('FX Rates', 'Manage currency conversion rates for deposits and withdrawals.')}
    <div class="panel">${skeletonRows(5)}</div>`);

  async function load() {
    try {
      const rates = await api.admin.fxRates();
      draw(rates);
    } catch (err) {
      render(outlet, html`${pageHeader('FX Rates')}<div class="panel">${errorState(err)}</div>`);
    }
  }

  function draw(rates) {
    render(outlet, html`
      ${pageHeader('FX Rates', 'Manage currency conversion rates for deposits and withdrawals.',
        html`<button class="btn-primary" data-action="add">${icon('plus', 'h-4 w-4')}Add rate</button>
         <button class="btn-quiet" data-action="refresh">${icon('refresh', 'h-4 w-4')}Refresh from API</button>`)}
      <section class="panel" aria-labelledby="rates-h">
        <div class="panel-head"><h2 id="rates-h" class="panel-title">Active rates</h2></div>
        ${rates.length ? html`<div class="overflow-x-auto"><table class="table">
          <thead><tr><th>Currency</th><th>Rate per USD</th><th>Override</th><th>Source</th><th>Status</th><th>Updated</th><th class="text-right">Actions</th></tr></thead>
          <tbody>${rates.map((r) => html`<tr>
            <td class="font-mono font-semibold">${r.currency}</td>
            <td>${r.rate_per_usd ? money(r.rate_per_usd) : '—'}</td>
            <td>${r.override_rate ? html`<span class="text-muted">${money(r.override_rate)}</span>` : '—'}</td>
            <td class="text-sm text-muted">${r.source || '—'}</td>
            <td>${pill(r.is_enabled ? 'enabled' : 'disabled')}</td>
            <td class="text-sm text-muted">${r.updated_at ? dateTime(r.updated_at) : '—'}</td>
            <td class="text-right">
              <button class="btn-quiet btn-sm text-xs" data-action="edit" data-currency="${r.currency}">${icon('edit', 'h-4 w-4')} Edit</button>
              <button class="btn-quiet btn-sm text-xs" data-action="toggle" data-currency="${r.currency}">
                ${icon(r.is_enabled ? 'off' : 'on', 'h-4 w-4')} ${r.is_enabled ? 'Disable' : 'Enable'}</button>
              <button class="btn-quiet btn-sm text-xs text-rejected" data-action="delete" data-currency="${r.currency}">${icon('trash', 'h-4 w-4')} Remove</button>
            </td>
          </tr>`)}</tbody>
        </table></div>`
        : emptyState('No FX rates configured', 'Add a currency rate to enable deposits and withdrawals in that currency.',
          html`<button class="btn-primary" data-action="add">${icon('plus', 'h-4 w-4')}Add rate</button>`)}
      </section>`);
  }

  on(outlet, 'click', '[data-action]', async (_, el) => {
    const action = el.dataset.action;
    const currency = el.dataset.currency;
    try {
      if (action === 'add') {
        await addRateDialog();
        load();
      } else if (action === 'edit') {
        await editRateDialog(currency);
        load();
      } else if (action === 'toggle') {
        await toggleRate(currency);
        load();
      } else if (action === 'delete') {
        const ok = await confirmDialog({ 
          title: 'Delete FX rate?', 
          danger: true, 
          confirmLabel: 'Delete',
          message: `This will remove the ${currency} rate. Users won't be able to deposit/withdraw in ${currency}.` 
        });
        if (ok) {
          await api.admin.deleteFxRate(currency);
          toast('FX rate deleted.');
          load();
        }
      } else if (action === 'refresh') {
        await api.admin.refreshFxRates();
        toast('FX rates refreshed from external API.');
        load();
      }
    } catch (err) { toastError(err); }
  });

  await load();
}

async function addRateDialog() {
  const { openDialog } = await import('../../lib/ui.js');
  return openDialog({
    title: 'Add FX rate',
    submitLabel: 'Add rate',
    body: html`
      <div class="field"><label class="label" for="fx-currency">Currency code</label>
        <input class="input font-mono uppercase" id="fx-currency" name="currency" maxlength="10" placeholder="EUR" required /></div>
      <div class="field"><label class="label" for="fx-rate">Rate per USD</label>
        <input class="input figure" id="fx-rate" name="rate_per_usd" type="number" inputmode="decimal" step="0.0000000001" min="0" placeholder="0.92" required />
        <p class="hint">Units of this currency per 1 USD. Example: 1 USD = 0.92 EUR</p></div>
      <div class="field"><label class="label" for="fx-override">Override rate <span class="font-normal text-muted">(optional)</span></label>
        <input class="input figure" id="fx-override" name="override_rate" type="number" inputmode="decimal" step="0.0000000001" min="0" placeholder="0.93" />
        <p class="hint">If set, this overrides the automatic rate. Leave blank to use the automatic rate.</p></div>
      <div class="field"><label class="label" for="fx-source">Source <span class="font-normal text-muted">(optional)</span></label>
        <input class="input" id="fx-source" name="source" maxlength="50" placeholder="open.er-api.com" /></div>
      <div class="field"><label class="choice"><input type="checkbox" id="fx-enabled" name="is_enabled" checked />
        <span>Enable this rate</span></label></div>`,
    onSubmit: async (v) => {
      const payload = {
        currency: v.currency.toUpperCase(),
        rate_per_usd: Number(v.rate_per_usd),
        is_enabled: v.is_enabled === 'on',
      };
      if (v.override_rate) payload.override_rate = Number(v.override_rate);
      if (v.source) payload.source = v.source;
      await api.admin.createFxRate(payload);
      toast('FX rate added.');
    },
  });
}

async function editRateDialog(currency) {
  const { openDialog } = await import('../../lib/ui.js');
  const rate = await api.admin.fxRate(currency);
  return openDialog({
    title: `Edit ${currency} rate`,
    submitLabel: 'Save changes',
    body: html`
      <div class="field"><label class="label" for="fx-rate">Rate per USD</label>
        <input class="input figure" id="fx-rate" name="rate_per_usd" type="number" inputmode="decimal" step="0.0000000001" min="0" value="${rate.rate_per_usd || ''}" required />
        <p class="hint">Units of this currency per 1 USD. Example: 1 USD = 0.92 EUR</p></div>
      <div class="field"><label class="label" for="fx-override">Override rate <span class="font-normal text-muted">(optional)</span></label>
        <input class="input figure" id="fx-override" name="override_rate" type="number" inputmode="decimal" step="0.0000000001" min="0" value="${rate.override_rate || ''}" />
        <p class="hint">If set, this overrides the automatic rate. Leave blank to use the automatic rate.</p></div>
      <div class="field"><label class="label" for="fx-source">Source</label>
        <input class="input" id="fx-source" name="source" maxlength="50" value="${rate.source || ''}" /></div>
      <div class="field"><label class="choice"><input type="checkbox" id="fx-enabled" name="is_enabled" ${rate.is_enabled ? 'checked' : ''} />
        <span>Enable this rate</span></label></div>`,
    onSubmit: async (v) => {
      const payload = { rate_per_usd: Number(v.rate_per_usd), is_enabled: v.is_enabled === 'on' };
      if (v.override_rate) payload.override_rate = Number(v.override_rate);
      if (v.source) payload.source = v.source;
      await api.admin.updateFxRate(currency, payload);
      toast('FX rate updated.');
    },
  });
}

async function toggleRate(currency) {
  const rate = await api.admin.fxRate(currency);
  await api.admin.updateFxRate(currency, { is_enabled: !rate.is_enabled });
  toast(`${currency} rate ${rate.is_enabled ? 'disabled' : 'enabled'}.`);
}

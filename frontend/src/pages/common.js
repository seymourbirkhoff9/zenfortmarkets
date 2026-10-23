import { html } from '../lib/dom.js';
import { date, money, statusPill, txLabel } from '../lib/format.js';

export const pageHeader = (title, intro = '', actions = '') => html`
  <div class="mb-6 flex flex-wrap items-end justify-between gap-4">
    <div>
      <h1 class="font-serif text-3xl">${title}</h1>
      ${intro ? html`<p class="mt-1 max-w-prose text-muted">${intro}</p>` : ''}
    </div>
    ${actions ? html`<div class="flex flex-wrap gap-2">${actions}</div>` : ''}
  </div>`;

export const pill = (status) => { const { cls, text } = statusPill(status); return html`<span class="${cls}">${text}</span>`; };

/** Signed amount for a user's own ledger: + for money in, − for money out. */
export function signedAmount(tx, displayCurrency = null, fxRates = []) {
  const sign = tx.direction === 'in' ? '+' : tx.direction === 'out' ? '−' : '';
  const tone = tx.status === 'rejected' ? 'text-muted line-through' : tx.direction === 'in' ? 'text-settled' : '';
  if (tx.input_currency && tx.input_amount) {
    return html`<span class="figure ${tone}">${sign}${money(tx.input_amount, tx.input_currency)} <span class="text-xs text-muted">(≈${money(tx.amount)} USD)</span></span>`;
  }
  // If no input currency but display currency is set and not USD, show conversion
  if (displayCurrency && displayCurrency !== 'USD' && fxRates.length > 0) {
    const rateObj = fxRates.find((r) => r.currency === displayCurrency);
    const rate = rateObj?.effective_rate;
    if (rate) {
      const convertedAmount = Number(tx.amount) * rate;
      return html`<span class="figure ${tone}">${sign}${money(convertedAmount, displayCurrency)} <span class="text-xs text-muted">(≈${money(tx.amount)} USD)</span></span>`;
    }
  }
  return html`<span class="figure ${tone}">${sign}${money(tx.amount)}</span>`;
}

export const txRow = (t, displayCurrency = null, fxRates = []) => html`
  <tr>
    <td class="whitespace-nowrap text-muted">${date(t.created_at)}</td>
    <td><span class="font-medium">${txLabel(t.tx_type)}</span>
      <span class="block text-xs text-muted">${t.description || ''}</span>
      ${t.rejection_reason ? html`<span class="mt-1 block text-xs text-rejected">Reason: ${t.rejection_reason}</span>` : ''}</td>
    <td>${pill(t.status)}</td>
    <td class="text-right">${signedAmount(t, displayCurrency, fxRates)}</td>
  </tr>`;

export const txTable = (rows, displayCurrency = null, fxRates = []) => html`
  <div class="overflow-x-auto"><table class="table">
    <thead><tr><th>Date</th><th>What</th><th>Status</th><th class="text-right">Amount</th></tr></thead>
    <tbody>${rows.map((t) => txRow(t, displayCurrency, fxRates))}</tbody>
  </table></div>`;

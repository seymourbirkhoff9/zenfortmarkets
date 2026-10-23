import { api } from '../../lib/api.js';
import { html, on, render } from '../../lib/dom.js';
import { ago, money } from '../../lib/format.js';
import { icon } from '../../lib/icons.js';
import { emptyState, errorState, skeletonRows, toast, toastError } from '../../lib/ui.js';
import { session } from '../../session.js';
import { invalidate, swr } from '../../lib/cache.js';
import { pageHeader, pill, txTable } from '../common.js';
import { depositDialog, moveDialog, sendDialog, withdrawDialog } from './actions.js';

export default async function overview(outlet) {
  let data;
  let fxRates = [];
  render(outlet, html`${pageHeader('Overview')}<div class="panel">${skeletonRows(6)}</div>`);

  // One request for the whole screen; instant from cache when revisiting.
  async function load() {
    try {
      await swr('dashboard', api.me.dashboard, async (d) => {
        session.user = d.user;
        data = { user: d.user, bal: Object.fromEntries(d.wallets.map((w) => [w.wallet_type, Number(w.balance)])),
          txs: d.recent, pending: d.pending, inv: d.active_investments };
        // Fetch FX rates for balance conversion
        try {
          const response = await api.fx.rates();
          fxRates = response?.rates || [];
        } catch { fxRates = []; }
        draw();
      });
    } catch (err) {
      if (!data) render(outlet, html`${pageHeader('Overview')}<div class="panel">${errorState(err)}</div>`);
    }
  }

  function convertToDisplayCurrency(usdAmount, displayCurrency) {
    if (displayCurrency === 'USD' || !displayCurrency) return usdAmount;
    const rateObj = fxRates.find((r) => r.currency === displayCurrency);
    const rate = rateObj?.effective_rate;
    if (rate) {
      return usdAmount * rate;
    }
    return usdAmount; // Fallback to USD if rate not found
  }

  function draw() {
    const { user, bal, txs, pending, inv } = data;
    const invested = Number(inv.capital);
    const first = user.full_name.split(' ')[0];
    const currency = user.display_currency || 'USD';

    // Convert USD balances to display currency
    const mainInCurrency = convertToDisplayCurrency(bal.main, currency);
    const profitInCurrency = convertToDisplayCurrency(bal.profit, currency);
    const investedInCurrency = convertToDisplayCurrency(invested, currency);

    render(outlet, html`
      ${pageHeader(`Hello, ${first}`)}
      ${notices(user)}

      <section class="panel overflow-hidden" aria-labelledby="balances-h">
        <h2 id="balances-h" class="sr-only">Balances</h2>
        <div class="grid gap-px bg-line md:grid-cols-[1.4fr_1fr_1fr]">
          <div class="bg-surface p-6">
            <p class="text-sm text-muted">Main wallet</p>
            <p class="figure mt-1 text-3xl md:text-5xl break-words">${money(mainInCurrency, currency)}</p>
            ${currency !== 'USD' ? html`<p class="mt-1 text-xs text-muted">≈ ${money(bal.main)} USD</p>` : ''}
            <span class="mt-3 block h-0.5 w-14 bg-brass" aria-hidden="true"></span>
            <p class="mt-3 text-sm text-muted">Spendable. Deposits arrive here; withdrawals and investments come from here.</p>
          </div>
          <div class="bg-surface p-6">
            <p class="text-sm text-muted">Profit wallet</p>
            <p class="figure mt-1 text-2xl md:text-3xl break-words">${money(profitInCurrency, currency)}</p>
            ${currency !== 'USD' ? html`<p class="mt-1 text-xs text-muted">≈ ${money(bal.profit)} USD</p>` : ''}
            <p class="mt-2 text-sm text-muted">Investment returns and credits.</p>
          </div>
          <div class="bg-surface p-6">
            <p class="text-sm text-muted">Invested</p>
            <p class="figure mt-1 text-2xl md:text-3xl break-words">${money(investedInCurrency, currency)}</p>
            ${currency !== 'USD' && invested > 0 ? html`<p class="mt-1 text-xs text-muted">≈ ${money(invested)} USD</p>` : ''}
            <p class="mt-2 text-sm text-muted">${inv.count ? `${inv.count} active plan${inv.count > 1 ? 's' : ''}` : 'No active plans'}</p>
          </div>
        </div>
        <div class="flex flex-wrap gap-2 border-t border-line bg-surface px-6 py-4">
          <button class="btn-primary" data-action="deposit">${icon('down', 'h-4 w-4')}Deposit</button>
          <button class="btn-quiet" data-action="withdraw">${icon('up', 'h-4 w-4')}Withdraw</button>
          <button class="btn-quiet" data-action="move">${icon('swap', 'h-4 w-4')}Move between wallets</button>
          <button class="btn-quiet" data-action="send">${icon('send', 'h-4 w-4')}Send to a customer</button>
        </div>
      </section>

      <div class="mt-6 grid gap-6 lg:grid-cols-[1fr_1.4fr]">
        <section class="panel" aria-labelledby="pending-h">
          <div class="panel-head"><h2 id="pending-h" class="panel-title">Waiting for review</h2></div>
          ${pending.length ? html`<ul class="divide-y divide-line">${pending.map((t) => html`
            <li class="flex items-start justify-between gap-4 px-5 py-3.5">
              <div><p class="font-medium">${t.tx_type === 'deposit' ? 'Deposit' : 'Withdrawal'} via ${t.gateway_name}</p>
                <p class="text-xs text-muted">Submitted ${ago(t.created_at)}${t.tx_type === 'withdrawal' ? '. Funds are on hold.' : ''}</p></div>
              <div class="text-right">
                ${t.input_currency && t.input_amount ? html`
                  <p class="figure">${money(t.input_amount, t.input_currency)}</p>
                  <p class="text-xs text-muted">≈ ${money(t.amount)} USD</p>
                ` : html`<p class="figure">${money(t.amount, currency)}</p>`}
                ${pill('pending')}
              </div>
            </li>`)}</ul>`
            : emptyState('Nothing pending', 'Deposits and withdrawals you submit appear here until an operator reviews them.')}
        </section>
        <section class="panel" aria-labelledby="recent-h">
          <div class="panel-head"><h2 id="recent-h" class="panel-title">Recent activity</h2></div>
            <a class="btn-link" href="#/activity">All activity</a></div>
          ${txs.length ? txTable(txs, currency, fxRates) : emptyState('No activity yet', 'Make your first deposit to get started.',
            html`<button class="btn-primary" data-action="deposit">Deposit</button>`)}
        </section>
      </div>`);
  }

  on(outlet, 'click', '[data-action]', async (_, el) => {
    const a = el.dataset.action;
    try {
      let done;
      if (a === 'deposit') done = await depositDialog();
      else if (a === 'withdraw') done = await withdrawDialog();
      else if (a === 'move') done = await moveDialog();
      else if (a === 'send') done = await sendDialog();
      else if (a === 'resend') { await api.auth.resendVerification(); toast('Confirmation email sent.'); }
      else if (a === 'retry') done = true;
      if (done) { invalidate('dashboard'); load(); }
    } catch (err) { toastError(err); }
  });

  await load();
}

function notices(user) {
  const items = [];
  if (user.is_blocked) items.push(html`<div class="panel border-rejected/40 bg-rejected/5 px-5 py-4" role="alert">
    <p class="font-semibold text-rejected">Your account is restricted</p>
    <p class="text-sm text-muted">Deposits, withdrawals and investments are paused. Contact support for details.</p></div>`);
  if (user.kyc_status === 'REJECTED') items.push(html`<div class="panel border-pending/40 px-5 py-4">
    <p class="font-semibold">Your ID document needs another look</p>
    <p class="text-sm text-muted">${user.kyc_rejection_reason || 'Upload a clearer document.'}</p>
    <a class="btn-link mt-2 inline-block" href="#/settings">Upload a new document</a></div>`);
  else if (user.kyc_status === 'UNVERIFIED') items.push(html`<div class="panel px-5 py-4">
    <p class="font-semibold">Verify your identity to withdraw</p>
    <p class="text-sm text-muted">Deposits and investing work now. Withdrawals need one ID check.</p>
    <a class="btn-link mt-2 inline-block" href="#/settings">Verify identity</a></div>`);
  if (!user.email_verified) items.push(html`<div class="panel px-5 py-4">
    <p class="font-semibold">Confirm your email</p>
    <p class="text-sm text-muted">We sent a link to ${user.email}. It expires after 24 hours.</p>
    ${user.impersonated_by ? '' : html`<button class="btn-link mt-2" data-action="resend">Send a new link</button>`}</div>`);
  return items.length ? html`<div class="mb-6 grid gap-3 md:grid-cols-2">${items}</div>` : '';
}

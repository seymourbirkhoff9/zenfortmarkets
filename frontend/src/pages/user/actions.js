/**
 * Money-moving dialogs shared by Overview and Deposits & withdrawals.
 * Each resolves to the created transaction, or undefined if cancelled.
 */
import { api } from '../../lib/api.js';
import { $, $$, html, render } from '../../lib/dom.js';
import { money } from '../../lib/format.js';
import { icon } from '../../lib/icons.js';
import { copy, filePicker, openDialog, toast } from '../../lib/ui.js';
import { session } from '../../session.js';

/**
 * Fresh standing + balances + payment methods in ONE request. Dialogs open
 * instantly with a skeleton and call this, so they never act on stale page data.
 */
async function context() {
  const ctx = await api.me.context();
  session.user = ctx.user;
  return {
    u: ctx.user, methods: ctx.payment_methods,
    bal: Object.fromEntries(ctx.wallets.map((w) => [w.wallet_type, Number(w.balance)]))
  };
}

const info = (title, text, extra = '') => ({ title, body: html`<p class="text-muted">${text}</p>${extra}`, onSubmit: undefined });

/** While an admin views this account, every money action is refused by the server; say so up front. */
export const viewOnly = () => Boolean(session.user?.impersonated_by);
const viewOnlyInfo = () => info('View only', 'You’re viewing this account as an admin. Exit to the console to make changes.');

const methodChoice = (m, name) => {
  const isBank = m.method_type === 'bank';
  let label = m.asset, sub;
  if (isBank) {
    try { const bd = JSON.parse(m.bank_details || '{}'); label = bd.bank_name || 'Bank Transfer'; } catch { label = 'Bank Transfer'; }
    sub = 'Bank transfer';
  } else {
    sub = `${m.network} network`;
  }
  return html`
  <label class="choice">
    <input type="radio" name="${name}" value="${m.id}" required />
    <span class="grid h-9 min-w-[2.75rem] place-items-center rounded bg-sunken px-1.5 text-xs font-bold">${isBank ? '🏦' : m.asset.slice(0, 5)}</span>
    <span><span class="block font-semibold">${label}</span><span class="block text-xs text-muted">${sub}</span></span>
  </label>`;
};

/* ── Deposit ───────────────────────────────────────────────────────── */
export function depositDialog() {
  let getProof = () => null;
  return openDialog({
    title: 'Report a deposit', submitLabel: 'Submit for review', load: async () => {
      if (viewOnly()) return viewOnlyInfo();
      const { u, methods: all } = await context();
      if (u.is_blocked || !u.can_deposit) return info('Deposits are unavailable', 'Deposits are turned off for your account. Contact support to find out why.');
      const methods = all.filter((m) => m.deposit_enabled);
      if (!methods.length) return info('No deposit methods yet', 'The operator has not published a deposit method. Check back later.');
      return {
        body: html`
      <fieldset class="grid gap-2">
        <legend class="label mb-1.5">1. Choose what you’re sending</legend>
        <div class="grid gap-2 sm:grid-cols-2">${methods.map((m) => methodChoice(m, 'payment_method_id'))}</div>
      </fieldset>
      <div id="dep-address" class="grid gap-2" hidden></div>
      <div class="field"><label class="label" for="dep-amount">3. Amount sent, in US dollars</label>
        <input class="input figure" id="dep-amount" name="amount" type="number" inputmode="decimal" min="0.01" step="0.01" placeholder="100.00" required />
        <p class="hint">Enter the dollar value of what you sent. Your wallet is credited in USD.</p></div>
      <div class="field"><label class="label" for="dep-hash" id="dep-hash-label">4. Transaction hash</label>
        <input class="input font-mono text-sm" id="dep-hash" name="tx_hash" autocomplete="off" spellcheck="false" placeholder="0x… or the TXID from your wallet app" />
        <p class="hint">Add the hash, a screenshot, or both.</p></div>
      <div class="field"><label class="label" for="dep-proof">Screenshot of the payment <span class="font-normal text-muted">(optional)</span></label>
        <input class="input text-sm" id="dep-proof" type="file" accept="image/png,image/jpeg,image/webp" />
        <div id="dep-preview" hidden></div></div>`,
        onMount: (dlg) => {
          getProof = filePicker(dlg, { inputSel: '#dep-proof', previewSel: '#dep-preview' });
          $$('input[name=payment_method_id]', dlg).forEach((r) => r.addEventListener('change', () => {
            const m = methods.find((x) => x.id === r.value);
            const box = $('#dep-address', dlg);
            box.hidden = false;
            if (m.method_type === 'bank') {
              let bd = {};
              try { bd = JSON.parse(m.bank_details || '{}'); } catch { /* ignore */ }
              const rows = [
                bd.bank_name && ['Bank name', bd.bank_name],
                bd.account_holder && ['Account holder', bd.account_holder],
                bd.account_number && ['Account number', bd.account_number],
                bd.sort_code && ['Sort / Routing', bd.sort_code],
                bd.iban && ['IBAN', bd.iban],
                bd.swift && ['SWIFT / BIC', bd.swift],
                bd.cvu && ['CVU', bd.cvu],
                bd.alias && ['Alias', bd.alias],
              ].filter(Boolean);
              render(box, html`
                <p class="label">2. Transfer funds to this bank account</p>
                <div class="rounded border border-line bg-sunken p-3 text-sm grid gap-1.5">
                  ${rows.map(([k, v]) => html`<div class="flex justify-between gap-4">
                    <span class="text-muted flex-shrink-0">${k}</span>
                    <span class="font-mono font-semibold text-right break-all">${v}</span>
                  </div>`)}
                </div>
                ${bd.reference_notes ? html`<p class="hint"><strong>Note:</strong> ${bd.reference_notes}</p>` : ''}
                ${Number(m.min_deposit) > 0 ? html`<p class="hint">Minimum deposit: ${money(m.min_deposit)}.</p>` : ''}`);
              $('#dep-hash-label', dlg).textContent = '4. Payment reference or bank confirmation number';
              $('#dep-hash', dlg).placeholder = 'e.g. bank reference or transfer ID';
            } else {
              render(box, html`
                <p class="label">2. Send ${m.asset} on the ${m.network} network to</p>
                <div class="copy-row"><span class="flex-1">${m.deposit_address}</span>
                  <button type="button" class="btn-quiet btn-sm" data-copy="${m.deposit_address}">${icon('copy', 'h-4 w-4')}Copy</button></div>
                ${m.deposit_memo ? html`<p class="text-sm">Memo / tag: <span class="font-mono">${m.deposit_memo}</span> &mdash; include it or the deposit cannot be matched.</p>` : ''}
                <p class="hint">Only send ${m.asset} on ${m.network}. Other assets or networks sent here are lost.
                  ${Number(m.min_deposit) > 0 ? html` Minimum ${money(m.min_deposit)}.` : ''}</p>`);
              $('#dep-hash-label', dlg).textContent = '4. Transaction hash';
              $('#dep-hash', dlg).placeholder = '0x... or the TXID from your wallet app';
              box.querySelector('[data-copy]').addEventListener('click', (e) => copy(e.currentTarget.dataset.copy, 'Address copied'));
            }
          }));
        },
        onSubmit: async (v) => {
          const proof = getProof();
          if (!v.tx_hash && !proof) throw new Error('Add the transaction hash or a screenshot so the operator can find your payment.');
          const tx = await api.wallets.deposit({
            payment_method_id: v.payment_method_id, amount: v.amount,
            tx_hash: v.tx_hash || null, proof_image_url: proof
          });
          toast('Deposit submitted. You’ll be notified when it’s reviewed.');
          return tx;
        },
      };
    }
  });
}

/* ── Withdraw ──────────────────────────────────────────────────────── */
export function withdrawDialog() {
  return openDialog({
    title: 'Withdraw to your wallet', submitLabel: 'Request withdrawal', load: async () => {
      if (viewOnly()) return viewOnlyInfo();
      const { u, methods: all, bal } = await context();
      const mainBalance = bal.main;
      if (u.is_blocked || !u.can_withdraw) return info('Withdrawals are unavailable', 'Withdrawals are turned off for your account. Contact support to find out why.');
      if (u.kyc_status !== 'VERIFIED') {
        return u.kyc_status === 'PENDING'
          ? info('Verify your identity first', 'Your ID is being reviewed. You can withdraw once it’s approved.')
          : info('Verify your identity first', 'Withdrawals need a verified identity. Upload an ID document in Settings; it usually takes one review.',
            html`<a class="btn-primary mt-4 inline-flex" href="#/settings">Go to Settings</a>`);
      }
      const methods = all.filter((m) => m.withdraw_enabled);
      if (!methods.length) return info('No payout methods yet', 'The operator hasn’t enabled any withdrawal methods.');
      return {
        body: html`
      <p class="text-sm text-muted">Available in Main wallet: <strong class="figure text-ink">${money(mainBalance)}</strong></p>
      <fieldset class="grid gap-2"><legend class="label mb-1.5">Receive as</legend>
        <div class="grid gap-2 sm:grid-cols-2">${methods.map((m) => methodChoice(m, 'payment_method_id'))}</div></fieldset>
      <div class="field"><label class="label" for="wd-address">Your wallet address</label>
        <input class="input font-mono text-sm" id="wd-address" name="withdrawal_address" autocomplete="off" spellcheck="false" required minlength="10" maxlength="128" />
        <p class="hint" id="wd-net-hint">Double-check it. Payouts sent to a wrong address can’t be recovered.</p></div>
      <div class="field"><label class="label" for="wd-details">Memo, tag or note for the operator <span class="font-normal text-muted">(optional)</span></label>
        <input class="input" id="wd-details" name="withdrawal_details" maxlength="500" placeholder="e.g. destination tag 123456" /></div>
      <div class="field"><label class="label" for="wd-amount">Amount, in US dollars</label>
        <input class="input figure" id="wd-amount" name="amount" type="number" inputmode="decimal" min="0.01" step="0.01" max="${mainBalance}" required />
        <p class="hint" id="wd-summary">Choose a method to see the fee.</p></div>`,
        onMount: (dlg) => {
          const update = () => {
            const m = methods.find((x) => x.id === $('input[name=payment_method_id]:checked', dlg)?.value);
            const amt = Number($('#wd-amount', dlg).value || 0);
            if (!m) return;
            $('#wd-net-hint', dlg).textContent = `Use an address on the ${m.network} network. Payouts sent to a wrong address can’t be recovered.`;
            const fee = Number(m.withdrawal_fee);
            const min = Number(m.min_withdrawal);
            $('#wd-summary', dlg).textContent = `Network fee ${money(fee)}.${min ? ` Minimum ${money(min)}.` : ''}` +
              (amt > fee ? ` You receive about ${money(amt - fee)} worth of ${m.asset}.` : '');
          };
          dlg.addEventListener('change', update);
          $('#wd-amount', dlg).addEventListener('input', update);
        },
        onSubmit: async (v) => {
          const tx = await api.wallets.withdraw({
            payment_method_id: v.payment_method_id, amount: v.amount,
            withdrawal_address: v.withdrawal_address, withdrawal_details: v.withdrawal_details || null
          });
          toast(`Withdrawal requested. ${money(tx.amount)} is on hold until it’s paid.`);
          return tx;
        },
      };
    }
  });
}

/* ── Move between own wallets ──────────────────────────────────────── */
export function moveDialog() {
  return openDialog({
    title: 'Move between your wallets', submitLabel: 'Move funds', load: async () => {
      if (viewOnly()) return viewOnlyInfo();
      const { bal } = await context();
      return {
        body: html`
      <fieldset class="grid gap-2"><legend class="label mb-1.5">Direction</legend>
        <label class="choice"><input type="radio" name="dir" value="profit-main" checked />
          <span>Profit → Main <span class="block text-xs text-muted">${money(bal.profit)} available</span></span></label>
        <label class="choice"><input type="radio" name="dir" value="main-profit" />
          <span>Main → Profit <span class="block text-xs text-muted">${money(bal.main)} available</span></span></label>
      </fieldset>
      <div class="field"><label class="label" for="mv-amount">Amount, in US dollars</label>
        <input class="input figure" id="mv-amount" name="amount" type="number" inputmode="decimal" min="0.01" step="0.01" required />
        <p class="hint">Returns land in Profit. Move them to Main to invest or withdraw.</p></div>`,
        onSubmit: async (v) => {
          const [from_wallet, to_wallet] = v.dir.split('-');
          const tx = await api.wallets.transfer({ from_wallet, to_wallet, amount: v.amount });
          toast(`Moved ${money(tx.amount)} to your ${to_wallet === 'main' ? 'Main' : 'Profit'} wallet.`);
          return tx;
        },
      };
    }
  });
}

/* ── Send to another customer ──────────────────────────────────────── */
export function sendDialog() {
  return openDialog({
    title: 'Send to another customer', submitLabel: 'Send', load: async () => {
      if (viewOnly()) return viewOnlyInfo();
      const { bal: { main: mainBalance } } = await context();
      return {
        body: html`
      <div class="field"><label class="label" for="p2p-email">Their account email</label>
        <input class="input" id="p2p-email" name="recipient_email" type="email" required /></div>
      <div class="field"><label class="label" for="p2p-amount">Amount, in US dollars</label>
        <input class="input figure" id="p2p-amount" name="amount" type="number" inputmode="decimal" min="0.01" step="0.01" max="${mainBalance}" required />
        <p class="hint">From your Main wallet (${money(mainBalance)} available). Transfers are instant and can’t be reversed.</p></div>
      <div class="field"><label class="label" for="p2p-note">Note <span class="font-normal text-muted">(optional)</span></label>
        <input class="input" id="p2p-note" name="description" maxlength="200" /></div>`,
        onSubmit: async (v) => {
          const tx = await api.wallets.p2p({ recipient_email: v.recipient_email, amount: v.amount, description: v.description || null });
          toast(`Sent ${money(tx.amount)} to ${v.recipient_email}.`);
          return tx;
        },
      };
    }
  });
}

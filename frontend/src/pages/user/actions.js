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
  let fxRates = [];
  return openDialog({
    title: 'Report a deposit', submitLabel: 'Submit for review', load: async () => {
      if (viewOnly()) return viewOnlyInfo();
      const { u, methods: all } = await context();
      if (u.is_blocked || !u.can_deposit) return info('Deposits are unavailable', 'Deposits are turned off for your account. Contact support to find out why.');
      const methods = all.filter((m) => m.deposit_enabled);
      if (!methods.length) return info('No deposit methods yet', 'The operator has not published a deposit method. Check back later.');
      try {
        const response = await api.fx.rates();
        fxRates = response?.rates || [];
      } catch { fxRates = []; }
      const enabledCurrencies = fxRates.filter((r) => r.effective_rate);
      return {
        body: html`
      <fieldset class="grid gap-2">
        <legend class="label mb-1.5">1. Choose what you’re sending</legend>
        <div class="grid gap-2 sm:grid-cols-2">${methods.map((m) => methodChoice(m, 'payment_method_id'))}</div>
      </fieldset>
      <div id="dep-address" class="grid gap-2" hidden></div>
      ${enabledCurrencies.length ? html`
      <div class="field"><label class="label" for="dep-currency">2. Currency</label>
        <select class="input" id="dep-currency" name="input_currency">
          <option value="">USD (default)</option>
          ${enabledCurrencies.map((c) => html`<option value="${c.currency}">${c.currency}</option>`)}
        </select>
        <p class="hint">Select if you sent in a different currency. Your wallet is credited in USD.</p></div>` : ''}
      <div class="field"><label class="label" for="dep-amount">${enabledCurrencies.length ? '3' : '2'}. Amount sent${enabledCurrencies.length ? '' : ', in US dollars'}</label>
        <input class="input figure" id="dep-amount" name="amount" type="number" inputmode="decimal" min="0.01" step="0.01" placeholder="100.00" required />
        <p class="hint" id="dep-hint">Enter the dollar value of what you sent. Your wallet is credited in USD.</p>
        <p class="hint" id="dep-min-hint"></p></div>
      <div id="dep-conversion" class="text-sm text-muted hidden"></div>
      <div class="field"><label class="label" for="dep-hash" id="dep-hash-label">${enabledCurrencies.length ? '4' : '3'}. Transaction hash</label>
        <input class="input font-mono text-sm" id="dep-hash" name="tx_hash" autocomplete="off" spellcheck="false" placeholder="0x… or the TXID from your wallet app" />
        <p class="hint">Add the hash, a screenshot, or both.</p></div>
      <div class="field"><label class="label" for="dep-proof">Screenshot of the payment <span class="font-normal text-muted">(optional)</span></label>
        <input class="input text-sm" id="dep-proof" type="file" accept="image/png,image/jpeg,image/webp" />
        <div id="dep-preview" hidden></div></div>`,
        onMount: (dlg) => {
          getProof = filePicker(dlg, { inputSel: '#dep-proof', previewSel: '#dep-preview' });
          
          // Currency change handler
          const updateConversion = () => {
            const currency = $('#dep-currency', dlg)?.value;
            const amount = Number($('#dep-amount', dlg)?.value || 0);
            const hint = $('#dep-hint', dlg);
            const minHint = $('#dep-min-hint', dlg);
            const conversion = $('#dep-conversion', dlg);

            // Get selected payment method's minimum deposit
            const selectedMethodId = $('input[name=payment_method_id]:checked', dlg)?.value;
            const selectedMethod = methods.find((m) => m.id === selectedMethodId);
            const minDepositUSD = selectedMethod?.min_deposit || 0;

            if (currency && amount > 0) {
              const rateObj = fxRates.find((r) => r.currency === currency);
              const rate = rateObj?.effective_rate;
              if (rate) {
                const usdAmount = amount / rate;
                conversion.hidden = false;
                conversion.textContent = `${amount} ${currency} ≈ $${usdAmount.toFixed(2)} USD (rate: ${rate})`;
                hint.textContent = `Enter the amount in ${currency}.`;
              } else {
                conversion.hidden = true;
                hint.textContent = `Enter the amount in ${currency}.`;
              }
            } else {
              conversion.hidden = true;
              hint.textContent = 'Enter the dollar value of what you sent. Your wallet is credited in USD.';
            }

            // Update minimum amount hint in selected currency
            if (currency && minDepositUSD > 0) {
              const rateObj = fxRates.find((r) => r.currency === currency);
              const rate = rateObj?.effective_rate;
              if (rate) {
                const minInCurrency = (minDepositUSD * rate).toFixed(2);
                minHint.textContent = `Minimum deposit: ${minInCurrency} ${currency} (~$${minDepositUSD} USD)`;
              } else {
                minHint.textContent = `Minimum deposit: $${minDepositUSD} USD`;
              }
            } else if (minDepositUSD > 0) {
              minHint.textContent = `Minimum deposit: $${minDepositUSD} USD`;
            } else {
              minHint.textContent = '';
            }
          };
          
          $('#dep-currency', dlg)?.addEventListener('change', updateConversion);
          $('#dep-amount', dlg)?.addEventListener('input', updateConversion);
          updateConversion(); // Initial call to show minimum hint

          $$('input[name=payment_method_id]', dlg).forEach((r) => r.addEventListener('change', () => {
            const m = methods.find((x) => x.id === r.value);
            const box = $('#dep-address', dlg);
            box.hidden = false;
            updateConversion(); // Update minimum hint when method changes
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
          const payload = {
            payment_method_id: v.payment_method_id, amount: Number(v.amount),
            tx_hash: v.tx_hash || null, proof_image_url: proof,
            input_currency: v.input_currency && v.input_currency.trim() ? v.input_currency.trim() : undefined
          };
          const tx = await api.wallets.deposit(payload);
          toast('Deposit submitted. You’ll be notified when it’s reviewed.');
          return tx;
        },
      };
    }
  });
}

/* ── Withdraw ──────────────────────────────────────────────────────── */
export function withdrawDialog() {
  let fxRates = [];
  return openDialog({
    title: 'Withdraw to your wallet', submitLabel: 'Request withdrawal', load: async () => {
      if (viewOnly()) return viewOnlyInfo();
      const { u, methods: all, bal } = await context();
      const mainBalance = bal.main;
      if (u.is_blocked || !u.can_withdraw) return info('Withdrawals are unavailable', 'Withdrawals are turned off for your account. Contact support to find out why.');
      if (u.kyc_status !== 'VERIFIED') {
        return u.kyc_status === 'PENDING'
          ? info("Verify your identity first', 'Your ID is being reviewed. You can withdraw once it's approved.")
          : info('Verify your identity first', 'Withdrawals need a verified identity. Upload an ID document in Settings; it usually takes one review.',
            html`<a class="btn-primary mt-4 inline-flex" href="#/settings">Go to Settings</a>`);
      }
      const methods = all.filter((m) => m.withdraw_enabled);
      if (!methods.length) return info("No payout methods yet', 'The operator hasn't enabled any withdrawal methods.");
      try {
        const response = await api.fx.rates();
        fxRates = response?.rates || [];
      } catch { fxRates = []; }
      const enabledCurrencies = fxRates.filter((r) => r.effective_rate);
      return {
        body: html`
      <p class="text-sm text-muted">Available in Main wallet: <strong class="figure text-ink">${money(mainBalance)}</strong></p>
      <fieldset class="grid gap-2"><legend class="label mb-1.5">Receive as</legend>
        <div class="grid gap-2 sm:grid-cols-2">${methods.map((m) => methodChoice(m, 'payment_method_id'))}</div></fieldset>
      <div id="wd-recipient-fields"></div>
      <div class="field"><label class="label" for="wd-details">Additional note for the operator <span class="font-normal text-muted">(optional)</span></label>
        <input class="input" id="wd-details" name="withdrawal_details" maxlength="500" placeholder="e.g. destination tag 123456" /></div>
      ${enabledCurrencies.length ? html`
      <div class="field"><label class="label" for="wd-currency">Currency</label>
        <select class="input" id="wd-currency" name="input_currency">
          <option value="">USD (default)</option>
          ${enabledCurrencies.map((c) => html`<option value="${c.currency}">${c.currency}</option>`)}
        </select>
        <p class="hint">Select if you want to withdraw in a different currency. Your wallet is debited in USD.</p></div>` : ''}
      <div class="field"><label class="label" for="wd-amount">Amount${enabledCurrencies.length ? '' : ', in US dollars'}</label>
        <input class="input figure" id="wd-amount" name="amount" type="number" inputmode="decimal" min="0.01" step="0.01" max="${mainBalance}" required />
        <p class="hint" id="wd-summary">Choose a method to see the fee.</p>
        <p class="hint" id="wd-min-hint"></p></div>
      <div id="wd-conversion" class="text-sm text-muted hidden"></div>`,
        onMount: (dlg) => {
          const updateRecipientFields = () => {
            const m = methods.find((x) => x.id === $('input[name=payment_method_id]:checked', dlg)?.value);
            const recipientFields = $('#wd-recipient-fields', dlg);
            if (!m) return;

            if (m.method_type === 'bank') {
              // Show bank account input fields
              recipientFields.innerHTML = `
                <div class="field"><label class="label" for="wd-bank-name">Bank name</label>
                  <input class="input" id="wd-bank-name" name="bank_name" placeholder="e.g. Barclays" /></div>
                <div class="field"><label class="label" for="wd-account-holder">Account holder name</label>
                  <input class="input" id="wd-account-holder" name="account_holder" placeholder="Your full name" required /></div>
                <div class="field"><label class="label" for="wd-account-number">Account number</label>
                  <input class="input font-mono text-sm" id="wd-account-number" name="account_number" autocomplete="off" spellcheck="false" required minlength="5" maxlength="34" /></div>
                <div class="field"><label class="label" for="wd-sort-code">Sort code / Routing number</label>
                  <input class="input font-mono text-sm" id="wd-sort-code" name="sort_code" autocomplete="off" spellcheck="false" maxlength="20" /></div>
                <div class="field"><label class="label" for="wd-iban">IBAN <span class="font-normal text-muted">(for international transfers)</span></label>
                  <input class="input font-mono text-sm" id="wd-iban" name="iban" autocomplete="off" spellcheck="false" maxlength="34" placeholder="e.g. GB82WEST12345698765432" /></div>
                <div class="field"><label class="label" for="wd-swift">SWIFT / BIC <span class="font-normal text-muted">(for international transfers)</span></label>
                  <input class="input font-mono text-sm" id="wd-swift" name="swift" autocomplete="off" spellcheck="false" maxlength="11" placeholder="e.g. WESTGB2B" /></div>
              `;
            } else {
              // Show crypto wallet address field
              recipientFields.innerHTML = `
                <div class="field"><label class="label" for="wd-address">Your wallet address</label>
                  <input class="input font-mono text-sm" id="wd-address" name="withdrawal_address" autocomplete="off" spellcheck="false" required minlength="10" maxlength="128" />
                  <p class="hint" id="wd-net-hint">Use an address on the ${m.network} network. Payouts sent to a wrong address can't be recovered.</p></div>
              `;
            }
          };

          const update = () => {
            const m = methods.find((x) => x.id === $('input[name=payment_method_id]:checked', dlg)?.value);
            const amt = Number($('#wd-amount', dlg).value || 0);
            const currency = $('#wd-currency', dlg)?.value;
            const conversion = $('#wd-conversion', dlg);
            if (!m) return;
            const fee = Number(m.withdrawal_fee);
            const min = Number(m.min_withdrawal);

            // Convert fee and minimum to selected currency
            let feeText = money(fee);
            let minText = min ? money(min) : '';
            if (currency && currency !== 'USD') {
              const rateObj = fxRates.find((r) => r.currency === currency);
              const rate = rateObj?.effective_rate;
              if (rate) {
                const feeInCurrency = (fee * rate).toFixed(2);
                feeText = `${feeInCurrency} ${currency} (~${money(fee)})`;
                if (min) {
                  const minInCurrency = (min * rate).toFixed(2);
                  minText = `${minInCurrency} ${currency} (~${money(min)})`;
                }
              }
            }

            $('#wd-summary', dlg).textContent = `Network fee ${feeText}.${minText ? ` Minimum ${minText}.` : ''}` +
              (amt > fee ? ` You receive about ${money(amt - fee)} worth of ${m.asset}.` : '');

            // Show payment method details for bank transfers
            const detailsBox = $('#wd-details-box', dlg);
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
              if (!detailsBox) {
                const newBox = document.createElement('div');
                newBox.id = 'wd-details-box';
                newBox.className = 'rounded border border-line bg-sunken p-3 text-sm grid gap-1.5 mt-2';
                $('#wd-address', dlg).parentNode.after(newBox);
              }
              render($('#wd-details-box', dlg), html`
                ${rows.map(([k, v]) => html`<div class="flex justify-between gap-4">
                  <span class="text-muted flex-shrink-0">${k}</span>
                  <span class="font-mono font-semibold text-right break-all">${v}</span>
                </div>`)}
                ${bd.reference_notes ? html`<p class="hint"><strong>Note:</strong> ${bd.reference_notes}</p>` : ''}`);
            } else if (detailsBox) {
              detailsBox.remove();
            }
            
            // Currency conversion preview
            if (currency && amt > 0) {
              const rateObj = fxRates.find((r) => r.currency === currency);
              const rate = rateObj?.effective_rate;
              if (rate) {
                const usdAmount = amt / rate;
                conversion.hidden = false;
                conversion.textContent = `${amt} ${currency} ≈ $${usdAmount.toFixed(2)} USD (rate: ${rate})`;
              } else {
                conversion.hidden = true;
              }
            } else {
              conversion.hidden = true;
            }

            // Update minimum amount hint in selected currency
            const minHint = $('#wd-min-hint', dlg);
            if (currency && min > 0) {
              const rateObj = fxRates.find((r) => r.currency === currency);
              const rate = rateObj?.effective_rate;
              if (rate) {
                const minInCurrency = (min * rate).toFixed(2);
                minHint.textContent = `Minimum withdrawal: ${minInCurrency} ${currency} (~$${min} USD)`;
              } else {
                minHint.textContent = `Minimum withdrawal: $${min} USD`;
              }
            } else if (min > 0) {
              minHint.textContent = `Minimum withdrawal: $${min} USD`;
            } else {
              minHint.textContent = '';
            }
          };
          dlg.addEventListener('change', update);
          // Only update recipient fields when payment method changes
          $('input[name=payment_method_id]', dlg).addEventListener('change', updateRecipientFields);
          $('#wd-amount', dlg).addEventListener('input', update);
          $('#wd-currency', dlg)?.addEventListener('change', update);
          updateRecipientFields(); // Initial call to show correct fields
          update(); // Initial call to show minimum hint
        },
        onSubmit: async (v) => {
          const m = methods.find((x) => x.id === v.payment_method_id);
          let withdrawal_address = null;
          let withdrawal_details = v.withdrawal_details || null;

          if (m.method_type === 'bank') {
            // Format bank details into withdrawal_details
            const bankDetails = {
              bank_name: v.bank_name || '',
              account_holder: v.account_holder || '',
              account_number: v.account_number || '',
              sort_code: v.sort_code || '',
              iban: v.iban || '',
              swift: v.swift || '',
            };
            // Only include non-empty fields
            const filteredDetails = Object.fromEntries(
              Object.entries(bankDetails).filter(([_, val]) => val.trim())
            );
            if (Object.keys(filteredDetails).length > 0) {
              withdrawal_details = JSON.stringify(filteredDetails);
            }
          } else {
            withdrawal_address = v.withdrawal_address;
          }

          const payload = {
            payment_method_id: v.payment_method_id,
            amount: Number(v.amount),
            withdrawal_address,
            withdrawal_details
          };
          if (v.input_currency && v.input_currency.trim()) payload.input_currency = v.input_currency.trim();
          const tx = await api.wallets.withdraw(payload);
          toast(`Withdrawal requested. ${money(tx.amount)} is on hold until it's paid.`);
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
      const { bal: { main: mainBalance }, u: user } = await context();
      let fxRates = [];
      try {
        const response = await api.fx.rates();
        fxRates = response?.rates || [];
      } catch { fxRates = []; }
      const enabledCurrencies = fxRates.filter((r) => r.effective_rate);
      const currency = user.display_currency || 'USD';
      return {
        body: html`
      <div class="field"><label class="label" for="p2p-email">Their account email</label>
        <input class="input" id="p2p-email" name="recipient_email" type="email" required /></div>
      ${enabledCurrencies.length ? html`
      <div class="field"><label class="label" for="p2p-currency">Currency</label>
        <select class="input" id="p2p-currency" name="input_currency">
          <option value="">USD (default)</option>
          ${enabledCurrencies.map((c) => html`<option value="${c.currency}" ${c.currency === currency ? 'selected' : ''}>${c.currency}</option>`)}
        </select>
        <p class="hint">Select if you want to send in a different currency. Your wallet is debited in USD.</p></div>` : ''}
      <div class="field"><label class="label" for="p2p-amount">Amount${enabledCurrencies.length ? '' : ', in US dollars'}</label>
        <input class="input figure" id="p2p-amount" name="amount" type="number" inputmode="decimal" min="0.01" step="0.01" required />
        <p class="hint" id="p2p-max-hint">Maximum: ${money(mainBalance)}. Transfers are instant and can't be reversed.</p>
        <p class="hint" id="p2p-conversion" class="hidden"></p></div>
      <div class="field"><label class="label" for="p2p-note">Note <span class="font-normal text-muted">(optional)</span></label>
        <input class="input" id="p2p-note" name="description" maxlength="200" /></div>`,
        onMount: (dlg) => {
          const update = () => {
            const amt = Number($('#p2p-amount', dlg).value || 0);
            const currency = $('#p2p-currency', dlg)?.value;
            const conversion = $('#p2p-conversion', dlg);
            const maxHint = $('#p2p-max-hint', dlg);

            // Update max hint with currency conversion
            if (currency && currency !== 'USD') {
              const rateObj = fxRates.find((r) => r.currency === currency);
              const rate = rateObj?.effective_rate;
              if (rate) {
                const maxInCurrency = mainBalance * rate;
                maxHint.textContent = `Maximum: ${money(maxInCurrency, currency)} (~${money(mainBalance)} USD). Transfers are instant and can't be reversed.`;
              }
            } else {
              maxHint.textContent = `Maximum: ${money(mainBalance)}. Transfers are instant and can't be reversed.`;
            }

            // Show conversion preview
            if (currency && amt > 0) {
              const rateObj = fxRates.find((r) => r.currency === currency);
              const rate = rateObj?.effective_rate;
              if (rate) {
                const usdAmount = amt / rate;
                conversion.hidden = false;
                conversion.textContent = `${amt} ${currency} ≈ $${usdAmount.toFixed(2)} USD (rate: ${rate})`;
              } else {
                conversion.hidden = true;
              }
            } else {
              conversion.hidden = true;
            }
          };
          dlg.addEventListener('change', update);
          $('#p2p-amount', dlg).addEventListener('input', update);
          $('#p2p-currency', dlg)?.addEventListener('change', update);
          update(); // Initial call
        },
        onSubmit: async (v) => {
          const payload = {
            recipient_email: v.recipient_email,
            amount: Number(v.amount),
            description: v.description || null
          };
          if (v.input_currency && v.input_currency.trim()) payload.input_currency = v.input_currency.trim();
          const tx = await api.wallets.p2p(payload);
          toast(`Sent ${money(tx.amount)} to ${v.recipient_email}.`);
          return tx;
        },
      };
    }
  });
}

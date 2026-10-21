/**
 * Settings → Two-factor sign-in. Guided setup with a QR code, recovery codes shown once,
 * and password + code required to change anything.
 */
import QRCode from 'qrcode';
import { api } from '../../lib/api.js';
import { html, raw, render } from '../../lib/dom.js';
import { copy, openDialog, toast, toastError } from '../../lib/ui.js';

const codesBlock = (codes) => html`
  <p class="text-muted">Save these recovery codes somewhere safe, like a password manager. Each one signs you in once if you lose your phone.
    <strong class="text-ink">You won’t see them again.</strong></p>
  <ol class="grid grid-cols-2 gap-2 rounded border border-line bg-sunken p-4 font-mono text-sm" translate="no">
    ${codes.map((c) => html`<li>${c}</li>`)}</ol>
  <div class="flex flex-wrap gap-2">
    <button type="button" class="btn-quiet btn-sm" data-copy-codes>Copy codes</button>
    <button type="button" class="btn-quiet btn-sm" data-download-codes>Download as a file</button></div>`;

function wireCodes(dlg, codes) {
  const text = `Zenfort Markets recovery codes (each works once)\n\n${codes.join('\n')}\n`;
  dlg.querySelector('[data-copy-codes]').addEventListener('click', () => copy(text, 'Recovery codes copied'));
  dlg.querySelector('[data-download-codes]').addEventListener('click', () => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain' }));
    a.download = 'zenfort-recovery-codes.txt';
    a.click();
    URL.revokeObjectURL(a.href);
  });
}

/** Renders the section body into `el`, and keeps it updated. */
export async function twoFactorSection(el, readOnly) {
  async function draw() {
    let st;
    try { st = await api.auth.twoFactorStatus(); } catch (err) { render(el, html`<p class="text-sm text-muted">${err.message}</p>`); return; }
    render(el, st.enabled ? html`
      <p>Status: <span class="pill-settled">On</span></p>
      <p class="text-sm text-muted">${st.recovery_codes_left} recovery code${st.recovery_codes_left === 1 ? '' : 's'} left.
        ${st.recovery_codes_left <= 2 ? html`<strong class="text-pending">Make new ones soon.</strong>` : ''}</p>
      <div class="flex flex-wrap gap-2">
        <button type="button" class="btn-quiet btn-sm" data-2fa="codes" ${readOnly ? 'disabled' : ''}>New recovery codes</button>
        <button type="button" class="btn-quiet btn-sm text-rejected" data-2fa="off" ${readOnly ? 'disabled' : ''}>Turn off</button></div>`
      : html`
      <p>Status: <span class="pill-neutral">Off</span></p>
      <p class="text-sm text-muted">Use an authenticator app such as Google Authenticator, Microsoft Authenticator or Authy.</p>
      <button type="button" class="btn-primary justify-self-start" data-2fa="on" ${readOnly ? 'disabled' : ''}>Turn on two-factor sign-in</button>`);
  }

  el.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-2fa]');
    if (!b) return;
    try {
      if (b.dataset['2fa'] === 'on') await turnOn();
      if (b.dataset['2fa'] === 'off') await withCode('Turn off two-factor sign-in', 'Turn off', true,
        (pw, code) => api.auth.twoFactorDisable(pw, code), () => toast('Two-factor sign-in is off.'));
      if (b.dataset['2fa'] === 'codes') await withCode('Make new recovery codes', 'Make new codes', false,
        (pw, code) => api.auth.twoFactorNewCodes(pw, code), null);
    } catch (err) { toastError(err); }
    draw();
  });
  await draw();
}

async function turnOn() {
  let step = 'password', setup = null;
  await openDialog({
    title: 'Turn on two-factor sign-in', submitLabel: 'Continue',
    body: html`<p class="text-muted">Confirm it’s you first.</p>
      <div class="field"><label class="label" for="tf-pw">Password</label>
        <input class="input" id="tf-pw" name="password" type="password" autocomplete="current-password" required /></div>`,
    onSubmit: async (v, dlg) => {
      const body = dlg.querySelector('[data-body]');
      const submit = dlg.querySelector('button[type=submit]');
      if (step === 'password') {
        setup = await api.auth.twoFactorSetup(v.password);
        const svg = await QRCode.toString(setup.otpauth_uri, { type: 'svg', margin: 1, width: 200, color: { dark: '#14243B', light: '#FFFFFF' } });
        render(body, html`
          <ol class="grid gap-4 text-sm">
            <li><strong>1.</strong> In your authenticator app, add an account and scan this code.
              <div class="mx-auto mt-3 w-48 rounded border border-line bg-white p-2">${raw(svg)}</div></li>
            <li><strong>2.</strong> Can’t scan? Enter this key instead:
              <div class="copy-row mt-2" translate="no"><span class="flex-1">${setup.secret.match(/.{1,4}/g).join(' ')}</span>
                <button type="button" class="btn-quiet btn-sm" data-copy-secret>Copy</button></div></li>
            <li><strong>3.</strong> Enter the 6-digit code the app shows.
              <input class="input figure mt-2 text-center text-xl tracking-[0.3em]" name="code" inputmode="numeric" pattern="[0-9]{6}"
                maxlength="6" autocomplete="one-time-code" placeholder="000000" required /></li>
          </ol>`);
        body.querySelector('[data-copy-secret]').addEventListener('click', () => copy(setup.secret, 'Key copied'));
        body.querySelector('[name=code]').focus();
        submit.textContent = 'Turn on';
        step = 'code';
        return false;                                            // keep the dialog open
      }
      if (step === 'code') {
        const res = await api.auth.twoFactorEnable(v.code);
        render(body, codesBlock(res.recovery_codes));
        wireCodes(dlg, res.recovery_codes);
        dlg.querySelector('[data-close]')?.remove();            // they must acknowledge the codes
        submit.textContent = 'I’ve saved my codes';
        step = 'done';
        toast('Two-factor sign-in is on.');
        return false;
      }
      return true;
    },
  });
}

async function withCode(title, label, danger, call, after) {
  let shown = false;
  await openDialog({
    title, submitLabel: label, danger,
    body: html`
      <div class="field"><label class="label" for="wc-pw">Password</label>
        <input class="input" id="wc-pw" name="password" type="password" autocomplete="current-password" required /></div>
      <div class="field"><label class="label" for="wc-code">Code from your authenticator app</label>
        <input class="input figure" id="wc-code" name="code" autocomplete="one-time-code" required placeholder="000000 or a recovery code" /></div>`,
    onSubmit: async (v, dlg) => {
      if (shown) return true;
      const res = await call(v.password, v.code);
      if (res?.recovery_codes) {
        render(dlg.querySelector('[data-body]'), codesBlock(res.recovery_codes));
        wireCodes(dlg, res.recovery_codes);
        dlg.querySelector('button[type=submit]').textContent = 'I’ve saved my codes';
        shown = true;
        return false;
      }
      after?.();
      return true;
    },
  });
}

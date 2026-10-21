import { api, ApiError } from '../../lib/api.js';
import { $, html, render } from '../../lib/dom.js';
import { authLayout, processAside } from './layout.js';
import { passwordToggles } from '../../lib/password.js';

const next = new URLSearchParams(location.search).get('next');
const notice = new URLSearchParams(location.search).get('reset') === '1'
  ? html`<p class="rounded border border-settled/40 bg-settled/10 p-3 text-sm" role="status">Password updated. Sign in with your new password.</p>` : '';

authLayout({
  title: 'Sign in',
  intro: 'Use the email and password you registered with.',
  aside: processAside,
  form: html`<div id="step">${notice}
    <form id="login" class="mt-4 grid gap-4" novalidate>
      <div class="field"><label class="label" for="email">Email</label>
        <input class="input" id="email" name="email" type="email" autocomplete="email" required /></div>
      <div class="field">
        <div class="flex items-baseline justify-between"><label class="label" for="password">Password</label>
          <a class="text-xs text-muted hover:text-ink hover:underline" href="/forgot-password.html">Forgot password?</a></div>
        <input class="input" id="password" name="password" type="password" autocomplete="current-password" required /></div>
      <p id="error" class="error-text" role="alert" hidden></p>
      <button class="btn-primary w-full py-2.5" type="submit">Sign in</button>
      <p class="text-sm text-muted">New here? <a class="btn-link" href="/signup.html">Create an account</a></p>
    </form></div>`,
});

passwordToggles();

// Already signed in? Skip the form.
api.auth.me({ quiet401: true }).then((u) => go(u)).catch(() => {});

function go(user) {
  const safeNext = next && next.startsWith('/') && !next.startsWith('//') ? next : null;
  location.href = safeNext || (user.is_admin ? '/admin.html' : '/app.html');
}

const fail = (form, label, ex) => {
  const err = form.querySelector('[role=alert]');
  err.textContent = ex instanceof ApiError ? ex.message : 'Sign-in failed. Please try again.';
  err.hidden = false;
  const btn = form.querySelector('button[type=submit]');
  btn.disabled = false; btn.textContent = label;
};

$('#login').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.currentTarget;
  form.querySelector('[role=alert]').hidden = true;
  if (!form.reportValidity()) return;
  const btn = form.querySelector('button[type=submit]');
  btn.disabled = true; btn.textContent = 'Signing in…';
  try {
    const res = await api.auth.login(form.email.value.trim(), form.password.value);
    if (res?.two_factor_required) return showCodeStep(res.challenge);
    go(await api.auth.me());
  } catch (ex) { fail(form, 'Sign in', ex); }
});

/** Second step when two-factor sign-in is on. */
function showCodeStep(challenge, recovery = false) {
  document.querySelector('h1').textContent = 'Two-factor sign-in';
  render('#step', html`
    <form id="code-form" class="grid gap-4" novalidate>
      <p class="text-muted">${recovery ? 'Enter one of the recovery codes you saved when you turned on two-factor sign-in. Each code works once.'
        : 'Open your authenticator app and enter the 6-digit code for Zenfort Markets.'}</p>
      <div class="field"><label class="label" for="code">${recovery ? 'Recovery code' : 'Authentication code'}</label>
        <input class="input figure text-center text-2xl tracking-[0.3em]" id="code" name="code" required autocomplete="one-time-code"
          ${recovery ? html`maxlength="9" placeholder="XXXX-XXXX" autocapitalize="characters"` : html`inputmode="numeric" pattern="[0-9]{6}" maxlength="6" placeholder="000000"`} /></div>
      <p class="error-text" role="alert" hidden></p>
      <button class="btn-primary w-full py-2.5" type="submit">Verify</button>
      <button type="button" class="btn-link justify-self-start text-sm" data-switch>${recovery ? 'Use my authenticator app instead' : 'Use a recovery code instead'}</button>
      <a class="text-sm text-muted hover:text-ink hover:underline" href="/login.html">Start over</a>
    </form>`);
  const form = $('#code-form');
  form.code.focus();
  form.querySelector('[data-switch]').addEventListener('click', () => showCodeStep(challenge, !recovery));
  form.code.addEventListener('input', () => { if (!recovery && /^\d{6}$/.test(form.code.value)) form.requestSubmit(); });
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    form.querySelector('[role=alert]').hidden = true;
    if (!form.reportValidity()) return;
    const btn = form.querySelector('button[type=submit]');
    btn.disabled = true; btn.textContent = 'Checking…';
    try { await api.auth.loginTwoFactor(challenge, form.code.value.trim()); go(await api.auth.me()); }
    catch (ex) { fail(form, 'Verify', ex); form.code.select(); }
  });
}

import { api, ApiError } from '../../lib/api.js';
import { $, html, render } from '../../lib/dom.js';
import { authLayout, processAside } from './layout.js';

authLayout({
  title: 'Reset your password',
  intro: 'Enter the email you registered with and we’ll send you a link to choose a new password.',
  aside: processAside,
  form: html`<div id="step">
    <form id="forgot" class="grid gap-4" novalidate>
      <div class="field"><label class="label" for="email">Email</label>
        <input class="input" id="email" name="email" type="email" autocomplete="email" required /></div>
      <p class="error-text" role="alert" hidden></p>
      <button class="btn-primary w-full py-2.5" type="submit">Send reset link</button>
      <a class="text-sm text-muted hover:text-ink hover:underline" href="/login.html">Back to sign in</a>
    </form></div>`,
});

$('#forgot').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.currentTarget;
  const err = form.querySelector('[role=alert]');
  err.hidden = true;
  if (!form.reportValidity()) return;
  const btn = form.querySelector('button[type=submit]');
  btn.disabled = true; btn.textContent = 'Sending…';
  try {
    const res = await api.auth.forgotPassword(form.email.value.trim());
    render('#step', html`<div role="status" class="grid gap-4">
      <p>${res.message}</p>
      <p class="text-sm text-muted">The link expires in 30 minutes and works once. Didn’t get it? Wait a minute, check spam, then try again.</p>
      <a class="btn-quiet justify-self-start" href="/login.html">Back to sign in</a></div>`);
  } catch (ex) {
    err.textContent = ex instanceof ApiError ? ex.message : 'That didn’t work. Please try again.';
    err.hidden = false; btn.disabled = false; btn.textContent = 'Send reset link';
  }
});

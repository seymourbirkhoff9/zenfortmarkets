import { api, ApiError } from '../../lib/api.js';
import { $, html, render } from '../../lib/dom.js';
import { authLayout, processAside } from './layout.js';
import { passwordToggles } from '../../lib/password.js';

const token = new URLSearchParams(location.search).get('token');

authLayout({
  title: 'Choose a new password',
  intro: 'For your security, you’ll be signed out on every device after changing it.',
  aside: processAside,
  form: token ? html`
    <form id="reset" class="grid gap-4" novalidate>
      <div class="field"><label class="label" for="pw">New password</label>
        <input class="input" id="pw" name="new_password" type="password" autocomplete="new-password" minlength="8" required />
        <p class="hint">At least 8 characters.</p></div>
      <div class="field"><label class="label" for="pw2">Confirm new password</label>
        <input class="input" id="pw2" name="confirm" type="password" autocomplete="new-password" required /></div>
      <p class="error-text" role="alert" hidden></p>
      <button class="btn-primary w-full py-2.5" type="submit">Update password</button>
    </form>`
    : html`<div class="grid gap-4"><p>This link is incomplete. Open the link from the email again, or request a new one.</p>
      <a class="btn-primary justify-self-start" href="/forgot-password.html">Request a new link</a></div>`,
});

if (token) {
  passwordToggles();
  $('#reset').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    const err = form.querySelector('[role=alert]');
    err.hidden = true;
    if (!form.reportValidity()) return;
    if (form.new_password.value !== form.confirm.value) {
      err.textContent = 'The passwords don’t match.'; err.hidden = false; return;
    }
    const btn = form.querySelector('button[type=submit]');
    btn.disabled = true; btn.textContent = 'Updating…';
    try {
      await api.auth.resetPassword(token, form.new_password.value);
      location.href = '/login.html?reset=1';
    } catch (ex) {
      const expired = ex instanceof ApiError && ex.status === 400;
      if (expired) {
        render('#auth-body', html`<h1 class="font-serif text-3xl">This link has expired</h1>
          <p class="mt-3 text-muted">${ex.message}</p><a class="btn-primary mt-8 w-full py-2.5" href="/forgot-password.html">Request a new link</a>`);
        return;
      }
      err.textContent = ex instanceof ApiError ? ex.message : 'That didn’t work. Please try again.';
      err.hidden = false; btn.disabled = false; btn.textContent = 'Update password';
    }
  });
}

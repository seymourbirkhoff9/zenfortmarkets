import { api, ApiError } from '../../lib/api.js';
import { $, html } from '../../lib/dom.js';
import { authLayout, processAside } from './layout.js';
import { passwordToggles } from '../../lib/password.js';

const next = new URLSearchParams(location.search).get('next');

authLayout({
  title: 'Sign in',
  intro: 'Use the email and password you registered with.',
  aside: processAside,
  form: html`
    <form id="login" class="grid gap-4" novalidate>
      <div class="field"><label class="label" for="email">Email</label>
        <input class="input" id="email" name="email" type="email" autocomplete="email" required /></div>
      <div class="field"><label class="label" for="password">Password</label>
        <input class="input" id="password" name="password" type="password" autocomplete="current-password" required /></div>
      <p id="error" class="error-text" role="alert" hidden></p>
      <button class="btn-primary w-full py-2.5" type="submit">Sign in</button>
      <p class="text-sm text-muted">New here? <a class="btn-link" href="/signup.html">Create an account</a></p>
    </form>`,
});

passwordToggles();

// Already signed in? Skip the form.
api.auth.me({ quiet401: true }).then((u) => go(u)).catch(() => {});

function go(user) {
  const safeNext = next && next.startsWith('/') && !next.startsWith('//') ? next : null;
  location.href = safeNext || (user.is_admin ? '/admin.html' : '/app.html');
}

$('#login').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.currentTarget;
  const err = $('#error');
  err.hidden = true;
  if (!form.reportValidity()) return;
  const btn = form.querySelector('button[type=submit]');
  btn.disabled = true; btn.textContent = 'Signing in…';
  try {
    await api.auth.login(form.email.value.trim(), form.password.value);
    go(await api.auth.me());
  } catch (ex) {
    err.textContent = ex instanceof ApiError ? ex.message : 'Sign in failed. Try again.';
    err.hidden = false;
    btn.disabled = false; btn.textContent = 'Sign in';
  }
});

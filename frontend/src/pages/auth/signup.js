import { api, ApiError } from '../../lib/api.js';
import { $, html, render } from '../../lib/dom.js';
import { authLayout, processAside } from './layout.js';
import { passwordToggles } from '../../lib/password.js';

// Must match backend CountryEnum values.
const COUNTRIES = ['Argentina','Australia','Austria','Bangladesh','Belgium','Brazil','Cameroon','Canada','China','Denmark','Egypt','Ethiopia','Finland','France','Germany','Ghana','Greece','India','Indonesia','Ireland','Italy','Ivory Coast','Japan','Kenya','Malaysia','Mexico','Netherlands','New Zealand','Nigeria','Norway','Pakistan','Philippines','Poland','Portugal','Russia','Saudi Arabia','Senegal','Singapore','South Africa','Spain','Sweden','Switzerland','Tanzania','Thailand','Turkey','Ukraine','United Arab Emirates','United Kingdom','United States','Vietnam','Zambia','Zimbabwe'];

const ref = new URLSearchParams(location.search).get('ref') || '';

authLayout({
  title: 'Create an account',
  intro: 'Every balance is kept in US dollars. Crypto is only how money arrives and leaves.',
  aside: processAside,
  form: html`
    <form id="signup" class="grid gap-4" novalidate>
      <div class="field"><label class="label" for="full_name">Full name</label>
        <input class="input" id="full_name" name="full_name" autocomplete="name" required /></div>
      <div class="field"><label class="label" for="email">Email</label>
        <input class="input" id="email" name="email" type="email" autocomplete="email" required /></div>
      <div class="grid gap-4 sm:grid-cols-2">
        <div class="field"><label class="label" for="country">Country</label>
          <select class="input" id="country" name="country" required>
            <option value="">Choose…</option>
            ${COUNTRIES.map((c) => html`<option>${c}</option>`)}
          </select></div>
        <div class="field"><label class="label" for="phone">Phone <span class="font-normal text-muted">(optional)</span></label>
          <input class="input" id="phone" name="phone" type="tel" autocomplete="tel" /></div>
      </div>
      <div class="field"><label class="label" for="password">Password</label>
        <input class="input" id="password" name="password" type="password" autocomplete="new-password" minlength="8" required />
        <p class="hint">At least 8 characters.</p></div>
      <div class="field"><label class="label" for="confirm_password">Confirm password</label>
        <input class="input" id="confirm_password" name="confirm_password" type="password" autocomplete="new-password" required /></div>
      <div class="field"><label class="label" for="referral_code">Referral code <span class="font-normal text-muted">(optional)</span></label>
        <input class="input uppercase" id="referral_code" name="referral_code" maxlength="8" value="${ref}" /></div>
      <label class="flex items-start gap-2 text-sm">
        <input type="checkbox" id="accept_terms" name="accept_terms" required class="mt-1 h-4 w-4 accent-settled" />
        <span>I agree to the <a class="btn-link" href="/terms.html" target="_blank" rel="noopener">Terms of Service</a>
          and <a class="btn-link" href="/privacy.html" target="_blank" rel="noopener">Privacy Policy</a>, and I’ve read the
          <a class="btn-link" href="/risk.html" target="_blank" rel="noopener">Risk Disclosure</a>.</span></label>
      <p id="error" class="error-text" role="alert" hidden></p>
      <button class="btn-primary w-full py-2.5" type="submit">Create account</button>
      <p class="text-sm text-muted">Already registered? <a class="btn-link" href="/login.html">Sign in</a></p>
    </form>`,
});

passwordToggles();

$('#signup').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.currentTarget;
  const err = $('#error');
  err.hidden = true;
  form.querySelectorAll('[aria-invalid]').forEach((el) => el.removeAttribute('aria-invalid'));
  if (!form.reportValidity()) return;
  if (form.password.value !== form.confirm_password.value) {
    form.confirm_password.setAttribute('aria-invalid', 'true');
    err.textContent = 'The passwords don’t match.'; err.hidden = false; return;
  }
  const payload = Object.fromEntries(new FormData(form).entries());
  Object.keys(payload).forEach((k) => { if (k !== 'password' && k !== 'confirm_password') payload[k] = payload[k].trim(); });
  if (!payload.phone) delete payload.phone;
  if (!payload.referral_code) delete payload.referral_code;
  payload.accept_terms = form.accept_terms.checked;

  const btn = form.querySelector('button[type=submit]');
  btn.disabled = true; btn.textContent = 'Creating account…';
  try {
    await api.auth.signup(payload);
    render('#root main > div', html`
      <div role="status">
        <h1 class="font-serif text-3xl">Check your inbox</h1>
        <p class="mt-3 text-muted">We sent a confirmation link to <strong class="text-ink">${payload.email}</strong>. You can sign in now and confirm later.</p>
        <a class="btn-primary mt-8 w-full py-2.5" href="/login.html">Sign in</a>
      </div>`);
  } catch (ex) {
    err.textContent = ex instanceof ApiError ? ex.message : 'Sign up failed. Try again.';
    err.hidden = false;
    Object.keys(ex.fields || {}).forEach((f) => form.querySelector(`[name="${f}"]`)?.setAttribute('aria-invalid', 'true'));
    btn.disabled = false; btn.textContent = 'Create account';
  }
});

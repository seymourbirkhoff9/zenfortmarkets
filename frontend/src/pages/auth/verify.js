import { api } from '../../lib/api.js';
import { html, render } from '../../lib/dom.js';
import { authLayout, processAside } from './layout.js';

const token = new URLSearchParams(location.search).get('token');
authLayout({ title: 'Confirming your email…', aside: processAside, form: html`<div id="result" class="text-muted">One moment.</div>` });

(async () => {
  const heading = document.querySelector('h1');
  if (!token) {
    heading.textContent = 'This link is incomplete';
    render('#result', html`<p>Open the link from the email again, or request a new one from Settings.</p>`);
    return;
  }
  try {
    await api.auth.verifyEmail(token);
    heading.textContent = 'Email confirmed';
    render('#result', html`<p>Thanks. We’ll use this address for deposit and withdrawal updates.</p>
      <a class="btn-primary mt-8 w-full py-2.5" href="/app.html">Go to your account</a>`);
  } catch (err) {
    heading.textContent = 'This link has expired';
    render('#result', html`<p>${err.message} Sign in and request a new link from Settings.</p>
      <a class="btn-primary mt-8 w-full py-2.5" href="/login.html">Sign in</a>`);
  }
})();

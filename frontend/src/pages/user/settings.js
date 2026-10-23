import { api } from '../../lib/api.js';
import { $, html, on, render } from '../../lib/dom.js';
import { date } from '../../lib/format.js';
import { confirmDialog, filePicker, fileToSquareDataUrl, setBusy, toast, toastError } from '../../lib/ui.js';
import { avatar } from '../../lib/avatar.js';
import { refreshUser, session } from '../../session.js';
import { pageHeader } from '../common.js';
import { passwordToggles } from '../../lib/password.js';
import { twoFactorSection } from './twofactor.js';
import { CURRENCIES } from '../../lib/currencies.js';

const KYC = {
  UNVERIFIED: ['pill-neutral', 'Not started'],
  PENDING: ['pill-pending', 'In review'],
  VERIFIED: ['pill-settled', 'Verified'],
  REJECTED: ['pill-rejected', 'Needs a new document'],
};

const section = (id, title, intro, body) => html`
  <section class="panel grid gap-6 p-6 md:grid-cols-[16rem_1fr]" aria-labelledby="${id}">
    <div><h2 id="${id}" class="panel-title">${title}</h2><p class="mt-1 text-sm text-muted">${intro}</p></div>
    <div>${body}</div>
  </section>`;

export default async function settings(outlet) {
  const u = await refreshUser();
  const [kCls, kText] = KYC[u.kyc_status];
  const ro = Boolean(u.impersonated_by);
  render(outlet, html`
    ${pageHeader('Settings', ro ? 'View only: you’re viewing this account as an admin.' : '')}
    <fieldset class="grid gap-5" ${ro ? 'disabled' : ''}>
      ${section('profile-h', 'Profile', 'Your name appears on transfers you send.', html`
        <div class="mb-6 flex items-center gap-4">
          <span id="photo-preview">${avatar(u, 'lg')}</span>
          <div class="grid gap-2">
            <div class="flex flex-wrap gap-2">
              <label class="btn-quiet btn-sm cursor-pointer">
                <input id="photo-input" type="file" accept="image/png,image/jpeg,image/webp" class="sr-only" />
                <span id="photo-label">${u.avatar_url ? 'Change photo' : 'Add a photo'}</span></label>
              <button type="button" class="btn-quiet btn-sm" data-action="remove-photo" ${u.avatar_url ? '' : 'hidden'}>Remove</button>
            </div>
            <p class="hint">Square images look best. We crop and resize it for you.</p>
          </div>
        </div>
        <form id="profile" class="grid max-w-md gap-4">
          <div class="field"><label class="label" for="s-name">Full name</label><input class="input" id="s-name" name="full_name" value="${u.full_name}" required /></div>
          <div class="field"><label class="label" for="s-phone">Phone</label><input class="input" id="s-phone" name="phone" type="tel" value="${u.phone || ''}" /></div>
          <div class="field"><label class="label" for="s-currency">Display currency</label>
            <select class="input" id="s-currency" name="display_currency">
              <option value="">USD (default)</option>
              ${CURRENCIES.map((c) => html`<option value="${c.code}" ${u.display_currency === c.code ? 'selected' : ''}>${c.code} - ${c.name}</option>`)}
            </select>
            <p class="hint">Choose your preferred currency for displaying balances and amounts.</p></div>
          <div class="field"><span class="label">Email</span>
            <p class="text-sm">${u.email} ${u.email_verified ? html`<span class="pill-settled ml-1">Confirmed</span>`
              : html`<span class="pill-pending ml-1">Not confirmed</span> <button type="button" class="btn-link ml-2" data-action="resend">Send link</button>`}</p></div>
          <p class="hint">Member since ${date(u.created_at)}. Country: ${u.country || '—'}.</p>
          <button class="btn-primary justify-self-start">Save profile</button>
        </form>`)}

      ${section('kyc-h', 'Identity verification', 'Required before your first withdrawal. Upload a passport, national ID or driver’s licence.', html`
        <div class="grid max-w-md gap-4">
          <p>Status: <span class="${kCls}">${kText}</span></p>
          ${u.kyc_status === 'REJECTED' && u.kyc_rejection_reason ? html`<p class="rounded border border-rejected/30 bg-rejected/5 p-3 text-sm">What to fix: ${u.kyc_rejection_reason}</p>` : ''}
          ${['UNVERIFIED', 'REJECTED'].includes(u.kyc_status) ? html`
            <form id="kyc" class="grid gap-3">
              <div class="field"><label class="label" for="kyc-file">ID document</label>
                <input class="input text-sm" id="kyc-file" type="file" accept="image/png,image/jpeg,image/webp,application/pdf" required />
                <p class="hint">A clear photo with all four corners visible, or a PDF under 1.4 MB.</p>
                <div id="kyc-preview" hidden></div></div>
              <button class="btn-primary justify-self-start">Submit for review</button>
            </form>`
          : u.kyc_status === 'PENDING' ? html`<p class="text-sm text-muted">An operator is reviewing your document. You’ll get a notification when it’s done.</p>`
          : html`<p class="text-sm text-muted">You can withdraw to any published payout method.</p>`}
        </div>`)}

      ${section('pw-h', 'Password', 'Use at least 8 characters.', html`
        <form id="password" class="grid max-w-md gap-4">
          <div class="field"><label class="label" for="pw-cur">Current password</label><input class="input" id="pw-cur" name="current_password" type="password" autocomplete="current-password" required /></div>
          <div class="field"><label class="label" for="pw-new">New password</label><input class="input" id="pw-new" name="new_password" type="password" autocomplete="new-password" minlength="8" required /></div>
          <button class="btn-primary justify-self-start">Change password</button>
        </form>`)}

      ${section('tf-h', 'Two-factor sign-in', 'Adds a 6-digit code from your phone when you sign in, so a stolen password isn’t enough.',
        html`<div id="twofactor" class="grid max-w-md gap-3"><div class="skeleton h-5 w-40"></div></div>`)}

      ${section('close-h', 'Close account', 'Withdraw your balance first. Your transaction history is kept for record-keeping.', html`
        <button class="btn-danger" data-action="close">Close my account</button>`)}
    </fieldset>`);

  passwordToggles(outlet);
  twoFactorSection(outlet.querySelector('#twofactor'), ro);

  on(outlet, 'submit', '#profile', async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector('button:not([type=button])');
    setBusy(btn, true);
    try { 
      await api.auth.updateMe({ 
        full_name: e.target.full_name.value.trim(), 
        phone: e.target.phone.value.trim(),
        display_currency: e.target.display_currency.value
      }); 
      await refreshUser(); 
      toast('Profile saved.'); 
    }
    catch (err) { toastError(err); } finally { setBusy(btn, false); }
  });

  const getDoc = $('#kyc', outlet) ? filePicker(outlet, { inputSel: '#kyc-file', previewSel: '#kyc-preview', allowPdf: true }) : null;
  on(outlet, 'submit', '#kyc', async (e) => {
    e.preventDefault();
    const doc = getDoc?.();
    if (!doc) return toast('Choose a document first.', 'warn');
    const btn = e.target.querySelector('button');
    setBusy(btn, true, 'Uploading…');
    try { await api.auth.submitKyc(doc); toast('Document submitted for review.'); settings(fresh(outlet)); }
    catch (err) { toastError(err); setBusy(btn, false); }
  });

  on(outlet, 'submit', '#password', async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector('button');
    setBusy(btn, true);
    try {
      await api.auth.changePassword({ current_password: e.target.current_password.value, new_password: e.target.new_password.value });
      e.target.reset(); toast('Password changed.');
    } catch (err) { toastError(err); } finally { setBusy(btn, false); }
  });

  // ── Profile photo ──
  const showPhoto = (user) => {
    session.user = user;
    render(outlet.querySelector('#photo-preview'), avatar(user, 'lg'));
    outlet.querySelector('#photo-label').textContent = user.avatar_url ? 'Change photo' : 'Add a photo';
    outlet.querySelector('[data-action="remove-photo"]').hidden = !user.avatar_url;
    window.dispatchEvent(new CustomEvent('zf:user-updated', { detail: user }));
  };
  on(outlet, 'change', '#photo-input', async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    const label = outlet.querySelector('#photo-label');
    label.textContent = 'Uploading…';
    try { showPhoto(await api.auth.uploadAvatar(await fileToSquareDataUrl(file))); toast('Photo updated.'); }
    catch (err) { toastError(err); label.textContent = session.user.avatar_url ? 'Change photo' : 'Add a photo'; }
  });
  on(outlet, 'click', '[data-action="remove-photo"]', async () => {
    try { showPhoto(await api.auth.removeAvatar()); toast('Photo removed.'); } catch (err) { toastError(err); }
  });

  on(outlet, 'click', '[data-action="resend"]', async () => {
    try { await api.auth.resendVerification(); toast('Confirmation email sent.'); } catch (err) { toastError(err); }
  });

  on(outlet, 'click', '[data-action="close"]', async () => {
    const ok = await confirmDialog({ title: 'Close your account?', danger: true, confirmLabel: 'Close account',
      message: 'You’ll be signed out and won’t be able to sign in again. This can’t be undone.' });
    if (!ok) return;
    try { await api.auth.closeAccount(); location.href = '/'; } catch (err) { toastError(err); }
  });
}

/** Re-render into a clean outlet so listeners don't stack. */
function fresh(outlet) {
  const el = outlet.cloneNode(false);
  outlet.replaceWith(el);
  return el;
}

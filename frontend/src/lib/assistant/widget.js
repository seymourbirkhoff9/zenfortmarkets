/**
 * Support assistant: a chat panel that answers common questions from kb.js, checks a
 * signed-in customer's live status, and hands complex issues to the support team
 * (POST /api/support/requests, which emails support with the conversation).
 * No third-party service and no API keys: conversations stay between the visitor and us.
 */
import { api } from '../api.js';
import { html, render } from '../dom.js';
import { money, waited } from '../format.js';
import { icon } from '../icons.js';
import { STARTERS, TOPICS } from './kb.js';
import { match } from './match.js';

const SUPPORT_EMAIL = 'support@zenfortmarkets.online';
const byId = Object.fromEntries(TOPICS.map((t) => [t.id, t]));

export function mountAssistant({ user = null } = {}) {
  if (document.getElementById('zf-assistant')) return;
  const transcript = [];
  let misses = 0;
  let me = user;

  const root = document.createElement('div');
  root.id = 'zf-assistant';
  render(root, html`
    <button id="zfa-launch" class="fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-full bg-navy px-4 py-3 text-sm font-semibold text-navy-fg shadow-lg hover:opacity-90"
      aria-expanded="false" aria-controls="zfa-panel">${icon('chat')}<span>Help</span></button>
    <section id="zfa-panel" role="dialog" aria-label="Support assistant" hidden
      class="fixed inset-0 z-[55] flex flex-col bg-surface shadow-2xl sm:inset-auto sm:bottom-20 sm:right-4 sm:h-[min(36rem,calc(100dvh-7rem))] sm:w-[24rem] sm:rounded-lg sm:border sm:border-line">
      <header class="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
        <div class="flex items-center gap-2.5">
          <span class="grid h-8 w-8 place-items-center rounded bg-navy font-serif text-navy-fg">Z</span>
          <div><p class="text-sm font-semibold">Zenfort help</p><p class="text-xs text-muted">Instant answers. A person for anything else.</p></div>
        </div>
        <button type="button" id="zfa-close" class="rounded p-1.5 text-muted hover:bg-sunken hover:text-ink" aria-label="Close help">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
      </header>
      <div id="zfa-log" class="flex-1 space-y-3 overflow-y-auto overscroll-contain px-4 py-4" role="log" aria-live="polite"></div>
      <form id="zfa-form" class="flex gap-2 border-t border-line p-3">
        <label for="zfa-input" class="sr-only">Type your question</label>
        <input id="zfa-input" class="input py-2" autocomplete="off" maxlength="500" placeholder="Type your question…" />
        <button class="btn-primary px-3" aria-label="Send">${icon('send', 'h-4 w-4')}</button>
      </form>
    </section>`);
  document.body.append(root);

  const panel = root.querySelector('#zfa-panel'), launch = root.querySelector('#zfa-launch');
  const log = root.querySelector('#zfa-log'), form = root.querySelector('#zfa-form'), input = root.querySelector('#zfa-input');
  let greeted = false;

  const scroll = () => { log.scrollTop = log.scrollHeight; };
  const bubble = (who, content) => {
    const el = document.createElement('div');
    el.className = who === 'you' ? 'ml-8 rounded-lg rounded-br-sm bg-navy px-3 py-2 text-sm text-navy-fg' : 'mr-6 grid gap-2 text-sm';
    render(el, who === 'you' ? html`${content}` : html`<div class="rounded-lg rounded-bl-sm bg-sunken px-3 py-2">${content}</div>`);
    log.append(el); scroll();
    return el;
  };
  const chips = (items) => {
    const el = document.createElement('div');
    el.className = 'flex flex-wrap gap-1.5';
    render(el, html`${items.map(([label, val, kind]) => kind === 'link'
      ? html`<a class="rounded-full border border-line bg-surface px-3 py-1 text-xs font-medium hover:border-brass" href="${val}">${label}</a>`
      : html`<button type="button" class="rounded-full border border-line bg-surface px-3 py-1 text-xs font-medium hover:border-brass" data-ask="${val}">${label}</button>`)}`);
    log.append(el); scroll();
  };
  const say = (text, extra = []) => { transcript.push({ who: 'assistant', text }); bubble('bot', text); if (extra.length) chips(extra); };

  function greet() {
    if (greeted) return; greeted = true;
    say(me ? `Hi ${me.full_name.split(' ')[0]}! What can I help you with?` : 'Hi! What can I help you with?');
    chips(STARTERS.map(([label, id]) => [label, `#${id}`]));
  }

  // ── Live checks for signed-in customers ──
  async function live(kind) {
    if (!me) return 'Sign in and ask again, and I can check this for your account.';
    try {
      if (kind === 'kyc') {
        const map = { UNVERIFIED: 'You haven’t uploaded an ID document yet.', PENDING: 'Your ID document is waiting for review.',
          VERIFIED: 'Your identity is verified, so withdrawals are available.',
          REJECTED: `Your last document was rejected${me.kyc_rejection_reason ? `: “${me.kyc_rejection_reason}”` : ''}. Upload a new one in Settings.` };
        return `On your account: ${map[me.kyc_status] || ''}`;
      }
      const d = await api.me.dashboard();
      if (kind === 'balance') {
        const b = Object.fromEntries(d.wallets.map((w) => [w.wallet_type, w.balance]));
        return `On your account: Main ${money(b.main)}, Profit ${money(b.profit)}.`;
      }
      const type = kind === 'deposits' ? 'deposit' : 'withdrawal';
      const pending = d.pending.filter((t) => t.tx_type === type);
      if (!pending.length) return `You have no ${type}s waiting for review right now.`;
      return `On your account: ${pending.map((t) => `${money(t.amount)} via ${t.gateway_name}, waiting ${waited(t.created_at)}`).join('; ')}.`;
    } catch { return ''; }
  }

  async function answer(topic) {
    let text = topic.answer;
    if (topic.live) { const extra = await live(topic.live); if (extra) text = `${extra} ${text}`; }
    const extra = (topic.links || []).map(([l, h]) => [l, h, 'link']);
    if (topic.escalate) extra.push(['Contact support', '#escalate']);
    else extra.push(['That didn’t help', '#escalate-soft']);
    say(text, extra);
  }

  async function ask(text) {
    const q = text.trim();
    if (!q) return;
    transcript.push({ who: 'you', text: q });
    bubble('you', q);
    const hit = match(q);
    if (hit) { misses = 0; return answer(hit.topic); }
    misses += 1;
    if (misses >= 2) return escalateForm('I’m not able to answer that one. Our support team can help.');
    say('I’m not sure I understood. Could you put it another way? Or pick a topic:', [
      ...STARTERS.slice(0, 4).map(([l, id]) => [l, `#${id}`]), ['Contact support', '#escalate']]);
  }

  // ── Hand-off to a person ──
  function escalateForm(intro = 'I’ll pass this to our support team. They reply by email, usually within a day.') {
    say(intro);
    const lastQuestion = [...transcript].reverse().find((l) => l.who === 'you')?.text || '';
    const box = document.createElement('form');
    box.className = 'mr-6 grid gap-2 rounded-lg border border-line p-3 text-sm';
    render(box, html`
      <label class="grid gap-1"><span class="text-xs font-medium">Your name</span><input class="input py-1.5" name="name" required maxlength="120" value="${me?.full_name || ''}" /></label>
      <label class="grid gap-1"><span class="text-xs font-medium">Email for the reply</span><input class="input py-1.5" name="email" type="email" required value="${me?.email || ''}" /></label>
      <label class="grid gap-1"><span class="text-xs font-medium">What’s the problem?</span>
        <textarea class="input py-1.5" name="message" rows="3" required minlength="5" maxlength="4000">${lastQuestion}</textarea></label>
      <input name="website" tabindex="-1" autocomplete="off" class="hidden" aria-hidden="true" />
      <p class="text-xs text-muted">This conversation is included so you don’t have to repeat yourself. Never share your password or codes.</p>
      <p class="error-text text-xs" role="alert" hidden></p>
      <button class="btn-primary btn-sm justify-self-start">Send to support</button>`);
    log.append(box); scroll();
    box.querySelector('[name=name]').focus();
    box.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!box.reportValidity()) return;
      const btn = box.querySelector('button'), err = box.querySelector('[role=alert]');
      btn.disabled = true; btn.textContent = 'Sending…'; err.hidden = true;
      const v = Object.fromEntries(new FormData(box).entries());
      try {
        const res = await api.support.send({ ...v, transcript: transcript.slice(-20), page: location.pathname + location.hash });
        box.remove();
        say(res.emailed
          ? `Sent. Your reference is ${res.reference}. We’ll reply to ${v.email}.`
          : `Saved with reference ${res.reference}, but our email system didn’t confirm delivery. If you don’t hear back within a day, email ${SUPPORT_EMAIL} and mention the reference.`,
          [['Email support directly', `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(`Support ${res.reference}`)}`, 'link']]);
      } catch (ex) {
        err.textContent = `${ex.message} You can also email ${SUPPORT_EMAIL}.`;
        err.hidden = false; btn.disabled = false; btn.textContent = 'Send to support';
      }
    });
  }

  // ── Wiring ──
  const open = () => {
    panel.hidden = false; launch.setAttribute('aria-expanded', 'true');
    launch.classList.add('max-sm:hidden');
    greet(); input.focus(); scroll();
  };
  const close = () => { panel.hidden = true; launch.setAttribute('aria-expanded', 'false'); launch.classList.remove('max-sm:hidden'); launch.focus(); };
  launch.addEventListener('click', () => (panel.hidden ? open() : close()));
  root.querySelector('#zfa-close').addEventListener('click', close);
  panel.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });
  form.addEventListener('submit', (e) => { e.preventDefault(); const q = input.value; input.value = ''; ask(q); });
  log.addEventListener('click', (e) => {
    const b = e.target.closest('[data-ask]');
    if (!b) return;
    const v = b.dataset.ask;
    if (v === '#escalate') { transcript.push({ who: 'you', text: 'Contact support' }); bubble('you', 'Contact support'); return escalateForm(); }
    if (v === '#escalate-soft') { transcript.push({ who: 'you', text: 'That didn’t help' }); bubble('you', 'That didn’t help'); return escalateForm('Sorry about that. Tell our support team what’s going on and they’ll help.'); }
    const t = byId[v.slice(1)];
    if (t) { transcript.push({ who: 'you', text: b.textContent }); bubble('you', b.textContent); answer(t); }
  });

  // Signed-in status (public pages): personalises answers and pre-fills the support form.
  if (!me) api.auth.me({ quiet401: true }).then((u) => { me = u; }).catch(() => {});
  return { open };
}

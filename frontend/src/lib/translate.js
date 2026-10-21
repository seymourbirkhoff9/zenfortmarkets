/**
 * Page translation via Google's free Website Translator.
 *
 * Privacy/performance: Google's script is loaded ONLY after a visitor picks a language
 * (or on later pages, if they already chose one). The choice lives in Google's own
 * `googtrans` cookie, so it carries across pages. Amounts, addresses and hashes are
 * marked "notranslate" (see render() in dom.js) so they're never altered.
 */
import { html, render } from './dom.js';
import { icon } from './icons.js';

export const LANGUAGES = [
  ['en', 'English'], ['fr', 'Français'], ['es', 'Español'], ['pt', 'Português'], ['de', 'Deutsch'], ['it', 'Italiano'],
  ['nl', 'Nederlands'], ['ar', 'العربية'], ['zh-CN', '中文 (简体)'], ['hi', 'हिन्दी'], ['ru', 'Русский'], ['tr', 'Türkçe'],
  ['ja', '日本語'], ['ko', '한국어'], ['id', 'Bahasa Indonesia'], ['vi', 'Tiếng Việt'], ['pl', 'Polski'], ['uk', 'Українська'],
  ['sw', 'Kiswahili'], ['yo', 'Yorùbá'], ['ig', 'Igbo'], ['ha', 'Hausa'], ['am', 'አማርኛ'], ['zu', 'isiZulu'],
];

const cookieDomains = () => {
  const h = location.hostname;
  return h === 'localhost' || /^[\d.]+$/.test(h) ? [''] : ['', `; domain=${h}`, `; domain=.${h.split('.').slice(-2).join('.')}`, `; domain=.${h}`];
};

export function currentLanguage() {
  const m = document.cookie.match(/(?:^|;\s*)googtrans=\/[^/]+\/([^;]+)/);
  return m ? decodeURIComponent(m[1]) : 'en';
}

function setCookie(lang) {
  const expire = lang === 'en' ? '; expires=Thu, 01 Jan 1970 00:00:00 GMT' : '; max-age=31536000';
  cookieDomains().forEach((d) => { document.cookie = `googtrans=${lang === 'en' ? '' : `/en/${lang}`}; path=/${d}${expire}`; });
}

let loading = null;
function loadGoogle() {
  if (loading) return loading;
  loading = new Promise((resolve, reject) => {
    const holder = document.createElement('div');
    holder.id = 'google_translate_element';
    holder.hidden = true;
    document.body.append(holder);
    window.zfTranslateInit = () => {
      // eslint-disable-next-line no-undef
      new google.translate.TranslateElement({ pageLanguage: 'en', autoDisplay: false }, 'google_translate_element');
      resolve();
    };
    const s = document.createElement('script');
    s.src = 'https://translate.google.com/translate_a/element.js?cb=zfTranslateInit';
    s.async = true;
    s.onerror = () => reject(new Error('Translation isn’t available right now. Check your connection and try again.'));
    document.head.append(s);
    setTimeout(() => reject(new Error('Translation is taking too long. Please try again.')), 15000);
  });
  return loading;
}

export async function setLanguage(lang) {
  setCookie(lang);
  location.reload();                         // Google applies the cookie as the page loads
}

/** Call once per page: if a language was chosen earlier, translate this page too. */
export function initTranslation() {
  if (currentLanguage() !== 'en') {
    loadGoogle().catch(() => {
      setCookie('en');
      import('./ui.js').then(({ toast }) => toast('Translation isn’t available right now, so the page is shown in English.', 'warn'));
    });
  }
}

/** Globe button + language menu. */
export const languageButton = () => html`
  <div class="relative" data-lang-root>
    <button type="button" class="flex items-center gap-1 rounded p-2 text-muted hover:bg-sunken hover:text-ink" data-lang-toggle
      aria-haspopup="true" aria-expanded="false" aria-label="Translate this page" title="Translate this page">
      ${icon('globe')}<span class="hidden text-xs font-semibold uppercase xl:inline">${currentLanguage().split('-')[0]}</span></button>
    <div class="panel absolute right-0 top-11 z-40 w-60 p-1.5 shadow-xl" data-lang-menu hidden>
      <p class="px-3 pb-1 pt-2 text-xs text-muted">Translate this page (by Google Translate)</p>
      <ul class="max-h-72 overflow-y-auto" translate="no">${LANGUAGES.map(([code, name]) => html`<li>
        <button type="button" class="nav-link w-full justify-between ${code === currentLanguage() ? 'text-ink' : ''}" data-lang="${code}" lang="${code}">
          <span>${name}</span>${code === currentLanguage() ? html`<span aria-label="current">✓</span>` : ''}</button></li>`)}</ul>
    </div>
  </div>`;

export function wireLanguageButtons(root = document) {
  root.querySelectorAll('[data-lang-root]').forEach((wrap) => {
    const btn = wrap.querySelector('[data-lang-toggle]'), menu = wrap.querySelector('[data-lang-menu]');
    const close = () => { menu.hidden = true; btn.setAttribute('aria-expanded', 'false'); };
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      menu.hidden = !menu.hidden;
      btn.setAttribute('aria-expanded', String(!menu.hidden));
      if (!menu.hidden) menu.querySelector('[data-lang]')?.focus();
    });
    menu.addEventListener('click', (e) => {
      const b = e.target.closest('[data-lang]');
      if (!b) return;
      close();
      if (b.dataset.lang !== currentLanguage()) setLanguage(b.dataset.lang);
    });
    document.addEventListener('click', (e) => { if (!wrap.contains(e.target)) close(); });
    wrap.addEventListener('keydown', (e) => { if (e.key === 'Escape') { close(); btn.focus(); } });
  });
}

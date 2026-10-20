import '../../styles.css';
import { html, raw, render } from '../../lib/dom.js';
import { SITE } from '../../site.js';

export const footer = () => html`
  <footer class="border-t border-line">
    <div class="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-8 text-sm text-muted sm:flex-row sm:items-center sm:justify-between">
      <p>${SITE.name} is an educational demo. Do not send real funds.</p>
      <nav aria-label="Legal" class="flex flex-wrap gap-x-5 gap-y-2">
        <a class="hover:text-ink hover:underline" href="/terms.html">Terms of Service</a>
        <a class="hover:text-ink hover:underline" href="/privacy.html">Privacy Policy</a>
        <a class="hover:text-ink hover:underline" href="/risk.html">Risk Disclosure</a>
        <a class="hover:text-ink hover:underline" href="mailto:${SITE.contactEmail}">Contact</a>
      </nav>
    </div>
  </footer>`;

export const header = () => html`
  <header class="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
    <a href="/" class="flex items-center gap-2.5 font-semibold">
      <span class="grid h-8 w-8 place-items-center rounded bg-navy font-serif text-lg text-navy-fg">Z</span>${SITE.name}</a>
    <nav class="flex items-center gap-2"><a class="btn-quiet" href="/login.html">Sign in</a>
      <a class="btn-primary" href="/signup.html">Create account</a></nav>
  </header>`;

/**
 * A legal document page. `sections` is [[heading, [paragraph, …]], …]; paragraphs are plain text,
 * except entries wrapped in raw() which may contain our own trusted markup (links, lists).
 */
export function legalPage({ title, intro, sections }) {
  document.title = `${title} — ${SITE.name}`;
  render('#root', html`
    <p class="border-b border-line bg-sunken px-4 py-1.5 text-center text-xs text-muted">
      Educational demo. Balances are simulated, no real funds are held, and nothing here is investment advice.
    </p>
    ${header()}
    <main class="mx-auto max-w-3xl px-6 pb-20 pt-6">
      <p class="text-sm text-muted">Last updated ${SITE.termsUpdated} (version ${SITE.termsVersion})</p>
      <h1 class="mt-2 font-serif text-4xl">${title}</h1>
      <p class="mt-4 text-lg text-muted">${intro}</p>
      <p class="mt-6 rounded border border-pending/40 bg-pending/5 p-3 text-sm">
        Draft for review. Have these documents checked by someone qualified in ${SITE.jurisdiction} before real users rely on them.</p>
      <nav aria-label="On this page" class="mt-8 rounded border border-line bg-surface p-4 text-sm">
        <p class="font-semibold">On this page</p>
        <ol class="mt-2 grid gap-1 sm:grid-cols-2">${sections.map(([h], i) => html`<li><a class="text-muted hover:text-ink hover:underline" href="#s${i + 1}">${i + 1}. ${h}</a></li>`)}</ol>
      </nav>
      ${sections.map(([h, paras], i) => html`
        <section id="s${i + 1}" class="mt-10 scroll-mt-6">
          <h2 class="font-serif text-2xl">${i + 1}. ${h}</h2>
          ${paras.map((p) => html`<p class="mt-3 leading-relaxed">${p}</p>`)}
        </section>`)}
    </main>
    ${footer()}`);
}

export { raw, SITE };

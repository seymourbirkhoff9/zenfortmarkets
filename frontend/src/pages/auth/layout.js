import '../../styles.css';
import { html, render } from '../../lib/dom.js';
import { themeButton, wireThemeButton } from '../../lib/theme.js';

/** Two-column auth layout: form on the left, a short factual note on the right. */
export function authLayout({ title, intro, form, aside }) {
  render('#root', html`
    <p class="border-b border-line bg-sunken px-4 py-1.5 text-center text-xs text-muted">
      Demo environment. Balances are simulated and nothing here is investment advice.
    </p>
    <div class="grid min-h-[calc(100vh-29px)] lg:grid-cols-[minmax(0,1fr)_minmax(0,0.85fr)]">
      <main class="flex flex-col px-6 py-8 sm:px-12">
        <div class="flex items-center justify-between">
          <a href="/" class="flex items-center gap-2.5 font-semibold">
            <span class="grid h-8 w-8 place-items-center rounded bg-navy font-serif text-lg text-navy-fg">Z</span>Zenfort Markets
          </a>
          ${themeButton()}
        </div>
        <div class="my-auto w-full max-w-sm py-10">
          <h1 class="font-serif text-3xl">${title}</h1>
          ${intro ? html`<p class="mt-2 text-muted">${intro}</p>` : ''}
          <div class="mt-8">${form}</div>
        </div>
        <nav aria-label="Legal" class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
          <a class="hover:text-ink hover:underline" href="/terms.html">Terms</a>
          <a class="hover:text-ink hover:underline" href="/privacy.html">Privacy</a>
          <a class="hover:text-ink hover:underline" href="/risk.html">Risk Disclosure</a></nav>
      </main>
      <aside class="hidden border-l border-line bg-surface lg:flex lg:items-center lg:px-14">${aside}</aside>
    </div>`);
  wireThemeButton();
}

/** What happens to money here, step by step — the honest version. */
export const processAside = html`
  <div class="max-w-md">
    <p class="text-sm font-semibold text-muted">How money moves in this demo</p>
    <ol class="mt-6 grid gap-6">
      ${[
        ['You send crypto to an address the operator publishes', 'Pick an asset and network, then report the USD value and transaction hash.'],
        ['An operator checks it and credits your Main wallet', 'Nothing is credited automatically. Each deposit is reviewed by a person.'],
        ['Withdrawals are paid out by hand', 'Funds are held while pending, and returned in full if the request is rejected.'],
      ].map(([t, d], i) => html`
        <li class="grid grid-cols-[2rem_1fr] gap-3">
          <span class="figure grid h-8 w-8 place-items-center rounded-full border border-line text-sm">${i + 1}</span>
          <span><span class="block font-medium">${t}</span><span class="mt-1 block text-sm text-muted">${d}</span></span>
        </li>`)}
    </ol>
  </div>`;

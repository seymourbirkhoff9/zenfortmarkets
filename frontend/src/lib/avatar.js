import { html } from './dom.js';

const SIZES = { sm: 'h-8 w-8 text-sm', md: 'h-10 w-10 text-sm', lg: 'h-20 w-20 text-2xl' };
export const initials = (name = '') =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((s) => s[0].toUpperCase()).join('') || '?';

/** Profile photo if the user has one, otherwise their initials. Decorative: the name is always shown next to it. */
export const avatar = (user, size = 'sm') => (user?.avatar_url
  ? html`<img src="${user.avatar_url}" alt="" class="${SIZES[size]} shrink-0 rounded-full object-cover" loading="lazy" />`
  : html`<span class="${SIZES[size]} grid shrink-0 place-items-center rounded-full bg-sunken font-semibold" aria-hidden="true">${initials(user?.full_name)}</span>`);

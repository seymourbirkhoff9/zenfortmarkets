# Batch 4 — homepage, public site, branded emails, loading

## Apply

Same as before: commit, then copy the unzipped `zenfortmarkets` contents over your project
(**Merge** folders, **Replace** files). No database migration. Restart the API and `npm run dev`.

## What's new

**Homepage (4)** — animated hero: a sample statement where a pending USDT deposit is confirmed by an
operator and the balance moves ($998.40 → $1,248.40). Then a *supported networks* strip and a plans
preview, both **live from your console** (no hard-coded copies), how money moves, what makes the back
office trustworthy, an FAQ preview and a closing call to action. Sections fade in as you scroll.
Everything respects "reduce motion". No partner logos, as agreed.

**Public pages (8)** — How it works, Fees & limits (live networks and plans), Security, FAQ, About,
Contact, plus the legal pages from Batch 3. Shared header with navigation (menu on phones) and a full
footer. The Security page only claims what the code actually does, and lists what's not there yet.

**Branded emails (11)** — every email now has the brand header, a clear heading, a details table
(amount, method, address, reference…), a button into the account and a footer with the legal links.
Built with tables and inline styles so it renders in Gmail, Outlook and Apple Mail. Each email also
carries a plain-text version (better delivery, fewer spam flags).

**Loading (16)** — a branded splash ("Every move reviewed. Every dollar recorded.") appears instantly
when the app or console opens and fades as soon as the first screen is ready — never held artificially.
Page changes keep the top progress bar and skeletons from Batch 1.

**Public data API** — `GET /api/public/payment-methods` and `GET /api/public/plans`: no sign-in, safe
fields only (no deposit addresses), cached for a minute, refreshed immediately when an admin changes a
plan or payment method.

**Responsive fix** — the public header overflowed on 390 px phones; sign-in buttons now move into the
menu on small screens. All 29 pages (public, customer, admin) were measured at phone width: none scroll
sideways, and that check is now part of the browser test.

## Vercel note
The homepage and Fees page call the API for live data, so `VITE_API_BASE=https://api.zenfortmarkets.com/api`
must be set in Vercel (as described for sign-in). If it isn't, those sections simply stay hidden.

## Tests
- Backend: 30 pass (public endpoints are safe and update immediately; emails escape input and have a text version).
- Browser: 38 steps pass on the single-service setup, including the homepage animation result, live data,
  every public page, the phone menu, the splash, and the no-sideways-scroll check.

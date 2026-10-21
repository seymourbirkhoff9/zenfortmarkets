# Final batch — live-site fix, friendly errors, support assistant, translation, password reset, 2FA

## 1. Apply

1. `git add -A && git commit -m "before final batch"`
2. Unzip, open `zenfortmarkets`, **Ctrl+A**, **Ctrl+C**, paste into your project → **Merge** folders, **Replace** files.
3. Backend (from `backend`, venv active):
   ```bash
   uv pip install -r requirements.txt        # adds pyotp (two-factor codes)
   alembic upgrade head                      # adds 2FA, session and email-delivery columns
   ```
4. Frontend (from `frontend`): `npm install` (adds the QR-code library), then restart `npm run dev`.
5. Restart the API. Locally, add `DEV_OUTBOX=true` to `backend/.env` to read sent emails at
   http://localhost:3000/api/dev/outbox (reset links, support requests) without Resend.

## 2. Fix the live site (why you saw "Not found")

Your site and API are on two different domains (`*.vercel.app` and `*.onrender.com`). Browsers treat them as
unrelated sites, so the sign-in cookie can't be shared, and an API address missing `/api` returns "Not found".
The new `frontend/vercel.json` makes Vercel forward every `/api/...` request to Render behind the scenes,
so the browser only ever talks to your Vercel address.

**Vercel** (Project → Settings → Environment Variables):
- **Delete `VITE_API_BASE`** (or leave it unset). The site now calls `/api` on its own address.
- Root Directory `frontend`, Framework **Vite**, build `npm run build`, output `dist`. Redeploy.

**Render** (Environment):
```
FRONTEND_URL=https://zenfortmarkets.vercel.app
FRONTEND_ORIGIN=https://zenfortmarkets.vercel.app
COOKIE_SECURE=true
FRONTEND_DIST=
EMAIL_FROM=Zenfort Markets <onboarding@resend.dev>      # until your domain is verified (see 4)
EMAIL_REPLY_TO=support@zenfortmarkets.online
SUPPORT_EMAIL=support@zenfortmarkets.online
```
Then **Manual Deploy → Deploy latest commit** (runs the migration on start).

**Check**: open https://zenfortmarkets.vercel.app/api/health — you should see `{"status":"ok"...}` (that's
Render answering through Vercel). Then sign in. DevTools → Application → Cookies should show `zf_session`
under `zenfortmarkets.vercel.app`.

Free Render instances sleep after ~15 minutes idle; the first visit then takes up to a minute. Page loads
retry automatically and show "starting up" instead of failing. A paid instance stays awake.

## 3. After you buy zenfortmarkets.online

1. Vercel → Domains: add `zenfortmarkets.online` and `www.zenfortmarkets.online` (redirect www → apex);
   add the DNS records Vercel shows. **Nothing changes in `vercel.json`**: `/api` keeps forwarding to Render.
2. Render: set `FRONTEND_URL` and `FRONTEND_ORIGIN` to `https://zenfortmarkets.online`. CORS already allows
   localhost, `zenfortmarkets.vercel.app` (+ its preview URLs) and `zenfortmarkets.online` (+ www).
3. Update `frontend/src/site.js` → `domain: 'zenfortmarkets.online'`, `contactEmail: 'support@zenfortmarkets.online'`.

## 4. Email delivery (why admin emails didn't arrive)

The code was sending them; Resend refused them. While you send from `onboarding@resend.dev`, **Resend only
delivers to the email address of your own Resend account**. Your earlier "Identity verified" email arrived
because it went to that address. Before this batch the refusal only showed in the server log; now:
- **Email a customer** reports "Delivered to their inbox", or shows Resend's exact reason.
- **Email customers** (broadcast) records delivered/failed counts and the last error in the history.

To email everyone: Resend → **Domains → Add** `zenfortmarkets.online`, add its DNS records (at your domain
registrar), wait for **Verified**, then set on Render:
`EMAIL_FROM=Zenfort Markets <no-reply@zenfortmarkets.online>`. Replies go to `support@zenfortmarkets.online`
(set up that mailbox with your domain/email provider).

## 5. What's new

| | |
|---|---|
| Friendly errors | Offline, unreachable, timeout, starting up, server error, and gateway "Not found" all become clear messages. Page loads retry when the server is waking; actions never auto-retry. The API never answers with a bare "Not Found"/"Internal Server Error". |
| View-as countdown | Ticks every second (29:59, 29:58…); screen readers hear it once a minute. |
| Back button | "← All customers" on the customer page. |
| Admin emails | Delivered immediately with a clear result; broadcasts batched (100/request) with delivery counts. From no-reply; replies to support. |
| Help assistant | On the public site, sign-in pages and the customer app. Built in (no third party, no AI service). Understands ~30 common topics including typos; checks a signed-in customer's live deposits/withdrawals/ID status; says when it's unsure; hands off to support with the conversation (email to `SUPPORT_EMAIL`, reply-to the customer; admins also get an in-app alert). Spam-protected and rate-limited. |
| Translate | Globe button on every page, 24 languages via Google Translate, loaded only when someone picks a language. Amounts, addresses and hashes are never translated. Disclosed in the Privacy Policy. |
| Password reset | "Forgot password?" on sign-in. Link valid 30 min, works once, signs out every device. Never reveals whether an email has an account. |
| Two-factor sign-in | Settings → Two-factor: QR setup for any authenticator app, 8 one-time recovery codes (copy/download), codes can't be reused. Admins can reset it for a locked-out customer (audited). |
| Rate limits | Sign-in (10 failures / 15 min; successes don't count), reset requests, 2FA codes, support requests. |
| Sessions | Password change/reset and 2FA changes sign out other devices; this device stays signed in. |
| Fix | The theme-switch patch made the sign-up confirmation replace the logo row. Fixed. |

## 6. Tests
- Backend: 38 pass. New: friendly errors, CORS allow/deny (including look-alike domains), sign-in rate limit,
  reset (no enumeration, one use, other sessions signed out), change password, full 2FA lifecycle (wrong code,
  reuse refused, recovery code once, admin reset), admin email delivery reporting, the exact Resend API payload
  (reply-to, text version, 403 explanation), support requests (honeypot, rate limit).
- Browser: 45 steps pass, including both error cases you hit, the live countdown, back button, reset by email,
  2FA setup and sign-in, the assistant (anonymous, signed-in live status, hand-off reaching support) and translation.
- Not testable from here: Google Translate itself (my sandbox can't reach Google; the fallback path was tested),
  real Resend delivery, and the Vercel→Render forwarding. Check those after deploying (section 2).

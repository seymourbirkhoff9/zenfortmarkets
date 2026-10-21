# Batch 2 — admin features + Render-ready

Copy over your project the same way as Batch 1 (merge, don't replace folders):

```bash
cd ~/Documents/projects/zenfortmarkets && git add -A && git commit -m "before batch 2"
cd ~/Downloads && unzip -o zenfortmarkets-batch2.zip -d batch2
cp -r batch2/zenfortmarkets/. ~/Documents/projects/zenfortmarkets/
cd ~/Documents/projects/zenfortmarkets && git status        # ~24 files + Dockerfile, .dockerignore
```

No database migration. Restart the API and `npm run dev`.

## What's new

**View as customer (2)** — Customers → row menu (⋯) → *View as customer*, or the button on a customer's page.
- Opens their real dashboard for 30 minutes with an amber banner, countdown and **Exit to console**.
- **Read-only, enforced by the server**: every change (deposit, withdraw, transfer, invest, settings,
  marking notifications read) is refused with 403, even if someone crafts the request by hand.
- Start and end are written to the audit log. Admin accounts can't be viewed this way.
- The old "Customer view" link (which showed the admin's own empty account) is gone.

**Customer controls (14)** — row menu on every customer: open page, view as customer, restrict / lift,
deposits on/off, withdrawals on/off, make admin / remove admin. Same controls on the customer page
(new *Access* panel for the role). Rules: you can't change your own role; there's always at least one admin;
all changes are audited and the customer is notified.

**Investments page (12)** — Records → *Investments*. A card per investment: progress bar that animates to the
days already paid, a lighter segment showing today's return building up live, earnings counting up,
countdown to the next payout and principal date. Totals on top. Respects "reduce motion".

**Smaller fixes**
- Legacy records with no wallet show as such in the queues; the API answers with a clear 409 instead of 404.
- The admin console only preloads its data for browsers that were signed in as an admin (no stray 403s).

## Deploying on Render (single service)

Why one service: two Render services get two `*.onrender.com` addresses, which browsers treat as different
sites, so the sign-in cookie wouldn't be sent. The new root `Dockerfile` builds the frontend and the API serves it.

1. Push the project to GitHub (check `git status` shows **no `.env`**; `.dockerignore` also keeps it out of the image).
2. Render → New → **Web Service** → your repo. Language: **Docker**. Region: **Frankfurt** (closest to Supabase eu-north-1).
   Root directory: leave empty (repo root). Health check path: `/health`.
3. Environment variables:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | your Supabase pooler URL (the **new** password) |
   | `SECRET_KEY` | a new long random string: `python -c "import secrets;print(secrets.token_urlsafe(48))"` |
   | `RESEND_API_KEY`, `EMAIL_FROM` | as in your `.env` (`EMAIL_FROM` on a domain verified in Resend) |
   | `FRONTEND_ORIGIN`, `FRONTEND_URL` | `https://<your-service>.onrender.com` |
   | `COOKIE_SECURE` | `true` |
   | `ENABLE_SCHEDULER`, `DB_KEEP_WARM` | `true` |

4. Deploy. The container runs `alembic upgrade head`, then starts. Open `https://<your-service>.onrender.com`.

Notes
- On the **free** plan the service sleeps after ~15 minutes without traffic; the first visit after that takes
  up to a minute. Accrual simply catches up when it wakes (it never pays a day twice). A paid instance stays awake.
- I couldn't run `docker build` in my sandbox. The same steps (build the frontend, serve it with
  `FRONTEND_DIST`) were run and browser-tested here; if the Render build fails, paste the build log.
- Local development is unchanged: `uvicorn` + `npm run dev` (leave `FRONTEND_DIST` unset locally).

## Tests
- Backend: 21 pass (`TEST_DATABASE_URL=… pytest`), including impersonation read-only, exit, guards, roles, legacy 409.
- Browser: 32 steps pass against the single-service setup (`E2E_BASE=http://localhost:8000`).

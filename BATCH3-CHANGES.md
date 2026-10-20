# Batch 3 — plan cards, profile photos, consent & legal pages

## Apply (same as before: merge, don't replace)

1. `git add -A && git commit -m "before batch 3"` in your project.
2. Unzip, open `zenfortmarkets`, press **Ctrl+H** (shows `.gitignore`), **Ctrl+A**, **Ctrl+C**.
3. Paste into your project folder → **Merge** folders (apply to all) → **Replace** files (apply to all).
4. Database migration (adds 3 columns to `users`), from `backend` with the venv active:
   ```bash
   alembic upgrade head
   ```
5. Restart the API and `npm run dev`.

## Set up Supabase Storage (needed for photos and documents in production)

1. Supabase dashboard → **Storage** → **New bucket**:
   - `avatars` — tick **Public bucket**
   - `private-docs` — leave **Public** unticked (private)
2. **Project Settings → API** → copy the **service_role** key (secret). It bypasses all security rules:
   put it only in the backend `.env` and Render, **never** in Vercel or any frontend file.
3. Add to `backend/.env` (and to Render's environment variables):
   ```
   SUPABASE_URL=https://hibekyslsdndexeexsro.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=<the service_role key>
   ```
4. Restart. Optional: move existing ID documents and screenshots out of the database into storage:
   ```bash
   python -m scripts.move_files_to_storage           # preview
   python -m scripts.move_files_to_storage --apply   # move
   ```

Without those two settings, files are saved in `backend/uploads/` instead. That's fine on your laptop, but
**not on Render with the frontend on Vercel**: Render's disk is wiped on every deploy, and the file links
would point at your Vercel domain. Production must use Supabase Storage.

## Before launch: fill in `frontend/src/site.js`

Contact email, operator name and governing-law jurisdiction appear in the Terms, Privacy and Risk pages
(currently placeholders in [brackets]). The pages are drafts and say so; have them reviewed.
When you change the legal text later, bump `termsVersion` there **and** `TERMS_VERSION` in the backend
settings. Every user is then asked to accept again on their next visit.

## What's new

**Plan cards (3)** — Invest page shows each plan as a card: daily rate, term, amount range and a worked
example ("$100.00 earns $24.00 over 30 days, then the $100.00 comes back to Main").

**Profile photos (5)** — Settings → Profile: add, change or remove a photo (cropped to a square, resized
to 512 px before upload). Shown in the header immediately and to admins in the customer list and page.

**Private files** — ID documents and deposit screenshots are now stored in a private bucket, not inside
database rows. Admins (and the owner, for their own screenshot) open them through links that expire after
5 minutes. Old records still open normally.

**Consent (9)**
- Sign-up requires ticking agreement to the Terms and Privacy Policy (and having read the Risk Disclosure).
  The server rejects sign-ups without it and records the version and time.
- Every existing user, **including your admin**, sees a one-time prompt to accept the current terms on
  their next visit. It can't be dismissed; the alternative is signing out.
- Investing requires ticking the Risk Disclosure acknowledgement (also enforced by the server).
- New pages `/terms.html`, `/privacy.html`, `/risk.html`, linked from the site, sign-in and sign-up footers.

## Tests
- Backend: 28 pass. New: consent required (including when the field is omitted), terms re-acceptance,
  risk acknowledgement, photo upload/replace/remove, private files only via expiring links (tampered link
  refused, not reachable publicly), legacy rows readable, and the Supabase client checked against a mock of
  Supabase's Storage API (endpoints, headers, both signed-link formats).
- Browser: 34 steps pass on the single-service setup.
- Not tested against your real Supabase project from here. After step 3 above, upload a profile photo and
  open an ID document in the admin console; if either fails, paste the server log.

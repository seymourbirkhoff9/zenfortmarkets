"""Browser test of the full operator/customer flow. Needs: pip install playwright && playwright install chromium.
Run against a FRESH database with one admin ops@zenfort.dev / Ops-pass-123, API on :8000 and `npm run preview` on :3000.
Put proof.png and id.png (any small PNGs) next to this file.Set E2E_BASE=http://localhost:8000 to test the single-service (Render-style) setup.
Run the API with DEV_OUTBOX=true so the password-reset and support steps can read sent emails.
"""
import re, sys, time
from playwright.sync_api import sync_playwright, expect

import os
BASE = os.environ.get("E2E_BASE", "http://localhost:3000")
problems = []

def watch(page, who):
    # Ignored: Google Fonts can't resolve in this sandbox; the sign-in page probes /me and expects a 401.
    page.on("console", lambda m: m.type == "error" and "ERR_NAME_NOT_RESOLVED" not in m.text
            and "status of 401" not in m.text and problems.append(f"[{who} console] {m.text}"))
    page.on("pageerror", lambda e: problems.append(f"[{who} pageerror] {e}"))
    page.on("dialog", lambda d: (problems.append(f"[{who}] JS dialog fired: {d.message}"), d.dismiss()))

def step(msg): print("✓", msg, flush=True)

with sync_playwright() as p:
    b = p.chromium.launch()
    A = b.new_context(viewport={"width": 1360, "height": 900}).new_page(); watch(A, "admin")
    C = b.new_context(viewport={"width": 1360, "height": 900}).new_page(); watch(C, "customer")

    # ── Operator sets up rails and a plan ─────────────────────────
    A.goto(f"{BASE}/login.html")
    A.fill("#email", "ops@zenfort.dev"); A.fill("#password", "Ops-pass-123"); A.click("button[type=submit]")
    A.wait_for_url("**/admin.html**")
    # Existing accounts haven't accepted any terms version yet, so the console asks once.
    tdlg = A.locator("dialog[open]"); expect(tdlg).to_contain_text("We’ve updated our terms")
    tdlg.locator("[name=agree]").check(); tdlg.get_by_role("button", name="Accept and continue").click()
    expect(A.locator("dialog[open]")).to_have_count(0)
    expect(A.get_by_role("heading", name="Nothing needs review")).to_be_visible()
    step("admin signs in, accepts the current terms once, lands on the console")

    A.goto(f"{BASE}/admin.html#/methods"); A.get_by_role("button", name="Add method").first.click()
    d = A.locator("dialog[open]")
    d.locator("[name=asset]").fill("usdt"); d.locator("[name=network]").fill("TRC20")
    d.locator("[name=deposit_address]").fill("TXyz9k2LmN4pQ8rS6tU1vW3xY5zA7bC9dE")
    d.locator("[name=min_deposit]").fill("10"); d.locator("[name=min_withdrawal]").fill("20"); d.locator("[name=withdrawal_fee]").fill("1.50")
    d.get_by_role("button", name="Add method").click()
    expect(A.get_by_text("USDT on TRC20 added.")).to_be_visible(); expect(A.locator("td", has_text="TRC20")).to_be_visible()
    step("admin publishes a USDT/TRC20 deposit address")

    A.goto(f"{BASE}/admin.html#/plans"); A.get_by_role("button", name="New plan").first.click()
    d = A.locator("dialog[open]")
    d.locator("[name=name]").fill("Starter 30"); d.locator("[name=min_amount]").fill("50"); d.locator("[name=max_amount]").fill("5000")
    d.locator("[name=daily_roi_percent]").fill("0.8"); d.locator("[name=duration_days]").fill("30")
    expect(d.locator("#pl-preview")).to_contain_text("24% of the principal")
    A.screenshot(path="shots/admin-plan-dialog.png")
    d.get_by_role("button", name="Publish plan").click(); expect(A.get_by_text("Starter 30 is live.")).to_be_visible()
    step("admin creates a dynamic plan; preview shows the obligation (0.8% × 30 = 24%)")

    # ── Customer signs up (name contains an XSS payload) ──────────
    evil = 'Tunde <img src=x onerror=alert(1)>'
    C.goto(f"{BASE}/signup.html?ref=OPSADMIN")
    C.fill("#full_name", evil); C.fill("#email", "tunde@zenfort.dev"); C.select_option("#country", "Nigeria")
    C.fill("#password", "Cust-pass-123"); C.fill("#confirm_password", "Cust-pass-123")
    expect(C.locator("#referral_code")).to_have_value("OPSADMIN")
    C.click("button[type=submit]")
    expect(C.get_by_role("heading", name="Check your inbox")).not_to_be_visible()      # consent box not ticked yet
    C.check("#accept_terms")
    C.click("button[type=submit]"); expect(C.get_by_role("heading", name="Check your inbox")).to_be_visible()
    step("customer signs up via referral link")
    C.get_by_role("link", name="Sign in").click()
    C.fill("#email", "tunde@zenfort.dev"); C.fill("#password", "Cust-pass-123")
    C.get_by_role("button", name=re.compile("Show password", re.I)).click()
    assert C.locator("#password").get_attribute("type") == "text"
    C.get_by_role("button", name=re.compile("password", re.I)).click()
    assert C.locator("#password").get_attribute("type") == "password"
    step("[B1] show/hide password toggle works on sign-in")
    C.click("button[type=submit]")
    C.wait_for_url("**/app.html**"); expect(C.get_by_role("heading", name=re.compile("Hello, Tunde"))).to_be_visible()
    assert C.locator("img[src=x]").count() == 0, "XSS payload rendered as an element!"
    step("customer lands on overview; malicious name rendered as text, no script ran")
    C.screenshot(path="shots/customer-overview-empty.png", full_page=True)

    # ── Deposit ───────────────────────────────────────────────────
    t0 = time.perf_counter(); C.get_by_role("button", name="Deposit").first.click(); d = C.locator("dialog[open]")
    d.wait_for(state="visible"); opened_ms = (time.perf_counter() - t0) * 1000
    assert opened_ms < 250, f"deposit dialog took {opened_ms:.0f} ms to appear"
    step(f"[B1] deposit dialog appeared in {opened_ms:.0f} ms (data fills in after)")
    d.locator("label.choice", has_text="USDT").click()
    expect(d.locator("#dep-address")).to_contain_text("TXyz9k2LmN4pQ8rS6tU1vW3xY5zA7bC9dE")
    d.locator("[name=amount]").fill("500"); d.locator("[name=tx_hash]").fill("0x7c1e44ab90ffe1a94d")
    d.locator("#dep-proof").set_input_files("proof.png"); expect(d.locator("#dep-preview img")).to_be_visible()
    C.screenshot(path="shots/customer-deposit-dialog.png")
    d.get_by_role("button", name="Submit for review").click()
    expect(C.get_by_text("Deposit submitted.")).to_be_visible()
    expect(C.locator("section", has_text="Waiting for review").get_by_text("Deposit via USDT (TRC20)")).to_be_visible()
    step("customer reports a 500 USD deposit with hash + screenshot; it shows as waiting")

    # ── Operator is alerted and confirms ──────────────────────────
    A.goto(f"{BASE}/admin.html#/"); A.reload()
    expect(A.locator("#bell-count")).to_have_text("1")
    expect(A.locator("[data-badge=deposits]")).to_have_text("1")
    expect(A.get_by_role("heading", name="1 item needs review")).to_be_visible()
    A.screenshot(path="shots/admin-overview.png", full_page=True)
    step("admin sees bell alert, sidebar badge and the 'needs review' queue")
    A.get_by_role("link", name=re.compile("Deposits to confirm")).click()
    A.get_by_role("button", name="View screenshot").click()
    expect(A.locator("dialog[open] img[alt='Payment screenshot']")).to_be_visible()
    A.keyboard.press("Escape")
    A.get_by_role("button", name="Confirm").click()
    A.locator("dialog[open]").get_by_role("button", name="Credit $500.00").click()
    expect(A.get_by_text("Credited $500.00 to tunde@zenfort.dev.")).to_be_visible()
    expect(A.get_by_text("Queue is clear")).to_be_visible()
    step("admin views the proof and confirms; queue clears")

    C.reload(); expect(C.locator("p.figure.text-5xl")).to_have_text("$500.00")
    step("customer Main wallet shows $500.00")

    # ── Invest ────────────────────────────────────────────────────
    C.goto(f"{BASE}/app.html#/invest")
    card = C.locator("li", has=C.get_by_role("heading", name="Starter 30"))
    expect(card).to_contain_text("$100.00 earns $24.00 over 30 days")                 # worked example on the card
    expect(card).to_contain_text("0.8%")
    step("[B3] plan shown as a card with a worked example ($100 → $24.00 over 30 days)")
    C.get_by_role("button", name="Invest in Starter 30").click()
    d = C.locator("dialog[open]"); d.locator("[name=amount]").fill("200")
    d.get_by_role("button", name="Confirm investment").click()
    expect(d).to_be_visible()                                                           # risk box not ticked
    d.locator("[name=accept_risk]").check()
    expect(d.locator("#inv-preview dd").first).to_have_text("$48.00")
    d.get_by_role("button", name="Confirm investment").click()
    expect(C.get_by_text("You invested $200.00 in Starter 30.")).to_be_visible()
    expect(C.get_by_text("0 of 30 days paid")).to_be_visible()
    C.screenshot(path="shots/customer-invest.png", full_page=True)
    step("customer invests $200 in the plan")

    # ── Withdraw is gated on KYC ─────────────────────────────────
    C.goto(f"{BASE}/app.html#/wallet"); C.get_by_role("button", name="Withdraw", exact=True).click()
    expect(C.locator("dialog[open]")).to_contain_text("Verify your identity first")
    C.locator("dialog[open]").get_by_role("link", name="Go to Settings").click()
    C.locator("#kyc-file").set_input_files("id.png"); expect(C.locator("#kyc-preview img")).to_be_visible()
    C.get_by_role("button", name="Submit for review").click()
    expect(C.get_by_text("Document submitted for review.")).to_be_visible(); expect(C.get_by_text("In review")).to_be_visible()
    step("withdrawal blocked until KYC; customer uploads ID")

    A.goto(f"{BASE}/admin.html#/kyc"); A.get_by_role("button", name="Review document").click()
    d = A.locator("dialog[open]"); expect(d.locator("img[alt^='ID document']")).to_be_visible()
    d.locator("label.choice", has_text="Verified").click(); d.get_by_role("button", name="Save decision").click()
    expect(A.get_by_text("is verified.")).to_be_visible()
    step("admin verifies the ID")

    # ── Withdraw, operator pays out ──────────────────────────────
    C.goto(f"{BASE}/app.html#/wallet"); C.reload(); C.get_by_role("button", name="Withdraw", exact=True).click()
    d = C.locator("dialog[open]"); d.locator("label.choice", has_text="USDT").click()
    d.locator("[name=withdrawal_address]").fill("TQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE")
    d.locator("[name=amount]").fill("100"); expect(d.locator("#wd-summary")).to_contain_text("You receive about $98.50")
    C.screenshot(path="shots/customer-withdraw-dialog.png")
    d.get_by_role("button", name="Request withdrawal").click()
    expect(C.get_by_text("Withdrawal requested. $100.00 is on hold until it’s paid.")).to_be_visible()
    step("customer requests $100 to a TRC20 address; fee shown, funds held")

    A.goto(f"{BASE}/admin.html#/withdrawals"); A.reload()
    expect(A.locator("td", has_text="$98.50")).to_be_visible()
    A.screenshot(path="shots/admin-withdrawals.png", full_page=True)
    A.get_by_role("button", name="Mark paid").click(); d = A.locator("dialog[open]")
    d.get_by_role("button", name="Mark as paid").click()
    expect(d).to_be_visible()                                     # still open: empty hash was refused
    assert d.locator("[name=payout_tx_hash]").evaluate("el => !el.validity.valid")
    d.locator("[name=payout_tx_hash]").fill("0xpayout55aa"); d.get_by_role("button", name="Mark as paid").click()
    expect(A.get_by_text("marked as paid")).to_be_visible()
    step("admin can't mark paid without a payout hash; records it")

    C.goto(f"{BASE}/app.html#/wallet?tab=withdrawal"); C.reload()
    expect(C.get_by_text("Payout ref")).to_be_visible(); expect(C.locator("text=Settled").first).to_be_visible()
    step("customer sees the withdrawal settled with payout reference")

    # ── Manual credit + audit ────────────────────────────────────
    A.goto(f"{BASE}/admin.html#/customers"); A.get_by_role("link", name=re.compile("Tunde")).click()
    expect(A.get_by_role("heading", name=re.compile("Tunde"))).to_be_visible()
    assert A.locator("img[src=x]").count() == 0
    A.get_by_role("button", name="Credit wallet").click(); d = A.locator("dialog[open]")
    d.locator("[name=amount]").fill("25"); d.locator("[name=description]").fill("Goodwill credit for slow review")
    d.get_by_role("button", name="Credit wallet").click(); expect(A.get_by_text("Credited $25.00.")).to_be_visible()
    expect(A.locator("p.figure", has_text="$225.00")).to_be_visible()   # 500 − 200 − 100 + 25
    A.screenshot(path="shots/admin-customer.png", full_page=True)
    step("admin credits $25 from the customer page; balance $225.00 (500 − 200 − 100 + 25)")

    A.goto(f"{BASE}/admin.html#/audit")
    for t in ["Added a payment method", "Created a plan", "Confirmed a deposit", "Verified an identity", "Paid a withdrawal", "Credited a wallet"]:
        expect(A.get_by_text(t, exact=True)).to_be_visible()
    A.screenshot(path="shots/admin-audit.png", full_page=True)
    step("audit log has every operator action")

    # ── Ledger, ROI, notifications, dark mode, mobile ─────────────
    A.goto(f"{BASE}/admin.html#/ledger"); expect(A.locator("#total")).to_contain_text("entr")
    A.goto(f"{BASE}/admin.html#/plans"); A.get_by_role("button", name="Run accrual now").click()
    expect(A.get_by_text("Accrual checked 1 investments: 0 day(s) paid")).to_be_visible()
    step("ledger loads; accrual run on a same-day investment pays nothing")

    # ── Batch 2 ──────────────────────────────────────────────────────
    # Pretend the investment started 3 days ago, then run accrual: 3 days are paid.
    import psycopg2
    with psycopg2.connect("postgresql://zf:zf@localhost/zf_e2e") as pg, pg.cursor() as cur:
        cur.execute("UPDATE user_investments SET start_date = start_date - interval '3 days', maturity_date = maturity_date - interval '3 days'")
    A.get_by_role("button", name="Run accrual now").click()
    expect(A.get_by_text("3 day(s) paid")).to_be_visible()

    A.goto(f"{BASE}/admin.html#/investments")
    inv = A.locator("article[data-inv]").first
    expect(inv).to_contain_text("Starter 30"); expect(inv).to_contain_text("Day 3 of 30 paid")
    expect(inv.locator("[data-count]")).to_have_text("$4.80", timeout=4000)          # count-up lands on 3 × $1.60
    expect(inv).to_contain_text("Next return of $1.60 in")
    A.wait_for_timeout(1600)
    w = inv.locator(".zf-bar").first.evaluate("e => e.getBoundingClientRect().width / e.parentElement.getBoundingClientRect().width")
    assert 0.09 < w < 0.11, f"progress bar should be ~10% after animating, got {w:.3f}"
    A.screenshot(path="shots/admin-investments.png", full_page=True)
    step(f"[B2] investments page: bar animated to {w*100:.0f}% (3/30 days), earnings counted up to $4.80, live countdown")

    # View as customer, from the row menu
    A.goto(f"{BASE}/admin.html#/customers"); A.get_by_role("button", name=re.compile("Actions for Tunde")).click()
    expect(A.get_by_role("menuitem").first).to_be_focused()          # keyboard users land in the menu
    A.get_by_role("menuitem", name="View as customer").click()
    A.wait_for_url("**/app.html**")
    expect(A.get_by_text("View only: nothing can be changed.")).to_be_visible()
    t1 = A.locator("#imp-left").inner_text(); A.wait_for_timeout(2200); t2 = A.locator("#imp-left").inner_text()
    assert re.fullmatch(r"Ends in \d+:\d\d", t1) and t1 != t2, (t1, t2)
    step(f"[B5] view-as countdown ticks live ({t1} → {t2})")
    expect(A.locator("p.figure.text-5xl")).to_have_text("$225.00")
    A.screenshot(path="shots/admin-viewing-as.png")
    A.get_by_role("button", name="Deposit").first.click()
    expect(A.locator("dialog[open]")).to_contain_text("You’re viewing this account as an admin")
    A.keyboard.press("Escape")
    A.goto(f"{BASE}/app.html#/settings")
    expect(A.locator("#pw-cur")).to_be_disabled()
    A.click("#bell-btn"); A.locator("#bell-panel li").first.wait_for()
    assert A.locator("#bell-panel [data-read]").count() == 0 and A.locator("[data-action=read-all]").count() == 0
    A.keyboard.press("Escape")
    # even a forged request is refused by the server
    forged = A.evaluate("""() => fetch('/api/wallets/transfer', {method:'POST', credentials:'include',
        headers:{'Content-Type':'application/json','X-Requested-With':'zenfort'},
        body: JSON.stringify({from_wallet:'main', to_wallet:'profit', amount:'1'})}).then(r => r.status)""")
    assert forged == 403, forged
    step("[B2] admin views Tunde's account read-only: banner + countdown, dialogs and settings locked, forged write → 403")
    A.get_by_role("button", name="Exit to console").click()
    A.wait_for_url(re.compile(r".*/admin\.html#/customers/.+"))
    expect(A.get_by_role("heading", name=re.compile("Tunde"))).to_be_visible()
    step("[B2] Exit returns to the customer's page in the console")
    A.get_by_role("button", name="Email").click(); d = A.locator("dialog[open]")
    d.locator("[name=subject]").fill("About your account"); d.locator("[name=body]").fill("Hello from support."); d.get_by_role("button", name="Send email").click()
    expect(A.get_by_text("Delivered to their inbox and their notifications.")).to_be_visible()
    A.get_by_role("link", name="All customers").click(); A.wait_for_url(re.compile(r".*#/customers$"))
    step("[B5] admin email reports delivery; back button returns to All customers")

    # Promote from the row menu, demote from the customer page
    A.goto(f"{BASE}/admin.html#/customers"); A.get_by_role("button", name=re.compile("Actions for Tunde")).click()
    A.get_by_role("menuitem", name="Make admin").click()
    A.locator("dialog[open]").get_by_role("button", name="Make admin").click()
    expect(A.get_by_text("is now an admin.")).to_be_visible()
    expect(A.locator("tr", has_text="tunde@zenfort.dev").get_by_text("Admin", exact=True)).to_be_visible()
    A.get_by_role("link", name=re.compile("Tunde")).click()
    A.get_by_role("button", name="Remove admin access").click()
    A.locator("dialog[open]").get_by_role("button", name="Remove admin access").click()
    expect(A.get_by_text("is no longer an admin.")).to_be_visible()
    expect(A.get_by_role("button", name="Make admin")).to_be_visible()
    step("[B2] promote via row menu, demote via Access panel")

    A.goto(f"{BASE}/admin.html#/audit")
    for t in ["Viewed an account as the customer", "Stopped viewing as the customer", "Gave admin access", "Removed admin access"]:
        expect(A.get_by_text(t, exact=True).first).to_be_visible()
    step("[B2] audit log records viewing and role changes")

    # ── Batch 3 ──────────────────────────────────────────────────────
    C.goto(f"{BASE}/app.html#/settings"); C.locator("#photo-input").set_input_files("proof.png")
    expect(C.get_by_text("Photo updated.")).to_be_visible()
    src = C.locator("#account-avatar img").get_attribute("src")
    assert "/avatars/" in src, src
    assert C.request.get(BASE + src if src.startswith("/") else src).ok
    expect(C.get_by_role("button", name="Remove")).to_be_visible()
    A.goto(f"{BASE}/admin.html#/customers")
    expect(A.locator("tr", has_text="tunde@zenfort.dev").locator("img")).to_have_count(1)
    step("[B3] customer adds a profile photo: header updates at once, admin list shows it")

    with psycopg2.connect("postgresql://zf:zf@localhost/zf_e2e") as pg, pg.cursor() as cur:
        cur.execute("UPDATE users SET terms_version = '2020-01' WHERE email = 'tunde@zenfort.dev'")
    C.goto(f"{BASE}/app.html#/"); C.reload()
    dlg = C.locator("dialog[open]")
    expect(dlg).to_contain_text("We’ve updated our terms")
    C.keyboard.press("Escape"); expect(dlg).to_be_visible()                              # can't be dismissed
    dlg.get_by_role("button", name="Accept and continue").click(); expect(dlg).to_be_visible()   # needs the tick
    dlg.locator("[name=agree]").check(); dlg.get_by_role("button", name="Accept and continue").click()
    expect(C.locator("dialog[open]")).to_have_count(0)
    with psycopg2.connect("postgresql://zf:zf@localhost/zf_e2e") as pg, pg.cursor() as cur:
        cur.execute("SELECT terms_version FROM users WHERE email = 'tunde@zenfort.dev'"); assert cur.fetchone()[0] == "2026-10"
    step("[B3] updated terms: blocking prompt, needs the tick, acceptance recorded")

    for path, heading in [("/terms.html", "Terms of Service"), ("/privacy.html", "Privacy Policy"), ("/risk.html", "Risk Disclosure")]:
        A.goto(BASE + path)
        expect(A.get_by_role("heading", name=heading, level=1)).to_be_visible()
        expect(A.get_by_role("navigation", name="Legal")).to_be_visible()
    A.screenshot(path="shots/risk-page.png", full_page=True)
    step("[B3] Terms, Privacy and Risk pages render with the legal footer")

    C.goto(f"{BASE}/app.html#/"); C.reload(); C.click("#bell-btn")
    expect(C.locator("#bell-panel")).to_contain_text("Withdrawal sent")
    expect(C.locator("#bell-panel")).to_contain_text("$500.00")
    assert "00000" not in C.locator("#bell-panel").inner_text()
    before = int(C.locator("#bell-count").inner_text())
    C.locator("#bell-panel [data-read]").first.click()
    expect(C.locator("#bell-count")).to_have_text(str(before - 1))
    step(f"[B1] single notification marked read ({before} → {before - 1}); amounts read $500.00")
    C.keyboard.press("Escape")
    C.click("#theme-btn"); C.click("body", position={"x": 5, "y": 400})
    C.screenshot(path="shots/customer-overview-dark.png", full_page=True)
    step("customer notifications show each review outcome; dark theme renders")

    # ── Batch 5 ──────────────────────────────────────────────────────
    import pyotp, json as _json, urllib.request as _url
    def outbox():
        with _url.urlopen(BASE + "/api/dev/outbox") as r: return _json.loads(r.read())

    # Friendly errors: the API unreachable, and a proxy answering "Not found"
    E = b.new_context().new_page()
    E.route("**/api/auth/login", lambda r: r.abort("internetdisconnected"))
    E.goto(f"{BASE}/login.html"); E.fill("#email", "x@y.dev"); E.fill("#password", "whatever1"); E.click("button[type=submit]")
    expect(E.get_by_text("We couldn’t reach Zenfort Markets. Check your connection and try again.")).to_be_visible()
    E.unroute("**/api/auth/login")
    E.route("**/api/auth/login", lambda r: r.fulfill(status=404, content_type="text/html", body="<h1>404: NOT_FOUND</h1>"))
    E.click("button[type=submit]")
    expect(E.get_by_text("This service isn’t available right now. Please try again shortly.")).to_be_visible()
    assert "Not found" not in E.locator("#error").inner_text()
    E.close()
    step("[B5] friendly errors: offline and 'Not found' become clear, actionable messages")

    # Password reset by email (fresh account)
    R = b.new_context(viewport={"width": 1280, "height": 900}).new_page(); watch(R, "reset")
    R.request.post(f"{BASE}/api/auth/signup", data={"full_name": "Rita Reset", "email": "rita@zenfort.dev", "password": "Rita-pass-123",
                   "confirm_password": "Rita-pass-123", "country": "Kenya", "accept_terms": True})
    R.goto(f"{BASE}/login.html"); R.get_by_role("link", name="Forgot password?").click()
    R.fill("#email", "rita@zenfort.dev"); R.click("button[type=submit]")
    expect(R.get_by_text("If an account uses that email")).to_be_visible()
    mail = next(m for m in outbox() if m["to"] == "rita@zenfort.dev" and "Reset your password" in m["subject"])
    link = re.search(r'href="([^"]*reset-password\.html\?token=[^"]+)"', mail["html"]).group(1)
    R.goto(BASE + link[link.index("/reset-password.html"):])
    R.fill("#pw", "Rita-newpass-456"); R.fill("#pw2", "Rita-newpass-456"); R.click("button[type=submit]")
    R.wait_for_url("**/login.html?reset=1"); expect(R.get_by_text("Password updated.")).to_be_visible()
    R.fill("#email", "rita@zenfort.dev"); R.fill("#password", "Rita-newpass-456"); R.click("button[type=submit]")
    R.wait_for_url("**/app.html**")
    tdlg = R.locator("dialog[open]")
    if tdlg.count(): tdlg.locator("[name=agree]").check(); tdlg.get_by_role("button", name="Accept and continue").click()
    step("[B5] password reset: emailed link, new password, signed in")

    # Two-factor: set up in Settings, then sign in with a code
    R.goto(f"{BASE}/app.html#/settings"); R.get_by_role("button", name="Turn on two-factor sign-in").click()
    d = R.locator("dialog[open]"); d.locator("[name=password]").fill("Rita-newpass-456"); d.get_by_role("button", name="Continue").click()
    expect(d.locator("svg").first).to_be_visible()                                  # QR code rendered
    secret = d.locator(".copy-row span").first.inner_text().replace(" ", "")
    totp = pyotp.TOTP(secret)
    d.locator("[name=code]").fill(totp.now()); d.get_by_role("button", name="Turn on").click()
    expect(d.locator("ol li")).to_have_count(8)                                    # recovery codes shown once
    d.get_by_role("button", name="I’ve saved my codes").click()
    expect(R.get_by_text("Status: On")).to_be_visible()
    R.click("#account-btn"); R.click("#logout-btn"); R.wait_for_url("**/login.html")
    R.fill("#email", "rita@zenfort.dev"); R.fill("#password", "Rita-newpass-456"); R.click("button[type=submit]")
    expect(R.get_by_role("heading", name="Two-factor sign-in")).to_be_visible()
    R.fill("#code", "123456"); expect(R.get_by_text("That code isn’t right")).to_be_visible()
    R.fill("#code", totp.at(time.time() + 30))                                       # next window: fresh, unused code
    R.wait_for_url("**/app.html**")
    step("[B5] two-factor: QR setup, 8 recovery codes, sign-in asks for and checks the code")

    # Help assistant: anonymous visitor, then signed-in customer with live status and a hand-off
    P = b.new_context().new_page(); watch(P, "public")
    P.goto(f"{BASE}/"); P.get_by_role("button", name="Help").click()
    P.locator("#zfa-input").fill("where is my deposit"); P.locator("#zfa-input").press("Enter")
    expect(P.locator("#zfa-log")).to_contain_text("Sign in and ask again")
    P.locator("#zfa-input").fill("purple elephant sandwich"); P.locator("#zfa-input").press("Enter")
    expect(P.locator("#zfa-log")).to_contain_text("not sure I understood")
    P.close()
    C.goto(f"{BASE}/app.html#/"); C.get_by_role("button", name="Help").click()
    C.locator("#zfa-log").get_by_role("button", name="Where is my deposit?").click()
    expect(C.locator("#zfa-log")).to_contain_text("no deposits waiting for review")
    C.locator("#zfa-input").fill("I sent to the wrong network"); C.locator("#zfa-input").press("Enter")
    C.locator("#zfa-log").get_by_role("button", name="Contact support").last.click()
    form = C.locator("#zfa-log form")
    expect(form.locator("[name=email]")).to_have_value("tunde@zenfort.dev")              # pre-filled for signed-in users
    form.get_by_role("button", name="Send to support").click()
    expect(C.locator("#zfa-log")).to_contain_text("Your reference is ZF-")
    sup = next(m for m in outbox() if "Support request" in m["subject"])
    assert sup["to"] == "support@zenfortmarkets.online" and "wrong network" in sup["text"]
    C.get_by_role("button", name="Close help").click()
    step("[B5] help assistant: answers, live status, admits when unsure, hands off to support (email reaches support)")

    # Translation: menu, choice remembered, graceful when Google is unreachable (as in this sandbox)
    T = b.new_context().new_page(); watch(T, "translate")
    T.goto(f"{BASE}/fees.html"); T.get_by_role("button", name="Translate this page").click()
    expect(T.get_by_role("button", name="Français")).to_be_visible()
    T.get_by_role("button", name="Français").click(); T.wait_for_load_state("load")
    expect(T.get_by_text("Translation isn’t available right now")).to_be_visible(timeout=20000)
    assert "googtrans=/en/fr" not in T.evaluate("document.cookie")                  # falls back to English cleanly
    expect(T.locator("#methods .figure").first).to_have_attribute("translate", "no")  # money is never translated
    T.close()
    step("[B5] translate menu works; amounts protected; falls back to English if Google is unreachable")

    M = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True).new_page(); watch(M, "mobile")
    M.goto(f"{BASE}/login.html"); M.fill("#email", "tunde@zenfort.dev"); M.fill("#password", "Cust-pass-123"); M.click("button[type=submit]")
    M.wait_for_url("**/app.html**"); M.wait_for_selector("p.figure.text-5xl")
    M.screenshot(path="shots/mobile-overview.png", full_page=True)
    M.click("#bell-btn"); M.locator("#bell-panel li").first.wait_for()
    box = M.locator("#bell-panel").bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 390, f"bell panel off-screen: {box}"
    M.screenshot(path="shots/mobile-bell.png"); M.keyboard.press("Escape")
    step(f"[B1] mobile notification panel fits the screen (x={box['x']:.0f}, w={box['width']:.0f} of 390)")
    M.goto(f"{BASE}/app.html#/activity"); M.locator("table.table td[data-label]").first.wait_for()
    assert M.locator("table.table thead").bounding_box()["height"] <= 1
    assert M.locator("table.table tbody tr").first.bounding_box()["width"] <= 390
    M.screenshot(path="shots/mobile-activity.png", full_page=True)
    step("[B1] tables stack into labelled cards on a phone")
    M.goto(f"{BASE}/app.html#/")
    M.click("#menu-btn"); expect(M.locator("#sidebar")).not_to_have_class(re.compile("-translate-x-full")); M.screenshot(path="shots/mobile-menu.png")
    step("mobile layout and drawer work")
    M.goto(f"{BASE}/"); M.click("#pub-menu"); expect(M.locator("#pub-nav")).to_be_visible()
    expect(M.locator("#pub-nav").get_by_role("link", name="Fees & limits")).to_be_visible()
    M.screenshot(path="shots/mobile-home.png", full_page=True)
    M.goto(f"{BASE}/app.html"); M.wait_for_selector("#splash", state="detached", timeout=8000)
    step("[B4] public menu on a phone; branded splash clears once the app is ready")
    overflow = []
    for u in ["/", "/how-it-works.html", "/fees.html", "/security.html", "/faq.html", "/about.html", "/contact.html",
              "/terms.html", "/privacy.html", "/risk.html", "/app.html#/", "/app.html#/wallet", "/app.html#/invest",
              "/app.html#/activity", "/app.html#/referrals", "/app.html#/settings"]:
        M.goto(BASE + u); M.wait_for_timeout(700)
        w = M.evaluate("document.documentElement.scrollWidth")
        if w > 390: overflow.append((u, w))
    assert not overflow, f"pages wider than the phone: {overflow}"
    step("[B4] 16 public and customer pages fit a 390 px phone with no sideways scrolling")

    # ── Batch 4 ──────────────────────────────────────────────────────
    A.goto(f"{BASE}/")
    expect(A.get_by_role("link", name="Open the console")).to_be_visible()             # signed-in admin
    expect(A.locator("#st-balance")).to_have_text("$1,248.40", timeout=6000)          # animation settles the deposit
    expect(A.locator('[data-row="dep"]')).to_contain_text("Confirmed by an operator")
    expect(A.locator("#network-list")).to_contain_text("USDT")
    expect(A.locator("#network-list")).to_contain_text("on TRC20")
    expect(A.locator("#plan-list")).to_contain_text("Starter 30")
    A.wait_for_timeout(1200); A.screenshot(path="shots/landing.png", full_page=True)
    step("[B4] homepage: statement animation settles the deposit ($998.40 → $1,248.40); live networks and plans shown")

    A.goto(f"{BASE}/fees.html")
    expect(A.locator("#methods")).to_contain_text("TRC20"); expect(A.locator("#methods")).to_contain_text("$1.50")
    expect(A.locator("#plan-table")).to_contain_text("Starter 30"); expect(A.locator("#plan-table")).to_contain_text("24%")
    assert "deposit_address" not in A.content() and "TXyz9k2LmN4pQ8rS6tU1vW3xY5zA7bC9dE" not in A.content()
    for path, h1 in [("/how-it-works.html", "How it works"), ("/security.html", "Security"), ("/faq.html", "Frequently asked questions"),
                     ("/about.html", "About Zenfort Markets"), ("/contact.html", "Contact")]:
        A.goto(BASE + path); expect(A.get_by_role("heading", name=h1, level=1)).to_be_visible()
        expect(A.get_by_role("navigation", name="Legal")).to_be_visible()
    A.goto(f"{BASE}/faq.html"); A.get_by_text("Why do I need to verify my identity?").click()
    expect(A.get_by_text("an identity check is required before the first one")).to_be_visible()
    step("[B4] fees page shows live networks (no deposit address leaked) and plan totals; all public pages render")
    b.close()

print("\nProblems:", *(problems or ["none"]), sep="\n  ")
sys.exit(1 if problems else 0)

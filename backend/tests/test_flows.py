from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.database import SessionLocal
from app.models import UserInvestment
from app.security import create_access_token, create_purpose_token
from tests.conftest import PNG


def bal(client, h, kind="main"):
    return Decimal(next(w for w in client.get("/api/wallets/", headers=h).json() if w["wallet_type"] == kind)["balance"])


def credit(client, admin, uid, amount, wallet="main"):
    r = client.post("/api/admin/credit", headers=admin,
                    json={"user_id": uid, "wallet_type": wallet, "amount": str(amount)})
    assert r.status_code == 201, r.text


# ── auth ──────────────────────────────────────
def test_signup_creates_usd_wallets_and_cookie_session(client, make_user):
    u = make_user()
    wallets = client.get("/api/wallets/", headers=u["h"]).json()
    assert {w["wallet_type"] for w in wallets} == {"main", "profit"}
    assert all(w["currency"] == "USD" for w in wallets)          # not NGN any more

    r = client.post("/api/auth/login", json={"email": u["email"], "password": "User-pass-1"})
    assert "zf_session" in r.cookies
    me = client.get("/api/auth/me")                              # cookie only
    assert me.status_code == 200 and "kyc_document_url" not in me.json()


def test_cookie_writes_require_csrf_header(client, make_user):
    u = make_user()
    client.post("/api/auth/login", json={"email": u["email"], "password": "User-pass-1"})
    body = {"from_wallet": "main", "to_wallet": "profit", "amount": "1"}
    assert client.post("/api/wallets/transfer", json=body).status_code == 403
    r = client.post("/api/wallets/transfer", json=body, headers={"X-Requested-With": "zenfort"})
    assert r.status_code == 422          # passed CSRF, failed on balance — as intended


def test_email_verification_tokens_are_purpose_bound(client, make_user):
    u = make_user()
    session_token = create_access_token(u["email"])
    assert client.post("/api/auth/verify-email", json={"token": session_token}).status_code == 401
    verify_token = create_purpose_token(u["email"], "email_verify", 10)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {verify_token}"}).status_code == 401
    r = client.post("/api/auth/verify-email", json={"token": verify_token})
    assert r.status_code == 200 and r.json()["email_verified"] is True


# ── deposits ──────────────────────────────────
def test_deposit_review_flow_alerts_admin_and_is_single_use(client, admin, make_user, method):
    referrer = make_user()
    u = make_user(referral_code=referrer["code"])
    before = client.get("/api/notifications/unread-count", headers=admin).json()["unread"]

    r = client.post("/api/wallets/deposits/", headers=u["h"], json={
        "payment_method_id": method["id"], "amount": "150", "tx_hash": "0xabc-1", "proof_image_url": PNG})
    assert r.status_code == 201, r.text
    dep = r.json()
    assert dep["status"] == "pending" and dep["has_proof"] and dep["network"] == method["network"]
    assert client.get("/api/notifications/unread-count", headers=admin).json()["unread"] == before + 1

    # same hash can't be reported twice
    dup = client.post("/api/wallets/deposits/", headers=u["h"], json={
        "payment_method_id": method["id"], "amount": "150", "tx_hash": "0xabc-1"})
    assert dup.status_code == 409

    queue = client.get("/api/admin/deposits/pending", headers=admin).json()
    item = next(d for d in queue if d["id"] == dep["id"])
    assert item["user_email"] == u["email"] and item["proof_image_url"] is None   # list stays light
    proof_url = client.get(f"/api/admin/transactions/{dep['id']}", headers=admin).json()["proof_image_url"]
    assert proof_url.startswith("/api/files/signed/") and client.get(proof_url).content.startswith(b"\x89PNG")

    ok = client.patch(f"/api/admin/deposits/{dep['id']}/review", headers=admin, json={"status": "approved"})
    assert ok.status_code == 200 and ok.json()["status"] == "completed"
    again = client.patch(f"/api/admin/deposits/{dep['id']}/review", headers=admin, json={"status": "approved"})
    assert again.status_code == 409
    assert bal(client, u["h"]) == Decimal("150")
    assert bal(client, referrer["h"]) == Decimal("10")              # referral bonus, once


def test_deposit_rules(client, admin, make_user, method):
    u = make_user()
    small = client.post("/api/wallets/deposits/", headers=u["h"],
                        json={"payment_method_id": method["id"], "amount": "5", "tx_hash": "0xsmall"})
    assert small.status_code == 422
    no_evidence = client.post("/api/wallets/deposits/", headers=u["h"],
                              json={"payment_method_id": method["id"], "amount": "50"})
    assert no_evidence.status_code == 422
    bad_file = client.post("/api/wallets/deposits/", headers=u["h"], json={
        "payment_method_id": method["id"], "amount": "50", "proof_image_url": "data:text/html;base64,PGI+"})
    assert bad_file.status_code == 422
    r = client.post("/api/wallets/deposits/", headers=u["h"],
                    json={"payment_method_id": method["id"], "amount": "50", "tx_hash": "0xrej"})
    no_reason = client.patch(f"/api/admin/deposits/{r.json()['id']}/review", headers=admin, json={"status": "rejected"})
    assert no_reason.status_code == 422
    rej = client.patch(f"/api/admin/deposits/{r.json()['id']}/review", headers=admin,
                       json={"status": "rejected", "rejection_reason": "Hash not found on chain"})
    assert rej.json()["status"] == "rejected" and bal(client, u["h"]) == 0


# ── withdrawals ───────────────────────────────
def _verify_kyc(client, admin, u):
    assert client.post("/api/auth/kyc/submit", headers=u["h"], json={"kyc_document_url": PNG}).status_code == 200
    r = client.patch(f"/api/admin/kyc/{u['id']}/review", headers=admin, json={"status": "VERIFIED"})
    assert r.status_code == 200, r.text


def test_withdrawal_hold_reject_refund_and_paid(client, admin, make_user, method):
    u = make_user()
    credit(client, admin, u["id"], 100)
    w = {"payment_method_id": method["id"], "amount": "40", "withdrawal_address": "TQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE"}
    assert client.post("/api/wallets/withdrawals/", headers=u["h"], json=w).status_code == 403   # KYC first
    _verify_kyc(client, admin, u)

    r1 = client.post("/api/wallets/withdrawals/", headers=u["h"], json=w).json()
    assert r1["fee"] == "1.50000000" and bal(client, u["h"]) == Decimal("60")       # held
    client.patch(f"/api/admin/withdrawals/{r1['id']}/review", headers=admin,
                 json={"status": "rejected", "rejection_reason": "Address on wrong network"})
    assert bal(client, u["h"]) == Decimal("100")                                     # refunded

    r2 = client.post("/api/wallets/withdrawals/", headers=u["h"], json=w).json()
    no_hash = client.patch(f"/api/admin/withdrawals/{r2['id']}/review", headers=admin, json={"status": "approved"})
    assert no_hash.status_code == 422
    paid = client.patch(f"/api/admin/withdrawals/{r2['id']}/review", headers=admin,
                        json={"status": "approved", "payout_tx_hash": "0xpayout"})
    assert paid.json()["status"] == "completed" and bal(client, u["h"]) == Decimal("60")


def test_concurrent_withdrawals_cannot_overdraw(client, admin, make_user, method):
    u = make_user()
    credit(client, admin, u["id"], 100)
    _verify_kyc(client, admin, u)
    w = {"payment_method_id": method["id"], "amount": "70", "withdrawal_address": "TQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE"}
    with ThreadPoolExecutor(max_workers=5) as pool:
        codes = list(pool.map(lambda _: client.post("/api/wallets/withdrawals/", headers=u["h"], json=w).status_code, range(5)))
    assert codes.count(201) == 1, codes
    assert bal(client, u["h"]) == Decimal("30")


# ── admin adjustments ─────────────────────────
def test_admin_credit_validation_and_audit(client, admin, make_user):
    u = make_user()
    neg = client.post("/api/admin/credit", headers=admin,
                      json={"user_id": u["id"], "wallet_type": "main", "amount": "-500"})
    assert neg.status_code == 422                      # used to silently debit
    credit(client, admin, u["id"], "25.50", "profit")
    assert bal(client, u["h"], "profit") == Decimal("25.50")
    logs = client.get("/api/admin/audit-logs", headers=admin).json()
    assert any(l["action"] == "CREDIT_WALLET" and l["target_email"] == u["email"] for l in logs)
    deps = client.get("/api/admin/deposits/pending", headers=admin).json()
    assert all(d["tx_type"] == "deposit" for d in deps)   # credits no longer pose as deposits


def test_user_cannot_reach_admin(client, make_user):
    u = make_user()
    assert client.get("/api/admin/stats", headers=u["h"]).status_code == 403


# ── investments ───────────────────────────────
def test_roi_accrual_is_idempotent_and_matures(client, admin, make_user):
    plan = client.post("/api/admin/plans/", headers=admin, json={
        "name": f"Test plan {datetime.now().timestamp()}", "min_amount": "50", "max_amount": "5000",
        "daily_roi_percent": "1.5", "duration_days": 5}).json()
    u = make_user()
    credit(client, admin, u["id"], 200)
    out_of_range = client.post("/api/investments/", headers=u["h"], json={"plan_id": plan["id"], "amount": "10", "accept_risk": True})
    assert out_of_range.status_code == 422
    inv = client.post("/api/investments/", headers=u["h"], json={"plan_id": plan["id"], "amount": "100", "accept_risk": True}).json()
    assert bal(client, u["h"]) == Decimal("100")

    db = SessionLocal()                                  # pretend it started 3 days ago
    row = db.get(UserInvestment, inv["id"])
    row.start_date -= timedelta(days=3)
    row.maturity_date -= timedelta(days=3)
    db.commit()
    for _ in range(3):
        client.post("/api/admin/investments/process-roi", headers=admin)
    assert bal(client, u["h"], "profit") == Decimal("4.50")      # 3 days × 1.50, not 9 × 1.50

    row = db.get(UserInvestment, inv["id"])
    row.start_date -= timedelta(days=10)
    row.maturity_date -= timedelta(days=10)
    db.commit()
    db.close()
    client.post("/api/admin/investments/process-roi", headers=admin)
    client.post("/api/admin/investments/process-roi", headers=admin)
    assert bal(client, u["h"], "profit") == Decimal("7.50")      # capped at 5 days
    assert bal(client, u["h"]) == Decimal("200")                 # principal back once
    mine = client.get("/api/investments/my-investments", headers=u["h"]).json()[0]
    assert mine["status"] == "completed" and mine["days_paid"] == 5

    bad = client.patch(f"/api/admin/plans/{plan['id']}", headers=admin, json={"max_amount": "10"})
    assert bad.status_code == 422                                 # max below min rejected on update
    assert client.delete(f"/api/admin/plans/{plan['id']}", headers=admin).status_code == 409


# ── overview ──────────────────────────────────
def test_admin_overview_and_user_detail(client, admin, make_user):
    u = make_user()
    credit(client, admin, u["id"], 12)
    stats = client.get("/api/admin/stats", headers=admin).json()
    assert stats["users_total"] >= 1 and Decimal(stats["total_main_balance"]) >= 12
    found = client.get("/api/admin/users", headers=admin, params={"q": u["email"]}).json()
    assert found["total"] == 1
    detail = client.get(f"/api/admin/users/{u['id']}", headers=admin).json()
    assert detail["user"]["email"] == u["email"] and len(detail["transactions"]) == 1


def test_account_closure_is_soft(client, admin, make_user):
    u = make_user()
    credit(client, admin, u["id"], 5)
    assert client.delete("/api/auth/account", headers=u["h"]).status_code == 400   # balance left
    client.post("/api/admin/wallets/debit", headers=admin,
                json={"user_id": u["id"], "wallet_type": "main", "amount": "5"})
    assert client.delete("/api/auth/account", headers=u["h"]).status_code == 204
    assert client.post("/api/auth/login", json={"email": u["email"], "password": "User-pass-1"}).status_code == 401


def test_admin_referral_code_never_breaks_deposit_approval(client, admin, make_user, method):
    """Regression: a customer referred by an admin (no wallets) made approval return 404 after crediting."""
    me = client.get("/api/auth/me", headers=admin).json()
    u = make_user(referral_code=me["referral_code"])
    dep = client.post("/api/wallets/deposits/", headers=u["h"], json={
        "payment_method_id": method["id"], "amount": "40", "tx_hash": "0xadminref"}).json()
    r = client.patch(f"/api/admin/deposits/{dep['id']}/review", headers=admin, json={"status": "approved"})
    assert r.status_code == 200, r.text
    assert bal(client, u["h"]) == Decimal("40")


# ── Batch 1: combined endpoints, query budgets, formatting ──
def _queries(r):
    return int(r.headers["X-DB-Queries"])


def test_customer_dashboard_one_request(client, admin, make_user, method):
    u = make_user()
    credit(client, admin, u["id"], "200")
    client.post("/api/wallets/deposits/", headers=u["h"],
                json={"payment_method_id": method["id"], "amount": "50", "tx_hash": "0xdash"})
    r = client.get("/api/users/me/dashboard", headers=u["h"])
    d = r.json()
    assert r.status_code == 200 and d["user"]["email"] == u["email"]
    assert {w["wallet_type"] for w in d["wallets"]} == {"main", "profit"}
    assert len(d["pending"]) == 1 and d["pending"][0]["status"] == "pending"
    assert d["recent"][0]["direction"] in ("in", None) and d["unread"] >= 1
    assert _queries(r) <= 7          # auth + 5 reads, the reads run in parallel


def test_dialog_context(client, make_user, method):
    u = make_user()
    r = client.get("/api/users/me/context", headers=u["h"])
    d = r.json()
    assert any(m["id"] == method["id"] for m in d["payment_methods"]) and len(d["wallets"]) == 2
    assert _queries(r) <= 3


def test_admin_overview_and_badges_are_cheap(client, admin, make_user, method):
    u = make_user()
    client.post("/api/wallets/deposits/", headers=u["h"],
                json={"payment_method_id": method["id"], "amount": "75", "tx_hash": "0xov"})
    r = client.get("/api/admin/overview", headers=admin)
    d = r.json()
    assert d["stats"]["pending_deposits"] >= 1 and d["oldest"]["deposit"] is not None and d["recent"]
    assert _queries(r) <= 8           # was ~22
    b = client.get("/api/admin/queue-counts", headers=admin)
    assert b.json()["deposits"] == d["stats"]["pending_deposits"] and _queries(b) <= 2   # was 12
    # /stats keeps its old contract
    assert client.get("/api/admin/stats", headers=admin).json()["pending_deposits"] == d["stats"]["pending_deposits"]


def test_amounts_in_messages_are_formatted(client, admin, make_user):
    u = make_user()
    credit(client, admin, u["id"], "1234.5")
    msgs = [n["message"] for n in client.get("/api/notifications/", headers=u["h"]).json()]
    assert any("$1,234.50" in m for m in msgs), msgs
    assert not any("00000" in m for m in msgs)


# ── Batch 2: view-only impersonation, roles, legacy records ──
import uuid as _uuid
from app.models import Transaction as _Tx, User as _User
from app.security import hash_password as _hash

CSRF = {"X-Requested-With": "zenfort"}


def _cookie_admin(client):
    """An admin signed in through the browser flow (session cookie), like the real console."""
    email = f"cookie-admin-{_uuid.uuid4().hex[:8]}@test.dev"
    db = SessionLocal()
    db.add(_User(email=email, full_name="Cookie Admin", hashed_password=_hash("Admin-pass-1"), is_active=True,
                 is_admin=True, referral_code=_uuid.uuid4().hex[:8].upper()))
    db.commit(); db.close()
    assert client.post("/api/auth/login", json={"email": email, "password": "Admin-pass-1"}).status_code == 200
    return email


def test_impersonation_is_view_only_and_audited(client, make_user, method):
    u = make_user()
    admin_email = _cookie_admin(client)

    r = client.post(f"/api/admin/users/{u['id']}/impersonate", headers=CSRF)
    assert r.status_code == 200 and r.json()["redirect"] == "/app.html"

    me = client.get("/api/auth/me").json()
    assert me["email"] == u["email"] and me["impersonated_by"] == admin_email and me["impersonation_expires_at"]
    assert client.get("/api/users/me/dashboard").status_code == 200            # reading works

    blocked = client.post("/api/wallets/deposits/", headers=CSRF,
                          json={"payment_method_id": method["id"], "amount": "50", "tx_hash": "0ximp"})
    assert blocked.status_code == 403 and "View only" in blocked.json()["detail"]
    assert client.post("/api/auth/change-password", headers=CSRF,
                       json={"current_password": "x", "new_password": "whatever123"}).status_code == 403
    assert client.patch("/api/notifications/read-all", headers=CSRF).status_code == 403
    assert client.get("/api/admin/stats").status_code == 403                   # no admin powers as the customer

    out = client.post("/api/auth/impersonation/exit", headers=CSRF)
    assert out.status_code == 200 and u["id"] in out.json()["redirect"]
    me = client.get("/api/auth/me").json()
    assert me["email"] == admin_email and me["impersonated_by"] is None
    actions = [(l["action"], l["target_email"]) for l in client.get("/api/admin/audit-logs").json()[:5]]
    assert ("IMPERSONATE_START", u["email"]) in actions and ("IMPERSONATE_END", u["email"]) in actions


def test_impersonation_guards(client, admin, make_user):
    u = make_user()
    other_admin = client.get("/api/auth/me", headers=admin).json()
    _cookie_admin(client)
    assert client.post(f"/api/admin/users/{other_admin['id']}/impersonate", headers=CSRF).status_code == 400
    assert client.post(f"/api/admin/users/{u['id']}/impersonate", headers=u["h"]).status_code == 403
    assert client.post("/api/auth/impersonation/exit", headers=CSRF).status_code == 400   # not impersonating


def test_role_changes(client, admin, make_user):
    u = make_user()
    me = client.get("/api/auth/me", headers=admin).json()
    assert client.patch(f"/api/admin/users/{me['id']}/role", headers=admin, json={"is_admin": False}).status_code == 400
    up = client.patch(f"/api/admin/users/{u['id']}/role", headers=admin, json={"is_admin": True})
    assert up.status_code == 200 and up.json()["is_admin"] is True
    assert client.get("/api/admin/stats", headers=u["h"]).status_code == 200      # new admin can use the console
    down = client.patch(f"/api/admin/users/{u['id']}/role", headers=admin, json={"is_admin": False})
    assert down.json()["is_admin"] is False
    logs = [l["action"] for l in client.get("/api/admin/audit-logs", headers=admin).json()[:3]]
    assert "PROMOTE_ADMIN" in logs and "DEMOTE_ADMIN" in logs


def test_legacy_withdrawal_without_wallet_gives_clear_409(client, admin):
    db = SessionLocal()
    tx = _Tx(amount=100, currency="USD", tx_type="withdrawal", status="pending", description="legacy")
    db.add(tx); db.commit(); tx_id = str(tx.id); db.close()
    r = client.patch(f"/api/admin/withdrawals/{tx_id}/review", headers=admin,
                     json={"status": "rejected", "rejection_reason": "x"})
    assert r.status_code == 409 and "legacy" in r.json()["detail"]


# ── Batch 3: consent, profile photos, private file storage ──
import httpx as _httpx
from app.services import storage as _storage
from app.services.storage import SupabaseStorage as _Supa


def test_signup_requires_terms_and_records_version(client):
    body = {"full_name": "No Consent", "email": f"nc-{_uuid.uuid4().hex[:6]}@test.dev", "password": "User-pass-1",
            "confirm_password": "User-pass-1", "country": "Nigeria"}
    r = client.post("/api/auth/signup", json=body)
    assert r.status_code == 422 and "Terms" in r.text
    ok = client.post("/api/auth/signup", json={**body, "accept_terms": True})
    assert ok.status_code == 201 and ok.json()["terms_current"] is True and ok.json()["terms_accepted_at"]


def test_existing_user_can_accept_new_terms(client, make_user):
    u = make_user()
    db = SessionLocal(); usr = db.get(_User, _uuid.UUID(u["id"])); usr.terms_version = "2020-01"; db.commit(); db.close()
    assert client.get("/api/auth/me", headers=u["h"]).json()["terms_current"] is False
    r = client.post("/api/auth/accept-terms", headers=u["h"])
    assert r.json()["terms_current"] is True


def test_investing_requires_risk_acknowledgement(client, admin, make_user):
    plan = client.post("/api/admin/plans/", headers=admin, json={"name": f"Risk {_uuid.uuid4().hex[:5]}", "min_amount": "10",
                       "max_amount": "100", "daily_roi_percent": "1", "duration_days": 5}).json()
    u = make_user(); credit(client, admin, u["id"], 50)
    r = client.post("/api/investments/", headers=u["h"], json={"plan_id": plan["id"], "amount": "20"})
    assert r.status_code == 422 and "Risk Disclosure" in r.text


def test_profile_photo_upload_replace_remove(client, make_user):
    u = make_user()
    r = client.post("/api/auth/avatar", headers=u["h"], json={"image": PNG})
    url1 = r.json()["avatar_url"]
    assert r.status_code == 200 and url1.startswith("/api/files/public/avatars/")
    img = client.get(url1)
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    url2 = client.post("/api/auth/avatar", headers=u["h"], json={"image": PNG}).json()["avatar_url"]
    assert url2 != url1 and client.get(url1).status_code == 404          # old photo deleted
    assert client.delete("/api/auth/avatar", headers=u["h"]).json()["avatar_url"] is None
    assert client.get(url2).status_code == 404
    bad = client.post("/api/auth/avatar", headers=u["h"], json={"image": "data:application/pdf;base64,JVBERi0="})
    assert bad.status_code == 422


def test_private_files_need_signed_links(client, admin, make_user, method):
    u = make_user()
    client.post("/api/auth/kyc/submit", headers=u["h"], json={"kyc_document_url": PNG})
    db = SessionLocal(); ref = db.get(_User, _uuid.UUID(u["id"])).kyc_document_url; db.close()
    assert ref.startswith("local://private-docs/kyc/") and "base64" not in ref        # bytes no longer in the DB

    doc = client.get(f"/api/admin/kyc/{u['id']}/document", headers=admin).json()
    assert doc["content_type"] == "image/png" and doc["document"].startswith("/api/files/signed/")
    assert client.get(doc["document"]).status_code == 200
    assert client.get(doc["document"][:-3] + "abc").status_code == 403               # tampered link refused
    assert client.get(f"/api/admin/kyc/{u['id']}/document", headers=u["h"]).status_code == 403
    path = ref.split("://", 1)[1].split("/", 1)[1]
    assert client.get(f"/api/files/public/private-docs/{path}").status_code == 404   # not reachable publicly

    dep = client.post("/api/wallets/deposits/", headers=u["h"], json={"payment_method_id": method["id"], "amount": "30",
                      "tx_hash": "0xstore", "proof_image_url": PNG}).json()
    assert dep["has_proof"] is True
    detail = client.get(f"/api/admin/transactions/{dep['id']}", headers=admin).json()
    assert detail["proof_image_url"].startswith("/api/files/signed/") and client.get(detail["proof_image_url"]).status_code == 200
    own = client.get(f"/api/wallets/transactions/{dep['id']}", headers=u["h"]).json()
    assert own["proof_image_url"].startswith("/api/files/signed/")


def test_legacy_data_url_rows_still_readable(client, admin, make_user):
    u = make_user()
    db = SessionLocal(); usr = db.get(_User, _uuid.UUID(u["id"])); usr.kyc_document_url = PNG; usr.kyc_status = "PENDING"
    db.commit(); db.close()
    doc = client.get(f"/api/admin/kyc/{u['id']}/document", headers=admin).json()
    assert doc["document"] == PNG and doc["content_type"] == "image/png"


def test_supabase_backend_speaks_the_storage_api():
    calls = []

    def handler(req: _httpx.Request):
        calls.append((req.method, req.url.path, dict(req.headers)))
        if "/object/sign/" in req.url.path:
            return _httpx.Response(200, json={"signedURL": "/object/sign/private-docs/kyc/a.png?token=T"})
        return _httpx.Response(200, json={"Key": "ok"})

    s = _Supa("https://proj.supabase.co", "service-key", client=_httpx.Client(transport=_httpx.MockTransport(handler)))
    s.put("private-docs", "kyc/a.png", b"x", "image/png")
    method_, path_, headers_ = calls[-1]
    assert (method_, path_) == ("POST", "/storage/v1/object/private-docs/kyc/a.png")
    assert headers_["authorization"] == "Bearer service-key" and headers_["apikey"] == "service-key"
    assert headers_["content-type"] == "image/png" and headers_["x-upsert"] == "true"
    assert s.signed_url("private-docs", "kyc/a.png", 60) == \
        "https://proj.supabase.co/storage/v1/object/sign/private-docs/kyc/a.png?token=T"
    assert s.public_url("avatars", "u/p.jpg") == "https://proj.supabase.co/storage/v1/object/public/avatars/u/p.jpg"
    s.delete("avatars", "u/p.jpg")
    assert calls[-1][:2] == ("DELETE", "/storage/v1/object/avatars")

    absolute = _Supa("https://proj.supabase.co", "k", client=_httpx.Client(transport=_httpx.MockTransport(
        lambda r: _httpx.Response(200, json={"signedURL": "https://proj.supabase.co/storage/v1/object/sign/b/p?token=Z"}))))
    assert absolute.signed_url("b", "p", 60) == "https://proj.supabase.co/storage/v1/object/sign/b/p?token=Z"


# ── Batch 4: public data, branded emails ──
from app.services.email_templates import html_to_text as _h2t, render_email as _render


def test_public_endpoints_are_safe_and_fresh(client, admin, method):
    methods = client.get("/api/public/payment-methods")              # no sign-in needed
    assert methods.status_code == 200 and methods.headers["cache-control"].startswith("public")
    m = next(x for x in methods.json() if x["network"] == method["network"])
    assert "deposit_address" not in m and "id" not in m and m["asset"] == "USDT"
    name = f"Public plan {_uuid.uuid4().hex[:5]}"
    client.get("/api/public/plans")                                   # warm the cache
    client.post("/api/admin/plans/", headers=admin, json={"name": name, "min_amount": "10", "max_amount": "99",
                "daily_roi_percent": "0.5", "duration_days": 7})
    assert any(p["name"] == name for p in client.get("/api/public/plans").json())   # admin change visible at once


def test_branded_email_escapes_and_has_text_version():
    html = _render("Withdrawal sent", "<b>Eve</b>", ["We sent $98.50 worth of USDT."],
                   cta=("Open your account", "https://zenfortmarkets.com/app.html#/wallet"),
                   rows=[("Amount sent", "$98.50"), ("To address", "TQn9<script>")])
    assert "<b>Eve</b>" not in html and "&lt;b&gt;Eve&lt;/b&gt;" in html and "<script>" not in html
    assert "Amount sent" in html and "Open your account" in html and "/terms.html" in html
    text = _h2t(html)
    assert "Hi <b>Eve</b>," in text and "Amount sent" in text and "$98.50" in text
    assert "Open your account (https://zenfortmarkets.com/app.html#/wallet)" in text and "<" not in text.replace("<b>", "").replace("</b>", "").replace("<script>", "")


# ── Batch 5: errors, CORS, rate limits, password reset, 2FA, email delivery, support ──
import re as _re
import time as _time

import pyotp as _pyotp

from app.config import settings as _settings
from app.services import mailer as _mailer, ratelimit as _rl


def _login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_friendly_errors_and_cors(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and "couldn’t find" in r.json()["detail"] and r.json()["detail"] != "Not Found"
    for origin, ok in [("http://localhost:3000", True), ("https://zenfortmarkets.vercel.app", True),
                       ("https://zenfortmarkets-git-dev-me.vercel.app", True), ("https://zenfortmarkets.online", True),
                       ("https://www.zenfortmarkets.online", True), ("https://evil.example", False),
                       ("https://zenfortmarkets.vercel.app.evil.com", False)]:
        pre = client.options("/api/auth/login", headers={"Origin": origin, "Access-Control-Request-Method": "POST",
                                                         "Access-Control-Request-Headers": "content-type,x-requested-with"})
        assert (pre.headers.get("access-control-allow-origin") == origin) is ok, origin
        if ok:
            assert pre.headers.get("access-control-allow-credentials") == "true"


def test_login_is_rate_limited(client, make_user):
    u = make_user()
    for _ in range(9):
        assert _login(client, u["email"], "wrong-password").status_code == 401
    assert _login(client, u["email"], "User-pass-1").status_code == 200          # success clears the failures
    for _ in range(10):
        assert _login(client, u["email"], "wrong-password").status_code == 401
    r = _login(client, u["email"], "User-pass-1")
    assert r.status_code == 429 and "Too many" in r.json()["detail"]             # 10 failures → locked, even with the right password
    _rl._hits.clear()


def test_password_reset_flow(client, make_user, monkeypatch):
    monkeypatch.setattr(_settings, "DEV_OUTBOX", True)
    _rl._hits.clear(); _mailer.OUTBOX.clear()
    u = make_user()
    unknown = client.post("/api/auth/forgot-password", json={"email": "nobody-here@test.dev"})
    known = client.post("/api/auth/forgot-password", json={"email": u["email"]})
    assert unknown.status_code == known.status_code == 202 and unknown.json() == known.json()   # no enumeration
    mail = [m for m in _mailer.OUTBOX if m["to"] == u["email"]][-1]
    token = _re.search(r"reset-password\.html\?token=([\w.-]+)", mail["html"]).group(1)

    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "short"}).status_code == 422
    ok = client.post("/api/auth/reset-password", json={"token": token, "new_password": "Brand-new-pass-9"})
    assert ok.status_code == 200
    assert client.get("/api/auth/me", headers=u["h"]).status_code == 401            # old session signed out
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "Another-pass-9"}).status_code == 400  # one use
    assert _login(client, u["email"], "User-pass-1").status_code == 401
    assert _login(client, u["email"], "Brand-new-pass-9").status_code == 200
    assert any(m["to"] == u["email"] and "was reset" in m["subject"] for m in _mailer.OUTBOX)


def test_change_password_signs_out_other_sessions(client, make_user):
    u = make_user()
    other_device = u["h"]
    r = client.post("/api/auth/change-password", headers=other_device,
                    json={"current_password": "User-pass-1", "new_password": "Changed-pass-9"})
    assert r.status_code == 204 and "zf_session" in r.cookies                       # this device gets a fresh session
    assert client.get("/api/auth/me", headers=other_device).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer " + r.cookies["zf_session"]}).status_code == 200


def test_two_factor_full_lifecycle(client, admin, make_user):
    _rl._hits.clear()
    u = make_user()
    assert client.post("/api/auth/2fa/setup", headers=u["h"], json={"password": "nope"}).status_code == 400
    setup = client.post("/api/auth/2fa/setup", headers=u["h"], json={"password": "User-pass-1"}).json()
    totp = _pyotp.TOTP(setup["secret"])
    assert setup["otpauth_uri"].startswith("otpauth://totp/Zenfort%20Markets:")
    assert client.post("/api/auth/2fa/enable", headers=u["h"], json={"code": "000000"}).status_code == 400
    en = client.post("/api/auth/2fa/enable", headers=u["h"], json={"code": totp.now()})
    codes = en.json()["recovery_codes"]
    assert en.status_code == 200 and len(codes) == 8 and _re.fullmatch(r"[A-Z2-9]{4}-[A-Z2-9]{4}", codes[0])
    assert client.get("/api/auth/me", headers=u["h"]).status_code == 401              # older sessions ended
    me = client.get("/api/auth/me", headers={"Authorization": "Bearer " + en.cookies["zf_session"]}).json()
    assert me["totp_enabled"] is True

    step1 = _login(client, u["email"], "User-pass-1").json()
    assert step1["two_factor_required"] is True and "access_token" not in step1
    assert client.post("/api/auth/login/2fa", json={"challenge": step1["challenge"], "code": "123456"}).status_code == 400
    # A code from the next 30 s window (allowed clock drift) that hasn't been used yet
    code = totp.at(_time.time() + 30)
    ok = client.post("/api/auth/login/2fa", json={"challenge": step1["challenge"], "code": code})
    assert ok.status_code == 200 and ok.json()["access_token"]
    replay = client.post("/api/auth/login/2fa", json={"challenge": _login(client, u["email"], "User-pass-1").json()["challenge"], "code": code})
    assert replay.status_code == 400                                                  # same code can't be reused

    ch = _login(client, u["email"], "User-pass-1").json()["challenge"]
    rec = client.post("/api/auth/login/2fa", json={"challenge": ch, "code": codes[0].lower()})
    assert rec.status_code == 200
    ch = _login(client, u["email"], "User-pass-1").json()["challenge"]
    assert client.post("/api/auth/login/2fa", json={"challenge": ch, "code": codes[0]}).status_code == 400   # one use only
    h = {"Authorization": "Bearer " + rec.json()["access_token"]}
    assert client.get("/api/auth/2fa", headers=h).json()["recovery_codes_left"] == 7

    reset = client.post(f"/api/admin/users/{u['id']}/reset-2fa", headers=admin)
    assert reset.status_code == 200 and reset.json()["totp_enabled"] is False
    assert client.get("/api/auth/me", headers=h).status_code == 401                   # signed out by the reset
    assert "access_token" in _login(client, u["email"], "User-pass-1").json()          # password-only again
    assert any(l["action"] == "RESET_2FA" for l in client.get("/api/admin/audit-logs", headers=admin).json()[:3])
    _rl._hits.clear()


def test_admin_email_reports_delivery(client, admin, make_user, monkeypatch):
    u = make_user()
    ok = client.post("/api/admin/emails/send-user", headers=admin, json={"user_id": u["id"], "subject": "Hi", "body": "Hello there"}).json()
    assert ok["email_sent"] is True and ok["in_app"] is True
    monkeypatch.setattr(_mailer, "send", lambda *a, **k: _mailer.Result(False, "403: You can only send testing emails to your own email address"))
    bad = client.post("/api/admin/emails/send-user", headers=admin, json={"user_id": u["id"], "subject": "Hi", "body": "Hello again"}).json()
    assert bad["email_sent"] is False and "own email" in bad["email_error"]
    titles = [n["title"] for n in client.get("/api/notifications/", headers=u["h"]).json()]
    assert titles.count("Message from support") == 2                                  # in-app copy always lands


def test_admin_broadcast_sends_and_records_delivery(client, admin, make_user, monkeypatch):
    monkeypatch.setattr(_settings, "DEV_OUTBOX", True)
    _mailer.OUTBOX.clear()
    u = make_user()
    r = client.post("/api/admin/emails/broadcast", headers=admin, json={"subject": "News", "body": "Hello all", "target_filter": "all"})
    assert r.status_code == 201
    log = next(l for l in client.get("/api/admin/emails/history", headers=admin).json() if l["id"] == r.json()["id"])
    assert log["delivered_count"] == log["recipient_count"] > 0 and log["failed_count"] == 0
    assert any(m["to"] == u["email"] and m["subject"] == "News" for m in _mailer.OUTBOX)
    assert "New announcement" in [n["title"] for n in client.get("/api/notifications/", headers=u["h"]).json()]

    monkeypatch.setattr(_mailer, "send_batch", lambda msgs: (_ for _ in ()).throw(RuntimeError("boom")))
    r = client.post("/api/admin/emails/broadcast", headers=admin, json={"subject": "Oops", "body": "x", "target_filter": "all"})
    log = next(l for l in client.get("/api/admin/emails/history", headers=admin).json() if l["id"] == r.json()["id"])
    assert log["delivered_count"] == 0 and "boom" in log["last_error"]                # never stuck on "Sending…"


def test_mailer_speaks_resend_api(monkeypatch):
    import httpx
    seen = {}

    def handler(req):
        seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers["authorization"], json.loads(req.content)
        if seen["body"]["to"] == ["blocked@x.dev"]:
            return httpx.Response(403, json={"statusCode": 403, "name": "validation_error",
                                             "message": "You can only send testing emails to your own email address"})
        return httpx.Response(200, json={"id": "abc"})

    import json
    monkeypatch.setattr(_settings, "RESEND_API_KEY", "re_live_123")
    monkeypatch.setattr(_settings, "EMAIL_REPLY_TO", "support@zenfortmarkets.online")
    monkeypatch.setattr(_mailer, "_client", httpx.Client(transport=httpx.MockTransport(handler)))
    r = _mailer.send("a@x.dev", "Subject", "<p>Hello <b>you</b></p>")
    assert r.ok and seen["url"] == "https://api.resend.com/emails" and seen["auth"] == "Bearer re_live_123"
    assert seen["body"]["reply_to"] == "support@zenfortmarkets.online" and seen["body"]["text"] and seen["body"]["html"]
    bad = _mailer.send("blocked@x.dev", "Subject", "<p>x</p>")
    assert not bad.ok and bad.reason.startswith("403") and "Verify your sending domain" in bad.reason


def test_support_requests(client, make_user, monkeypatch):
    monkeypatch.setattr(_settings, "DEV_OUTBOX", True)
    _rl._hits.clear(); _mailer.OUTBOX.clear()
    body = {"name": "Ada", "email": "ada@test.dev", "message": "My deposit has been pending for two days",
            "transcript": [{"who": "you", "text": "where is my deposit"}, {"who": "assistant", "text": "Deposits are reviewed…"}],
            "page": "/app.html#/wallet"}
    r = client.post("/api/support/requests", json=body)
    assert r.status_code == 201 and r.json()["reference"].startswith("ZF-")
    mail = _mailer.OUTBOX[-1]
    assert mail["to"] == _settings.SUPPORT_EMAIL and "where is my deposit" in mail["text"] and "pending for two days" in mail["text"]
    assert client.post("/api/support/requests", json={**body, "message": "hi"}).status_code == 422
    n = len(_mailer.OUTBOX)
    assert client.post("/api/support/requests", json={**body, "website": "http://spam"}).status_code == 201
    assert len(_mailer.OUTBOX) == n                                                   # honeypot: silently dropped
    assert client.post("/api/support/requests", json=body).status_code == 201
    assert client.post("/api/support/requests", json=body).status_code == 201
    assert client.post("/api/support/requests", json=body).status_code == 429         # 3 per email per hour
    _rl._hits.clear()

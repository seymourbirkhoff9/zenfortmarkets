"""
Integration tests run against a real, disposable PostgreSQL database.

    TEST_DATABASE_URL=postgresql://user:pass@localhost/zenfort_test pytest -q

Never point this at Supabase/production: the schema is dropped and recreated.
"""
import os
import uuid

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL")
if not TEST_DB:
    pytest.skip("Set TEST_DATABASE_URL to a disposable Postgres database.", allow_module_level=True)
import tempfile
os.environ.setdefault("LOCAL_UPLOAD_DIR", tempfile.mkdtemp(prefix="zf-uploads-"))
os.environ.update(SUPABASE_URL="", SUPABASE_SERVICE_ROLE_KEY="")       # tests use local file storage
os.environ.update(DATABASE_URL=TEST_DB, SECRET_KEY=os.environ.get("SECRET_KEY", "x" * 40),
                  RESEND_API_KEY="re_XXXX", ENABLE_SCHEDULER="false", DB_KEEP_WARM="false")

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, User  # noqa: E402
from app.security import hash_password  # noqa: E402

PNG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
       "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


@pytest.fixture(scope="session", autouse=True)
def schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def _bearer(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin(client):
    email = f"admin-{uuid.uuid4().hex[:8]}@test.dev"
    db = SessionLocal()
    db.add(User(email=email, full_name="Ada Admin", hashed_password=hash_password("Admin-pass-1"),
                is_active=True, is_admin=True, referral_code=uuid.uuid4().hex[:8].upper()))
    db.commit()
    db.close()
    return _bearer(client, email, "Admin-pass-1")


@pytest.fixture()
def make_user(client):
    def _make(referral_code=None):
        email = f"user-{uuid.uuid4().hex[:8]}@test.dev"
        body = {"full_name": "Tunde Test", "email": email, "password": "User-pass-1",
                "confirm_password": "User-pass-1", "country": "Nigeria", "accept_terms": True}
        if referral_code:
            body["referral_code"] = referral_code
        r = client.post("/api/auth/signup", json=body)
        assert r.status_code == 201, r.text
        return {"email": email, "id": r.json()["id"], "code": r.json()["referral_code"],
                "h": _bearer(client, email, "User-pass-1")}
    return _make


@pytest.fixture()
def method(client, admin):
    r = client.post("/api/admin/payment-methods", headers=admin, json={
        "asset": "usdt", "network": f"TRC20-{uuid.uuid4().hex[:4]}",
        "deposit_address": "TXyz1234567890abcdefABCDEF", "min_deposit": "10",
        "min_withdrawal": "20", "withdrawal_fee": "1.50"})
    assert r.status_code == 201, r.text
    return r.json()

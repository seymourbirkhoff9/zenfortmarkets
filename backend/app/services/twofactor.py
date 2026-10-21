"""
app/services/twofactor.py — authenticator-app (TOTP) codes and recovery codes.

* The TOTP secret is stored encrypted (Fernet, key derived from SECRET_KEY).
* A code can't be reused: we remember the last accepted 30-second step.
* Codes from the previous/next step are accepted to tolerate clock drift.
* Recovery codes: 8 random one-time codes; only their SHA-256 hashes are stored.
"""
import base64
import hashlib
import json
import secrets
import time
from typing import List, Optional, Tuple

import pyotp
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

ISSUER = "Zenfort Markets"
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"      # no 0/O/1/I confusion


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(("totp:" + settings.SECRET_KEY).encode()).digest())
    return Fernet(key)


def new_secret() -> Tuple[str, str]:
    """Returns (plain secret for the QR code, encrypted secret for the database)."""
    secret = pyotp.random_base32()
    return secret, _fernet().encrypt(secret.encode()).decode()


def decrypt(encrypted: Optional[str]) -> Optional[str]:
    if not encrypted:
        return None
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken:
        return None


def provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def check_code(encrypted_secret: str, code: str, last_step: Optional[int], now: Optional[float] = None) -> Optional[int]:
    """Returns the accepted time step (to store), or None. Rejects reused or stale codes."""
    secret = decrypt(encrypted_secret)
    code = "".join(c for c in (code or "") if c.isdigit())
    if not secret or len(code) != 6:
        return None
    totp = pyotp.TOTP(secret)
    now = now or time.time()
    current = int(now // totp.interval)
    for step in (current, current - 1, current + 1):
        if last_step is not None and step <= last_step:
            continue
        if secrets.compare_digest(totp.at(step * totp.interval), code):
            return step
    return None


def _hash(code: str) -> str:
    return hashlib.sha256(code.replace("-", "").upper().encode()).hexdigest()


def new_recovery_codes(n: int = 8) -> Tuple[List[str], str]:
    """Returns (codes to show the user once, JSON of hashes to store)."""
    codes = ["".join(secrets.choice(_ALPHABET) for _ in range(4)) + "-" + "".join(secrets.choice(_ALPHABET) for _ in range(4))
             for _ in range(n)]
    return codes, json.dumps([_hash(c) for c in codes])


def use_recovery_code(stored: Optional[str], code: str) -> Optional[str]:
    """If `code` matches an unused recovery code, returns the updated JSON (code removed); else None."""
    if not stored or not code:
        return None
    hashes = json.loads(stored)
    h = _hash(code.strip())
    if h not in hashes:
        return None
    hashes.remove(h)
    return json.dumps(hashes)


def remaining(stored: Optional[str]) -> int:
    return len(json.loads(stored)) if stored else 0

"""
app/services/storage.py — files (profile photos, ID documents, payment screenshots).

Two backends behind one interface:
  * Supabase Storage, when SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set (production).
  * A local folder, otherwise (development and tests). Same behaviour, served by /api/files.

What the database stores is a *reference*, never the bytes:
    sb://<bucket>/<path>      a Supabase Storage object
    local://<bucket>/<path>   a file under LOCAL_UPLOAD_DIR
    data:<mime>;base64,...    legacy rows from before this change; still readable

Public bucket (profile photos): permanent public URL.
Private bucket (ID documents, payment screenshots): short-lived signed URL, issued only by
endpoints that have already checked the caller may see the file.
"""
import base64
import mimetypes
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

import httpx
from fastapi import HTTPException
from jose import jwt

from app.config import settings

_DATA_URL = re.compile(r"^data:(?P<mime>[\w/+.-]+);base64,(?P<data>.+)$", re.S)
EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "application/pdf": "pdf"}


def decode_data_url(value: str) -> Tuple[bytes, str]:
    m = _DATA_URL.match(value or "")
    if not m:
        raise HTTPException(status_code=422, detail="Upload a file.")
    return base64.b64decode(m.group("data")), m.group("mime").lower()


def new_path(prefix: str, mime: str) -> str:
    """Unguessable object name, e.g. kyc/<user-id>/20261020-1a2b3c4d5e.jpg"""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{prefix}/{stamp}-{secrets.token_hex(8)}.{EXT.get(mime, 'bin')}"


# ── Backends ──────────────────────────────────
class SupabaseStorage:
    scheme = "sb"

    def __init__(self, url: str, key: str, client: Optional[httpx.Client] = None):
        self.base = url.rstrip("/") + "/storage/v1"
        self.client = client or httpx.Client(timeout=30)
        self.headers = {"Authorization": f"Bearer {key}", "apikey": key}

    def put(self, bucket: str, path: str, data: bytes, mime: str) -> None:
        r = self.client.post(f"{self.base}/object/{bucket}/{path}", content=data,
                             headers={**self.headers, "Content-Type": mime, "x-upsert": "true"})
        if r.status_code >= 300:
            raise HTTPException(status_code=502, detail="The file couldn't be stored. Try again.")

    def public_url(self, bucket: str, path: str) -> str:
        return f"{self.base}/object/public/{bucket}/{path}"

    def signed_url(self, bucket: str, path: str, seconds: int) -> str:
        r = self.client.post(f"{self.base}/object/sign/{bucket}/{path}", json={"expiresIn": seconds},
                             headers=self.headers)
        if r.status_code >= 300:
            raise HTTPException(status_code=502, detail="The file couldn't be opened. Try again.")
        signed = r.json().get("signedURL") or r.json().get("signedUrl")
        # Supabase returns a path relative to /storage/v1; tolerate an absolute URL too.
        return signed if signed.startswith("http") else f"{self.base}{signed}"

    def delete(self, bucket: str, path: str) -> None:
        self.client.request("DELETE", f"{self.base}/object/{bucket}", json={"prefixes": [path]},
                            headers=self.headers)


class LocalStorage:
    scheme = "local"

    def __init__(self, root: str):
        self.root = Path(root)

    def _file(self, bucket: str, path: str) -> Path:
        f = (self.root / bucket / path).resolve()
        if self.root.resolve() not in f.parents:
            raise HTTPException(status_code=400, detail="Bad file path.")
        return f

    def put(self, bucket: str, path: str, data: bytes, mime: str) -> None:
        f = self._file(bucket, path)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)

    def public_url(self, bucket: str, path: str) -> str:
        return f"/api/files/public/{bucket}/{path}"

    def signed_url(self, bucket: str, path: str, seconds: int) -> str:
        token = jwt.encode({"typ": "file", "b": bucket, "p": path,
                            "exp": datetime.now(timezone.utc) + timedelta(seconds=seconds)},
                           settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return f"/api/files/signed/{token}"

    def delete(self, bucket: str, path: str) -> None:
        f = self._file(bucket, path)
        if f.exists():
            f.unlink()

    def read(self, bucket: str, path: str) -> Tuple[bytes, str]:
        f = self._file(bucket, path)
        if not f.is_file():
            raise HTTPException(status_code=404, detail="File not found.")
        return f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream"


_backend = None


def backend():
    global _backend
    if _backend is None:
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            _backend = SupabaseStorage(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        else:
            _backend = LocalStorage(settings.LOCAL_UPLOAD_DIR)
    return _backend


# ── Public API used by routers ────────────────
def store(data_url: str, prefix: str, private: bool) -> str:
    """Save an (already validated) data URL; returns the reference to keep in the database."""
    data, mime = decode_data_url(data_url)
    bucket = settings.STORAGE_PRIVATE_BUCKET if private else settings.STORAGE_PUBLIC_BUCKET
    path = new_path(prefix, mime)
    b = backend()
    b.put(bucket, path, data, mime)
    return f"{b.scheme}://{bucket}/{path}"


def _split(ref: str) -> Tuple[str, str, str]:
    scheme, rest = ref.split("://", 1)
    bucket, path = rest.split("/", 1)
    return scheme, bucket, path


def url_for(ref: Optional[str]) -> Optional[str]:
    """A URL the browser can open: public URL, short-lived signed URL, or a legacy data URL."""
    if not ref:
        return None
    if ref.startswith("data:"):
        return ref
    _, bucket, path = _split(ref)
    b = backend()
    if bucket == settings.STORAGE_PUBLIC_BUCKET:
        return b.public_url(bucket, path)
    return b.signed_url(bucket, path, settings.SIGNED_URL_SECONDS)


def content_type(ref: Optional[str]) -> Optional[str]:
    if not ref:
        return None
    if ref.startswith("data:"):
        return ref[5:ref.index(";")]
    return mimetypes.guess_type(ref)[0]


def remove(ref: Optional[str]) -> None:
    """Best effort: a failed delete must never break the action that replaced the file."""
    if not ref or ref.startswith("data:"):
        return
    try:
        _, bucket, path = _split(ref)
        backend().delete(bucket, path)
    except Exception:
        pass

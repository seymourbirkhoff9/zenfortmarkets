from __future__ import annotations
"""
app/utils/uploads.py — validation for files sent as data URLs.

Proof-of-payment images and KYC documents arrive as `data:<mime>;base64,<...>`.
We check the MIME type, that the payload really is base64, and the decoded size.
For production, move these to object storage (e.g. Supabase Storage) and keep
only the object path in the database.
"""
import base64
import binascii
import re

from fastapi import HTTPException

from app.config import settings

_DATA_URL = re.compile(r"^data:(?P<mime>[\w/+.-]+);base64,(?P<data>[A-Za-z0-9+/=\s]+)$")

IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}
DOCUMENT_TYPES = IMAGE_TYPES | {"application/pdf"}


def validate_data_url(value: str, allowed: set[str], field: str) -> str:
    match = _DATA_URL.match(value or "")
    if not match:
        raise HTTPException(status_code=422, detail=f"{field} must be an uploaded file.")
    mime = match.group("mime").lower()
    if mime not in allowed:
        nice = ", ".join(sorted(t.split("/")[1].upper() for t in allowed))
        raise HTTPException(status_code=422, detail=f"{field} must be one of: {nice}.")
    try:
        raw = base64.b64decode(match.group("data"), validate=False)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail=f"{field} is not a valid file.")
    if len(raw) > settings.MAX_UPLOAD_BYTES:
        mb = settings.MAX_UPLOAD_BYTES / 1_000_000
        raise HTTPException(status_code=413, detail=f"{field} must be smaller than {mb:g} MB.")
    return value

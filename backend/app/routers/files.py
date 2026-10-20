"""
app/routers/files.py — serves files in LOCAL storage mode (development, tests).

In production (Supabase Storage) the browser loads files straight from Supabase:
public URLs for profile photos, short-lived signed URLs for private documents.
Here we mimic that: public files by path, private files only with a signed, expiring token.
"""
from fastapi import APIRouter, HTTPException, Response
from jose import JWTError, jwt

from app.config import settings
from app.services.storage import LocalStorage, backend

router = APIRouter(prefix="/api/files", tags=["Files (local mode)"], include_in_schema=False)


def _local() -> LocalStorage:
    b = backend()
    if not isinstance(b, LocalStorage):
        raise HTTPException(status_code=404, detail="Not found.")
    return b


@router.get("/public/{bucket}/{path:path}")
def public_file(bucket: str, path: str):
    if bucket != settings.STORAGE_PUBLIC_BUCKET:
        raise HTTPException(status_code=404, detail="Not found.")
    data, mime = _local().read(bucket, path)
    return Response(data, media_type=mime, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/signed/{token}")
def signed_file(token: str):
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=403, detail="This link has expired.")
    if claims.get("typ") != "file":
        raise HTTPException(status_code=403, detail="This link has expired.")
    data, mime = _local().read(claims["b"], claims["p"])
    return Response(data, media_type=mime, headers={"Cache-Control": "private, no-store"})

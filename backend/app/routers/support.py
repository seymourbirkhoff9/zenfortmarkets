"""
app/routers/support.py — escalations from the support assistant (chat widget).

Anyone can send one (signed in or not). It's emailed to SUPPORT_EMAIL with the
conversation attached and reply-to set to the customer, and, when the sender is
signed in, every admin also gets an in-app alert. Rate-limited per IP and per email.
"""
import secrets
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.security import SESSION_COOKIE, decode_access_payload
from app.services import mailer, ratelimit
from app.services.admin_alerts import notify_admins
from app.services.email_templates import render_email

router = APIRouter(prefix="/api/support", tags=["Support"])


class ChatLine(BaseModel):
    who: str          # "you" | "assistant"
    text: str


class SupportRequest(BaseModel):
    name: str
    email: EmailStr
    message: str
    transcript: List[ChatLine] = []
    page: Optional[str] = None
    website: Optional[str] = None        # honeypot: real people leave it empty

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 5:
            raise ValueError("Tell us a little more about the problem.")
        return v[:4000]

    @field_validator("name")
    @classmethod
    def name_ok(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Please add your name.")
        return v[:120]


def _signed_in_user(request: Request, db: Session) -> Optional[User]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        payload = decode_access_payload(token)
    except HTTPException:
        return None
    return db.query(User).filter(User.email == payload["sub"]).first()


@router.post("/requests", status_code=201)
def create_request(payload: SupportRequest, request: Request, db: Session = Depends(get_db)):
    if payload.website:                                   # bot filled the hidden field
        return {"reference": "ZF-" + secrets.token_hex(3).upper(), "emailed": True}
    ratelimit.limit(f"support:{ratelimit.client_ip(request)}", 5, 60 * 60,
                    "You’ve sent several requests already. We’ll reply by email; please wait before sending more.")
    ratelimit.limit(f"support:{payload.email.lower()}", 3, 60 * 60,
                    "You’ve sent several requests already. We’ll reply by email; please wait before sending more.")
    ref = "ZF-" + secrets.token_hex(3).upper()
    user = _signed_in_user(request, db)
    who = f"{payload.name} <{payload.email}>" + (f" (signed in as {user.email})" if user else " (not signed in)")
    lines = [f"Reference: {ref}", f"From: {who}", f"Page: {payload.page or 'unknown'}", "", "Message:", payload.message]
    if payload.transcript:
        lines += ["", "Conversation with the assistant:"] + [f"{l.who}: {l.text[:600]}" for l in payload.transcript[-20:]]
    html = render_email(f"Support request {ref}", "Support team", lines)
    result = mailer.send(settings.SUPPORT_EMAIL, f"[{ref}] Support request from {payload.name}", html, reply_to=payload.email)
    if user:
        notify_admins(db, f"Support request {ref}", f"{payload.name} ({payload.email}): {payload.message[:300]}", "account")
        db.commit()
    return {"reference": ref, "emailed": result.ok}

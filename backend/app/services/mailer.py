"""
app/services/mailer.py — sends email through Resend's HTTP API.

We call the API directly (not the SDK): every failure comes back as a clear
(ok=False, reason) instead of being swallowed, and broadcasts use Resend's batch
endpoint (100 emails per request).

Without a real RESEND_API_KEY, emails are only logged (and kept in the dev outbox
when DEV_OUTBOX=true), so development never needs a mail account.
"""
import logging
from collections import deque
from dataclasses import dataclass
from typing import List, Optional

import httpx

from app.config import settings
from app.services.email_templates import html_to_text

logger = logging.getLogger("zenfort.mail")
API = "https://api.resend.com"
_client = httpx.Client(timeout=20)
OUTBOX: deque = deque(maxlen=50)          # dev only


@dataclass
class Result:
    ok: bool
    reason: Optional[str] = None


def configured() -> bool:
    key = (settings.RESEND_API_KEY or "").strip()
    return bool(key) and not key.startswith("re_XXXX")


def _payload(to: str, subject: str, html: str, reply_to: Optional[str] = None) -> dict:
    data = {"from": settings.EMAIL_FROM, "to": [to], "subject": subject, "html": html, "text": html_to_text(html)}
    reply = reply_to or settings.EMAIL_REPLY_TO
    if reply:
        data["reply_to"] = reply
    return data


def _explain(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        msg = body.get("message") or body.get("error") or str(body)
    except ValueError:
        msg = resp.text[:200]
    if resp.status_code == 403 and "own email" in msg.lower():
        msg += " (Verify your sending domain in Resend to email other people.)"
    return f"{resp.status_code}: {msg}"


def send(to: str, subject: str, html: str, reply_to: Optional[str] = None) -> Result:
    if settings.DEV_OUTBOX:
        OUTBOX.append({"to": to, "subject": subject, "html": html, "text": html_to_text(html)})
    if not configured():
        logger.info("[mock email] to=%s subject=%r", to, subject)
        return Result(True)
    try:
        r = _client.post(f"{API}/emails", json=_payload(to, subject, html, reply_to),
                         headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"})
    except httpx.HTTPError as e:
        logger.error("Email to %s failed: %s", to, e)
        return Result(False, "Couldn't reach the email service.")
    if r.status_code >= 300:
        reason = _explain(r)
        logger.error("Email to %s rejected: %s", to, reason)
        return Result(False, reason)
    logger.info("Email sent → %s: %s", to, subject)
    return Result(True)


def send_batch(messages: List[dict]) -> List[Result]:
    """messages: [{"to","subject","html"}]. Sent 100 at a time via /emails/batch."""
    results: List[Result] = []
    for m in messages:
        if settings.DEV_OUTBOX:
            OUTBOX.append({**m, "text": html_to_text(m["html"])})
    if not configured():
        for m in messages:
            logger.info("[mock email] to=%s subject=%r", m["to"], m["subject"])
        return [Result(True) for _ in messages]
    for i in range(0, len(messages), 100):
        chunk = messages[i:i + 100]
        try:
            r = _client.post(f"{API}/emails/batch", json=[_payload(m["to"], m["subject"], m["html"]) for m in chunk],
                             headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"})
            ok = r.status_code < 300
            reason = None if ok else _explain(r)
        except httpx.HTTPError:
            ok, reason = False, "Couldn't reach the email service."
        if not ok:
            logger.error("Batch email failed for %d recipients: %s", len(chunk), reason)
        results.extend(Result(ok, reason) for _ in chunk)
    return results

"""
app/services/mailer.py — sends email through Resend's HTTP API.

We call the API directly (not the SDK): every failure comes back as a clear
(ok=False, reason) instead of being swallowed, and broadcasts use Resend's batch
endpoint (100 emails per request).

Without a real RESEND_API_KEY, emails are only logged (and kept in the dev outbox
when DEV_OUTBOX=true), so development never needs a mail account.
"""
import logging
import time
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
    """Turn a Resend error into a sentence an admin can act on (the raw error goes to the log)."""
    try:
        body = resp.json()
        msg = body.get("message") or body.get("error") or str(body)
    except ValueError:
        msg = resp.text[:200]
    logger.warning("Resend error %s: %s", resp.status_code, msg)
    low, code = msg.lower(), resp.status_code
    if "own email" in low or "domain is not verified" in low or "verify a domain" in low:
        return ("The sending domain isn't verified with the email service yet, so it only delivers to the "
                "account owner's address. Verify the domain in Resend.")
    if code == 401 or "api key" in low:
        return "The email service didn't accept our API key. Check RESEND_API_KEY on the server."
    if code == 422 and ("`to`" in low or "testing email" in low or ("invalid" in low and "email" in low)):
        return "Not a real email address (for example a test account), so it was skipped."
    if code == 429:
        return "Too many emails at once; the email service asked us to slow down. Try again in a minute."
    if code >= 500:
        return "The email service is having problems right now. Try again later."
    return f"The email service refused this message: {msg}"


# Reserved for documentation/testing (RFC 2606/6761); never deliverable, and Resend rejects
# a whole batch if one of them is in it.
_RESERVED = ("example.com", "example.net", "example.org")
_RESERVED_TLDS = (".example", ".test", ".invalid", ".localhost", ".local")
SKIPPED = "Not a real email address (for example a test account), so it was skipped."


def deliverable(address: str) -> bool:
    domain = (address or "").rsplit("@", 1)[-1].strip().lower()
    if not domain or "." not in domain or domain == "localhost":
        return False
    return not (domain in _RESERVED or domain.endswith(tuple("." + d for d in _RESERVED)) or domain.endswith(_RESERVED_TLDS))


def send(to: str, subject: str, html: str, reply_to: Optional[str] = None) -> Result:
    if settings.DEV_OUTBOX:
        OUTBOX.append({"to": to, "subject": subject, "html": html, "text": html_to_text(html)})
    if not configured():
        logger.info("[mock email] to=%s subject=%r", to, subject)
        return Result(True)
    return _post(to, subject, html, reply_to)


def _post(to: str, subject: str, html: str, reply_to: Optional[str] = None) -> Result:
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
    """
    messages: [{"to","subject","html"}] → one Result per message, in the same order.
    Undeliverable (test) addresses are skipped; the rest go 100 at a time via /emails/batch.
    Resend rejects a whole batch over one bad address, so a refused batch is retried one by one
    (paced under Resend's default 2 requests/second) and only the bad addresses fail.
    """
    results: List[Optional[Result]] = [None] * len(messages)
    todo = []
    for i, m in enumerate(messages):
        if deliverable(m["to"]):
            todo.append(i)
        else:
            results[i] = Result(False, SKIPPED)
    for i in todo:
        if settings.DEV_OUTBOX:
            OUTBOX.append({**messages[i], "text": html_to_text(messages[i]["html"])})
    if not configured():
        for i in todo:
            logger.info("[mock email] to=%s subject=%r", messages[i]["to"], messages[i]["subject"])
            results[i] = Result(True)
        return results
    for start in range(0, len(todo), 100):
        chunk = todo[start:start + 100]
        try:
            r = _client.post(f"{API}/emails/batch",
                             json=[_payload(messages[i]["to"], messages[i]["subject"], messages[i]["html"]) for i in chunk],
                             headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"})
            ok = r.status_code < 300
            reason = None if ok else _explain(r)
            retry_singly = not ok and r.status_code in (400, 422)
        except httpx.HTTPError:
            ok, reason, retry_singly = False, "Couldn't reach the email service.", False
        if ok:
            for i in chunk:
                results[i] = Result(True)
            continue
        logger.error("Batch email failed for %d recipients: %s", len(chunk), reason)
        if not retry_singly:
            for i in chunk:
                results[i] = Result(False, reason)
            continue
        for i in chunk:
            time.sleep(0.6)
            m = messages[i]
            results[i] = _post(m["to"], m["subject"], m["html"])
    return results

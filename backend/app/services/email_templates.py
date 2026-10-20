"""
app/services/email_templates.py — one consistent, escaped HTML email layout.

Every dynamic value is HTML-escaped. Names and reasons are user/admin input, and
interpolating them raw into HTML lets anyone inject markup into our emails.
"""
from decimal import Decimal
from html import escape


def usd(value) -> str:
    """Human money for messages: 200.00000000 → $200.00."""
    return f"${Decimal(str(value or 0)):,.2f}"


def render_email(heading: str, name: str, paragraphs: list[str], cta: tuple[str, str] | None = None) -> str:
    body = "".join(f'<p style="margin:0 0 12px;line-height:1.55;">{escape(p)}</p>' for p in paragraphs)
    button = ""
    if cta:
        label, url = cta
        button = (
            f'<p style="margin:20px 0;"><a href="{escape(url, quote=True)}" '
            'style="background:#1d3a5f;color:#fff;padding:11px 18px;border-radius:6px;'
            f'text-decoration:none;font-weight:600;">{escape(label)}</a></p>'
        )
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:auto;color:#1c2633;">'
        f'<h2 style="color:#1d3a5f;margin:0 0 16px;">{escape(heading)}</h2>'
        f'<p style="margin:0 0 12px;">Hi {escape(name)},</p>{body}{button}'
        '<hr style="border:none;border-top:1px solid #dde3ea;margin:24px 0 12px;"/>'
        '<small style="color:#6b7787;">Zenfort Markets — educational demo platform.</small></div>'
    )

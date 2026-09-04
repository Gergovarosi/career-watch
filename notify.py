"""
E-mail küldés SMTP-n keresztül.

A belépési adatok környezeti változókból jönnek (soha ne írd őket a kódba):

    SMTP_HOST   pl. smtp.gmail.com
    SMTP_PORT   pl. 587
    SMTP_USER   a küldő e-mail cím
    SMTP_PASS   app-jelszó (Gmailnél NEM a rendes jelszó!)
    MAIL_TO     ahova a riasztás megy
"""

from __future__ import annotations

import html as _html
import os
import smtplib
from email.message import EmailMessage


def _cfg(key: str, default: str | None = None) -> str:
    val = os.environ.get(key, default)
    if val is None:
        raise RuntimeError(f"Hiányzó környezeti változó: {key}")
    return val


def _build_html(jobs) -> str:
    rows = []
    for j in jobs:
        loc = _html.escape(j.location) if j.location else "&mdash;"
        rows.append(
            f"<tr>"
            f"<td style='padding:10px 14px;border-bottom:1px solid #eee'>"
            f"<a href='{_html.escape(j.url)}' style='color:#0b5cad;font-weight:600;"
            f"text-decoration:none'>{_html.escape(j.title)}</a><br>"
            f"<span style='color:#666;font-size:13px'>{_html.escape(j.company)} &middot; {loc}</span>"
            f"</td></tr>"
        )
    return (
        "<div style=\"font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;"
        "max-width:600px\">"
        f"<h2 style='font-size:17px;margin:0 0 14px'>{len(jobs)} új pozíció</h2>"
        "<table style='border-collapse:collapse;width:100%'>"
        + "".join(rows)
        + "</table></div>"
    )


def _build_text(jobs) -> str:
    lines = [f"{len(jobs)} új pozíció:\n"]
    for j in jobs:
        lines.append(f"- {j.title}")
        lines.append(f"  {j.company} | {j.location or '?'}")
        lines.append(f"  {j.url}\n")
    return "\n".join(lines)


def send_email(jobs) -> None:
    if not jobs:
        return

    first = jobs[0]
    if len(jobs) == 1:
        subject = f"Új pozíció: {first.title} — {first.company}"
    else:
        subject = f"{len(jobs)} új pozíció ({first.company} és mások)"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _cfg("SMTP_USER")
    msg["To"] = _cfg("MAIL_TO")
    msg.set_content(_build_text(jobs))
    msg.add_alternative(_build_html(jobs), subtype="html")

    host, port = _cfg("SMTP_HOST"), int(_cfg("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=30) as s:
        s.starttls()
        s.login(_cfg("SMTP_USER"), _cfg("SMTP_PASS"))
        s.send_message(msg)

"""OpenRecon notifications — outbound email (send-back alerts to preparers).

Configured entirely from the environment (set these in the deployment, never in the repo):
  NOTIFY_ENABLED   "1"/"true" to actually send; anything else = dry-run (compose + log, no SMTP)
  SMTP_HOST        e.g. smtp.office365.com / your relay
  SMTP_PORT        default 587
  SMTP_USER        auth user (optional for an open internal relay)
  SMTP_PASSWORD    auth password (held in a secret manager / 600 env file — never committed)
  SMTP_STARTTLS    "1"/"true" (default true) — STARTTLS on the port above
  NOTIFY_FROM      From: address, e.g. "OpenRecon <recon-noreply@acme.com>"

Design: **fail-open**. A notification must never break the workflow action that triggered it —
if SMTP is unconfigured, disabled, or errors, we log the composed message and return a result
the API surfaces (dispatched=false, mode="dry-run"/"error") instead of raising.
"""
from __future__ import annotations

import os
import smtplib
import logging
from email.message import EmailMessage

log = logging.getLogger("openrecon.notify")


def _truthy(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def send_email(to_addr: str, subject: str, body: str, to_name: str = "") -> dict:
    """Send (or dry-run) a plain-text email. Returns a result dict; never raises."""
    sender = os.environ.get("NOTIFY_FROM", "OpenRecon <recon-noreply@localhost>")
    result = {"to": to_addr, "subject": subject, "dispatched": False, "mode": "dry-run"}

    if not _truthy(os.environ.get("NOTIFY_ENABLED")) or not os.environ.get("SMTP_HOST"):
        # disabled or unconfigured → compose-only; log so it's visible in TEST
        log.info("notify dry-run → %s | %s", to_addr, subject)
        return result

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = f"{to_name} <{to_addr}>" if to_name else to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    try:
        with smtplib.SMTP(host, port, timeout=10) as s:
            if _truthy(os.environ.get("SMTP_STARTTLS"), default=True):
                s.starttls()
            user, pw = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASSWORD")
            if user and pw:
                s.login(user, pw)
            s.send_message(msg)
        result.update(dispatched=True, mode="sent")
        log.info("notify sent → %s | %s", to_addr, subject)
    except Exception as e:                       # fail-open: log, don't raise into the request
        result.update(mode="error", error=str(e))
        log.warning("notify FAILED → %s | %s | %s", to_addr, subject, e)
    return result


def send_back_notice(preparer_name: str, preparer_email: str, reviewer_name: str,
                     account_code: str, account_name: str, period: str, reason: str = "") -> dict:
    """Compose + send the 'your account was sent back for rework' email to the preparer."""
    subject = f"[OpenRecon] Account {account_code} — {account_name}: sent back for rework ({period})"
    lines = [
        f"Hi {preparer_name},",
        "",
        f"{reviewer_name} has sent account {account_code} — {account_name} back to you for rework "
        f"as part of the {period} close.",
    ]
    if reason:
        lines += ["", f"Reason: {reason}"]
    lines += ["", "Please review, correct, and re-submit it for approval in OpenRecon.",
              "", "— OpenRecon notifications"]
    return send_email(preparer_email, subject, "\n".join(lines), to_name=preparer_name)

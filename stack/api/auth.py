"""Authentication + session handling for OpenRecon.

Local password auth verifies against the bcrypt hash stored by pgcrypto (`crypt`), so no password
ever leaves the database in plaintext and the API needs no crypto dependency. Federated users
(auth_source = oidc|saml) are minted a session from the verified IdP subject instead — see
`session_from_idp`. Every login/logout is written to the immutable audit trail by the caller.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

SESSION_TTL_HOURS = 12


def verify_local(c, username: str, password: str):
    """Return the user row if username+password match an active local account, else None."""
    u = c.execute(
        "SELECT * FROM app_user WHERE (name=%s OR id=%s) AND status='active'",
        (username, username),
    ).fetchone()
    if not u or u.get("auth_source") != "local" or not u.get("password_hash"):
        return None
    ok = c.execute("SELECT (password_hash = crypt(%s, password_hash)) AS ok FROM app_user WHERE id=%s",
                   (password, u["id"])).fetchone()
    return u if ok and ok["ok"] else None


def find_federated(c, subject: str):
    """Resolve an IdP subject to an active federated user (OIDC/SAML stub seam)."""
    return c.execute(
        "SELECT * FROM app_user WHERE external_subject=%s AND status='active' AND auth_source IN ('oidc','saml')",
        (subject,),
    ).fetchone()


def create_session(c, user_id: str, source_ip: str | None = None) -> dict:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
    c.execute(
        "INSERT INTO auth_session (token, user_id, expires_at, source_ip) VALUES (%s,%s,%s,%s)",
        (token, user_id, expires, source_ip),
    )
    c.execute("UPDATE app_user SET last_login_at=now() WHERE id=%s", (user_id,))
    return {"token": token, "expires_at": expires.isoformat()}


def session_user(c, token: str):
    """Return the active user behind a bearer token, or None if missing/expired/revoked/disabled."""
    if not token:
        return None
    row = c.execute(
        """SELECT u.* FROM auth_session s JOIN app_user u ON u.id = s.user_id
           WHERE s.token=%s AND s.revoked_at IS NULL AND s.expires_at > now() AND u.status='active'""",
        (token,),
    ).fetchone()
    return row


def revoke_session(c, token: str) -> bool:
    cur = c.execute("UPDATE auth_session SET revoked_at=now() WHERE token=%s AND revoked_at IS NULL", (token,))
    return cur.rowcount > 0

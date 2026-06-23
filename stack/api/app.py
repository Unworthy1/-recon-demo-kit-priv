"""OpenRecon API — serves the same data contract the UI (web/) consumes, from the database.

Endpoints mirror what web/assets/app.js builds client-side, so a deployment points the UI at
this API instead of the embedded demo data (see docs/DEPLOYMENT.md, "wire the UI").
"""
from __future__ import annotations

import os
from datetime import date

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json
from fastapi import FastAPI, HTTPException, Request

from fastapi.middleware.cors import CORSMiddleware

import config
import engine
import notify
import auth
import etl
from ferc.classifier import FERCClassifier

app = FastAPI(title="OpenRecon API", version="1.8.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB_URL = os.environ["DATABASE_URL"]
PERIOD = date.fromisoformat(os.environ.get("PERIOD_END", "2026-05-31"))
FERC = FERCClassifier.from_yaml(os.environ["FERC_MAP"]) if os.environ.get("FERC_MAP") else FERCClassifier()


def db():
    return psycopg.connect(DB_URL, row_factory=dict_row)


# ───────────────────────── audit trail (immutable, hash-chained in the DB) ─────────────────────────
def audit(c, actor, action, *, entity_type=None, entity_id=None, period_end=None,
          before=None, after=None, detail=None, actor_role=None, ip=None):
    """Append one event to the tamper-evident trail. The DB trigger stamps time + hash chain."""
    c.execute(
        """INSERT INTO audit_event
             (actor, actor_role, action, entity_type, entity_id, period_end, before, after, detail, source_ip,
              prev_hash, row_hash)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'','')""",
        (actor, actor_role, action, entity_type, entity_id, period_end,
         Json(before) if before is not None else None,
         Json(after) if after is not None else None,
         Json(detail) if detail is not None else None, ip),
    )


def actor_of(c, request: Request | None, fallback: str):
    """Resolve the acting identity: a real session (Bearer token) wins; else the supplied user
    (back-compat for the unauthenticated showcase UI). Returns (name, role, ip)."""
    ip = request.client.host if request and request.client else None
    token = ""
    if request:
        h = request.headers.get("authorization", "")
        token = h[7:].strip() if h.lower().startswith("bearer ") else ""
    if token:
        u = auth.session_user(c, token)
        if u:
            return u["name"], u.get("org_role"), ip
    role = None
    r = c.execute("SELECT org_role FROM app_user WHERE name=%s OR id=%s", (fallback, fallback)).fetchone()
    if r:
        role = r["org_role"]
    return fallback, role, ip


@app.get("/api/health")
def health():
    with db() as c:
        c.execute("SELECT 1")
    return {"ok": True}


@app.get("/api/accounts")
def accounts():
    """The overview board: every account + its current reconciliation, grouped by type."""
    with db() as c:
        rows = c.execute(
            """SELECT a.id, a.code, a.name, a.grp, a.bank, a.mask, a.assigned_to AS assigned,
                      a.tolerance AS tol, r.gl_balance AS gl, r.statement_balance AS stmt,
                      r.variance, r.status, r.work_status AS work, r.ocr_account AS ocr_acct,
                      r.ocr_date, r.document_ref
               FROM gl_account a
               LEFT JOIN reconciliation r ON r.gl_account_id = a.id AND r.period_end = %s
               ORDER BY a.grp, a.code""",
            (PERIOD,),
        ).fetchall()
    return {"period_end": PERIOD.isoformat(), "accounts": rows}


@app.get("/api/kpis")
def kpis():
    accs = accounts()["accounts"]
    in_scope = len(accs)
    reconciled = sum(1 for a in accs if a["status"] == "reconciled")
    variance = sum(1 for a in accs if a["status"] == "variance")
    unreconciled = sum(1 for a in accs if a["status"] in (None, "unreconciled"))
    var_total = sum(abs(a["variance"]) for a in accs if a["status"] == "variance" and a["variance"] is not None)
    return {"inScope": in_scope, "reconciled": reconciled, "variance": variance,
            "unreconciled": unreconciled, "varTotal": float(var_total),
            "progress": round(reconciled / in_scope * 100) if in_scope else 0,
            "exceptions": variance + unreconciled}


@app.get("/api/account/{account_id}")
def account(account_id: str):
    with db() as c:
        a = c.execute(
            """SELECT a.*, r.gl_balance, r.statement_balance, r.variance, r.status, r.work_status,
                      r.ocr_account, r.ocr_date, r.document_ref, r.note, r.resolved_by
               FROM gl_account a
               LEFT JOIN reconciliation r ON r.gl_account_id = a.id AND r.period_end = %s
               WHERE a.id = %s""",
            (PERIOD, account_id),
        ).fetchone()
        if not a:
            raise HTTPException(404, "account not found")
        docs = c.execute(
            "SELECT filename, uploaded_by, uploaded_at, note, dms_doc_id, dms_url "
            "FROM supporting_document WHERE gl_account_id = %s ORDER BY uploaded_at",
            (account_id,),
        ).fetchall()
    return {"account": a, "supporting_documents": docs}


@app.post("/api/reconcile")
def reconcile():
    """Recompute the board for the current period from the wired GL + treasury adapters."""
    cfg = config.load()
    gl_adapter = config.build_gl(cfg)
    treasury_adapters = config.build_treasury(cfg)
    with db() as c:
        summary = engine.run(c, PERIOD, gl_adapter, treasury_adapters)
    return {"reconciled": summary}


@app.post("/api/account/{account_id}/resolve")
def resolve(account_id: str, note: str = "", user: str = "Joe B.", request: Request = None):
    with db() as c:
        cur = c.execute(
            """UPDATE reconciliation SET status='reconciled', work_status='resolved',
                   note=%s, resolved_by=%s, resolved_at=now()
               WHERE gl_account_id=%s AND period_end=%s""",
            (note, user, account_id, PERIOD),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "no reconciliation for that account/period")
        actor, role, ip = actor_of(c, request, user)
        audit(c, actor, "account.resolve", entity_type="reconciliation", entity_id=account_id,
              period_end=PERIOD, after={"work_status": "resolved", "note": note}, actor_role=role, ip=ip)
        c.commit()
    return {"ok": True, "account": account_id}


# ───────────── project reconciliations (one document settles many FERC accounts) ─────────────
@app.get("/api/projects")
def projects():
    """Project reconciliations for the period, with tie-out (source vs sum of allocations) and the
    distinct FERC functions the lines span (derived from each account's FERC range)."""
    with db() as c:
        recs = c.execute("SELECT * FROM project_reconciliation WHERE period_end=%s ORDER BY id", (PERIOD,)).fetchall()
        out = []
        for p in recs:
            lines = c.execute("SELECT gl_code, allocated_amount FROM project_line WHERE project_id=%s", (p["id"],)).fetchall()
            allocated = round(sum(float(l["allocated_amount"]) for l in lines), 2)
            variance = round(float(p["source_amount"]) - allocated, 2)
            out.append({**p, "allocated": allocated, "variance": variance, "accounts": len(lines),
                        "status": "tied" if abs(variance) <= float(p["tolerance"]) else "variance",
                        "functions": sorted({FERC.project_for(l["gl_code"]) for l in lines})})
    return {"period_end": PERIOD.isoformat(), "projects": out}


@app.get("/api/project/{pid}")
def project(pid: str):
    with db() as c:
        p = c.execute("SELECT * FROM project_reconciliation WHERE id=%s", (pid,)).fetchone()
        if not p:
            raise HTTPException(404, "project not found")
        lines = c.execute("SELECT gl_code, gl_name, allocated_amount FROM project_line WHERE project_id=%s ORDER BY gl_code", (pid,)).fetchall()
    for l in lines:
        cl = FERC.classify(l["gl_code"])
        l["project"], l["expense_type"] = cl["project"], cl["expense_type"]
    allocated = round(sum(float(l["allocated_amount"]) for l in lines), 2)
    variance = round(float(p["source_amount"]) - allocated, 2)
    return {"project": p, "lines": lines, "allocated": allocated, "variance": variance,
            "status": "tied" if abs(variance) <= float(p["tolerance"]) else "variance"}


@app.post("/api/project/{pid}/settle")
def settle_project(pid: str, user: str = "Joe B.", request: Request = None):
    """Settle all member accounts of a project reconciliation in one action."""
    with db() as c:
        cur = c.execute("""UPDATE project_reconciliation SET work_status='resolved', settled_by=%s, settled_at=now()
                     WHERE id=%s AND period_end=%s""", (user, pid, PERIOD))
        if cur.rowcount == 0:
            raise HTTPException(404, "project reconciliation not found")
        actor, role, ip = actor_of(c, request, user)
        audit(c, actor, "project.settle", entity_type="project", entity_id=pid,
              period_end=PERIOD, after={"work_status": "resolved"}, actor_role=role, ip=ip)
        c.commit()
    return {"ok": True, "project": pid}


# ───────────── year-end close: periods, lock, roll-forward, carry-forward, audit package ─────────────
ROLLFWD_TOL = 1000.0


@app.get("/api/periods")
def periods():
    """Close periods (monthly / quarterly / annual) with lock status."""
    with db() as c:
        rows = c.execute("SELECT * FROM close_period ORDER BY period_type, period_key").fetchall()
    return {"fiscal_year": "FY 2026", "periods": rows}


@app.post("/api/period/{key}/lock")
def lock_period(key: str, user: str = "Joe B.", request: Request = None):
    """Lock (close) a period — it becomes read-only."""
    with db() as c:
        cur = c.execute("UPDATE close_period SET status='locked', closed_by=%s, closed_at=now(), progress=100 WHERE period_key=%s", (user, key))
        if cur.rowcount == 0:
            raise HTTPException(404, "period not found")
        actor, role, ip = actor_of(c, request, user)
        audit(c, actor, "period.lock", entity_type="period", entity_id=key,
              after={"status": "locked"}, actor_role=role, ip=ip)
        c.commit()
    return {"ok": True, "period": key}


def _rollforward_rows(c, period_key: str):
    rows = c.execute("SELECT gl_code, gl_name, opening, activity, evidence FROM rollforward WHERE period_key=%s ORDER BY gl_code", (period_key,)).fetchall()
    for r in rows:
        r["closing"] = round(float(r["opening"]) + float(r["activity"]), 2)   # continuity: opening + activity
        r["tie"] = round(r["closing"] - float(r["evidence"]), 2)              # tie: closing vs evidence
        r["status"] = "tied" if abs(r["tie"]) <= ROLLFWD_TOL else "true-up"
        r["ferc_project"] = FERC.project_for(r["gl_code"])
    return rows


@app.get("/api/rollforward")
def rollforward(period: str = "2026-FY"):
    """Year-end roll-forward continuity: opening + activity = closing, tied to evidence."""
    with db() as c:
        rows = _rollforward_rows(c, period)
    tied = sum(1 for r in rows if r["status"] == "tied")
    return {"period": period, "tolerance": ROLLFWD_TOL, "rollforward": rows,
            "summary": {"count": len(rows), "tied": tied, "true_ups": len(rows) - tied,
                        "net_closing": round(sum(r["closing"] for r in rows), 2)}}


@app.post("/api/period/{key}/carry-forward")
def carry_forward(key: str, user: str = "Joe B.", request: Request = None):
    """Seed next-FY openings from this period's roll-forward closings."""
    with db() as c:
        rows = _rollforward_rows(c, key)
        actor, role, ip = actor_of(c, request, user)
        audit(c, actor, "period.carry_forward", entity_type="period", entity_id=key,
              detail={"accounts": len(rows)}, actor_role=role, ip=ip)
        c.commit()
    return {"from": key, "carried_forward": [
        {"gl_code": r["gl_code"], "name": r["gl_name"], "closing": r["closing"], "next_opening": r["closing"]} for r in rows]}


@app.get("/api/period/{key}/audit-package")
def audit_package(key: str):
    """The close binder: account + project + roll-forward reconciliations, for external audit."""
    accts = accounts()["accounts"]
    projs = projects()["projects"]
    with db() as c:
        rf = _rollforward_rows(c, "2026-FY")
    exceptions = (sum(1 for a in accts if a["status"] in (None, "variance", "unreconciled"))
                  + sum(1 for p in projs if p["status"] != "tied")
                  + sum(1 for r in rf if r["status"] != "tied"))
    total = len(accts) + len(projs) + len(rf)
    return {"software": "OpenRecon", "fiscal_year": "FY 2026", "period": key,
            "summary": {"reconciliations": total, "signed_off": total - exceptions, "open_exceptions": exceptions},
            "account_reconciliations": accts, "project_reconciliations": projs, "year_end_rollforward": rf}


# ───────────── RBAC: users, capabilities, and gated approval (segregation of duties) ─────────────
def _user_caps(c, who: str):
    u = c.execute("SELECT * FROM app_user WHERE name=%s OR id=%s", (who, who)).fetchone()
    if not u:
        return None
    u["capabilities"] = [r["capability"] for r in
                         c.execute("SELECT capability FROM role_capability WHERE org_role=%s", (u["org_role"],)).fetchall()]
    return u


@app.get("/api/users")
def users():
    """The accountant directory: org role + workflow capabilities per user."""
    with db() as c:
        us = c.execute("SELECT * FROM app_user WHERE active ORDER BY org_role, name").fetchall()
        caps: dict = {}
        for r in c.execute("SELECT * FROM role_capability").fetchall():
            caps.setdefault(r["org_role"], []).append(r["capability"])
    return {"users": [{**u, "capabilities": caps.get(u["org_role"], [])} for u in us]}


@app.get("/api/me")
def me(user: str = "Joe B."):
    """The current user + what they can do (drives gating)."""
    with db() as c:
        u = _user_caps(c, user)
    if not u:
        raise HTTPException(404, "user not found")
    return u


@app.post("/api/account/{account_id}/approve")
def approve(account_id: str, user: str = "Maria L.", request: Request = None):
    """Approve a reconciliation — requires the approve capability AND not being its preparer (SoD)."""
    with db() as c:
        u = _user_caps(c, user)
        if not u or "approve" not in u["capabilities"]:
            raise HTTPException(403, f"{user} ({u['org_role'] if u else 'unknown'}) is not permitted to approve")
        a = c.execute("SELECT assigned_to FROM gl_account WHERE id=%s", (account_id,)).fetchone()
        if not a:
            raise HTTPException(404, "account not found")
        if a["assigned_to"] == u["name"]:
            raise HTTPException(409, "segregation of duties: you cannot approve your own preparation")
        c.execute("""UPDATE reconciliation SET work_status='approved', approved_by=%s, approved_at=now()
                     WHERE gl_account_id=%s AND period_end=%s""", (u["name"], account_id, PERIOD))
        _, _, ip = actor_of(c, request, user)
        audit(c, u["name"], "account.approve", entity_type="reconciliation", entity_id=account_id,
              period_end=PERIOD, after={"work_status": "approved"},
              detail={"preparer": a["assigned_to"] if a else None}, actor_role=u["org_role"], ip=ip)
        c.commit()
    return {"ok": True, "account": account_id, "approved_by": u["name"], "role": u["org_role"]}


@app.post("/api/account/{account_id}/send-back")
def send_back(account_id: str, user: str = "Maria L.", reason: str = "", request: Request = None):
    """Send a reconciliation back for rework — requires the approve capability AND not being its
    preparer (SoD) — and email the preparer that it's been returned to them."""
    with db() as c:
        u = _user_caps(c, user)
        if not u or "approve" not in u["capabilities"]:
            raise HTTPException(403, f"{user} ({u['org_role'] if u else 'unknown'}) is not permitted to send back")
        a = c.execute("""SELECT a.assigned_to, a.code, a.name, pu.email AS prep_email
                         FROM gl_account a LEFT JOIN app_user pu ON pu.name = a.assigned_to
                         WHERE a.id=%s""", (account_id,)).fetchone()
        if not a:
            raise HTTPException(404, "account not found")
        if a["assigned_to"] == u["name"]:
            raise HTTPException(409, "segregation of duties: you cannot send back your own preparation")
        c.execute("""UPDATE reconciliation
                     SET work_status='sent_back', sent_back_by=%s, sent_back_at=now(), sent_back_reason=%s
                     WHERE gl_account_id=%s AND period_end=%s""", (u["name"], reason, account_id, PERIOD))
        _, _, ip = actor_of(c, request, user)
        audit(c, u["name"], "account.send_back", entity_type="reconciliation", entity_id=account_id,
              period_end=PERIOD, after={"work_status": "sent_back"},
              detail={"preparer": a["assigned_to"], "reason": reason}, actor_role=u["org_role"], ip=ip)
        c.commit()
    # fail-open: the send-back is committed regardless of whether the email goes out
    note = notify.send_back_notice(
        preparer_name=a["assigned_to"] or "preparer",
        preparer_email=a["prep_email"] or "",
        reviewer_name=u["name"], account_code=a["code"], account_name=a["name"],
        period=PERIOD.isoformat(), reason=reason)
    return {"ok": True, "account": account_id, "sent_back_by": u["name"],
            "preparer": a["assigned_to"], "notification": note}


@app.get("/api/dashboard")
def dashboard(user: str = "Joe B."):
    """An accountant's landing page: their prepare workload + (if a reviewer) the whole team's workload."""
    with db() as c:
        u = _user_caps(c, user)
        if not u:
            raise HTTPException(404, "user not found")

        def _stats(name):
            assigned = c.execute("SELECT count(*) n FROM gl_account WHERE assigned_to=%s", (name,)).fetchone()["n"]
            prepared = c.execute("""SELECT count(*) n FROM gl_account a JOIN reconciliation r
                ON r.gl_account_id=a.id AND r.period_end=%s
                WHERE a.assigned_to=%s AND r.work_status IN ('resolved','approved')""", (PERIOD, name)).fetchone()["n"]
            approved = c.execute("SELECT count(*) n FROM reconciliation WHERE approved_by=%s AND period_end=%s",
                                 (name, PERIOD)).fetchone()["n"]
            return {"assigned": assigned, "prepared": prepared, "approved": approved}

        mine = _stats(user)
        accts = c.execute("""SELECT a.id, a.code, a.name, r.work_status FROM gl_account a
            LEFT JOIN reconciliation r ON r.gl_account_id=a.id AND r.period_end=%s
            WHERE a.assigned_to=%s ORDER BY a.code""", (PERIOD, user)).fetchall()
        out = {"user": u, "my_work": {**mine, "accounts": accts}}

        if "review" in u["capabilities"]:   # reviewers (principal/director) see the whole team
            team = c.execute("SELECT name, org_role FROM app_user WHERE active ORDER BY org_role DESC, name").fetchall()
            out["team"] = [{"name": m["name"], "role": m["org_role"], **_stats(m["name"])} for m in team]
    return out


# ═══════════════════════════ authentication & sessions ═══════════════════════════
@app.post("/api/auth/login")
def login(request: Request, user: str = "", password: str = ""):
    """Local password login → an opaque bearer session token. Audited (success or failure)."""
    ip = request.client.host if request.client else None
    with db() as c:
        u = auth.verify_local(c, user, password)
        if not u:
            audit(c, user or "(unknown)", "auth.login_failed", entity_type="user", entity_id=user, ip=ip)
            c.commit()
            raise HTTPException(401, "invalid credentials")
        sess = auth.create_session(c, u["id"], source_ip=ip)
        audit(c, u["name"], "auth.login", entity_type="user", entity_id=u["id"],
              detail={"mfa": u["mfa_enabled"]}, actor_role=u["org_role"], ip=ip)
        c.commit()
    return {"token": sess["token"], "expires_at": sess["expires_at"],
            "user": {"name": u["name"], "role": u["org_role"], "mfa_enabled": u["mfa_enabled"]}}


@app.post("/api/auth/logout")
def logout(request: Request):
    token = (request.headers.get("authorization", "")[7:]).strip()
    with db() as c:
        u = auth.session_user(c, token)
        ok = auth.revoke_session(c, token)
        if u:
            audit(c, u["name"], "auth.logout", entity_type="user", entity_id=u["id"],
                  actor_role=u["org_role"], ip=request.client.host if request.client else None)
        c.commit()
    return {"ok": ok}


@app.get("/api/auth/whoami")
def whoami(request: Request):
    """Resolve the current bearer session to the authenticated user (drives the real, gated UI)."""
    token = (request.headers.get("authorization", "")[7:]).strip()
    with db() as c:
        u = auth.session_user(c, token)
        if not u:
            raise HTTPException(401, "no active session")
        caps = _user_caps(c, u["name"])
    return {"name": u["name"], "role": u["org_role"], "email": u.get("email"),
            "mfa_enabled": u["mfa_enabled"], "capabilities": caps["capabilities"] if caps else []}


# ═══════════════════════════ audit trail (read + integrity verify) ═══════════════════════════
@app.get("/api/audit")
def audit_log(entity_type: str = "", entity_id: str = "", actor: str = "", limit: int = 100):
    """Read the immutable activity trail (filterable). Most recent first."""
    where, args = [], []
    if entity_type:
        where.append("entity_type=%s"); args.append(entity_type)
    if entity_id:
        where.append("entity_id=%s"); args.append(entity_id)
    if actor:
        where.append("actor=%s"); args.append(actor)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    args.append(max(1, min(limit, 1000)))
    with db() as c:
        rows = c.execute(
            f"""SELECT id, event_ts, actor, actor_role, action, entity_type, entity_id, period_end,
                       before, after, detail, source_ip, row_hash
                FROM audit_event {clause} ORDER BY id DESC LIMIT %s""", args).fetchall()
    return {"events": rows, "count": len(rows)}


@app.get("/api/audit/verify")
def audit_verify():
    """Re-walk the hash chain and confirm it's intact — proves the trail hasn't been tampered with.
    Recomputes each row's hash with the *exact same SQL expression* as the insert trigger (so jsonb
    rendering is identical), and checks every prev_hash links to the prior row."""
    with db() as c:
        row = c.execute(
            """WITH chained AS (
                 SELECT id, prev_hash, row_hash,
                   encode(digest(
                     prev_hash || '|' || event_ts::text || '|' || actor || '|' || action || '|' ||
                     COALESCE(entity_type,'') || '|' || COALESCE(entity_id,'') || '|' ||
                     COALESCE(period_end::text,'') || '|' || COALESCE(before::text,'') || '|' ||
                     COALESCE(after::text,'') || '|' || COALESCE(detail::text,''), 'sha256'),'hex') AS recomputed,
                   LAG(row_hash) OVER (ORDER BY id) AS prev_actual
                 FROM audit_event)
               SELECT count(*) AS events,
                      count(*) FILTER (WHERE row_hash <> recomputed) AS bad_hash,
                      count(*) FILTER (WHERE prev_hash <> COALESCE(prev_actual,'GENESIS')) AS bad_link,
                      min(id) FILTER (WHERE row_hash <> recomputed
                                         OR prev_hash <> COALESCE(prev_actual,'GENESIS')) AS broken_at
               FROM chained""").fetchone()
    intact = (row["bad_hash"] == 0 and row["bad_link"] == 0)
    return {"intact": intact, "events": row["events"],
            "tampered_rows": row["bad_hash"] + row["bad_link"], "broken_at": row["broken_at"]}


# ═══════════════════════════ access recertification (a SOX access control) ═══════════════════════════
@app.get("/api/access-reviews")
def access_reviews(campaign: str = ""):
    with db() as c:
        clause, args = ("WHERE campaign=%s", [campaign]) if campaign else ("", [])
        rows = c.execute(
            f"""SELECT ar.*, u.name, u.org_role, u.status FROM access_review ar
                JOIN app_user u ON u.id=ar.user_id {clause} ORDER BY ar.id DESC""", args).fetchall()
    return {"reviews": rows}


@app.post("/api/access-review")
def access_review(request: Request, user_id: str, decision: str, reviewer: str = "Robert K.",
                  campaign: str = "ad-hoc", note: str = ""):
    """Recertify or revoke a user's access. Reviewers (principal/director) only. Audited."""
    if decision not in ("recertified", "revoked"):
        raise HTTPException(400, "decision must be 'recertified' or 'revoked'")
    with db() as c:
        rv = _user_caps(c, reviewer)
        if not rv or "review" not in rv["capabilities"]:
            raise HTTPException(403, f"{reviewer} is not permitted to recertify access")
        c.execute("""INSERT INTO access_review (campaign, user_id, reviewer, decision, reviewed_at, note)
                     VALUES (%s,%s,%s,%s,now(),%s)""", (campaign, user_id, rv["name"], decision, note))
        if decision == "revoked":
            c.execute("UPDATE app_user SET status='disabled' WHERE id=%s", (user_id,))
            c.execute("UPDATE auth_session SET revoked_at=now() WHERE user_id=%s AND revoked_at IS NULL", (user_id,))
        actor, role, ip = actor_of(c, request, reviewer)
        audit(c, rv["name"], "access.review", entity_type="user", entity_id=user_id,
              detail={"decision": decision, "campaign": campaign, "note": note}, actor_role=rv["org_role"], ip=ip)
        c.commit()
    return {"ok": True, "user_id": user_id, "decision": decision, "reviewer": rv["name"]}


# ═══════════════════════════ historical ETL (prior-year backfill) ═══════════════════════════
def _etl_gate(c, who: str):
    """Loading/rolling-back history is a privileged action — reviewers (principal/director) only."""
    caps = _user_caps(c, who)
    if not caps or "review" not in caps["capabilities"]:
        raise HTTPException(403, "historical import requires a reviewer/director")
    return caps


@app.post("/api/import/dry-run")
def import_dry_run(source: str):
    """Validate a source file and report what would load — no writes."""
    try:
        rows = etl.read_source(source)
    except FileNotFoundError:
        raise HTTPException(404, f"source not found: {source}")
    with db() as c:
        return {"source": source, **etl.plan(c, rows)}


@app.post("/api/import/commit")
def import_commit(source: str, user: str = "Robert K.", note: str = "", request: Request = None):
    """Load a prior-year source into closed periods (idempotent, provenance-tagged, audited)."""
    try:
        rows = etl.read_source(source)
    except FileNotFoundError:
        raise HTTPException(404, f"source not found: {source}")
    batch_id = etl.new_batch_id()
    with db() as c:
        actor, role, ip = actor_of(c, request, user)
        _etl_gate(c, actor)
        res = etl.commit(c, rows, batch_id, source, actor, note)
        audit(c, actor, "import.commit", entity_type="import", entity_id=batch_id,
              detail={k: res[k] for k in ("loaded", "accounts_created", "periods_created", "rejected")},
              actor_role=role, ip=ip)
        c.commit()
    return res


@app.get("/api/import/batches")
def import_batches():
    with db() as c:
        rows = c.execute("SELECT * FROM import_batch ORDER BY created_at DESC").fetchall()
    return {"batches": rows}


@app.post("/api/import/{batch_id}/rollback")
def import_rollback(batch_id: str, user: str = "Robert K.", request: Request = None):
    with db() as c:
        actor, role, ip = actor_of(c, request, user)
        _etl_gate(c, actor)
        res = etl.rollback(c, batch_id)
        if res is None:
            raise HTTPException(404, "batch not found")
        audit(c, actor, "import.rollback", entity_type="import", entity_id=batch_id, detail=res,
              actor_role=role, ip=ip)
        c.commit()
    return res

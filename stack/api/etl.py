"""Historical ETL driver — backfill prior-year reconciliations into the recon scope.

Reads a canonical CSV (one row per account × period) and loads it into the database so roll-forward
continuity, trend reporting, and the multi-year audit binder have real history to work from.

Properties that make this safe rather than a CSV dump:
  • idempotent — upsert by (account, period); re-running a load never duplicates.
  • dry-run first — validate every row and report inserts/updates/rejects before committing.
  • provenance — every loaded record is tagged origin='historical_import' + a batch id, so migrated
    evidence is never mistaken for a reconciliation that passed live SoD/approval.
  • reversible — a batch can be rolled back cleanly by id.
  • loads into closed/locked periods (prior years are closed) — an admin/ETL action, audited by the API.

Canonical columns: period_end, account_code, account_name, group, assigned_to,
                    gl_balance, statement_balance, status, work_status, resolved_by, approved_by, note
Required: period_end (ISO date), account_code, gl_balance.
"""
from __future__ import annotations

import csv
import os
import secrets
from datetime import date

REQUIRED = ["period_end", "account_code", "gl_balance"]
NUMERIC = ["gl_balance", "statement_balance"]


def new_batch_id() -> str:
    return "imp-" + secrets.token_hex(4)


def read_source(name: str, import_dir: str | None = None) -> list[dict]:
    """Load rows from a CSV under IMPORT_DIR. basename-only — no path traversal out of the dir."""
    import_dir = import_dir or os.environ.get("IMPORT_DIR", "/samples")
    path = os.path.join(import_dir, os.path.basename(name))
    if not os.path.exists(path):
        raise FileNotFoundError(name)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def validate(rows: list[dict]):
    valid, errors = [], []
    for i, r in enumerate(rows, 1):
        missing = [k for k in REQUIRED if not (r.get(k) or "").strip()]
        if missing:
            errors.append({"row": i, "error": f"missing required: {', '.join(missing)}"})
            continue
        try:
            date.fromisoformat(r["period_end"].strip())
            for k in NUMERIC:
                if (r.get(k) or "").strip():
                    float(r[k])
        except (ValueError, TypeError) as e:
            errors.append({"row": i, "error": str(e)})
            continue
        valid.append(r)
    return valid, errors


def plan(c, rows: list[dict]) -> dict:
    """Dry-run: what would load, what would be rejected — no writes."""
    valid, errors = validate(rows)
    existing_a = {x["id"] for x in c.execute("SELECT id FROM gl_account").fetchall()}
    have = {(x["gl_account_id"], x["period_end"].isoformat())
            for x in c.execute("SELECT gl_account_id, period_end FROM reconciliation").fetchall()}
    inserts = updates = 0
    for r in valid:
        key = (r["account_code"].strip(), r["period_end"].strip())
        updates += 1 if key in have else 0
        inserts += 0 if key in have else 1
    accts = {r["account_code"].strip() for r in valid}
    return {
        "valid_rows": len(valid), "rejected_rows": len(errors), "errors": errors[:25],
        "new_accounts": sorted(accts - existing_a),
        "periods": sorted({r["period_end"].strip() for r in valid}),
        "rec_inserts": inserts, "rec_updates": updates,
    }


def commit(c, rows: list[dict], batch_id: str, source: str, created_by: str, note: str = "") -> dict:
    """Idempotent load. Creates missing accounts/periods, upserts reconciliations, all tagged to the batch."""
    valid, errors = validate(rows)
    existing_a = {x["id"] for x in c.execute("SELECT id FROM gl_account").fetchall()}
    existing_p = {x["period_key"] for x in c.execute("SELECT period_key FROM close_period").fetchall()}
    c.execute("INSERT INTO import_batch (id, source, created_by, note) VALUES (%s,%s,%s,%s)",
              (batch_id, source, created_by, note))
    loaded = a_created = p_created = 0
    for r in valid:
        code = r["account_code"].strip()
        pe = r["period_end"].strip()
        if code not in existing_a:
            c.execute("""INSERT INTO gl_account (id, code, name, grp, assigned_to, origin, import_batch_id)
                         VALUES (%s,%s,%s,%s,%s,'historical_import',%s) ON CONFLICT (id) DO NOTHING""",
                      (code, code, (r.get("account_name") or code), (r.get("group") or "Imported"),
                       (r.get("assigned_to") or None), batch_id))
            existing_a.add(code); a_created += 1
        if pe not in existing_p:   # one close_period per historical period_end (keyed by the date)
            c.execute("""INSERT INTO close_period (period_key, label, period_type, status, progress,
                              origin, import_batch_id, closed_by, closed_at)
                         VALUES (%s,%s,'annual','locked',100,'historical_import',%s,%s,now())
                         ON CONFLICT (period_key) DO NOTHING""",
                      (pe, f"FY{pe[:4]} (imported)", batch_id, created_by))
            existing_p.add(pe); p_created += 1
        gl = float(r["gl_balance"])
        st = (r.get("statement_balance") or "").strip()
        stv = float(st) if st else None
        var = round(gl - stv, 2) if stv is not None else None
        c.execute("""INSERT INTO reconciliation
                       (gl_account_id, period_end, gl_balance, statement_balance, variance, status,
                        work_status, note, resolved_by, approved_by, origin, import_batch_id, source_ref)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'historical_import',%s,%s)
                     ON CONFLICT (gl_account_id, period_end) DO UPDATE SET
                       gl_balance=EXCLUDED.gl_balance, statement_balance=EXCLUDED.statement_balance,
                       variance=EXCLUDED.variance, status=EXCLUDED.status, work_status=EXCLUDED.work_status,
                       note=EXCLUDED.note, resolved_by=EXCLUDED.resolved_by, approved_by=EXCLUDED.approved_by,
                       origin='historical_import', import_batch_id=EXCLUDED.import_batch_id,
                       source_ref=EXCLUDED.source_ref""",
                  (code, pe, gl, stv, var, (r.get("status") or "reconciled"),
                   (r.get("work_status") or "approved"), (r.get("note") or None),
                   (r.get("resolved_by") or None), (r.get("approved_by") or None), batch_id, source))
        loaded += 1
    c.execute("UPDATE import_batch SET rows_loaded=%s, accounts_created=%s, periods_created=%s WHERE id=%s",
              (loaded, a_created, p_created, batch_id))
    return {"batch": batch_id, "loaded": loaded, "accounts_created": a_created,
            "periods_created": p_created, "rejected": len(errors), "errors": errors[:25]}


def rollback(c, batch_id: str):
    """Remove everything a batch loaded. Accounts are only dropped if nothing else now references them."""
    b = c.execute("SELECT id FROM import_batch WHERE id=%s", (batch_id,)).fetchone()
    if not b:
        return None
    recs = c.execute("DELETE FROM reconciliation WHERE import_batch_id=%s", (batch_id,)).rowcount
    pers = c.execute("""DELETE FROM close_period WHERE import_batch_id=%s
                        AND period_key NOT IN (SELECT period_end::text FROM reconciliation)""",
                     (batch_id,)).rowcount
    accs = c.execute("""DELETE FROM gl_account WHERE import_batch_id=%s
                        AND id NOT IN (SELECT gl_account_id FROM reconciliation)""", (batch_id,)).rowcount
    c.execute("UPDATE import_batch SET status='rolled_back' WHERE id=%s", (batch_id,))
    return {"batch": batch_id, "reconciliations_removed": recs,
            "periods_removed": pers, "accounts_removed": accs}

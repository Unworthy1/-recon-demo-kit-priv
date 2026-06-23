"""Reconciliation engine — the one place matching/tolerance/status logic lives.

Pulls GL balances (GLAdapter, read-only) and statement balances (TreasuryAdapter) for a
period, matches by the account map, computes variance vs. tolerance, and writes the result.
Swapping a bank or GL is a one-adapter change; this logic never changes.

Scale: matching is O(n) — GL balances and statements are indexed into dicts, so each account
is an O(1) lookup (no nested scan). Writes are batched (chunked executemany) so reconciling
thousands of accounts is a handful of round-trips, not one per account. The result is a bounded
summary (counts + a capped exception sample), not a row per account, so the response stays small
whether the close has 50 accounts or 50,000.
"""
from __future__ import annotations

from datetime import date

WRITE_SQL = """INSERT INTO reconciliation
     (gl_account_id, period_end, gl_balance, statement_balance, variance, status,
      ocr_account, ocr_date, document_ref)
   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
   ON CONFLICT (gl_account_id, period_end) DO UPDATE SET
     gl_balance=EXCLUDED.gl_balance, statement_balance=EXCLUDED.statement_balance,
     variance=EXCLUDED.variance, status=EXCLUDED.status,
     ocr_account=EXCLUDED.ocr_account, ocr_date=EXCLUDED.ocr_date,
     document_ref=EXCLUDED.document_ref"""

EXCEPTION_SAMPLE_CAP = 500   # bound the response; the full board is read via /api/accounts


def classify(gl_balance, statement_balance, tolerance):
    """Return (variance, status). status in {reconciled, variance, unreconciled}."""
    if gl_balance is None or statement_balance is None:
        return None, "unreconciled"
    variance = round(float(gl_balance) - float(statement_balance), 2)
    status = "reconciled" if abs(variance) <= float(tolerance) else "variance"
    return variance, status


def run(conn, period_end: date, gl_adapter, treasury_adapters, *, batch_size: int = 1000):
    """Recompute every in-scope reconciliation for `period_end`. Returns a bounded summary.

    O(n) in the number of accounts; writes are flushed in batches of `batch_size`.
    """
    cur = conn.cursor()
    cur.execute("SELECT id, code, source_account, tolerance FROM gl_account")
    accounts = [{"id": r["id"], "code": r["code"], "source": r["source_account"], "tol": r["tolerance"]}
                for r in cur.fetchall()]

    # index GL balances and statements by key -> O(1) match per account (no nested scan)
    codes = [a["code"] for a in accounts]
    gl = {b.gl_account: b for b in gl_adapter.fetch_balances(period_end, codes)}
    stmts: dict[str, object] = {}
    dup_statements = 0
    for ta in treasury_adapters:
        for s in ta.fetch_statements(period_end):
            if s.source_account in stmts:
                dup_statements += 1            # operational signal: two statements for one account
            stmts[s.source_account] = s

    counts = {"total": len(accounts), "reconciled": 0, "variance": 0, "unreconciled": 0,
              "no_statement": 0, "no_gl": 0, "duplicate_statements": dup_statements}
    exceptions: list[dict] = []
    batch: list[tuple] = []

    for a in accounts:
        glb = gl.get(a["code"])
        stmt = stmts.get(a["source"]) if a["source"] else None
        gl_balance = glb.balance if glb else None
        stmt_balance = stmt.balance if stmt else None
        variance, status = classify(gl_balance, stmt_balance, a["tol"])

        counts[status] += 1
        if gl_balance is None:
            counts["no_gl"] += 1
        if a["source"] and stmt is None:
            counts["no_statement"] += 1
        if status != "reconciled" and len(exceptions) < EXCEPTION_SAMPLE_CAP:
            exceptions.append({"account": a["id"], "status": status, "variance": variance})

        batch.append((a["id"], period_end, gl_balance, stmt_balance, variance, status,
                      getattr(stmt, "source_account", None), getattr(stmt, "statement_date", None),
                      getattr(stmt, "document_ref", None)))
        if len(batch) >= batch_size:
            cur.executemany(WRITE_SQL, batch)
            batch.clear()

    if batch:
        cur.executemany(WRITE_SQL, batch)
    conn.commit()

    counts["exceptions"] = counts["variance"] + counts["unreconciled"]
    return {**counts, "exception_sample": exceptions,
            "exception_sample_truncated": counts["exceptions"] > len(exceptions)}

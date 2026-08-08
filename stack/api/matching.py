"""Transaction-level matching engine (#34, free tier). See docs/FUND-MATCHING-DESIGN.md.

Three passes per (gl_account, period) — always account-scoped, never cross-account:
  1. exact      — amount equal AND reference equal (both non-empty)      → auto_exact, matched
  2. rule       — a match_rule fires (amount tolerance / date window /
                  ref regex; account-specific rules before global)       → auto_rule, matched
  3. suggestion — amount equal within the suggest window, ref differs    → suggested (human decides)

Greedy 1:1 and deterministic: lines are processed oldest-first and each line joins at most one
live match. Unmatched lines are the OPEN ITEMS (outstanding checks / deposits in transit) and
must explain the reconciliation variance:  variance == sum(gl open) − sum(stmt open).

The pure functions (match_passes, age_bucket, tie_out) know nothing about the DB — that is what
matching_tests exercises offline. The DB layer below mirrors etl.py's idioms (batch provenance,
dry-run-able ingest, audited by the API layer).
"""
from __future__ import annotations

import os
import re
import secrets
from datetime import date
from typing import Iterable, Optional

# ─────────────────────────── pure core (offline-testable) ───────────────────────────

SUGGEST_WINDOW_DAYS = 30


def _norm_ref(ref: Optional[str]) -> str:
    return (ref or "").strip().upper()


def _cents(amount) -> int:
    return round(float(amount) * 100)


def match_passes(gl: list[dict], stmt: list[dict], rules: list[dict],
                 suggest_window: int = SUGGEST_WINDOW_DAYS) -> list[dict]:
    """Pair unmatched lines for ONE account. Each line dict: {id, amount, date, ref}.
    Rules (already filtered to this account + globals): {id, amount_tol, date_window,
    ref_pattern, priority} — applied in (priority, id) order, account-specific first
    (the caller orders them; this function just respects list order).

    Returns matches: {gl_ids, stmt_ids, match_type, rule_id, status} — 1:1 pairs, greedy,
    deterministic (both sides walked oldest-first, then by id)."""
    gl_open = sorted(gl, key=lambda r: (r["date"], r["id"]))
    st_open = sorted(stmt, key=lambda r: (r["date"], r["id"]))
    taken_gl: set = set()
    taken_st: set = set()
    out: list[dict] = []

    def _claim(g, s, mtype, rule_id=None, status="matched"):
        taken_gl.add(g["id"]); taken_st.add(s["id"])
        out.append({"gl_ids": [g["id"]], "stmt_ids": [s["id"]],
                    "match_type": mtype, "rule_id": rule_id, "status": status})

    # pass 1 — exact: amount equal + ref equal (both non-empty)
    by_key: dict = {}
    for s in st_open:
        ref = _norm_ref(s.get("ref"))
        if ref:
            by_key.setdefault((_cents(s["amount"]), ref), []).append(s)
    for g in gl_open:
        ref = _norm_ref(g.get("ref"))
        if not ref:
            continue
        for s in by_key.get((_cents(g["amount"]), ref), []):
            if s["id"] not in taken_st:
                _claim(g, s, "auto_exact")
                break

    # pass 2 — rules: tolerance / date window / optional ref regex on BOTH refs
    for rule in rules:
        pat = re.compile(rule["ref_pattern"]) if rule.get("ref_pattern") else None
        for g in gl_open:
            if g["id"] in taken_gl:
                continue
            for s in st_open:
                if s["id"] in taken_st:
                    continue
                if abs(float(g["amount"]) - float(s["amount"])) > float(rule.get("amount_tol") or 0) + 1e-9:
                    continue
                if abs((g["date"] - s["date"]).days) > int(rule.get("date_window") or 0):
                    continue
                if pat and not (pat.search(_norm_ref(g.get("ref"))) and pat.search(_norm_ref(s.get("ref")))):
                    continue
                _claim(g, s, "auto_rule", rule_id=rule.get("id"))
                break

    # pass 3 — suggestions: same amount inside the window, refs didn't line up
    for g in gl_open:
        if g["id"] in taken_gl:
            continue
        for s in st_open:
            if s["id"] in taken_st:
                continue
            if _cents(g["amount"]) == _cents(s["amount"]) and \
                    abs((g["date"] - s["date"]).days) <= suggest_window:
                _claim(g, s, "suggested", status="suggested")
                break
    return out


def age_bucket(item_date: date, as_of: date) -> str:
    days = (as_of - item_date).days
    if days <= 30:
        return "0-30"
    if days <= 60:
        return "31-60"
    if days <= 90:
        return "61-90"
    return "90+"


def tie_out(variance, gl_open_sum, stmt_open_sum, tol: float = 0.01) -> dict:
    """The engine's assertion: open items must explain the balance-level variance.
    variance = gl_balance − statement_balance; GL-side open items are entries the bank hasn't
    shown yet, statement-side open items are bank activity the GL hasn't booked — so
    variance should equal gl_open − stmt_open. Residual ≠ 0 means something is unexplained."""
    explained = round(float(gl_open_sum) - float(stmt_open_sum), 2)
    residual = round(float(variance or 0) - explained, 2)
    return {"explained": explained, "residual": residual, "ties": abs(residual) <= tol}


# ─────────────────────────── DB layer (mirrors etl.py idioms) ───────────────────────────

def new_batch_id() -> str:
    return "stm-" + secrets.token_hex(4)


def ingest_statement_file(c, name: str, created_by: str, import_dir: str | None = None) -> dict:
    """Parse one statement file (BAI2/camt.053/MT940/OFX, sniffed) into statement_line rows.
    source_account is resolved through the §E map (gl_account.source_account); unmapped
    accounts are reported, not silently dropped. Idempotent per file re-run is NOT assumed —
    every ingest is a new batch; roll back a bad one with rollback_batch()."""
    from adapters import formats
    import_dir = import_dir or os.environ.get("IMPORT_DIR", "/samples")
    path = os.path.join(import_dir, os.path.basename(name))
    if not os.path.exists(path):
        raise FileNotFoundError(name)
    with open(path, "rb") as f:
        content = f.read()
    parsed = list(formats.parse(content))

    amap = {r["source_account"]: r["id"] for r in
            c.execute("SELECT id, source_account FROM gl_account WHERE source_account IS NOT NULL").fetchall()}
    batch = new_batch_id()
    c.execute("INSERT INTO import_batch (id, source, created_by, note) VALUES (%s,%s,%s,%s)",
              (batch, name, created_by, "statement-line ingest (#34)"))
    loaded, unmapped, balances = 0, [], []
    for ps in parsed:
        gl_id = amap.get(ps.source_account)
        if not gl_id:
            unmapped.append(ps.source_account)
            continue
        for ln in ps.lines:
            c.execute("""INSERT INTO statement_line
                           (gl_account_id, stmt_date, amount, description, bank_ref, import_batch_id)
                         VALUES (%s,%s,%s,%s,%s,%s)""",
                      (gl_id, ln.stmt_date, ln.amount, ln.description, ln.bank_ref, batch))
            loaded += 1
        balances.append({"account": gl_id, "closing": ps.closing,
                         "as_of": ps.as_of.isoformat() if ps.as_of else None,
                         "ties_internally": ps.ties()})
    c.execute("UPDATE import_batch SET rows_loaded=%s WHERE id=%s", (loaded, batch))
    return {"batch": batch, "accounts_parsed": len(parsed), "lines_loaded": loaded,
            "unmapped_source_accounts": sorted(set(unmapped)), "statement_balances": balances}


def ingest_csv_with_profile(c, name: str, profile_name: str, created_by: str,
                            import_dir: str | None = None) -> dict:
    """Ingest a CSV statement export through a saved mapping profile (#37 csvmap).
    Only the 'statement' target lands here (statement_line rows); other targets are
    consumed by their adapters at reconcile time."""
    from adapters.formats import csvmap
    row = c.execute("SELECT target, config FROM mapping_profile WHERE name=%s AND active",
                    (profile_name,)).fetchone()
    if not row:
        raise LookupError(f"no active mapping profile '{profile_name}'")
    if row["target"] != "statement":
        raise ValueError(f"profile '{profile_name}' targets '{row['target']}', not statement")
    profile = csvmap.MappingProfile.from_dict(row["config"])
    import_dir = import_dir or os.environ.get("IMPORT_DIR", "/samples")
    path = os.path.join(import_dir, os.path.basename(name))
    if not os.path.exists(path):
        raise FileNotFoundError(name)
    with open(path, "rb") as f:
        parsed = csvmap.parse_csv(f.read(), profile)

    amap = {r["source_account"]: r["id"] for r in
            c.execute("SELECT id, source_account FROM gl_account WHERE source_account IS NOT NULL").fetchall()}
    batch = new_batch_id()
    c.execute("INSERT INTO import_batch (id, source, created_by, note) VALUES (%s,%s,%s,%s)",
              (batch, name, created_by, f"csv statement ingest via profile '{profile_name}' (#37)"))
    loaded, unmapped = 0, []
    for r in parsed["rows"]:
        gl_id = amap.get(r["source_account"])
        if not gl_id:
            unmapped.append(r["source_account"])
            continue
        c.execute("""INSERT INTO statement_line
                       (gl_account_id, stmt_date, amount, description, bank_ref, import_batch_id)
                     VALUES (%s,%s,%s,%s,%s,%s)""",
                  (gl_id, r["stmt_date"], r["amount"], r.get("description") or "",
                   r.get("bank_ref") or None, batch))
        loaded += 1
    c.execute("UPDATE import_batch SET rows_loaded=%s WHERE id=%s", (loaded, batch))
    return {"batch": batch, "profile": profile_name, "lines_loaded": loaded,
            "row_errors": parsed["errors"][:25],
            "unmapped_source_accounts": sorted(set(unmapped))}


def rollback_batch(c, batch_id: str) -> dict:
    lines = c.execute("DELETE FROM statement_line WHERE import_batch_id=%s", (batch_id,)).rowcount
    c.execute("UPDATE import_batch SET status='rolled_back' WHERE id=%s", (batch_id,))
    return {"batch": batch_id, "lines_removed": lines}


def _unmatched(c, table: str, id_col: str, gl_account_id: str, period_end: date) -> list[dict]:
    date_col = "txn_date" if table == "gl_transaction" else "stmt_date"
    ref_col = "doc_ref" if table == "gl_transaction" else "bank_ref"
    rows = c.execute(
        f"""SELECT t.id, t.amount, t.{date_col} AS date, t.{ref_col} AS ref
            FROM {table} t
            WHERE t.gl_account_id = %s AND t.{date_col} <= %s
              AND NOT EXISTS (SELECT 1 FROM txn_match_member m
                              JOIN txn_match x ON x.id = m.match_id
                              WHERE m.{id_col} = t.id AND x.status <> 'rejected')
            ORDER BY t.{date_col}, t.id""",
        (gl_account_id, period_end)).fetchall()
    return rows


def run_matching(c, gl_account_id: str, period_end: date) -> dict:
    """Run the three passes for one account and persist the results."""
    gl = _unmatched(c, "gl_transaction", "gl_txn_id", gl_account_id, period_end)
    st = _unmatched(c, "statement_line", "stmt_line_id", gl_account_id, period_end)
    rules = c.execute(
        """SELECT id, amount_tol, date_window, ref_pattern, priority FROM match_rule
           WHERE active AND (gl_account_id = %s OR gl_account_id IS NULL)
           ORDER BY (gl_account_id IS NULL), priority, id""",
        (gl_account_id,)).fetchall()
    matches = match_passes(gl, st, rules)
    counts = {"auto_exact": 0, "auto_rule": 0, "suggested": 0}
    for m in matches:
        row = c.execute(
            """INSERT INTO txn_match (match_type, status, rule_id, matched_by)
               VALUES (%s,%s,%s,'engine') RETURNING id""",
            (m["match_type"], m["status"], m["rule_id"])).fetchone()
        for gid in m["gl_ids"]:
            c.execute("INSERT INTO txn_match_member (match_id, gl_txn_id) VALUES (%s,%s)",
                      (row["id"], gid))
        for sid in m["stmt_ids"]:
            c.execute("INSERT INTO txn_match_member (match_id, stmt_line_id) VALUES (%s,%s)",
                      (row["id"], sid))
        counts[m["match_type"]] += 1
    return {"account": gl_account_id, "period_end": period_end.isoformat(),
            "gl_lines": len(gl), "stmt_lines": len(st), **counts,
            "open_after": (len(gl) + len(st)) - 2 * (counts["auto_exact"] + counts["auto_rule"])}


def decide(c, match_id: int, decision: str, user: str) -> dict:
    """Confirm or reject an engine suggestion (maker = engine, checker = the human)."""
    m = c.execute("SELECT id, status, match_type FROM txn_match WHERE id=%s", (match_id,)).fetchone()
    if not m:
        return {"error": "no such match"}
    if m["status"] != "suggested":
        return {"error": f"match is '{m['status']}', only suggestions can be decided"}
    new_status = "matched" if decision == "confirm" else "rejected"
    c.execute("""UPDATE txn_match SET status=%s, match_type='manual', decided_by=%s, decided_at=now()
                 WHERE id=%s""", (new_status, user, match_id))
    return {"match": match_id, "status": new_status, "decided_by": user}


def open_items(c, gl_account_id: str, period_end: date) -> dict:
    """The aged open items behind an account's variance, plus the tie-out assertion."""
    rows = c.execute(
        """SELECT side, id, item_date, amount, description, ref FROM open_item
           WHERE gl_account_id = %s AND item_date <= %s ORDER BY item_date, side, id""",
        (gl_account_id, period_end)).fetchall()
    rec = c.execute(
        "SELECT variance FROM reconciliation WHERE gl_account_id=%s AND period_end=%s",
        (gl_account_id, period_end)).fetchone()
    gl_sum = sum(float(r["amount"]) for r in rows if r["side"] == "gl")
    st_sum = sum(float(r["amount"]) for r in rows if r["side"] == "stmt")
    for r in rows:
        r["age"] = age_bucket(r["item_date"], period_end)
        r["item_date"] = r["item_date"].isoformat()
    return {"account": gl_account_id, "period_end": period_end.isoformat(),
            "items": rows, "gl_open_sum": round(gl_sum, 2), "stmt_open_sum": round(st_sum, 2),
            "tie_out": tie_out(rec["variance"], gl_sum, st_sum) if rec and rec["variance"] is not None
                       else {"explained": None, "residual": None, "ties": None,
                             "note": "no balance-level reconciliation for this period"}}

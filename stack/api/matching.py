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


def _read_import(name: str, import_dir: str | None) -> bytes:
    import_dir = import_dir or os.environ.get("IMPORT_DIR", "/samples")
    path = os.path.join(import_dir, os.path.basename(name))
    if not os.path.exists(path):
        raise FileNotFoundError(name)
    with open(path, "rb") as f:
        return f.read()


def _duplicate_of(c, sha: str) -> Optional[dict]:
    return c.execute(
        """SELECT id, status, created_by, created_at FROM import_batch
           WHERE content_sha256 = %s AND status IN ('committed', 'quarantined')
           ORDER BY created_at LIMIT 1""", (sha,)).fetchone()


def _open_batch(c, name: str, created_by: str, note: str, sha: str, status: str) -> str:
    batch = new_batch_id()
    c.execute("""INSERT INTO import_batch (id, source, created_by, note, content_sha256, status)
                 VALUES (%s,%s,%s,%s,%s,%s)""", (batch, name, created_by, note, sha, status))
    return batch


def _record_controls(c, batch: str, results) -> list[dict]:
    out = []
    for r in results:
        c.execute("""INSERT INTO ingest_control_result
                       (import_batch_id, control, scope, status, severity, expected, actual, detail)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                  (batch, r.control, r.scope, r.status, r.severity, r.expected, r.actual, r.detail))
        out.append(r.to_dict())
    return out


def _control_summary(results: list[dict]) -> dict:
    return {"controls": results,
            "blocking_failures": [r for r in results
                                  if r["status"] == "fail" and r["severity"] == "blocking"],
            "warnings": [r for r in results if r["status"] == "fail" and r["severity"] == "warning"]}


def _reject(c, name: str, created_by: str, note: str, sha: str, result) -> dict:
    """Record a refused file: a batch row + the failed control, zero lines. The evidence that
    someone tried is as auditable as a load."""
    batch = _open_batch(c, name, created_by, note, sha, "rejected")
    return {"batch": batch, "status": "rejected", "lines_loaded": 0,
            **_control_summary(_record_controls(c, batch, [result]))}


def _duplicate_result(dup: dict):
    from adapters.formats import controls
    return controls.ControlResult(
        "file.duplicate", "file", controls.FAIL, controls.BLOCKING,
        expected="a file not already loaded", actual=f"identical to batch {dup['id']}",
        detail=f"byte-identical file already loaded as {dup['id']} ({dup['status']}) by "
               f"{dup['created_by']} - roll that batch back first if a reload is intended")


def _unmapped_result(unmapped: list[str], parsed_accounts: int):
    from adapters.formats import controls
    return controls.ControlResult(
        "mapping.source_accounts", "file", controls.FAIL if unmapped else controls.PASS,
        controls.WARNING, expected=f"{parsed_accounts} mapped", actual=f"{len(unmapped)} unmapped",
        detail=("lines for unmapped source accounts were not loaded: " + ", ".join(unmapped))
               if unmapped else "every source account maps to a GL account")


def ingest_statement_file(c, name: str, created_by: str, import_dir: str | None = None) -> dict:
    """Parse one statement file (BAI2/camt.053/MT940/OFX, sniffed) into statement_line rows,
    behind the #41 ingest data controls:

      byte-identical to a live batch  -> rejected    (no lines; the attempt is recorded)
      unparseable                     -> rejected    (no lines)
      a blocking control fails        -> quarantined (lines loaded as evidence, excluded from
                                                      matching/open items until released)
      otherwise                       -> committed

    source_account is resolved through the §E map (gl_account.source_account); unmapped
    accounts are reported as a warning control, not silently dropped."""
    from adapters import formats
    from adapters.formats import controls
    content = _read_import(name, import_dir)
    sha = controls.sha256(content)
    note = "statement-line ingest (#34)"

    dup = _duplicate_of(c, sha)
    if dup:
        return _reject(c, name, created_by, note, sha, _duplicate_result(dup)) | {"duplicate_of": dup["id"]}
    try:
        fmt = formats.detect(content)
        parsed = list(formats.parse(content, fmt))
    except Exception as e:                        # any parser failure is a refusal, never a 500
        return _reject(c, name, created_by, note, sha, controls.ControlResult(
            "file.parse", "file", controls.FAIL, controls.BLOCKING, detail=str(e)[:500]))

    results = controls.evaluate(content, fmt, parsed)
    amap = {r["source_account"]: r["id"] for r in
            c.execute("SELECT id, source_account FROM gl_account WHERE source_account IS NOT NULL").fetchall()}
    unmapped = sorted({ps.source_account for ps in parsed if ps.source_account not in amap})
    results.append(_unmapped_result(unmapped, len(parsed)))
    status = controls.outcome(results)

    batch = _open_batch(c, name, created_by, note, sha, status)
    loaded, balances = 0, []
    for ps in parsed:
        gl_id = amap.get(ps.source_account)
        if not gl_id:
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
    return {"batch": batch, "status": status, "format": fmt, "accounts_parsed": len(parsed),
            "lines_loaded": loaded, "unmapped_source_accounts": unmapped,
            "statement_balances": balances, **_control_summary(_record_controls(c, batch, results))}


def ingest_csv_with_profile(c, name: str, profile_name: str, created_by: str,
                            import_dir: str | None = None, expected_rows: int | None = None,
                            control_total: float | None = None) -> dict:
    """Ingest a CSV statement export through a saved mapping profile (#37 csvmap).
    Only the 'statement' target lands here (statement_line rows); other targets are
    consumed by their adapters at reconcile time.

    CSV carries no bank-supplied integrity evidence, so the #41 controls are: duplicate file,
    rows that failed to parse (a partial file quarantines rather than loading silently), and
    optional operator-declared expected row count / control total."""
    from adapters.formats import controls, csvmap
    row = c.execute("SELECT target, config FROM mapping_profile WHERE name=%s AND active",
                    (profile_name,)).fetchone()
    if not row:
        raise LookupError(f"no active mapping profile '{profile_name}'")
    if row["target"] != "statement":
        raise ValueError(f"profile '{profile_name}' targets '{row['target']}', not statement")
    profile = csvmap.MappingProfile.from_dict(row["config"])
    content = _read_import(name, import_dir)
    sha = controls.sha256(content)
    note = f"csv statement ingest via profile '{profile_name}' (#37)"

    dup = _duplicate_of(c, sha)
    if dup:
        return (_reject(c, name, created_by, note, sha, _duplicate_result(dup))
                | {"profile": profile_name, "duplicate_of": dup["id"]})
    parsed = csvmap.parse_csv(content, profile)

    results = controls.csv_controls(parsed, expected_rows, control_total)
    amap = {r["source_account"]: r["id"] for r in
            c.execute("SELECT id, source_account FROM gl_account WHERE source_account IS NOT NULL").fetchall()}
    sources = {r["source_account"] for r in parsed["rows"]}
    unmapped = sorted(a for a in sources if a not in amap)
    results.append(_unmapped_result(unmapped, len(sources)))
    status = controls.outcome(results)

    batch = _open_batch(c, name, created_by, note, sha, status)
    loaded = 0
    for r in parsed["rows"]:
        gl_id = amap.get(r["source_account"])
        if not gl_id:
            continue
        c.execute("""INSERT INTO statement_line
                       (gl_account_id, stmt_date, amount, description, bank_ref, import_batch_id)
                     VALUES (%s,%s,%s,%s,%s,%s)""",
                  (gl_id, r["stmt_date"], r["amount"], r.get("description") or "",
                   r.get("bank_ref") or None, batch))
        loaded += 1
    c.execute("UPDATE import_batch SET rows_loaded=%s WHERE id=%s", (loaded, batch))
    return {"batch": batch, "status": status, "profile": profile_name, "lines_loaded": loaded,
            "row_errors": parsed["errors"][:25], "unmapped_source_accounts": unmapped,
            **_control_summary(_record_controls(c, batch, results))}


def batch_controls(c, batch_id: str) -> Optional[dict]:
    b = c.execute("""SELECT id, source, created_by, created_at, status, rows_loaded, note,
                            content_sha256, released_by, released_at, release_reason
                     FROM import_batch WHERE id=%s""", (batch_id,)).fetchone()
    if not b:
        return None
    rows = c.execute("""SELECT control, scope, status, severity, expected, actual, detail
                        FROM ingest_control_result WHERE import_batch_id=%s ORDER BY id""",
                     (batch_id,)).fetchall()
    return {"batch": b, **_control_summary(rows)}


def release_batch(c, batch_id: str, releaser: str, reason: str) -> Optional[dict]:
    """Quarantined -> committed. The caller (API) enforces who may release; this guards the state
    transition itself so a concurrent release or rollback can't double-apply."""
    return c.execute(
        """UPDATE import_batch SET status='committed', released_by=%s, released_at=now(),
                  release_reason=%s
           WHERE id=%s AND status='quarantined'
           RETURNING id, source, created_by, rows_loaded, released_at""",
        (releaser, reason, batch_id)).fetchone()


def rollback_batch(c, batch_id: str) -> dict:
    lines = c.execute("DELETE FROM statement_line WHERE import_batch_id=%s", (batch_id,)).rowcount
    c.execute("UPDATE import_batch SET status='rolled_back' WHERE id=%s", (batch_id,))
    return {"batch": batch_id, "lines_removed": lines}


def _unmatched(c, table: str, id_col: str, gl_account_id: str, period_end: date) -> list[dict]:
    date_col = "txn_date" if table == "gl_transaction" else "stmt_date"
    ref_col = "doc_ref" if table == "gl_transaction" else "bank_ref"
    # #41: statement lines from a quarantined / rejected / rolled-back batch never feed matching
    batch_gate = ("" if table == "gl_transaction" else
                  """AND (t.import_batch_id IS NULL OR EXISTS (SELECT 1 FROM import_batch b
                         WHERE b.id = t.import_batch_id AND b.status = 'committed'))""")
    rows = c.execute(
        f"""SELECT t.id, t.amount, t.{date_col} AS date, t.{ref_col} AS ref
            FROM {table} t
            WHERE t.gl_account_id = %s AND t.{date_col} <= %s
              {batch_gate}
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

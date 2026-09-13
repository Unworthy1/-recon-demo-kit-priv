"""Proposed journal entries (#43, free tier).

Reconciling items become DRAFT entries — never posted automatically:
  stmt_open_item  a statement line with no GL match (bank fee, interest, charge) → book it
  grir            an aged GR/IR clearing residue → clear it to a variance account
  residual        the unexplained part of a reconciliation variance → book it to suspense
  manual          an entry a preparer writes on a reconciliation

Workflow: draft → submitted → approved → exported (submitted → draft = returned; draft/submitted/
approved → void). Maker-checker: the approver is never the creator or the submitter. Export renders
approved entries through an outbound profile (the inverse of #37 mapping profiles) to a generic CSV;
each export is stored with its hash so a re-download is byte-identical.

Sign convention: a signed amount on an account is debit-positive — the same convention statement
lines use for the account they belong to (a deposit to cash is +, a charge to a card liability is −).
Booking a statement item of amount `a` on account A therefore posts `a` to A and `−a` to the offset.

Pure functions (proposal building, validation, CSV rendering) know nothing about the DB — that is
what journal_tests exercises offline. The DB layer below mirrors matching.py's idioms; the API
layer (app.py) enforces capabilities and audits every transition.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

CENT = Decimal("0.01")
KINDS = ("stmt_open_item", "grir", "residual", "manual")
TRANSITIONS = {("draft", "submitted"), ("submitted", "approved"), ("submitted", "draft"),
               ("approved", "exported"), ("draft", "void"), ("submitted", "void"), ("approved", "void")}
EXPORT_FIELDS = ("entry_number", "entry_id", "period_end", "posting_date", "memo", "line_no",
                 "account_code", "account_name", "description", "debit", "credit", "amount",
                 "fund_id", "gl_account_id", "source_kind", "source_ref", "prepared_by", "approved_by")
_NUMERIC_FIELDS = {"entry_id", "line_no", "debit", "credit", "amount"}
_CSV_INJECTION = ("=", "+", "-", "@", "\t", "\r")


def money(v) -> Decimal:
    return Decimal(str(v)).quantize(CENT, rounding=ROUND_HALF_UP)


def entry_number(entry_id: int) -> str:
    return f"JE-{int(entry_id):06d}"


def period_key(d: date) -> str:
    return d.strftime("%Y-%m")


# ─────────────────────────── lines ───────────────────────────

def signed_line(account_code: str, account_name: str, amount, description: str = "",
                gl_account_id: Optional[str] = None, fund_id: Optional[str] = None) -> dict:
    a = money(amount)
    return {"account_code": account_code, "account_name": account_name, "gl_account_id": gl_account_id,
            "fund_id": fund_id, "description": description,
            "debit": a if a > 0 else Decimal("0.00"), "credit": -a if a < 0 else Decimal("0.00")}


def validate_lines(lines) -> list[str]:
    """Every reason these lines can't form an entry. Mirrors the DB constraints so the API can
    answer 400 with a useful message instead of a constraint error at commit."""
    if not isinstance(lines, list) or len(lines) < 2:
        return ["an entry needs at least two lines"]
    errs, dr, cr = [], Decimal(0), Decimal(0)
    for i, ln in enumerate(lines, 1):
        if not isinstance(ln, dict):
            errs.append(f"line {i}: must be an object"); continue
        if not str(ln.get("account_code") or "").strip():
            errs.append(f"line {i}: account_code is required")
        try:
            d = Decimal(str(ln.get("debit") or 0)); c = Decimal(str(ln.get("credit") or 0))
        except Exception:
            errs.append(f"line {i}: debit/credit must be numbers"); continue
        if d < 0 or c < 0:
            errs.append(f"line {i}: debit/credit cannot be negative")
        if (d > 0) == (c > 0):
            errs.append(f"line {i}: exactly one of debit or credit must be non-zero")
        if d != d.quantize(CENT) or c != c.quantize(CENT):
            errs.append(f"line {i}: amounts carry at most 2 decimal places")
        dr += d; cr += c
    if not errs and dr != cr:
        errs.append(f"unbalanced: debits {dr} ≠ credits {cr}")
    return errs


def totals(lines) -> dict:
    dr = sum((money(l["debit"]) for l in lines), Decimal(0))
    cr = sum((money(l["credit"]) for l in lines), Decimal(0))
    return {"debits": dr, "credits": cr, "balanced": dr == cr}


def can_transition(old: str, new: str) -> bool:
    return (old, new) in TRANSITIONS


# ─────────────────────────── proposals ───────────────────────────

def pick_offset(rules: list[dict], kind: str, description: str) -> Optional[dict]:
    """First active rule for the kind, by priority, whose pattern matches (NULL pattern = fallback)."""
    text = description or ""
    for r in sorted((r for r in rules if r["source_kind"] == kind and r.get("active", True)),
                    key=lambda r: (r["priority"], r.get("id", 0))):
        if not r.get("pattern") or re.search(r["pattern"], text, re.IGNORECASE):
            return r
    return None


def propose_stmt_item(item: dict, account: dict, rules: list[dict]) -> Optional[dict]:
    """A statement line nobody booked: post it to the reconciled account, offset per rule."""
    off = pick_offset(rules, "stmt_open_item", item.get("description", ""))
    if off is None or money(item["amount"]) == 0:
        return None
    amt = money(item["amount"])
    why = (f"Statement line {item.get('ref') or item['id']} ({item.get('description') or 'no description'}) "
           f"for {amt} has no ledger match. Offset account {off['account_code']} chosen by "
           + (f"rule pattern /{off['pattern']}/" if off.get("pattern") else "the fallback rule — classify before approving")
           + ".")
    desc = (item.get("description") or "").strip()[:200]
    return {"source_kind": "stmt_open_item", "source_ref": str(item["id"]), "gl_account_id": account["id"],
            "memo": f"Book unrecorded bank item — {desc or item.get('ref') or item['id']}",
            "rationale": why,
            "lines": [signed_line(account["code"], account["name"], amt, desc, gl_account_id=account["id"]),
                      signed_line(off["account_code"], off["account_name"], -amt, desc)]}


def propose_grir(item: dict, clearing: dict, rules: list[dict], as_of: date, min_age_days: int) -> Optional[dict]:
    """An aged GR/IR residue: clear it. Clearing GL balance ties to −Σ open residue, so clearing a
    residue of r posts +r to the clearing account and −r to the variance account."""
    off = pick_offset(rules, "grir", item.get("reason", ""))
    last = item.get("last_activity")
    if isinstance(last, str):
        last = date.fromisoformat(last[:10])
    if off is None or last is None or (as_of - last).days < min_age_days or money(item["open_amount"]) == 0:
        return None
    r = money(item["open_amount"])
    days = (as_of - last).days
    off_code, off_name = off["account_code"], off["account_name"]
    if off_code == "@po_gl_code":
        if not item.get("gl_code"):
            return None                      # the rule needs the PO's account and this PO has none
        off_code, off_name = item["gl_code"], item.get("gl_name") or f"PO {item['po_id']} account"
    reason = {"grni": "received, not invoiced", "over_invoiced": "invoiced beyond receipt",
              "invoiced_not_received": "invoiced, nothing received"}.get(item.get("reason"), item.get("reason"))
    desc = f"PO {item['po_id']} {item.get('vendor') or ''} — {reason}".strip()
    return {"source_kind": "grir", "source_ref": str(item["po_id"]), "gl_account_id": clearing["id"],
            "memo": f"Clear aged GR/IR residue — PO {item['po_id']}",
            "rationale": (f"PO {item['po_id']} has {r} open on the clearing account ({reason}), no activity for "
                          f"{days} days (threshold {min_age_days}). Clearing it to {off_code} "
                          + (("(the PO's own account) expenses the invoice that never had a receipt"
                              if item.get("reason") == "invoiced_not_received"
                              else "(the PO's own account) reverses the receipt that was never invoiced")
                             if off["account_code"] == "@po_gl_code" else "books it as a variance")
                          + " — confirm the PO is complete before approving."),
            "lines": [signed_line(clearing["code"], clearing["name"], r, desc, gl_account_id=clearing["id"]),
                      signed_line(off_code, off_name, -r, desc)]}


def propose_residual(account: dict, rec_id, residual, rules: list[dict], period_end: date) -> Optional[dict]:
    """The part of a variance open items don't explain (variance = GL − statement): bring the GL to
    the statement by posting −residual to the account, offset to suspense."""
    off = pick_offset(rules, "residual", "")
    if off is None or residual is None or money(residual) == 0:
        return None
    r = money(residual)
    desc = f"Unexplained reconciliation residual {period_end.isoformat()}"
    return {"source_kind": "residual", "source_ref": str(rec_id), "gl_account_id": account["id"],
            "memo": f"Book unexplained residual — {account['code']} {account['name']}",
            "rationale": (f"After open items, {r} of the variance on {account['code']} is unexplained. Booking it "
                          f"to {off['account_code']} brings the ledger to the statement; it should be investigated "
                          f"and reclassified, not left in suspense."),
            "lines": [signed_line(account["code"], account["name"], -r, desc, gl_account_id=account["id"]),
                      signed_line(off["account_code"], off["account_name"], r, desc)]}


# ─────────────────────────── export ───────────────────────────

def validate_profile(cfg) -> list[str]:
    if not isinstance(cfg, dict):
        return ["profile config must be an object"]
    errs = []
    cols = cfg.get("columns")
    if not isinstance(cols, list) or not cols:
        errs.append("columns must be a non-empty list")
    else:
        for i, col in enumerate(cols, 1):
            if not isinstance(col, dict) or not str(col.get("header") or "").strip():
                errs.append(f"column {i}: needs a header"); continue
            if ("field" in col) == ("value" in col):
                errs.append(f"column {i}: give exactly one of field or value")
            elif "field" in col and col["field"] not in EXPORT_FIELDS:
                errs.append(f"column {i}: unknown field '{col['field']}' (one of {', '.join(EXPORT_FIELDS)})")
    if cfg.get("amount_sign", "debit_positive") not in ("debit_positive", "credit_positive"):
        errs.append("amount_sign must be debit_positive or credit_positive")
    if cfg.get("line_ending", "crlf") not in ("crlf", "lf"):
        errs.append("line_ending must be crlf or lf")
    d = cfg.get("delimiter", ",")
    if not isinstance(d, str) or len(d) != 1 or d in "\r\n\"":
        errs.append("delimiter must be a single character")
    try:
        date(2026, 5, 31).strftime(cfg.get("date_format", "%Y-%m-%d"))
    except Exception:
        errs.append("date_format is not a valid strftime format")
    return errs


def _cell(v) -> str:
    """Text cells are neutralised against spreadsheet formula injection (OWASP CSV injection)."""
    s = "" if v is None else str(v)
    return "'" + s if s.startswith(_CSV_INJECTION) else s


def render_csv(entries: list[dict], cfg: dict) -> str:
    """entries: [{id, period_end, memo, source_kind, source_ref, gl_account_id, created_by,
    approved_by, lines: [...]}] — lines in line_no order."""
    fmt = cfg.get("date_format", "%Y-%m-%d")
    credit_pos = cfg.get("amount_sign", "debit_positive") == "credit_positive"
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=cfg.get("delimiter", ","),
                   lineterminator="\r\n" if cfg.get("line_ending", "crlf") == "crlf" else "\n")
    cols = cfg["columns"]
    if cfg.get("include_header", True):
        w.writerow([_cell(c["header"]) for c in cols])
    for e in entries:
        pe = e["period_end"] if isinstance(e["period_end"], date) else date.fromisoformat(str(e["period_end"])[:10])
        for ln in e["lines"]:
            dr, cr = money(ln["debit"]), money(ln["credit"])
            signed = dr - cr
            vals = {"entry_number": entry_number(e["id"]), "entry_id": e["id"],
                    "period_end": pe.strftime(fmt), "posting_date": pe.strftime(fmt), "memo": e["memo"],
                    "line_no": ln["line_no"], "account_code": ln["account_code"], "account_name": ln["account_name"],
                    "description": ln["description"], "debit": f"{dr:.2f}" if dr else "",
                    "credit": f"{cr:.2f}" if cr else "", "amount": f"{(-signed if credit_pos else signed):.2f}",
                    "fund_id": ln.get("fund_id"), "gl_account_id": ln.get("gl_account_id"),
                    "source_kind": e["source_kind"], "source_ref": e.get("source_ref"),
                    "prepared_by": e["created_by"], "approved_by": e.get("approved_by")}
            w.writerow([(str(c["value"]) if "value" in c else
                         (vals[c["field"]] if c["field"] in _NUMERIC_FIELDS else _cell(vals[c["field"]])))
                        for c in cols])
    return buf.getvalue()


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ─────────────────────────── DB layer ───────────────────────────

class JournalError(Exception):
    """A request the workflow refuses. `code` is the HTTP status the API should answer."""
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def _jsonable(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            out[k] = f"{v:.2f}"
        elif isinstance(v, (date, datetime)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def assert_period_open(c, period_end: date) -> None:
    row = c.execute("SELECT status FROM close_period WHERE period_key=%s", (period_key(period_end),)).fetchone()
    if row and row["status"] == "locked":
        raise JournalError(409, f"period {period_key(period_end)} is locked — entries can't be created or approved in it")


def get_entry(c, entry_id: int) -> Optional[dict]:
    e = c.execute("SELECT * FROM journal_entry WHERE id=%s", (entry_id,)).fetchone()
    if not e:
        return None
    lines = c.execute("""SELECT line_no, account_code, account_name, gl_account_id, fund_id, description,
                                debit, credit FROM journal_entry_line WHERE entry_id=%s ORDER BY line_no""",
                      (entry_id,)).fetchall()
    t = totals(lines) if lines else {"debits": Decimal(0), "credits": Decimal(0), "balanced": False}
    return {**_jsonable(e), "entry_number": entry_number(e["id"]), "lines": [_jsonable(l) for l in lines],
            "totals": _jsonable(t)}


def _insert(c, entry: dict, period_end: date, created_by: str) -> int:
    row = c.execute("""INSERT INTO journal_entry (period_end, gl_account_id, memo, source_kind, source_ref,
                                                  rationale, created_by)
                       VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (period_end, entry.get("gl_account_id"), entry["memo"], entry["source_kind"],
                     entry.get("source_ref"), entry.get("rationale", ""), created_by)).fetchone()
    _write_lines(c, row["id"], entry["lines"])
    return row["id"]


def _write_lines(c, entry_id: int, lines: list[dict]) -> None:
    for n, ln in enumerate(lines, 1):
        c.execute("""INSERT INTO journal_entry_line (entry_id, line_no, account_code, account_name, gl_account_id,
                                                     fund_id, description, debit, credit)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                  (entry_id, n, str(ln["account_code"]).strip(), ln.get("account_name") or "",
                   ln.get("gl_account_id") or None, ln.get("fund_id") or None, ln.get("description") or "",
                   money(ln.get("debit") or 0), money(ln.get("credit") or 0)))


def _check_line_accounts(c, lines: list) -> None:
    ids = {l.get("gl_account_id") for l in lines if isinstance(l, dict) and l.get("gl_account_id")}
    if ids:
        known = {r["id"] for r in c.execute("SELECT id FROM gl_account WHERE id = ANY(%s)", (list(ids),)).fetchall()}
        if ids - known:
            raise JournalError(400, f"unknown gl_account_id on lines: {sorted(ids - known)}")


def create_manual(c, body: dict, created_by: str) -> int:
    try:
        pe = date.fromisoformat(str(body.get("period_end") or "")[:10])
    except ValueError:
        raise JournalError(400, "period_end must be a date")
    if not str(body.get("memo") or "").strip():
        raise JournalError(400, "memo is required")
    errs = validate_lines(body.get("lines"))
    if errs:
        raise JournalError(400, "; ".join(errs))
    if body.get("gl_account_id") and not c.execute("SELECT 1 FROM gl_account WHERE id=%s",
                                                   (body["gl_account_id"],)).fetchone():
        raise JournalError(400, f"unknown gl_account_id '{body['gl_account_id']}'")
    _check_line_accounts(c, body["lines"])
    assert_period_open(c, pe)
    return _insert(c, {"memo": body["memo"].strip(), "source_kind": "manual", "gl_account_id": body.get("gl_account_id"),
                       "rationale": str(body.get("rationale") or ""), "lines": body["lines"]}, pe, created_by)


def _rules(c) -> list[dict]:
    return c.execute("SELECT * FROM je_offset_rule WHERE active ORDER BY priority, id").fetchall()


def _live_sources(c, kind: str) -> set:
    return {r["source_ref"] for r in c.execute(
        "SELECT source_ref FROM journal_entry WHERE source_kind=%s AND status <> 'void' AND source_ref IS NOT NULL",
        (kind,)).fetchall()}


def propose_for_account(c, account_id: str, period_end: date, created_by: str, open_items: dict) -> dict:
    """Drafts for one reconciliation: every statement-side open item nobody has an entry for, and
    the unexplained residual if the tie-out doesn't close. Items already carrying a live entry are
    skipped, so proposing twice never duplicates."""
    acct = c.execute("SELECT id, code, name FROM gl_account WHERE id=%s", (account_id,)).fetchone()
    if not acct:
        raise JournalError(404, "account not found")
    assert_period_open(c, period_end)
    rules, live = _rules(c), _live_sources(c, "stmt_open_item")
    created, skipped = [], []
    for it in open_items["items"]:
        if it["side"] != "stmt":
            continue
        if str(it["id"]) in live:
            skipped.append({"item": it["id"], "reason": "already has a live entry"}); continue
        p = propose_stmt_item(it, acct, rules)
        if p:
            created.append(_insert(c, p, period_end, created_by))
    tie = open_items.get("tie_out") or {}
    rec = c.execute("SELECT id FROM reconciliation WHERE gl_account_id=%s AND period_end=%s",
                    (account_id, period_end)).fetchone()
    if rec and tie.get("ties") is False and tie.get("residual") is not None:
        if str(rec["id"]) in _live_sources(c, "residual"):
            skipped.append({"residual": rec["id"], "reason": "already has a live entry"})
        else:
            p = propose_residual(acct, rec["id"], tie["residual"], rules, period_end)
            if p:
                created.append(_insert(c, p, period_end, created_by))
    return {"account": account_id, "period_end": period_end.isoformat(), "created": created, "skipped": skipped}


def propose_for_grir(c, period_end: date, created_by: str, min_age_days: int) -> dict:
    clearing = c.execute("SELECT id, code, name FROM gl_account WHERE recon_type='clearing'").fetchone()
    if not clearing:
        raise JournalError(404, "no clearing account configured (gl_account.recon_type='clearing')")
    assert_period_open(c, period_end)
    rules, live = _rules(c), _live_sources(c, "grir")
    created, skipped = [], []
    for it in c.execute("""SELECT g.*, po.gl_name FROM grir_open_item g
                           JOIN purchase_order po ON po.id = g.po_id ORDER BY g.po_id""").fetchall():
        if str(it["po_id"]) in live:
            skipped.append({"po": it["po_id"], "reason": "already has a live entry"}); continue
        p = propose_grir(it, clearing, rules, period_end, min_age_days)
        if p:
            created.append(_insert(c, p, period_end, created_by))
        else:
            skipped.append({"po": it["po_id"], "reason": f"younger than {min_age_days} days or zero"})
    return {"period_end": period_end.isoformat(), "min_age_days": min_age_days, "created": created, "skipped": skipped}


def replace_lines(c, entry_id: int, lines: list, actor: str) -> dict:
    e = c.execute("SELECT status FROM journal_entry WHERE id=%s", (entry_id,)).fetchone()
    if not e:
        raise JournalError(404, "entry not found")
    if e["status"] != "draft":
        raise JournalError(409, f"entry is {e['status']} — only drafts can be edited")
    errs = validate_lines(lines)
    if errs:
        raise JournalError(400, "; ".join(errs))
    _check_line_accounts(c, lines)
    before = get_entry(c, entry_id)["lines"]
    c.execute("DELETE FROM journal_entry_line WHERE entry_id=%s", (entry_id,))
    _write_lines(c, entry_id, lines)
    return {"before": before, "after": get_entry(c, entry_id)["lines"]}


def transition(c, entry_id: int, new: str, actor: str, reason: str = "") -> dict:
    """Apply one workflow step. Capability checks live in the API; the separation-of-duties and
    state rules live here so every caller gets them."""
    e = c.execute("SELECT * FROM journal_entry WHERE id=%s", (entry_id,)).fetchone()
    if not e:
        raise JournalError(404, "entry not found")
    old = e["status"]
    if not can_transition(old, new):
        raise JournalError(409, f"entry is {old} — it can't be moved to {new}")
    if new in ("draft", "void") and not reason.strip():
        raise JournalError(400, "a reason is required")
    if new == "approved":
        if actor in (e["created_by"], e["submitted_by"]):
            raise JournalError(409, "segregation of duties: you cannot approve an entry you prepared or submitted")
        assert_period_open(c, e["period_end"])
    if new == "submitted":
        assert_period_open(c, e["period_end"])
    sets = {"submitted": "submitted_by=%s, submitted_at=now()",
            "approved": "approved_by=%s, approved_at=now()",
            "draft": "returned_by=%s, returned_at=now(), return_reason=%s, submitted_by=NULL, submitted_at=NULL",
            "void": "voided_by=%s, voided_at=now(), void_reason=%s"}[new]
    args = [actor, reason.strip()] if new in ("draft", "void") else [actor]
    cur = c.execute(f"UPDATE journal_entry SET status=%s, {sets} WHERE id=%s AND status=%s",
                    [new, *args, entry_id, old])
    if cur.rowcount != 1:
        raise JournalError(409, "entry changed state concurrently; reload and retry")
    return {"entry": entry_id, "entry_number": entry_number(entry_id), "from": old, "to": new, "by": actor}


def export(c, profile_name: str, actor: str, entry_ids: Optional[list] = None) -> dict:
    prof = c.execute("SELECT name, config FROM je_export_profile WHERE name=%s AND active", (profile_name,)).fetchone()
    if not prof:
        raise JournalError(404, f"no active export profile '{profile_name}'")
    if entry_ids:
        rows = c.execute("SELECT id, status FROM journal_entry WHERE id = ANY(%s) ORDER BY id FOR UPDATE",
                         ([int(i) for i in entry_ids],)).fetchall()
        missing = set(int(i) for i in entry_ids) - {r["id"] for r in rows}
        if missing:
            raise JournalError(404, f"entries not found: {sorted(missing)}")
        not_ready = [entry_number(r["id"]) + f" ({r['status']})" for r in rows if r["status"] != "approved"]
        if not_ready:
            raise JournalError(409, "only approved entries can be exported: " + ", ".join(not_ready))
        ids = [r["id"] for r in rows]
    else:
        ids = [r["id"] for r in c.execute(
            "SELECT id FROM journal_entry WHERE status='approved' ORDER BY id FOR UPDATE").fetchall()]
    if not ids:
        raise JournalError(409, "no approved entries waiting for export")
    entries = []
    for i in ids:
        e = c.execute("SELECT * FROM journal_entry WHERE id=%s", (i,)).fetchone()
        e["lines"] = c.execute("SELECT * FROM journal_entry_line WHERE entry_id=%s ORDER BY line_no", (i,)).fetchall()
        entries.append(e)
    content = render_csv(entries, prof["config"])
    from psycopg.types.json import Json
    ex = c.execute("""INSERT INTO je_export (profile_name, profile, created_by, entry_count, line_count,
                                            content_sha256, content)
                      VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id, created_at""",
                   (prof["name"], Json(prof["config"]), actor, len(entries), sum(len(e["lines"]) for e in entries),
                    sha256(content), content)).fetchone()
    c.execute("UPDATE journal_entry SET status='exported', export_id=%s, exported_at=now() WHERE id = ANY(%s)",
              (ex["id"], ids))
    return {"export": ex["id"], "profile": prof["name"], "entries": [entry_number(i) for i in ids],
            "entry_count": len(ids), "line_count": sum(len(e["lines"]) for e in entries),
            "sha256": sha256(content), "download": f"/api/journal/exports/{ex['id']}/file"}

"""Ingest data controls (#41) — prove a statement file is complete and unaltered before it
feeds matching.

Banks already ship integrity evidence inside the file (BAI2 trailers, camt.053 transaction
summaries, opening/closing balances). This module evaluates it — pure functions, no DB, offline
testable — and returns one ControlResult per check.

Design rule: HIGH PRECISION. A control that quarantines a legitimate bank file trains people to
release without reading, which is worse than having no control. So only checks with unambiguous
semantics are BLOCKING; anything that legitimately varies between banks is a WARNING; anything
that can't be evaluated is `not_available` — never counted as a pass.

    results = controls.evaluate(content, fmt, statements)
    status  = controls.outcome(results)          # 'committed' | 'quarantined'

`file.duplicate` needs the database, so the ingest layer adds it (it REJECTS rather than
quarantines — an identical re-upload is never legitimate).
"""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable, Optional

from .bai2 import funds_extra

PASS, FAIL, NA = "pass", "fail", "not_available"
BLOCKING, WARNING = "blocking", "warning"


@dataclass
class ControlResult:
    control: str                    # e.g. 'bai2.account_trailer'
    scope: str                      # 'file' | 'group:1' | 'account:<id>' | 'statement:<id>'
    status: str                     # pass | fail | not_available
    severity: str                   # blocking | warning
    expected: Optional[str] = None
    actual: Optional[str] = None
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def outcome(results: Iterable[ControlResult]) -> str:
    """Any failed BLOCKING control quarantines the batch; warnings never do."""
    return "quarantined" if any(r.status == FAIL and r.severity == BLOCKING for r in results) \
        else "committed"


# ─────────────────────────────── BAI2 trailers (49 / 98 / 99) ───────────────────────────────
#
# Per the BAI2 specification:
#   49 account trailer: control total = sum of all amount fields in the 03, 16 and 88 records
#      for the account; record count = the 03, all 16 and 88 records, and the 49 itself.
#   98 group trailer:  control total = sum of the account control totals in the group;
#      number of accounts = count of 03; records = the 02 through the 98, inclusive.
#   99 file trailer:   control total = sum of the group control totals; number of groups =
#      count of 02; records = every record in the file including the 99.
#
# Everything is compared as INTEGERS in the file's implied-decimal form — no float, no currency
# exponent, no tolerance.
#
# Sign ambiguity: the spec calls the total a sum of amount fields but does not say whether debit
# detail amounts (type codes 400-699, unsigned in the file) count as written or negated, and bank
# implementation guides warn that banks vary. Both readings are accepted; `detail` records which
# one tied. A truncated or altered file fails both.

def _int(raw: str) -> Optional[int]:
    """Parse a BAI2 amount/count field. '' → None. Non-numeric → ValueError (malformed file)."""
    s = (raw or "").strip()
    if not s:
        return None
    sign = -1 if s.startswith("-") else 1
    digits = s.lstrip("+-")
    if not digits.isdigit():
        raise ValueError(f"non-numeric field {raw!r}")
    return sign * int(digits)


def _logical_records(content: bytes) -> list[tuple[list[str], int]]:
    """Join 88 continuations onto their parent. Returns (fields, physical_record_count)."""
    out: list[tuple[list[str], int]] = []
    for line in content.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        line = line.rstrip("/")
        if line.startswith("88,") and out:
            fields, phys = out[-1]
            out[-1] = (fields + line[3:].split(","), phys + 1)
            continue
        out.append((line.split(","), 1))
    return out


def _03_amounts(f: list[str]) -> list[int]:
    """Primary amount of each (type code, amount, item count, funds type) group on an 03,
    stepping past funds-type extensions: S = 3 availability amounts, V = value date + time,
    D = a distribution count then (days, amount) pairs."""
    amounts, i = [], 3
    while i < len(f):
        amt = _int(f[i + 1]) if i + 1 < len(f) else None
        if amt is not None:
            amounts.append(amt)
        i += 4 + funds_extra(f, i + 3)
    return amounts


def bai2_trailers(content: bytes) -> list[ControlResult]:
    res: list[ControlResult] = []
    try:
        records = _logical_records(content)
    except Exception as e:                              # pragma: no cover - decode is lenient
        return [ControlResult("bai2.structure", "file", FAIL, BLOCKING, detail=str(e))]

    file_phys = 0
    groups = 0
    group_totals_declared = 0
    saw_file_trailer = False

    g_phys = g_accounts = 0
    g_acct_totals_declared = 0
    in_group = False

    a_phys = 0
    a_written = a_negated = 0
    a_id: Optional[str] = None

    def close_account_missing(reason: str):
        res.append(ControlResult("bai2.account_trailer", f"account:{a_id}", FAIL, BLOCKING,
                                 detail=f"missing 49 account trailer ({reason})"))

    for fields, phys in records:
        rtype = fields[0].strip()
        if saw_file_trailer:
            res.append(ControlResult("bai2.file_trailer", "file", FAIL, BLOCKING,
                                     detail=f"content after the 99 file trailer (record {rtype})"))
            break
        file_phys += phys
        try:
            if rtype == "01":
                continue
            if rtype == "02":
                if a_id is not None:
                    close_account_missing("next group began")
                    a_id = None
                in_group, groups = True, groups + 1
                g_phys, g_accounts, g_acct_totals_declared = phys, 0, 0
                continue
            if rtype == "03":
                if a_id is not None:
                    close_account_missing("next account began")
                a_id = fields[1].strip() if len(fields) > 1 else "?"
                g_accounts += 1
                a_phys = phys
                amts = _03_amounts(fields)
                a_written = a_negated = sum(amts)
                g_phys += phys
                continue
            if rtype == "16":
                a_phys += phys
                g_phys += phys
                amt = _int(fields[2]) if len(fields) > 2 else None
                if amt is not None:
                    code = fields[1].strip()
                    a_written += amt
                    a_negated += -abs(amt) if code[:1] in ("4", "5", "6") else amt
                continue
            if rtype == "49":
                a_phys += phys
                g_phys += phys
                declared_total = _int(fields[1]) if len(fields) > 1 else None
                declared_recs = _int(fields[2]) if len(fields) > 2 else None
                scope = f"account:{a_id}"
                if declared_total is None and declared_recs is None:
                    res.append(ControlResult("bai2.account_trailer", scope, NA, BLOCKING,
                                             detail="49 carries no control total or record count"))
                else:
                    problems, reading = [], ""
                    if declared_recs is not None and declared_recs != a_phys:
                        problems.append(f"records declared {declared_recs}, counted {a_phys}")
                    if declared_total is not None:
                        if declared_total == a_written:
                            reading = "amounts as written"
                        elif declared_total == a_negated:
                            reading = "debit detail negated"
                        else:
                            problems.append(f"control total declared {declared_total}, computed "
                                            f"{a_written} (as written) / {a_negated} (debits negated)")
                    res.append(ControlResult(
                        "bai2.account_trailer", scope, FAIL if problems else PASS, BLOCKING,
                        expected=f"total={declared_total} records={declared_recs}",
                        actual=f"total={a_written} records={a_phys}",
                        detail="; ".join(problems) if problems else f"tied ({reading or 'count only'})"))
                g_acct_totals_declared += declared_total or 0
                a_id = None
                continue
            if rtype == "98":
                if a_id is not None:
                    close_account_missing("group trailer reached")
                    a_id = None
                g_phys += phys
                d_total = _int(fields[1]) if len(fields) > 1 else None
                d_accts = _int(fields[2]) if len(fields) > 2 else None
                d_recs = _int(fields[3]) if len(fields) > 3 else None
                problems = []
                if d_total is not None and d_total != g_acct_totals_declared:
                    problems.append(f"group total declared {d_total}, sum of account totals "
                                    f"{g_acct_totals_declared}")
                if d_accts is not None and d_accts != g_accounts:
                    problems.append(f"accounts declared {d_accts}, counted {g_accounts}")
                if d_recs is not None and d_recs != g_phys:
                    problems.append(f"records declared {d_recs}, counted {g_phys}")
                res.append(ControlResult(
                    "bai2.group_trailer", f"group:{groups}", FAIL if problems else PASS, BLOCKING,
                    expected=f"total={d_total} accounts={d_accts} records={d_recs}",
                    actual=f"total={g_acct_totals_declared} accounts={g_accounts} records={g_phys}",
                    detail="; ".join(problems) or "tied"))
                group_totals_declared += d_total or 0
                in_group = False
                continue
            if rtype == "99":
                saw_file_trailer = True
                d_total = _int(fields[1]) if len(fields) > 1 else None
                d_groups = _int(fields[2]) if len(fields) > 2 else None
                d_recs = _int(fields[3]) if len(fields) > 3 else None
                problems = []
                if d_total is not None and d_total != group_totals_declared:
                    problems.append(f"file total declared {d_total}, sum of group totals "
                                    f"{group_totals_declared}")
                if d_groups is not None and d_groups != groups:
                    problems.append(f"groups declared {d_groups}, counted {groups}")
                if d_recs is not None and d_recs != file_phys:
                    problems.append(f"records declared {d_recs}, counted {file_phys}")
                res.append(ControlResult(
                    "bai2.file_trailer", "file", FAIL if problems else PASS, BLOCKING,
                    expected=f"total={d_total} groups={d_groups} records={d_recs}",
                    actual=f"total={group_totals_declared} groups={groups} records={file_phys}",
                    detail="; ".join(problems) or "tied"))
                continue
        except ValueError as e:
            res.append(ControlResult("bai2.structure", f"record:{rtype}", FAIL, BLOCKING,
                                     detail=f"malformed {rtype} record: {e}"))
            return res

    if not saw_file_trailer:
        if a_id is not None:
            close_account_missing("end of file")
        if in_group:
            res.append(ControlResult("bai2.group_trailer", f"group:{groups}", FAIL, BLOCKING,
                                     detail="missing 98 group trailer — file appears truncated"))
        res.append(ControlResult("bai2.file_trailer", "file", FAIL, BLOCKING,
                                 detail="missing 99 file trailer — file appears truncated"))
    return res


# ─────────────────────────────── camt.053 transaction summary ───────────────────────────────

def _ln(el) -> str:
    return el.tag.rsplit("}", 1)[-1]


def _child(el, *path):
    cur = el
    for name in path:
        cur = next((c for c in cur if _ln(c) == name), None)
        if cur is None:
            return None
    return cur


def _dec(text: Optional[str]) -> Optional[Decimal]:
    try:
        return Decimal((text or "").strip()) if (text or "").strip() else None
    except InvalidOperation:
        return None


def camt053_summary(content: bytes) -> list[ControlResult]:
    """TxsSummry/TtlNtries: NbOfNtries must equal the number of <Ntry>, and Sum (the total of the
    entries' amounts, which camt carries unsigned) must equal the sum of their <Amt>."""
    res: list[ControlResult] = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        return [ControlResult("camt053.structure", "file", FAIL, BLOCKING, detail=f"XML: {e}")]
    for stmt in (el for el in root.iter() if _ln(el) in ("Stmt", "Rpt")):
        acct_el = _child(stmt, "Acct", "Id", "IBAN") or _child(stmt, "Acct", "Id", "Othr", "Id")
        scope = f"statement:{(acct_el.text or '').strip() if acct_el is not None else '?'}"
        entries = [e for e in stmt if _ln(e) == "Ntry"]
        total = _child(stmt, "TxsSummry", "TtlNtries")
        if total is None:
            res.append(ControlResult("camt053.entry_summary", scope, NA, BLOCKING,
                                     actual=f"entries={len(entries)}",
                                     detail="statement carries no TxsSummry/TtlNtries"))
            continue
        d_count = _dec(getattr(_child(total, "NbOfNtries"), "text", None))
        d_sum = _dec(getattr(_child(total, "Sum"), "text", None))
        a_sum = sum((_dec(getattr(_child(e, "Amt"), "text", None)) or Decimal(0)) for e in entries)
        problems = []
        if d_count is not None and int(d_count) != len(entries):
            problems.append(f"entries declared {int(d_count)}, found {len(entries)}")
        if d_sum is not None and d_sum != a_sum:
            problems.append(f"sum declared {d_sum}, computed {a_sum}")
        res.append(ControlResult(
            "camt053.entry_summary", scope, FAIL if problems else PASS, BLOCKING,
            expected=f"entries={d_count} sum={d_sum}", actual=f"entries={len(entries)} sum={a_sum}",
            detail="; ".join(problems) or "tied"))
    return res


# ─────────────────────────────── balance continuity (all formats) ───────────────────────────

def balance_continuity(statements) -> list[ControlResult]:
    """opening + Σ lines = closing. A WARNING, not blocking: banks legitimately report
    summary-only accounts or partial detail, and the reconciliation itself surfaces the
    variance — so this informs the reviewer without holding up matching."""
    res = []
    for s in statements:
        scope = f"statement:{s.source_account}"
        if s.opening is None or s.closing is None:
            res.append(ControlResult("balance.continuity", scope, NA, WARNING,
                                     detail="format/statement does not carry both balances"))
            continue
        if not s.lines and round(s.opening, 2) != round(s.closing, 2):
            res.append(ControlResult("balance.continuity", scope, NA, WARNING,
                                     detail="summary-only account: no detail lines to test"))
            continue
        net = round(sum(l.amount for l in s.lines), 2)
        ok = s.ties()
        res.append(ControlResult(
            "balance.continuity", scope, PASS if ok else FAIL, WARNING,
            expected=f"closing={s.closing:.2f}", actual=f"opening+lines={s.opening + net:.2f}",
            detail="tied" if ok else f"detail does not explain the balance change "
                                     f"(residual {round(s.closing - s.opening - net, 2):.2f})"))
    return res


# ─────────────────────────────── CSV (no bank-supplied evidence) ─────────────────────────────

def csv_controls(parsed: dict, expected_rows: Optional[int] = None,
                 control_total: Optional[float] = None) -> list[ControlResult]:
    """CSV exports carry no integrity evidence of their own, so completeness comes from the
    mapper (rows that failed to parse) and, optionally, totals the operator declares at upload."""
    rows, errors = parsed.get("rows", []), parsed.get("errors", [])
    # A header-only export can be a genuine no-activity day, so empty is a WARNING, not a block —
    # but it must never commit silently.
    res = [ControlResult("csv.nonempty", "file", PASS if (rows or errors) else FAIL, WARNING,
                         actual=f"rows={len(rows)}",
                         detail="" if (rows or errors) else "no data rows found below the header")]
    res += [ControlResult(
        "csv.row_errors", "file", FAIL if errors else PASS, BLOCKING,
        expected="0", actual=str(len(errors)),
        detail=(f"{len(errors)} row(s) failed to parse and were not loaded — a partial file "
                f"must not feed matching silently") if errors else "every data row parsed")]
    if expected_rows is None:
        res.append(ControlResult("csv.declared_rows", "file", NA, BLOCKING,
                                 actual=str(len(rows) + len(errors)),
                                 detail="no expected row count declared at upload"))
    else:
        seen = len(rows) + len(errors)
        res.append(ControlResult("csv.declared_rows", "file", PASS if seen == expected_rows else FAIL,
                                 BLOCKING, expected=str(expected_rows), actual=str(seen),
                                 detail="tied" if seen == expected_rows else "row count differs"))
    if control_total is None:
        res.append(ControlResult("csv.declared_total", "file", NA, BLOCKING,
                                 detail="no control total declared at upload"))
    else:
        got = sum(Decimal(str(r["amount"])).quantize(Decimal("0.01")) for r in rows
                  if r.get("amount") is not None)
        want = Decimal(str(control_total)).quantize(Decimal("0.01"))
        res.append(ControlResult("csv.declared_total", "file", PASS if got == want else FAIL,
                                 BLOCKING, expected=str(want), actual=str(got),
                                 detail="tied" if got == want else "control total differs"))
    return res


# ─────────────────────────────── entry point ─────────────────────────────────────────────────

def evaluate(content: bytes, fmt: str, statements) -> list[ControlResult]:
    """All file-level controls for a sniffed bank format. (`file.duplicate` is added by the
    ingest layer, which has the database.)"""
    statements = list(statements)
    lines = sum(len(s.lines) for s in statements)
    res = [ControlResult("file.nonempty", "file", PASS if statements else FAIL, BLOCKING,
                         actual=f"statements={len(statements)} lines={lines}",
                         detail="" if statements else "no statements parsed")]
    if fmt == "bai2":
        res += bai2_trailers(content)
    elif fmt == "camt053":
        res += camt053_summary(content)
    else:
        res.append(ControlResult(f"{fmt}.integrity", "file", NA, BLOCKING,
                                 detail=f"{fmt} carries no file-level control totals"))
    res += balance_continuity(statements)
    return res

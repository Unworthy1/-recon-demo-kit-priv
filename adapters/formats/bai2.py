"""BAI2 — the US cash-management / institutional treasury statement format.

Record types: 01 file header · 02 group header (carries the as-of date) · 03 account
identifier (account, currency, summary/status codes incl. balances) · 16 transaction detail ·
88 continuation · 49/98/99 trailers. Amounts carry an implied decimal (2 for USD — the only
exponent handled here; extend via CURRENCY_EXP if a deployment needs JPY etc.).

Sign convention: detail type codes 100–399 are credits (+), 400–699 debits (−).
Balance status codes on 03: 010 opening ledger, 015 closing ledger.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

from ..base import StatementLine
from . import ParsedStatement

CURRENCY_EXP = {"": 2, "USD": 2, "CAD": 2, "EUR": 2, "GBP": 2, "JPY": 0}

_OPENING, _CLOSING = "010", "015"


def _amount(raw: str, currency: str) -> float:
    exp = CURRENCY_EXP.get(currency, 2)
    sign = -1.0 if raw.strip().startswith("-") else 1.0
    digits = raw.strip().lstrip("+-") or "0"
    return sign * int(digits) / (10 ** exp)


def funds_extra(f: list[str], j: int) -> int:
    """How many fields follow the funds-type field at f[j]: S = 3 availability amounts
    (immediate, one-day, two-plus-day), V = value date + time, D = a distribution count then
    (days, amount) pairs. 0/1/2/Z/blank carry nothing extra. Shared with controls.py."""
    funds = f[j].strip().upper() if j < len(f) else ""
    if funds == "S":
        return 3
    if funds == "V":
        return 2
    if funds == "D":
        n = f[j + 1].strip() if j + 1 < len(f) else ""
        return 1 + 2 * (int(n) if n.isdigit() else 0)
    return 0


def _logical_records(content: bytes) -> list[list[str]]:
    """Join 88 continuations onto their parent, strip the '/' terminators, split fields."""
    logical: list[str] = []
    for line in content.decode("utf-8", "replace").splitlines():
        line = line.strip().rstrip("/")
        if not line:
            continue
        if line.startswith("88,"):
            if logical:
                logical[-1] += "," + line[3:]
            continue
        logical.append(line)
    return [rec.split(",") for rec in logical]


def parse(content: bytes) -> Iterable[ParsedStatement]:
    stmts: list[ParsedStatement] = []
    cur: ParsedStatement | None = None
    as_of: date | None = None
    for f in _logical_records(content):
        rtype = f[0]
        if rtype == "02":                          # group header: ...,as-of-date(YYMMDD),...
            for tok in f[1:]:
                tok = tok.strip()
                if len(tok) == 6 and tok.isdigit():
                    as_of = datetime.strptime(tok, "%y%m%d").date()
                    break
        elif rtype == "03":                        # account: acct, ccy, then (code,amt,count,funds)*
            currency = (f[2] or "USD").strip() if len(f) > 2 else "USD"
            cur = ParsedStatement(source_account=f[1].strip(), currency=currency or "USD",
                                  as_of=as_of)
            stmts.append(cur)
            i = 3
            while i + 1 < len(f):
                code, amt = f[i].strip(), f[i + 1].strip()
                if code and amt not in ("", "/"):
                    if code == _OPENING:
                        cur.opening = _amount(amt, cur.currency)
                    elif code == _CLOSING:
                        cur.closing = _amount(amt, cur.currency)
                i += 4 + funds_extra(f, i + 3)     # code, amount, item count, funds type[, extras]
        elif rtype == "16" and cur is not None:    # detail: code, amount, funds, [refs...], text
            code = f[1].strip()
            amt = _amount(f[2], cur.currency)
            if code and code[0] in "456":          # 400–699 = debit
                amt = -abs(amt)
            i = 3
            if i < len(f):
                i += 1 + funds_extra(f, 3)         # funds type[, S/V/D extras]
            bank_ref = f[i].strip() if i < len(f) else ""
            text = ",".join(f[i + 2:]).strip() if i + 2 < len(f) else ""
            cur.lines.append(StatementLine(
                source_account=cur.source_account, amount=amt,
                stmt_date=cur.as_of or date.today(), description=text,
                bank_ref=bank_ref or None, raw={"type_code": code}))
    return stmts

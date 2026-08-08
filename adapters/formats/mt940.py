"""MT940 — SWIFT customer statement, still ubiquitous internationally.

Tags: :25: account · :60F: opening balance · :61: transaction (value date YYMMDD, entry date
MMDD, D/C mark with optional R(eversal) prefix, amount comma-decimal, type, refs) · :86:
info for the preceding :61: · :62F: closing balance. Multiple statements per file are
separated by a lone '-' line. Sign: C → +, D → −; an R prefix (RC/RD) flips the sign.
"""
from __future__ import annotations

import re
from datetime import datetime, date
from typing import Iterable, Optional

from ..base import StatementLine
from . import ParsedStatement

_TAG = re.compile(r"^:(\d{2}[A-Z]?):(.*)$")
_BAL = re.compile(r"^([CD])(\d{6})([A-Z]{3})([\d,]+)$")
_TXN = re.compile(r"^(\d{6})(\d{4})?(R?[CD])([A-Z])?([\d,]+)([A-Z][A-Z0-9]{3})(.*)$")


def _amt(raw: str) -> float:
    return float(raw.replace(",", "."))


def _bal(payload: str):
    m = _BAL.match(payload.strip())
    if not m:
        return None, None, None
    sign = 1.0 if m.group(1) == "C" else -1.0
    return sign * _amt(m.group(4)), datetime.strptime(m.group(2), "%y%m%d").date(), m.group(3)


def parse(content: bytes) -> Iterable[ParsedStatement]:
    stmts: list[ParsedStatement] = []
    for block in re.split(r"\n-\s*\n|\n-\s*$", content.decode("utf-8", "replace")):
        if ":25:" not in block:
            continue
        ps = ParsedStatement(source_account="")
        pending: Optional[StatementLine] = None
        for line in block.splitlines():
            m = _TAG.match(line.strip())
            if not m:                                   # continuation of the previous :86:
                if pending is not None and line.strip():
                    ps.lines[-1] = _with_desc(ps.lines[-1], line.strip())
                continue
            tag, payload = m.group(1), m.group(2).strip()
            if tag == "25":
                ps.source_account = payload.split("/")[-1] if "/" in payload else payload
            elif tag in ("60F", "60M"):
                ps.opening, _, ccy = _bal(payload)
                if ccy:
                    ps.currency = ccy
            elif tag in ("62F", "62M"):
                ps.closing, ps.as_of, ccy = _bal(payload)
                if ccy:
                    ps.currency = ccy
            elif tag == "61":
                t = _TXN.match(payload)
                if not t:
                    continue
                sign = 1.0 if t.group(3).lstrip("R") == "C" else -1.0
                if t.group(3).startswith("R"):
                    sign = -sign
                refs = t.group(7) or ""
                cust_ref = refs.split("//")[0].strip()
                pending = StatementLine(
                    source_account=ps.source_account,
                    amount=sign * _amt(t.group(5)),
                    stmt_date=datetime.strptime(t.group(1), "%y%m%d").date(),
                    description="",
                    bank_ref=cust_ref or None,
                    raw={"type": t.group(6)})
                ps.lines.append(pending)
            elif tag == "86" and pending is not None:
                ps.lines[-1] = _with_desc(ps.lines[-1], payload)
        stmts.append(ps)
    return stmts


def _with_desc(line: StatementLine, extra: str) -> StatementLine:
    desc = (line.description + " " + extra).strip()
    return StatementLine(source_account=line.source_account, amount=line.amount,
                         stmt_date=line.stmt_date, description=desc,
                         bank_ref=line.bank_ref, raw=line.raw)

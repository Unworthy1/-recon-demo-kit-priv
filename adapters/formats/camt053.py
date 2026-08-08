"""camt.053 / camt.052 (ISO 20022) — the format the banking industry is migrating to.

Namespace-agnostic: matches XML elements by local name, so any camt.053.001.NN version
parses. Per <Stmt>: account (IBAN or Othr/Id), OPBD/CLBD balances, and <Ntry> entries
(amount, credit/debit indicator, booking date, reference, additional info).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date
from typing import Iterable, Optional

from ..base import StatementLine
from . import ParsedStatement


def _ln(el) -> str:
    return el.tag.rsplit("}", 1)[-1]


def _find(el, *path) -> Optional[ET.Element]:
    cur = el
    for name in path:
        cur = next((c for c in cur if _ln(c) == name), None)
        if cur is None:
            return None
    return cur


def _text(el, *path) -> str:
    found = _find(el, *path)
    return (found.text or "").strip() if found is not None else ""


def _date(el, *path) -> Optional[date]:
    node = _find(el, *path)
    if node is None:
        return None
    raw = _text(node, "Dt") or _text(node, "DtTm") or (node.text or "").strip()
    return date.fromisoformat(raw[:10]) if raw else None


def _signed(amount_el, cd_ind: str) -> float:
    val = float((amount_el.text or "0").strip())
    return -val if cd_ind == "DBIT" else val


def parse(content: bytes) -> Iterable[ParsedStatement]:
    root = ET.fromstring(content)
    stmts: list[ParsedStatement] = []
    for stmt_el in (el for el in root.iter() if _ln(el) in ("Stmt", "Rpt")):
        acct = _text(stmt_el, "Acct", "Id", "IBAN") or _text(stmt_el, "Acct", "Id", "Othr", "Id")
        ccy = _text(stmt_el, "Acct", "Ccy") or "USD"
        ps = ParsedStatement(source_account=acct, currency=ccy,
                             bank_name=_text(stmt_el, "Acct", "Svcr", "FinInstnId", "Nm"))
        for bal in (el for el in stmt_el if _ln(el) == "Bal"):
            code = _text(bal, "Tp", "CdOrPrtry", "Cd")
            amt_el = _find(bal, "Amt")
            if amt_el is None:
                continue
            val = _signed(amt_el, _text(bal, "CdtDbtInd"))
            if code == "OPBD":
                ps.opening = val
            elif code == "CLBD":
                ps.closing = val
                ps.as_of = _date(bal, "Dt") or ps.as_of
            if amt_el.get("Ccy"):
                ps.currency = amt_el.get("Ccy")
        for ntry in (el for el in stmt_el if _ln(el) == "Ntry"):
            amt_el = _find(ntry, "Amt")
            if amt_el is None:
                continue
            ps.lines.append(StatementLine(
                source_account=acct,
                amount=_signed(amt_el, _text(ntry, "CdtDbtInd")),
                stmt_date=_date(ntry, "BookgDt") or _date(ntry, "ValDt") or ps.as_of or date.min,
                description=_text(ntry, "AddtlNtryInf"),
                bank_ref=_text(ntry, "NtryRef") or _text(ntry, "AcctSvcrRef") or None,
                raw={"status": _text(ntry, "Sts")}))
        stmts.append(ps)
    return stmts

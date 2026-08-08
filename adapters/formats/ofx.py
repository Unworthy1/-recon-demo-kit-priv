"""OFX / QFX — the download format of small-business and consumer bank portals.

OFX 1.x is SGML (unclosed tags), 2.x is XML; a tolerant regex pass handles both. Reads
<ACCTID>, <STMTTRN> blocks (TRNAMT already signed, DTPOSTED, FITID, NAME/MEMO) and
<LEDGERBAL> (closing balance + as-of). One statement per BANKACCTFROM/CCACCTFROM block.
"""
from __future__ import annotations

import re
from datetime import datetime, date
from typing import Iterable, Optional

from ..base import StatementLine
from . import ParsedStatement

_STMT_SPLIT = re.compile(r"<STMTRS>|<CCSTMTRS>", re.I)
_FIELD = {name: re.compile(rf"<{name}>\s*([^<\r\n]+)", re.I)
          for name in ("ACCTID", "CURDEF", "BALAMT", "DTASOF", "TRNAMT", "DTPOSTED",
                       "FITID", "NAME", "MEMO", "CHECKNUM", "ORG")}
_TRN = re.compile(r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|$)", re.I | re.S)
_LEDGER = re.compile(r"<LEDGERBAL>(.*?)(?:</LEDGERBAL>|(?=<AVAILBAL>)|$)", re.I | re.S)


def _get(pattern_key: str, text: str) -> str:
    m = _FIELD[pattern_key].search(text)
    return m.group(1).strip() if m else ""


def _ofx_date(raw: str) -> Optional[date]:
    digits = re.sub(r"[^\d].*$", "", raw)
    return datetime.strptime(digits[:8], "%Y%m%d").date() if len(digits) >= 8 else None


def parse(content: bytes) -> Iterable[ParsedStatement]:
    text = content.decode("utf-8", "replace")
    bank = _get("ORG", text)
    blocks = _STMT_SPLIT.split(text)[1:] or [text]
    stmts: list[ParsedStatement] = []
    for block in blocks:
        acct = _get("ACCTID", block)
        if not acct:
            continue
        ps = ParsedStatement(source_account=acct, currency=_get("CURDEF", block) or "USD",
                             bank_name=bank)
        ledger = _LEDGER.search(block)
        if ledger:
            bal_raw = _get("BALAMT", ledger.group(1))
            ps.closing = float(bal_raw) if bal_raw else None
            ps.as_of = _ofx_date(_get("DTASOF", ledger.group(1)))
        for trn in _TRN.finditer(block):
            body = trn.group(1)
            amt_raw = _get("TRNAMT", body)
            if not amt_raw:
                continue
            name, memo = _get("NAME", body), _get("MEMO", body)
            ps.lines.append(StatementLine(
                source_account=acct,
                amount=float(amt_raw.replace(",", "")),
                stmt_date=_ofx_date(_get("DTPOSTED", body)) or ps.as_of or date.min,
                description=" — ".join(x for x in (name, memo) if x),
                bank_ref=_get("FITID", body) or _get("CHECKNUM", body) or None))
        stmts.append(ps)
    return stmts

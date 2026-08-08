"""Bank statement format parsers (#37) — the 'maximum compatibility' layer.

Parse the standard formats every bank emits and any bank works, regardless of how the file
arrives (upload / watched folder / SFTP / IMAP — the transports in treasury.py). Each parser
returns ParsedStatement objects: the closing balance (feeds today's balance-level recs) plus
transaction lines (feeds the #34 matching engine via TreasuryAdapter.fetch_lines()).

    from adapters import formats
    for stmt in formats.parse(raw_bytes):          # sniffs the format
        ...

Formats: BAI2 (US institutional), camt.053 (ISO 20022), MT940 (SWIFT), OFX/QFX (SMB banks).
Plug into a transport with `parse_fn=formats.parse`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Optional

from ..base import StatementLine


@dataclass
class ParsedStatement:
    """One account's statement as parsed from a file (a file may contain many accounts)."""
    source_account: str
    currency: str = "USD"
    opening: Optional[float] = None       # opening ledger balance, if the format carries it
    closing: Optional[float] = None       # closing ledger balance
    as_of: Optional[date] = None          # statement period-end
    bank_name: str = ""
    lines: list = field(default_factory=list)   # list[StatementLine]

    def ties(self, tol: float = 0.01) -> Optional[bool]:
        """opening + sum(lines) == closing, when all three are known. None = can't check."""
        if self.opening is None or self.closing is None:
            return None
        return abs(self.opening + sum(l.amount for l in self.lines) - self.closing) <= tol


def detect(content: bytes) -> str:
    """Sniff the format. Returns 'bai2' | 'camt053' | 'mt940' | 'ofx'."""
    head = content[:2048].decode("utf-8", "replace").lstrip("﻿ \r\n\t")
    lower = head.lower()
    if lower.startswith("01,"):
        return "bai2"
    if "<ofx" in lower or "ofxheader" in lower:
        return "ofx"
    if "camt.053" in lower or "camt.052" in lower or "<bktocstmrstmt" in lower or (
            lower.startswith("<?xml") and "document" in lower and "stmt" in lower):
        return "camt053"
    if ":20:" in head or ":25:" in head:
        return "mt940"
    raise ValueError("unrecognized bank statement format (expected BAI2 / camt.053 / MT940 / OFX)")


def parse(content: bytes, fmt: Optional[str] = None) -> Iterable[ParsedStatement]:
    """Parse a statement file into ParsedStatement objects, sniffing the format unless given."""
    from . import bai2, camt053, mt940, ofx
    fmt = fmt or detect(content)
    parser = {"bai2": bai2.parse, "camt053": camt053.parse,
              "mt940": mt940.parse, "ofx": ofx.parse}[fmt]
    return parser(content)

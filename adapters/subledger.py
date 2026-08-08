"""Subledger adapters (INTAKE §R): billing/AR, AP, payroll, fixed assets. All READ-ONLY.

Feed subledger reconciliations — the GL control account ties against the subledger total —
and (for billing) the participant receivables the funding layer generates (#36). Also the
"statement side" of clearing-account recs like GR/IR (#35).

Reference: CSVSubledger (works today against a subledger export).
Stubs: ODBCSubledger, BillingAPISubledger — implement the marked section per your INTAKE.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Iterable

from .base import StatementLine, SubledgerAdapter, SubledgerBalance, register


@register("subledger", "csv_export")
class CSVSubledger(SubledgerAdapter):
    """READY. Reads a subledger export CSV (aged trial balance / open-items summary).

    Expected columns (configurable): control_account, balance[, subledger, open_items].
    INTAKE §R 'scheduled export'.
    """
    name = "subledger:csv_export"

    def __init__(self, path: str, account_col="control_account", balance_col="balance",
                 subledger_col="subledger", open_items_col="open_items"):
        self.path = path
        self.account_col, self.balance_col = account_col, balance_col
        self.subledger_col, self.open_items_col = subledger_col, open_items_col

    def fetch_balances(self, period_end: date, accounts: list[str]) -> Iterable[SubledgerBalance]:
        wanted = set(accounts or [])
        with open(Path(self.path), newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                acct = row[self.account_col].strip()
                if wanted and acct not in wanted:
                    continue
                oi = row.get(self.open_items_col)
                yield SubledgerBalance(
                    gl_account=acct,
                    balance=float(str(row[self.balance_col]).replace(",", "").replace("$", "")),
                    as_of=period_end,
                    subledger=(row.get(self.subledger_col) or "").strip().lower(),
                    open_items=int(oi) if oi not in (None, "",) else None,
                    raw=row)


@register("subledger", "odbc")
class ODBCSubledger(SubledgerAdapter):
    """STUB. Generic ODBC against an on-prem subledger (ERP AP/AR tables).

    Implement per INTAKE §R: read-only login from the secret store (INTAKE §H); one
    SELECT summing open items per control account (fetch_balances) and, optionally, the
    open-item detail (fetch_lines) for the matching engine. Never issue DML.
    """
    name = "subledger:odbc"

    def __init__(self, dsn_secret: str, query: str = ""):
        self.dsn_secret, self.query = dsn_secret, query

    def fetch_balances(self, period_end: date, accounts: list[str]) -> Iterable[SubledgerBalance]:
        raise NotImplementedError(
            "Implement: pyodbc read-only connection; open-items-per-control-account query; "
            "yield SubledgerBalance(...) per row.")


@register("subledger", "billing_api")
class BillingAPISubledger(SubledgerAdapter):
    """STUB. A billing/AR system's REST API (utility CIS, participant billing, invoicing SaaS).

    Implement per INTAKE §R: credentials from the secret store; pull the AR aging /
    open-invoice summary per control account for fetch_balances, and open invoices as
    lines for fetch_lines (invoice no → bank_ref, customer/participant → description).
    For participant billing (#36) the participant id should ride in raw[] so the funding
    layer can tie each receivable back to a participant statement.
    """
    name = "subledger:billing_api"

    def __init__(self, api_secret: str, base_url: str = ""):
        self.api_secret, self.base_url = api_secret, base_url

    def fetch_balances(self, period_end: date, accounts: list[str]) -> Iterable[SubledgerBalance]:
        raise NotImplementedError(
            "Implement: GET the AR aging summary; yield SubledgerBalance(subledger='billing', ...).")

    def fetch_lines(self, period_end: date, gl_account: str) -> Iterable[StatementLine]:
        raise NotImplementedError(
            "Implement: GET open invoices for the control account; yield StatementLine(...) "
            "with invoice no as bank_ref and participant/customer in raw.")

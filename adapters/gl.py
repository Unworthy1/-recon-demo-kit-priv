"""GL adapters (INTAKE §C). All READ-ONLY.

Reference: CSVExportGL (works today against a trial-balance export).
Stubs: DynamicsGPGL, NetSuiteGL, ODBCGL — implement the marked section per your INTAKE.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Iterable

from .base import GLAdapter, GLBalance, register


@register("gl", "csv_export")
class CSVExportGL(GLAdapter):
    """READY. Reads a period-end trial-balance CSV the ERP exports on a schedule.

    Expected columns (configurable): account, balance, as_of.  INTAKE §C 'scheduled export'.
    """
    name = "gl:csv_export"

    def __init__(self, path: str, account_col="account", balance_col="balance", as_of_col="as_of"):
        self.path, self.account_col, self.balance_col, self.as_of_col = path, account_col, balance_col, as_of_col

    def fetch_balances(self, period_end: date, accounts: list[str]) -> Iterable[GLBalance]:
        wanted = set(accounts or [])
        with open(Path(self.path), newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                acct = row[self.account_col].strip()
                if wanted and acct not in wanted:
                    continue
                yield GLBalance(gl_account=acct,
                                balance=float(str(row[self.balance_col]).replace(",", "").replace("$", "")),
                                as_of=period_end, raw=row)


@register("gl", "dynamics_gp")
class DynamicsGPGL(GLAdapter):
    """STUB — Microsoft Dynamics GP via read-only ODBC/SQL (INTAKE §C 'direct database').

    GP stores period balances in GL20000 (open year) / GL30000 (history), accounts in GL00100.
    Implement fetch_balances() with a read-only service account. NEVER write.
    """
    name = "gl:dynamics_gp"

    def __init__(self, dsn: str, company_db: str = "DYNAMICS"):
        self.dsn, self.company_db = dsn, company_db

    def fetch_balances(self, period_end: date, accounts: list[str]) -> Iterable[GLBalance]:
        # IMPLEMENT (per your system): use pyodbc against `self.dsn`; example shape:
        #   SELECT a.ACTNUMST AS account, SUM(t.PERDBLNC) AS balance
        #   FROM GL20000 t JOIN GL00105 a ON t.ACTINDX = a.ACTINDX
        #   WHERE t.YEAR1 = ? AND t.PERIODID = ?  GROUP BY a.ACTNUMST
        # Map period_end -> (YEAR1, PERIODID). Filter by `accounts`. Read-only login only.
        raise NotImplementedError("Implement DynamicsGPGL.fetch_balances per your GP schema (read-only).")


@register("gl", "netsuite")
class NetSuiteGL(GLAdapter):
    """STUB — NetSuite via SuiteQL/REST (INTAKE §C 'vendor API'). Implement with a saved
    search or SuiteQL 'SELECT account, sum(amount) ... AS of period'. Token-based auth."""
    name = "gl:netsuite"

    def __init__(self, account_id: str, auth: dict):
        self.account_id, self.auth = account_id, auth

    def fetch_balances(self, period_end: date, accounts: list[str]) -> Iterable[GLBalance]:
        raise NotImplementedError("Implement NetSuiteGL.fetch_balances via SuiteQL/REST.")


@register("gl", "odbc")
class ODBCGL(GLAdapter):
    """STUB — generic read-only ODBC for any SQL-backed ERP (SAP/Sage/Oracle/QuickBooks Desktop).
    Provide the trial-balance query in `query` with :period_end / :accounts params."""
    name = "gl:odbc"

    def __init__(self, dsn: str, query: str):
        self.dsn, self.query = dsn, query

    def fetch_balances(self, period_end: date, accounts: list[str]) -> Iterable[GLBalance]:
        raise NotImplementedError("Implement ODBCGL.fetch_balances using pyodbc + self.query (read-only).")

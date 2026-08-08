"""Budget adapters (INTAKE §Q). All READ-ONLY — the budget system is authoritative.

Reference: CSVBudget (works today against a budget export).
Stubs: ODBCBudget, AdaptivePlanningBudget — implement the marked section per your INTAKE.
Gov/utility budget modules (Tyler Munis, Questica, Oracle EPBCS/Hyperion) export CSV on a
schedule — they land on CSVBudget + a saved mapping profile, no native connector needed.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Iterable

from .base import BudgetAdapter, BudgetAmount, register


@register("budget", "csv_export")
class CSVBudget(BudgetAdapter):
    """READY. Reads a budget export CSV the budget system produces on a schedule.

    Expected columns (configurable): account, amount[, scenario, basis]. INTAKE §Q 'scheduled export'.
    """
    name = "budget:csv_export"

    def __init__(self, path: str, account_col="account", amount_col="amount",
                 scenario_col="scenario", basis_col="basis"):
        self.path = path
        self.account_col, self.amount_col = account_col, amount_col
        self.scenario_col, self.basis_col = scenario_col, basis_col

    def fetch_budget(self, period_end: date, accounts: list[str]) -> Iterable[BudgetAmount]:
        wanted = set(accounts or [])
        with open(Path(self.path), newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                acct = row[self.account_col].strip()
                if wanted and acct not in wanted:
                    continue
                yield BudgetAmount(
                    gl_account=acct,
                    amount=float(str(row[self.amount_col]).replace(",", "").replace("$", "")),
                    as_of=period_end,
                    scenario=(row.get(self.scenario_col) or "adopted").strip().lower(),
                    basis=(row.get(self.basis_col) or "period").strip().lower(),
                    raw=row)


@register("budget", "odbc")
class ODBCBudget(BudgetAdapter):
    """STUB. Generic ODBC against an on-prem budget module (ERP budget tables, Munis, etc.).

    Implement per INTAKE §Q: connection string from the secret store (INTAKE §H), one
    parameterised SELECT returning (account, amount[, scenario]) for the period. READ-ONLY:
    connect with a read-only login; never issue DML.
    """
    name = "budget:odbc"

    def __init__(self, dsn_secret: str, query: str = ""):
        self.dsn_secret, self.query = dsn_secret, query

    def fetch_budget(self, period_end: date, accounts: list[str]) -> Iterable[BudgetAmount]:
        raise NotImplementedError(
            "Implement: pyodbc.connect(<dsn from secret store>, readonly=True); "
            "execute the period query; yield BudgetAmount(...) per row.")


@register("budget", "adaptive")
class AdaptivePlanningBudget(BudgetAdapter):
    """STUB. Workday Adaptive Planning — exportData API (XML) or a scheduled report export.

    Implement per INTAKE §Q: credentials from the secret store; call exportData for the
    version named in the INTAKE (maps to `scenario`); parse rows into BudgetAmount.
    Prefer the scheduled-export path (CSVBudget) unless the deployment needs live pulls.
    """
    name = "budget:adaptive"

    def __init__(self, instance_secret: str, version: str = "adopted"):
        self.instance_secret, self.version = instance_secret, version

    def fetch_budget(self, period_end: date, accounts: list[str]) -> Iterable[BudgetAmount]:
        raise NotImplementedError(
            "Implement: Adaptive exportData API call for self.version; "
            "yield BudgetAmount(scenario=self.version, ...) per row.")

"""Adapter contracts — the three points where OpenRecon plugs into a business's systems.

A coding agent reads the filled INTAKE.md and, for each of the three connection points,
either reuses a reference adapter (below / in the sibling modules) or implements one of the
provided stubs for the named system. The reconciliation engine (stack/engine.py) only ever
talks to these interfaces, so the rest of the software is unchanged regardless of which
bank / GL / DMS a business runs.

    INTAKE §B  ->  TreasuryAdapter   (bank statement balances in)
    INTAKE §C  ->  GLAdapter         (general-ledger balances in, READ-ONLY)
    INTAKE §D  ->  DMSAdapter        (source/support documents stored + linked)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Optional


# ─────────────────────────── value objects (the contract data) ───────────────────────────
@dataclass(frozen=True)
class StatementBalance:
    source_account: str                 # bank account id as it appears on the statement
    balance: float                      # closing/statement balance
    as_of: date                         # statement period-end
    statement_date: Optional[date] = None
    bank_name: Optional[str] = None
    document_ref: Optional[str] = None  # DMS doc id or URL for the source statement
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GLBalance:
    gl_account: str                     # GL account key (matches the account map in INTAKE §E)
    balance: float                      # period-end balance
    as_of: date
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class AllocationLine:
    gl_account: str                     # FERC account the cost was allocated to
    amount: float
    name: str = ""


@dataclass(frozen=True)
class ProjectExpense:
    project_id: str
    name: str
    source_amount: float                # the one expense the lines must tie to
    lines: list                         # list[AllocationLine]
    wo: str = ""
    vendor: str = ""
    source_doc: str = ""
    source_ref: str = ""


@dataclass(frozen=True)
class StoredDocument:
    doc_id: str
    title: str
    url: Optional[str] = None           # deep link into the DMS, if any
    correspondent: Optional[str] = None
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class StatementLine:
    """One bank-statement transaction (#37/#34). Balance-only sources never produce these."""
    source_account: str                 # bank account id as it appears on the statement
    amount: float                       # signed: credits positive, debits negative
    stmt_date: date
    description: str = ""
    bank_ref: Optional[str] = None      # bank reference / check number / FITID
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class BudgetAmount:
    """One budget figure for budget-vs-actual (INTAKE §Q)."""
    gl_account: str                     # GL account key (INTAKE §E account map)
    amount: float                       # budgeted amount for the period (or annual — see basis)
    as_of: date                         # period-end the figure applies to
    scenario: str = "adopted"           # adopted | amended | forecast
    basis: str = "period"               # period | annual (annual is spread above this layer)
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SubledgerBalance:
    """A subledger's control-account total (INTAKE §R): AP, AR/billing, payroll, fixed assets.
    The reconciliation ties this against the GL control account's balance."""
    gl_account: str                     # the GL control account the subledger rolls up to
    balance: float                      # subledger total at period-end
    as_of: date
    subledger: str = ""                 # ap | ar | billing | payroll | fixed_assets | ...
    open_items: Optional[int] = None    # count of open documents behind the total, if known
    raw: dict = field(default_factory=dict)


# ─────────────────────────── the three interfaces ───────────────────────────
class TreasuryAdapter(ABC):
    """Bring bank/treasury statement balances in (INTAKE §B). One instance per source."""

    name: str = "treasury"

    @abstractmethod
    def fetch_statements(self, period_end: date) -> Iterable[StatementBalance]:
        """Return the statement balance(s) available for this period. Implementations may
        pull (SFTP/API), read a watched folder/mailbox, or yield what was manually uploaded."""

    def fetch_lines(self, period_end: date) -> Iterable[StatementLine]:
        """Transaction-level detail for the matching engine (#34). OPTIONAL — balance-only
        adapters (PDF statements, manual uploads) simply don't override this; the engine
        falls back to balance-level reconciliation for those accounts."""
        return ()


class GLAdapter(ABC):
    """Read general-ledger balances (INTAKE §C). MUST be read-only — never writes to the GL."""

    name: str = "gl"
    read_only: bool = True

    @abstractmethod
    def fetch_balances(self, period_end: date, accounts: list[str]) -> Iterable[GLBalance]:
        """Return period-end balances for the requested GL accounts (or all in-scope if empty)."""


class DMSAdapter(ABC):
    """Store and link source + supporting documents (INTAKE §D)."""

    name: str = "dms"

    @abstractmethod
    def ingest(self, content: bytes, filename: str, metadata: dict) -> StoredDocument:
        """File a document into the DMS (with OCR if the DMS does it) and return its handle."""

    @abstractmethod
    def url_for(self, doc_id: str) -> str:
        """Return a deep link a reviewer can open for the given document id."""


class ProjectAdapter(ABC):
    """Bring in project-cost allocations (INTAKE §K). For each project/expense, returns the one
    source amount + the allocation lines across (FERC) accounts — what a project reconciliation
    ties out and settles together. The FERC range -> Project grouping is applied above this layer."""

    name: str = "project"

    @abstractmethod
    def fetch_projects(self, period_end: date) -> Iterable[ProjectExpense]:
        """Return the open project reconciliations for the period (source amount + allocation lines)."""


class BudgetAdapter(ABC):
    """Bring budget figures in for budget-vs-actual (INTAKE §Q). READ-ONLY — the budget
    system is authoritative; OpenRecon never writes back."""

    name: str = "budget"
    read_only: bool = True

    @abstractmethod
    def fetch_budget(self, period_end: date, accounts: list[str]) -> Iterable[BudgetAmount]:
        """Return budget amounts for the requested GL accounts (or all in-scope if empty)."""


class SubledgerAdapter(ABC):
    """Bring a subledger's control totals in (INTAKE §R): billing/AR, AP, payroll, fixed
    assets. Feeds subledger reconciliations (control account ↔ subledger tie-out) and, for
    billing, the participant receivables the funding layer generates. READ-ONLY."""

    name: str = "subledger"
    read_only: bool = True

    @abstractmethod
    def fetch_balances(self, period_end: date, accounts: list[str]) -> Iterable[SubledgerBalance]:
        """Return subledger control totals for the requested GL control accounts."""

    def fetch_lines(self, period_end: date, gl_account: str) -> Iterable[StatementLine]:
        """OPTIONAL open-item detail behind a control total (invoice/receipt level), for the
        matching engine (#34). Balance-only subledger feeds simply don't override this."""
        return ()


# ─────────────────────────── registry (INTAKE choice -> adapter class) ───────────────────────────
# The agent maps the ticked option in the INTAKE to a key here. Reference + stub adapters
# register themselves in the sibling modules (treasury.py / gl.py / dms.py / budget.py / subledger.py).
_REGISTRY: dict[str, dict[str, type]] = {"treasury": {}, "gl": {}, "dms": {}, "project": {},
                                         "budget": {}, "subledger": {}}


def register(kind: str, key: str):
    def deco(cls):
        _REGISTRY[kind][key] = cls
        return cls
    return deco


def get_adapter(kind: str, key: str) -> type:
    try:
        return _REGISTRY[kind][key]
    except KeyError:
        raise KeyError(f"no {kind} adapter '{key}'. Available: {sorted(_REGISTRY[kind])}")


def available(kind: str) -> list[str]:
    return sorted(_REGISTRY[kind])

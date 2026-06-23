"""Treasury / bank-statement adapters (INTAKE §B). One instance per source.

Reference: WatchedFolderTreasury, ManualUploadTreasury (work today).
Stubs: IMAPTreasury, SFTPTreasury, BankAPITreasury — implement per your INTAKE source.

Parsing note: PDF statements are OCR'd by the DMS (see dms.py) and the balance/account/date
are extracted there; structured feeds (BAI2/MT940/CSV/OFX) are parsed here. `parse_fn` lets
the agent plug a format parser without changing the adapter.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Callable, Iterable, Optional

from .base import StatementBalance, TreasuryAdapter, register


@register("treasury", "csv_statements")
class CSVStatementTreasury(TreasuryAdapter):
    """READY. Reads pre-extracted statement balances from a CSV (structured feed / demo).
    Columns: source_account, balance, as_of[, statement_date, bank_name, document_ref]."""
    name = "treasury:csv_statements"

    def __init__(self, path: str):
        self.path = path

    def fetch_statements(self, period_end: date) -> Iterable[StatementBalance]:
        with open(Path(self.path), newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("as_of") and date.fromisoformat(row["as_of"]) != period_end:
                    continue
                sd = row.get("statement_date")
                yield StatementBalance(
                    source_account=row["source_account"].strip(),
                    balance=float(str(row["balance"]).replace(",", "").replace("$", "")),
                    as_of=period_end,
                    statement_date=date.fromisoformat(sd) if sd else None,
                    bank_name=row.get("bank_name") or None,
                    document_ref=row.get("document_ref") or None, raw=row)


@register("treasury", "watched_folder")
class WatchedFolderTreasury(TreasuryAdapter):
    """READY. Picks up statement files dropped in a folder / network share (INTAKE §B watched folder)."""
    name = "treasury:watched_folder"

    def __init__(self, folder: str, parse_fn: Callable[[bytes, str], Optional[StatementBalance]]):
        self.folder, self.parse_fn = folder, parse_fn

    def fetch_statements(self, period_end: date) -> Iterable[StatementBalance]:
        for p in sorted(Path(self.folder).glob("*")):
            if p.is_file():
                bal = self.parse_fn(p.read_bytes(), p.name)
                if bal:
                    yield bal


@register("treasury", "manual_upload")
class ManualUploadTreasury(TreasuryAdapter):
    """READY. Serves statements the user uploaded through the UI (already parsed into StatementBalance)."""
    name = "treasury:manual_upload"

    def __init__(self, uploaded: list[StatementBalance] | None = None):
        self.uploaded = uploaded or []

    def fetch_statements(self, period_end: date) -> Iterable[StatementBalance]:
        return [s for s in self.uploaded if s.as_of == period_end]


@register("treasury", "imap")
class IMAPTreasury(TreasuryAdapter):
    """STUB — pull statements from a monitored mailbox (INTAKE §B email/IMAP).
    Implement: connect IMAP (TLS), search UNSEEN with attachments from the bank sender,
    save attachment, parse_fn -> StatementBalance, mark seen. Creds from the secret store."""
    name = "treasury:imap"

    def __init__(self, host: str, mailbox: str, parse_fn, secret_ref: str):
        self.host, self.mailbox, self.parse_fn, self.secret_ref = host, mailbox, parse_fn, secret_ref

    def fetch_statements(self, period_end: date) -> Iterable[StatementBalance]:
        raise NotImplementedError("Implement IMAPTreasury.fetch_statements (imaplib + parse_fn).")


@register("treasury", "sftp")
class SFTPTreasury(TreasuryAdapter):
    """STUB — pull from a bank SFTP outbound dir (INTAKE §B SFTP). Implement with paramiko;
    download new files since last run, parse_fn, then archive/mark processed."""
    name = "treasury:sftp"

    def __init__(self, host: str, remote_path: str, parse_fn, secret_ref: str):
        self.host, self.remote_path, self.parse_fn, self.secret_ref = host, remote_path, parse_fn, secret_ref

    def fetch_statements(self, period_end: date) -> Iterable[StatementBalance]:
        raise NotImplementedError("Implement SFTPTreasury.fetch_statements (paramiko + parse_fn).")


@register("treasury", "bank_api")
class BankAPITreasury(TreasuryAdapter):
    """STUB — direct bank/aggregator API (INTAKE §B bank API, e.g. Plaid/BAI2 feed).
    Implement the balances call; map to StatementBalance. Token auth from the secret store."""
    name = "treasury:bank_api"

    def __init__(self, base_url: str, auth: dict):
        self.base_url, self.auth = base_url, auth

    def fetch_statements(self, period_end: date) -> Iterable[StatementBalance]:
        raise NotImplementedError("Implement BankAPITreasury.fetch_statements for your provider.")

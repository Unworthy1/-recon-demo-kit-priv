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

    def fetch_lines(self, period_end: date):
        """Transaction detail for the matching engine (#34): any dropped file that sniffs as a
        structured format (BAI2/camt.053/MT940/OFX) yields its lines; anything else (PDF, images)
        stays balance-only via parse_fn/OCR — same folder, both tiers."""
        from . import formats
        for p in sorted(Path(self.folder).glob("*")):
            if not p.is_file():
                continue
            try:
                for ps in formats.parse(p.read_bytes()):
                    yield from ps.lines
            except ValueError:
                continue                      # unrecognized format — balance-only file


@register("treasury", "manual_upload")
class ManualUploadTreasury(TreasuryAdapter):
    """READY. Serves statements the user uploaded through the UI (already parsed into StatementBalance)."""
    name = "treasury:manual_upload"

    def __init__(self, uploaded: list[StatementBalance] | None = None):
        self.uploaded = uploaded or []

    def fetch_statements(self, period_end: date) -> Iterable[StatementBalance]:
        return [s for s in self.uploaded if s.as_of == period_end]


def _structured_statements(blob: bytes):
    """Best-effort parse of one file through the format layer. Returns [] for files the
    sniffer doesn't recognize (PDFs etc. stay on the OCR/balance-only path)."""
    from . import formats
    try:
        return list(formats.parse(blob))
    except ValueError:
        return []


@register("treasury", "imap")
class IMAPTreasury(TreasuryAdapter):
    """READY — pulls statement attachments from a monitored mailbox (INTAKE §B email/IMAP).

    Polls `mailbox` for UNSEEN messages (optionally from a specific sender), extracts every
    attachment, and feeds structured files (BAI2/camt/MT940/OFX, sniffed) through the format
    layer; unrecognized attachments go to `fallback_fn` (e.g. the DMS/OCR path). Processed
    messages are marked \\Seen by the fetch and optionally copied to `processed_folder` —
    which is what makes re-runs idempotent. The password is read from `password_file`
    (a root-600 file from the INTAKE §H secret store) at connect time, never stored.

    `client_factory` exists for tests/alternate transports: it must return an
    imaplib.IMAP4-compatible object, already connected but not logged in.
    """
    name = "treasury:imap"

    def __init__(self, host: str, user: str, password_file: str, mailbox: str = "INBOX",
                 sender: str | None = None, processed_folder: str | None = None,
                 fallback_fn: Optional[Callable[[bytes, str], Optional[StatementBalance]]] = None,
                 client_factory=None, port: int = 993):
        self.host, self.port, self.user = host, port, user
        self.password_file, self.mailbox = password_file, mailbox
        self.sender, self.processed_folder = sender, processed_folder
        self.fallback_fn = fallback_fn
        self.client_factory = client_factory

    def _connect(self):
        import imaplib
        client = (self.client_factory() if self.client_factory
                  else imaplib.IMAP4_SSL(self.host, self.port))
        password = Path(self.password_file).read_text(encoding="utf-8").strip()
        client.login(self.user, password)
        client.select(self.mailbox)
        return client

    def _attachments(self, client):
        """Yield (message_id, filename, bytes) for every attachment on unseen messages."""
        import email
        criteria = f'(UNSEEN FROM "{self.sender}")' if self.sender else "(UNSEEN)"
        ok, data = client.search(None, criteria)
        if ok != "OK" or not data or not data[0]:
            return
        for num in data[0].split():
            ok, msg_data = client.fetch(num, "(RFC822)")
            if ok != "OK":
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            for part in msg.walk():
                fname = part.get_filename()
                if not fname:
                    continue
                payload = part.get_payload(decode=True)
                if payload:
                    yield num, fname, payload
            if self.processed_folder:
                client.copy(num, self.processed_folder)

    def fetch_statements(self, period_end: date) -> Iterable[StatementBalance]:
        client = self._connect()
        try:
            for _num, fname, blob in self._attachments(client):
                stmts = _structured_statements(blob)
                if stmts:
                    for ps in stmts:
                        if ps.closing is not None:
                            yield StatementBalance(source_account=ps.source_account,
                                                   balance=ps.closing, as_of=ps.as_of or period_end,
                                                   bank_name=ps.bank_name or None)
                elif self.fallback_fn:
                    bal = self.fallback_fn(blob, fname)
                    if bal:
                        yield bal
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def fetch_lines(self, period_end: date):
        client = self._connect()
        try:
            for _num, _fname, blob in self._attachments(client):
                for ps in _structured_statements(blob):
                    yield from ps.lines
        finally:
            try:
                client.logout()
            except Exception:
                pass


@register("treasury", "sftp")
class SFTPTreasury(TreasuryAdapter):
    """READY — pulls from a bank's outbound SFTP directory (INTAKE §B SFTP; the institutional
    BAI2/camt delivery path).

    Key auth only (`key_file` from the INTAKE §H secret store; no passwords). Host-key
    verification is ON: the server's key must be present in `known_hosts_file` — capture it
    once with ssh-keyscan FROM A SECOND VANTAGE and pin it. After a file parses, it is moved
    to `archive_dir` on the remote (rename), which is what makes re-runs idempotent; files
    that don't parse are left in place and reported via `skipped`.

    Requires `paramiko` (lazy import): uncomment it in stack/api/requirements.txt for
    deployments that tick SFTP in the INTAKE. `client_factory` returns a paramiko-SFTPClient-
    compatible object (listdir/open/rename) for tests.
    """
    name = "treasury:sftp"

    def __init__(self, host: str, user: str, key_file: str, remote_dir: str,
                 known_hosts_file: str | None = None, archive_dir: str | None = "processed",
                 client_factory=None, port: int = 22):
        self.host, self.port, self.user = host, port, user
        self.key_file, self.remote_dir = key_file, remote_dir
        self.known_hosts_file, self.archive_dir = known_hosts_file, archive_dir
        self.client_factory = client_factory
        self.skipped: list[str] = []

    def _connect(self):
        if self.client_factory:
            return self.client_factory()
        try:
            import paramiko
        except ImportError as e:
            raise RuntimeError("SFTPTreasury needs paramiko — uncomment it in "
                               "stack/api/requirements.txt and rebuild the api image") from e
        ssh = paramiko.SSHClient()
        if self.known_hosts_file:
            ssh.load_host_keys(self.known_hosts_file)
        else:
            ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(paramiko.RejectPolicy())   # pinned host keys only
        ssh.connect(self.host, port=self.port, username=self.user,
                    key_filename=self.key_file, look_for_keys=False, allow_agent=False)
        return ssh.open_sftp()

    def _files(self, sftp):
        """Yield (name, bytes) for each regular file in remote_dir; archive after the caller
        consumes a parsed file (see _pull)."""
        for name in sorted(sftp.listdir(self.remote_dir)):
            path = f"{self.remote_dir.rstrip('/')}/{name}"
            try:
                with sftp.open(path, "rb") as fh:
                    yield name, path, fh.read()
            except IOError:
                continue                                   # subdirectory or vanished file

    def _archive(self, sftp, name, path):
        if not self.archive_dir:
            return
        dest_dir = f"{self.remote_dir.rstrip('/')}/{self.archive_dir}"
        try:
            sftp.listdir(dest_dir)
        except IOError:
            sftp.mkdir(dest_dir)
        sftp.rename(path, f"{dest_dir}/{name}")

    def _pull(self):
        sftp = self._connect()
        self.skipped = []
        try:
            for name, path, blob in self._files(sftp):
                stmts = _structured_statements(blob)
                if stmts:
                    yield stmts
                    self._archive(sftp, name, path)
                else:
                    self.skipped.append(name)
        finally:
            try:
                sftp.close()
            except Exception:
                pass

    def fetch_statements(self, period_end: date) -> Iterable[StatementBalance]:
        for stmts in self._pull():
            for ps in stmts:
                if ps.closing is not None:
                    yield StatementBalance(source_account=ps.source_account, balance=ps.closing,
                                           as_of=ps.as_of or period_end, bank_name=ps.bank_name or None)

    def fetch_lines(self, period_end: date):
        for stmts in self._pull():
            for ps in stmts:
                yield from ps.lines


@register("treasury", "bank_api")
class BankAPITreasury(TreasuryAdapter):
    """STUB — direct bank/aggregator API (INTAKE §B bank API, e.g. Plaid/BAI2 feed).
    Implement the balances call; map to StatementBalance. Token auth from the secret store."""
    name = "treasury:bank_api"

    def __init__(self, base_url: str, auth: dict):
        self.base_url, self.auth = base_url, auth

    def fetch_statements(self, period_end: date) -> Iterable[StatementBalance]:
        raise NotImplementedError("Implement BankAPITreasury.fetch_statements for your provider.")

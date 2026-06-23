# Adapters — where OpenRecon plugs into your systems

The reconciliation engine only ever talks to three interfaces (see [`base.py`](base.py)). Everything
else — the UI, the board, the dashboard — is unchanged regardless of which bank, GL, or DMS you run.
That's what makes this deployable into an arbitrary business: a coding agent reads your
[`../INTAKE.md`](../INTAKE.md), picks the matching adapter per connection point, and implements the
one stub that fits (if it isn't already built).

```
INTAKE §B  ──▶  TreasuryAdapter.fetch_statements()   (bank statement balances in)
INTAKE §C  ──▶  GLAdapter.fetch_balances()           (GL balances in — READ-ONLY)
INTAKE §D  ──▶  DMSAdapter.ingest() / url_for()       (documents stored + linked)
```

## Support matrix

| Connection | INTAKE option | Adapter key | Status |
|---|---|---|---|
| **Treasury** | Manual upload | `manual_upload` | ✅ ready |
| | Watched folder / share | `watched_folder` | ✅ ready |
| | Email mailbox (IMAP) | `imap` | 🧩 stub |
| | SFTP pull | `sftp` | 🧩 stub |
| | Bank API / aggregator | `bank_api` | 🧩 stub |
| **General ledger** | Scheduled export (CSV/TB) | `csv_export` | ✅ ready |
| | Dynamics GP (ODBC) | `dynamics_gp` | 🧩 stub |
| | NetSuite (SuiteQL/REST) | `netsuite` | 🧩 stub |
| | Generic ODBC (SAP/Sage/Oracle/QB) | `odbc` | 🧩 stub |
| **DMS** | Paperless-ngx (bundled) | `paperless` | ✅ ready* |
| | Filesystem / share | `filesystem` | ✅ ready |
| | Laserfiche | `laserfiche` | 🧩 stub |
| | SharePoint / OneDrive (Graph) | `sharepoint` | 🧩 stub |

✅ ready = usable as-is · 🧩 stub = interface + approach defined, agent implements the marked block ·
\*Paperless `ingest` has the documented post+poll flow to wire.

## Implementing a stub (the agent's job, per the INTAKE)

1. Open the module for the connection point (`gl.py` / `treasury.py` / `dms.py`).
2. Find the class for the system named in the INTAKE (e.g. `DynamicsGPGL`).
3. Implement the one method marked `raise NotImplementedError(...)`, following the comment.
4. Keep GL adapters **read-only** — they must never write to the ledger.
5. Pull credentials from the secret store named in INTAKE §H — **never** hardcode secrets here.
6. Register is automatic via the `@register(kind, key)` decorator; the engine resolves the key
   from the deployment config (`stack/config.example.yaml`).

## Contract guarantees

- Adapters return the small value objects in `base.py` (`StatementBalance`, `GLBalance`,
  `StoredDocument`) — the engine never sees vendor specifics.
- Matching, tolerance, FX, roles, and the UI live above this layer (`stack/engine.py`), so swapping
  a bank or GL is a one-adapter change, not a rewrite.

"""OpenRecon Historical-ETL MCP (standalone server).

The agent-facing cockpit for backfilling prior-year reconciliations into a deployment. Historical
migration is messy, one-time, and judgment-heavy — exactly what an agent should drive interactively
rather than a fire-and-forget script. This MCP is a thin control surface over the stack's ETL API
(/api/import/*): the engine, validation, idempotency, provenance, and audit all live in the stack.

Playbook (see the migrate_history prompt): inspect_source -> propose_mapping -> dry_run_import ->
review the plan with the operator -> commit_import (reviewer/director identity) -> verify, per year.

Run by PATH (not `python -m`, which clashes with the `mcp` SDK package name):
    pip install -r mcp/requirements.txt
    RECON_API=http://localhost:8002 python mcp/recon-etl-server.py
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from mcp.server.fastmcp import FastMCP

API = os.environ.get("RECON_API", "http://localhost:8002").rstrip("/")

mcp = FastMCP("recon-etl", instructions=(
    "Backfill prior-year reconciliations into a OpenRecon deployment. Read recon://import/format "
    "first. Always dry_run_import and review the plan with the operator BEFORE commit_import. Loads "
    "are idempotent (safe to re-run), tagged origin='historical_import' (migrated evidence, NOT live "
    "approvals), audited, and reversible via rollback_batch. Commit/rollback require a reviewer/director."
))

CANONICAL_FORMAT = """OpenRecon historical import — canonical CSV (one row per account × period)

columns:
  period_end        ISO date of the close (e.g. 2024-12-31)        [required]
  account_code      GL account key                                  [required]
  gl_balance        general-ledger balance                          [required]
  account_name      account name (defaults to the code)
  group             account group (Cash & equivalents, AR, ...)
  assigned_to       preparer of record
  statement_balance bank/sub-ledger balance (blank = none)
  status            reconciled | variance | unreconciled            (default reconciled)
  work_status       approved | reviewed | resolved                  (default approved)
  resolved_by       preparer who signed
  approved_by       approver who signed
  note              free text

Rules: required fields must be present and well-typed; rows that fail validation are rejected and
reported (the rest still load). Upsert key = (account_code, period_end), so re-running updates in
place. Missing accounts and closed periods are created and tagged to the batch."""


def _http(path: str, method: str = "GET", timeout: int = 60) -> dict | str:
    try:
        req = urllib.request.Request(f"{API}{path}", method=method)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:               # surface the API's error body (403/404/...)
        return {"error": e.code, "detail": e.read().decode()[:300]}
    except Exception as e:  # noqa: BLE001
        return {"error": "unreachable", "detail": str(e)}


def _q(**kw) -> str:
    return urllib.parse.urlencode({k: v for k, v in kw.items() if v not in (None, "")})


# ─────────────────────────────── resources ───────────────────────────────
@mcp.resource("recon://import/format")
def import_format() -> str:
    """The canonical historical-import CSV schema the agent maps a legacy source onto."""
    return CANONICAL_FORMAT


@mcp.resource("recon://import/batches")
def import_batches_res() -> str:
    """Every import batch loaded into this deployment (id, source, counts, status)."""
    return json.dumps(_http("/api/import/batches"), indent=2, default=str)


# ───────────────────────────────── tools ─────────────────────────────────
@mcp.tool()
def inspect_source(source: str) -> str:
    """Validate a prior-year source file and summarise it (valid/rejected rows, new accounts, periods)
    — a non-committing dry run. `source` is a filename under the stack's IMPORT_DIR."""
    return json.dumps(_http(f"/api/import/dry-run?{_q(source=source)}", "POST"), indent=2, default=str)


@mcp.tool()
def propose_mapping() -> str:
    """Return the canonical import schema so you can map a legacy export's columns onto it."""
    return CANONICAL_FORMAT


@mcp.tool()
def dry_run_import(source: str) -> str:
    """Plan a load: what would insert/update and what would be rejected, with no writes. Review with
    the operator before committing."""
    return json.dumps(_http(f"/api/import/dry-run?{_q(source=source)}", "POST"), indent=2, default=str)


@mcp.tool()
def commit_import(source: str, user: str = "Robert K.", note: str = "") -> str:
    """Load a prior-year source into the recon scope (idempotent, provenance-tagged, audited).
    `user` must be a reviewer/director (principal/director), or the API returns 403."""
    return json.dumps(_http(f"/api/import/commit?{_q(source=source, user=user, note=note)}", "POST"),
                      indent=2, default=str)


@mcp.tool()
def list_batches() -> str:
    """List all historical-import batches and their status (committed | rolled_back)."""
    return json.dumps(_http("/api/import/batches"), indent=2, default=str)


@mcp.tool()
def rollback_batch(batch_id: str, user: str = "Robert K.") -> str:
    """Reverse a batch — removes every record it loaded (reviewer/director only). Audited."""
    return json.dumps(_http(f"/api/import/{batch_id}/rollback?{_q(user=user)}", "POST"), indent=2, default=str)


@mcp.prompt()
def migrate_history(years: str = "the last 2–3 fiscal years") -> str:
    """Playbook for migrating prior-year reconciliations into a OpenRecon deployment."""
    return (
        f"Migrate {years} of reconciliation history into this OpenRecon deployment.\n\n"
        "1. Read recon://import/format. For each legacy source (a prior tool's export, the GL's "
        "historical trial balance, or spreadsheets), map its columns onto the canonical schema and "
        "write one CSV per source into the stack's IMPORT_DIR.\n"
        "2. inspect_source / dry_run_import on each file. Show the operator the plan (valid vs "
        "rejected rows, new accounts, periods). Fix mapping/rejects and re-run until clean.\n"
        "3. commit_import as a reviewer/director, one source at a time. Loads are idempotent, so a "
        "re-run after a fix is safe.\n"
        "4. Confirm with list_batches and the stack's /api/audit. Remember: imported records are "
        "migrated EVIDENCE (origin='historical_import'), not live approvals — never present them as "
        "if they passed in-system maker-checker. Use rollback_batch if a load was wrong."
    )


if __name__ == "__main__":
    mcp.run()

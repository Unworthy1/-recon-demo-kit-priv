# MCP servers — for installing & configuring OpenRecon

Deploying OpenRecon into a business is an agent-driven job (read the intake → wire the GL/treasury/DMS
→ stand up the stack → verify). These MCP servers give a coding agent the tools and context to do that
safely, and the list below is the set worth connecting for a smooth install.

## In this repo

### `recon_deploy` — the OpenRecon Deployment MCP
Drives the install/config lifecycle from a filled [`../INTAKE.md`](../INTAKE.md).

**Resources:** `recon://intake-template`, `recon://intake-example`, `recon://deployment-guide`,
`recon://adapters`, `recon://architecture`.
**Tools:** `intake_status`, `list_adapters`, `scaffold_config`, `stack(up|down|status|logs|build)`,
`reconcile`, `verify_deploy`.
**Prompt:** `deploy_recon` — the end-to-end workflow.

Run it from the deploy host:
```bash
pip install -r mcp/requirements.txt
RECON_REPO=$(pwd) python mcp/recon-deploy-server.py     # stdio
```
> Run it **by path** (not `python -m mcp.…`) — the repo folder is named `mcp/`, which would shadow
> the `mcp` SDK package if imported as a module.

Connect from a Claude Code instance:
```json
{ "mcpServers": { "recon-deploy": {
    "command": "python", "args": ["/opt/openrecon/mcp/recon-deploy-server.py"],
    "env": { "RECON_REPO": "/opt/openrecon", "RECON_API": "http://localhost:8002" } } } }
```

### `recon_etl` — the Historical-ETL MCP
The agent-facing cockpit for backfilling prior-year reconciliations (a thin control surface over the
stack's `/api/import/*`). Historical migration is messy and one-time — exactly what an agent should drive.

**Resources:** `recon://import/format` (canonical CSV schema), `recon://import/batches`.
**Tools:** `inspect_source`, `propose_mapping`, `dry_run_import`, `commit_import`, `list_batches`, `rollback_batch`.
**Prompt:** `migrate_history` — the inspect → map → dry-run → commit → verify playbook, per year.

```bash
RECON_API=http://localhost:8002 python mcp/recon-etl-server.py     # stdio, run by path
```
Loads are idempotent, provenance-tagged (`origin='historical_import'`), audited, and reversible; commit/
rollback require a reviewer/director identity.

## Companion MCPs to connect (per the intake)

The deploy MCP orchestrates; these give the agent hands on the actual systems. Connect the ones that
match the filled intake. (Names are the common community/official servers; pin and vet before use.)

| Need | INTAKE | MCP to connect | Used for |
|---|---|---|---|
| The recon database | always | **Postgres MCP** (`@modelcontextprotocol/server-postgres` or `postgres-mcp`) | inspect schema, load the real account list, sanity-check the board |
| Container lifecycle | §G | **Docker MCP** (`docker-mcp`) | build/run/inspect the stack beyond the bundled compose tools |
| Files / config on the host | §G/§H | **Filesystem MCP** (`@modelcontextprotocol/server-filesystem`) | place config, secrets templates, watched-folder wiring |
| **General ledger** | §C | a **SQL/ODBC MCP** (e.g. **MSSQL MCP** for Dynamics GP, or a generic ODBC MCP) | validate the read-only GL query before building the `dynamics_gp`/`odbc` adapter |
| **DMS** | §D | an **HTTP/REST MCP** (or a system-specific one) | exercise the Laserfiche / SharePoint API before building that adapter |
| Secrets | §H | your secret-manager's MCP (e.g. **Vault MCP**) or the platform's | resolve `${ENV_REFS}` at deploy time without ever printing values |
| Notifications | §I | **Teams/Slack MCP** | wire + test the close-status channel |
| Source control | — | **Git/GitHub MCP** | branch the per-customer config, PR the implemented adapters |

### How they fit together
```
 coding agent
   ├─ recon-deploy MCP   → intake → scaffold_config → stack up → reconcile → verify
   ├─ Postgres MCP       → load real accounts, inspect the board
   ├─ SQL/ODBC MCP (GL)  → prove the read-only GL query → implement adapters/gl.py
   ├─ HTTP/DMS MCP       → prove the DMS API → implement adapters/dms.py
   ├─ Filesystem/Docker  → place config, manage containers
   └─ Secrets MCP        → inject ${ENV_REFS}, never in the repo
```

### Guardrails (same as the adapters)
- GL access is **read-only** — the GL MCP and the GL adapter must never write to the ledger.
- Secrets come from §H's manager via a secrets MCP / env injection — never committed, never printed.
- Validate each connection with its MCP **before** implementing the matching adapter — prove the query/API
  works, then codify it.

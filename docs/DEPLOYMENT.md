# Deployment — for the coding agent

You're deploying OpenRecon into a business. Your inputs are a filled [`../INTAKE.md`](../INTAKE.md)
and this repo. Your job: stand up the stack and wire it to the business's treasury, GL, and DMS.

## 0. Read the intake
Parse `INTAKE.md`. For each of the three connection points, note the chosen option and its details:
- **§B treasury** → one or more sources (one adapter each)
- **§C GL** → one GL adapter
- **§D DMS** → one DMS adapter (or the bundled one)
Also note §E rules (tolerances, account map), §F roles, §G environment, §H secrets. Treat any `TBD`
as a blocker to raise, not a value to invent.

## 1. Pick the adapters
Map each intake choice to an adapter key using [`../adapters/README.md`](../adapters/README.md). If the
key is ✅ ready, configure it. If it's 🧩 a stub, implement the one marked method in
`../adapters/{gl,treasury,dms}.py` following the comment — read-only for GL, secrets from §H's store.

## 2. Configure
Copy `stack/config.example.yaml` → `stack/config.yaml` and fill the `adapter` + `args` for each point
from the intake. Put the §E account map into the GL accounts (the `gl_account.source_account` column ties
a statement source to a GL account). Secrets are referenced (e.g. `${PAPERLESS_TOKEN}`), never inlined.

## 3. Stand up the stack (TEST tier)
```bash
cd stack
DB_PASSWORD=<from-secret-store> docker compose up -d --build   # db + api + web
```
- `db` applies `db/01-schema.sql` + `db/02-seed.sql` (replace the seed with the real account list from the GL).
- `api` serves the data contract on `:8002`; `web` serves the UI on `:8080`.
- Verify: `curl localhost:8002/api/health`, `…/api/kpis`, `…/api/accounts`.

## 4. Load the real accounts, then reconcile
- Replace `db/02-seed.sql` with the in-scope accounts (or load them from the GL once via the adapter).
- `curl -X POST localhost:8002/api/reconcile` → pulls GL + statement balances through the adapters,
  matches within tolerance, writes the board. Confirm the KPIs/board look right.

## 5. Wire the UI to the API
The UI (`web/`) ships with embedded demo data so it renders standalone. To run it live, point it at the
API: in `web/assets/app.js`, replace the static `RECON` object with a fetch of `/api/accounts` +
`/api/kpis` (and `/api/account/{id}` on the detail page). Keep the embedded data as the offline fallback.
Front it with the reverse proxy from §G (TLS, SSO).

## 6. Schedule + notify
- Run `POST /api/reconcile` on the close cadence (cron / the orchestrator in §J, or the bundled n8n —
  see the optional services note below).
- Wire the §I notification channel on new exceptions / sign-offs.

## 7. Harden for PROD
Follow [`PROMOTION.md`](PROMOTION.md): real secrets store, SSO + the §F role model and segregation of
duties, immutable audit trail, monitoring, separate TEST/PROD. Never let real financials touch a public
or demo tier.

---

### Optional bundled services
For a self-contained TEST environment you can add **Paperless-ngx** (DMS) and **n8n** (orchestration)
to `stack/compose.yaml` as extra services (use the `paperless` / `n8n` adapter + a scheduled
`POST /api/reconcile`). In a real deployment these are usually the business's existing systems (Laserfiche,
their scheduler) wired via the adapters instead.

### Guardrails
- GL adapters are **read-only** — never write to the ledger.
- Secrets come from §H's store; nothing secret is committed.
- The engine is the only place matching/tolerance logic lives — don't scatter it into the UI or adapters.

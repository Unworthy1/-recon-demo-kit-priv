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

---

## Adding a feature — downstream deployment impact

Standing up the stack is the easy part; the holes appear when a feature lands and a deployment step is
missed. Use this as a **release checklist keyed by what kind of change you made**. (Maintainers: keep it
honest — see "Spot-check every release" below.)

**A. New table / schema change** (`stack/db/NN-*.sql`)
- initdb applies `db/*.sql` **alphabetically** — number a new file after the last (`08`, `09`, `10`, …) and
  mind FK order (a table must exist before another references it).
- **A running database does not pick up a schema change.** In TEST you recreate the volume:
  `docker compose down -v && docker compose up -d --build db api`. In **PROD you do NOT wipe the volume** —
  `db/*.sql` is *initdb-only* (runs on an empty data dir). A production schema change needs a **forward
  migration** (a versioned `ALTER`/`CREATE` applied by `psql`/a migration runner) in a maintenance window,
  reversible, taken against a backup.
- If the new table is evidence (sign-offs, comments, documents), add it to the **audit-package export** so
  it isn't silently omitted.

**B. New / changed API endpoint** (`stack/api/`)
- Rebuild the api image (`--build`) — the running container holds a baked copy; editing the file on disk
  does nothing until rebuild.
- A new Python package under `api/` needs a `COPY` line in `stack/api/Dockerfile` (a missed COPY = an
  `ImportError` only at container start).
- A **state-mutating** endpoint must: resolve the *authenticated* actor (session overrides any client
  `user=`), enforce the §F capability **and** segregation of duties, **append to the audit trail**, and
  **404/409 on a no-op or illegal transition** (never write a phantom audit row).

**C. New / changed web asset** (`web/`)
- **Bump the `?v=` cache-bust on every asset URL** referencing the changed file. HTML is dynamic; `.js`/`.css`
  sit behind a CDN cache (hours). A "stale UI / old branding" report is almost always a CDN cache HIT, not
  stale source — bump the version, don't chase ghosts.
- Redeploy to **every** static surface you run (each public + internal docroot). **Extract over** the docroot
  (`tar -x` into it); never `rm -rf` a bind-mounted docroot (it detaches the mount).
- A new page must be added to the sidebar nav (`renderSidebar()` in `app.js`) or it's unreachable.

**D. A new configuration choice** (an adapter, a tolerance/threshold, a team, on-prem vs cloud)
- Capture it **up front** as a question in [`../INTAKE.md`](../INTAKE.md) so a deployer supplies it *before*
  the build, not as a surprise after. Every feature that hinges on a customer decision earns an INTAKE line.

**E. New secret / external dependency**
- Route it through §H's secret store (referenced, never inlined/committed), document it in `SECURITY.md`,
  and add any new outbound host the deployment must reach.

**F. Multiple editions / open-core**
- A feature merged to one repo is *missing from the fork*. Port it (with the fork's branding) and **verify
  both repos carry the same feature set** as part of the same release — don't let the editions drift.

**Verify before you call it shipped:** syntax-gate (`py_compile` / `node --check`), a **fresh** end-to-end
rebuild (not an incremental one over stale state — confirm staged files actually landed on the host first),
and an actual **browser/DOM check** of the new surface.

## Transaction matching & statement ingest (#34, core)

`POST /api/matching/ingest` reads bank statement files (BAI2 / camt.053 / MT940 / OFX, format-sniffed)
from the same **`IMPORT_DIR`** volume the historical ETL uses — mount the statement drop path there.
Statement accounts resolve through the INTAKE §E `source_account` map; unmapped accounts are reported in
the response, not silently dropped. Every ingest is a provenance batch (`stm-*`) with
`/api/matching/{batch}/rollback`. No new secrets or external dependencies.

**Ingest data controls (#41).** Every file is checked against the integrity evidence it carries (BAI2
trailers, camt.053 transaction summary, balance continuity, duplicate SHA-256; CSV row errors and optional
`expected_rows` / `control_total`). A failed blocking control **quarantines** the batch — lines are stored
but excluded from matching and open items until a principal/director other than the uploader releases it
with a reason (`POST /api/matching/{batch}/release`). A byte-identical re-drop is **rejected** with no lines.
Operational notes:
- Watched-folder and SFTP transports that re-deliver the same file are now safe: the second copy is a
  recorded `rejected` batch, not a double load. To deliberately reload a file, roll its batch back first.
- Monitor the queue with `GET /api/import/batches?status=quarantined` — a quarantined file blocks nothing
  else, so it can sit unnoticed.
- If a bank's files quarantine routinely on `bai2.*_trailer`, capture a sample and check its trailer
  convention before releasing in bulk; the control accepts both common sign conventions.
- Schema: `18-ingest-controls.sql` runs on first init. Existing databases apply it once with
  `psql -f stack/db/18-ingest-controls.sql` (additive; existing batches keep `committed`).

**Prep rules (#42).** Named rule sets transform parsed lines before load — alias bank account ids, pull
check/lockbox numbers out of memo text into `bank_ref`, compose references, net out fees, drop memo lines.
Apply one per ingest with `?prep=<name>`, or set a CSV mapping profile's `prep` default. Operational notes:
- Build rules against real files with `POST /api/prep/preview` first — it writes nothing and shows each
  row before/after plus what would be dropped or fail.
- Saving a rule set needs approve capability (senior+) and is audited with the before/after rules.
  Editing a rule set never rewrites history: loaded lines keep the trace of the version that ran.
- Filtered rows are kept in `prep_dropped_row`; a row a rule cannot process quarantines the batch (#41).
- A rule set does not change the duplicate guard — re-ingesting the same file with different rules
  needs a rollback of the earlier batch first.
- Watched-folder / SFTP transports feeding `fetch_lines()` do not run rule sets yet; use the ingest API.
- Schema: `19-prep-rules.sql` (additive) — apply once to existing databases after 18.

### Spot-check this guide every release
This document is only worth anything if it stays true to the code. **At every feature close / wrap-up,
spot-check this guide** against what you just shipped — did the feature introduce a new surface, a migration
ordering constraint, a new secret, a new external dependency, a new cache key, a new edition to keep in
sync? If yes and it isn't reflected above, add it. A deployment guide that silently lags the code is worse
than none: it reports the holes are covered when they aren't.

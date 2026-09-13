# Changelog

## Unreleased — proposed journal entries (#43)
Ported from this arc's build (free tier; identical core diff, verified end-to-end on an OpenRecon stack):
- **Proposed journal entries (#43, core)**: reconciling items become **draft entries — never posted automatically**. `stack/api/journal.py` proposes from three sources: **unbooked statement lines** (bank fee → Dr 6510 / Cr cash; interest → Dr cash / Cr 4910; unknown → suspense, flagged), **aged GR/IR residues** (receipt with no invoice / invoice with no receipt reverse against the PO's own GL account; over-invoicing goes to purchase price variance; `min_age_days` threshold), and the **unexplained residual** of a reconciliation (to suspense, "investigate and reclassify"). Every proposal carries a deterministic rationale naming the rule that chose the offset; offsets are configuration (`je_offset_rule`). Manual entries too.
- **Workflow + maker-checker**: draft → submitted → approved → exported (return to draft with reason; void with reason). Approver needs approve capability and is **never the creator or submitter** (409); entries can't be created, submitted or approved in a **locked period**; proposing twice never duplicates (one live entry per reconciling item); voiding frees the item. Every step audited.
- **Invariants enforced by the database** (`stack/db/20-journal-entries.sql`), not just the API: balanced (Σ debits = Σ credits) with ≥2 lines checked at commit by a deferred constraint trigger; each line exactly one of debit/credit, non-negative, 2dp; lines frozen outside draft; only legal status transitions; header immutable after draft; entries never deleted; unique live entry per source item.
- **Export**: outbound profiles (`je_export_profile` — columns from a fixed field list or constants, date format, delimiter, header, `debit_positive`/`credit_positive` signed amount, CRLF/LF) render approved entries to a **generic CSV** (`generic-csv` seeded). Each export is stored with its SHA-256; re-download is byte-identical (`X-Content-SHA256`) and audited. Text cells are neutralised against spreadsheet formula injection.
- **API**: `POST /api/account/{id}/journal/propose`, `POST /api/journal/propose-grir`, `GET/POST /api/journal/entries`, `GET /api/journal/entries/{id}`, `PUT .../lines` (drafts), `POST .../submit|approve|return|void`, `GET/POST /api/journal/export-profiles`, `POST /api/journal/export`, `GET /api/journal/exports[/{id}/file]`. Open items now show the live entry on statement items.
- **UI**: an open item with a proposed entry shows a "📒 JE-… · status" chip and an entry card (lines, rationale) with approve/return gated by capability and segregation of duties.
- Tests: 62-check `stack/api/journal_tests/test_journal.py` (signs on asset and liability accounts, offset selection, GR/IR routing + aging, residual direction, status machine cross-checked against the SQL trigger, CSV rendering and injection). Verified end-to-end on a fresh stack — full propose → edit → submit → approve/return/void → export cycle, SoD 409s, locked period 409, and direct-SQL attacks on every database invariant all refused; audit chain intact. Found and fixed during e2e: PL/pgSQL trigger functions touched `OLD`/`NEW` fields inside `CASE` (resolved on every branch).

## Unreleased — prep rules (#42)
Ported from this arc's build (free tier; identical core diff, verified end-to-end on an OpenRecon stack):
- **Prep rules (#42, core)**: the transformation layer between parsing and load. `adapters/formats/prep.py` (pure, offline-tested) runs an ordered, declarative rule list — **lookup** (bank alias → source account, vendor alias → canonical), **extract** (regex capture: check / lockbox / invoice number out of a memo), **concat** (templated composite references), **calc** (decimal-safe arithmetic, e.g. net of fee), **fill** (defaults) and **filter** (drop rows by condition) — each with an optional `when` condition (`all`/`any`/`not`, eq/gt/contains/matches/in/…). Rules are data: named **rule sets** (`stack/db/19-prep-rules.sql`) applied to **bank files and CSV alike** via `?prep=<name>`, or by default from a CSV mapping profile's `prep`.
- **Explainable and lossless**: every batch records the rule-set name, fingerprint and a snapshot of the rules it ran; every changed line carries a `prep_trace` (rule, op, label, field, before → after); filtered rows are stored in `prep_dropped_row`, never lost. `GET /api/statement-line/{id}/explain` answers "why does this line look like this" from the version that actually ran, even after the rule set is edited.
- **Safe by construction**: no `eval` — calc walks a whitelisted AST; templates substitute `{field}` by regex (no format-string attribute access); regex patterns are length-capped, compiled at save, and searched against at most 1,000 characters.
- **Ordering with #41**: ingest controls judge the file as sent; prep runs after them. A row a rule cannot process (e.g. `lookup` with `on_missing: error`) is not loaded and quarantines the batch (`prep.row_errors`).
- **API**: `GET/POST /api/prep-rulesets` (save needs approve capability — rules decide what reaches matching; audited with before/after rules), `POST /api/prep/preview` (dry run against a file — before/after, drops, errors — with a saved rule set or unsaved inline rules; writes nothing). Mapping profiles gained an optional `prep` default (validated to exist).
- **UI**: a prepped statement line shows a small "⚙ N rules" chip on the matching panel that expands to the rule trace; untouched lines look exactly as before.
- Tests: 61-check `adapters/format_tests/test_prep.py`; controls 46, formats 39, transports 12, csvmap 17, matching 21 unchanged and passing. Verified end-to-end on a fresh stack: save gates (junior 403, invalid 400), preview writes nothing, a lockbox CSV with no references went from **0 to 2 exact matches** after alias + filter + extract + concat + net-of-fee rules, the dropped memo line is kept, explain survives a rule-set edit, a profile's default rule set quarantines an unprocessable row, rule sets apply to BAI2, audit chain intact.

## Unreleased — ingest data controls (#41)
Ported from this arc's build (free tier; identical core diff, verified end-to-end on an OpenRecon stack):
- **Ingest data controls (#41, core)**: a statement file must prove it is complete and unaltered before its lines feed matching. `adapters/formats/controls.py` (pure, offline-tested) evaluates the evidence banks already ship: **BAI2 49/98/99 trailers** (control totals + record counts, integer math, 88 continuations counted; both debit-sign interpretations accepted, the one that tied is recorded), **camt.053 `TxsSummry/TtlNtries`** (entry count + sum), **balance continuity** (opening + lines = closing, a *warning* — never blocks), **file non-empty**, **byte-identical duplicate** (SHA-256), and for CSV **row parse errors**, a header-only-file *warning*, and optional operator-declared `expected_rows` / `control_total`. Unverifiable checks record `not_available`, never a pass.
- **Outcomes**: `committed` · `quarantined` (a blocking control failed — lines are loaded as evidence but excluded from `run_matching` and the `open_item` view) · `rejected` (duplicate or unparseable — no lines, the attempt is recorded). `stack/db/18-ingest-controls.sql`: `import_batch.content_sha256` with a **partial unique index** (one live batch per file, enforced by the DB), status CHECK, release columns, `ingest_control_result`.
- **Release (maker-checker)**: `POST /api/matching/{batch}/release?reason=` — principal/director only (403), never the uploader (409), reason mandatory (400), audited `ingest.released` with the overridden failures. Also `GET /api/matching/{batch}/controls`, `GET /api/import/batches?status=quarantined`; ingest audits `ingest.quarantined` / `ingest.rejected`. Ingest responses now always carry `status`, `controls`, `blocking_failures`, `warnings`.
- **UI**: a quarantine notice on the account's matching panel (why it was held, gated release with reason) — invisible when every control passes.
- **Fixes found on the way**: the BAI2 parser mis-walked **S / V / D funds-type** extensions on 03 and 16 records (could misread opening/closing balances and bank refs); the demo sample and test fixtures carried **non-spec trailer totals** (49 = closing balance) and are corrected. A parser exception on ingest is now a recorded `rejected` batch instead of a 500.
- Tests: 46-check `adapters/format_tests/test_controls.py`; existing 39 format / 12 transport / 17 csvmap / 21 matching checks unchanged and passing. Verified end-to-end on a fresh stack: good file committed → same file rejected (0 lines) → tampered file quarantined and absent from matching + open items → release by uploader 409 / senior 403 / no reason 400 → reviewer release commits → truncated BAI2 quarantined, broken camt rejected, CSV bad row quarantined → audit chain intact.

## 1.12.0 — 2026-08-08 — transaction matching · statement formats · CSV profiles · GR/IR
Ported from this arc's build (free tier, all offline-tested here: 39/39 formats, 17/17 csvmap, 21/21 matching):
- **Transaction-level matching engine (#34)**: `stack/db/13-matching.sql` + `stack/api/matching.py` — exact → rule → suggestion passes per account (greedy 1:1, deterministic), aged open items (outstanding checks / deposits in transit), variance tie-out `variance == gl_open − stmt_open`, maker-checker decisions, all audited. Endpoints: `/api/matching/ingest[?profile=]`, `/{batch}/rollback`, `/api/account/{id}/match/run|matches|open-items`, `/api/match/{id}/decide`.
- **Bank statement format parsers (#37)**: `adapters/formats/` — BAI2, camt.053/052, MT940, OFX/QFX, transaction-level with sniffing; statements self-check opening + lines == closing.
- **CSV mapping profiles (#37)**: `adapters/formats/csvmap.py` + `mapping_profile` table + `GET/POST /api/mapping-profiles` — odd exports become saved config, per-row errors reported.
- **New adapter kinds (#37)**: `BudgetAdapter` (INTAKE §Q) + `SubledgerAdapter` (billing/AR, AP — §R), CSV references ready + ODBC/Adaptive/billing-API stubs; `StatementLine` + optional `fetch_lines()` contracts; `WatchedFolderTreasury` feeds structured files to the engine.
- **GR/IR clearing-account reconciliation (#35)**: `recon_type` on `gl_account`, `grir_open_item` view (grni / over_invoiced / invoiced_not_received, aged), `GET /api/grir` with a to-the-penny tie-out over the procurement chain.
- **Account-page matching panel**: tie-out badge (fully-explained / unexplained residual), aged open items, suggestion confirm/reject; balance-only accounts unchanged.


## 1.8.2 — 2026-06-21
**Reconciliation engine — scale hardening** (verified at 3,000 accounts: 0.13s, ~22k accts/sec, idempotent).
- **Batched writes**: chunked `executemany` instead of one `INSERT` per account (was N+1 round-trips). Matching was already O(1)/account (GL + statements dict-indexed — no nested scan).
- **Bounded summary**: `run()` now returns aggregate counts + operational signals (`no_statement`, `no_gl`, `duplicate_statements`) + a capped exception sample, instead of a row-per-account list (so the response stays small at any scale). _(Changes the `/api/reconcile` response shape from a list to a summary dict.)_
- Landing scale stats corrected to real org size: **2,800+ accounts / 700+ reconciliations per close** (were one accountant's 600/150).

## 1.8.1 — 2026-06-21
**Mobile / responsive UI** — the showcase now adapts to phones (one responsive stylesheet, **not** a separate mobile site, so it's one URL that reflows).
- The 10 app-shell pages get a **slide-in hamburger drawer** (a dark mobile top bar with the brand; the sidebar slides in over a backdrop, injected by `renderSidebar()`).
- Landing / how-it-works / director-dashboard reflow: wrapped top nav, scaled hero, stat band 4→2, feature cards + pipeline steps + the director 2-col grid stack to one column.
- KPI grids collapse 4→2→1; wide account tables **scroll horizontally inside their panel** instead of crushing; headers/toolbars wrap.
- Breakpoints at 860px (tablet/phone) and 440px (small phone). Asset cache-bust `?v=1.8.1`.

## 1.8.0 — 2026-06-21
**SOX/ICFR foundation — immutable audit trail + real auth — and a historical ETL driver.**
- **Audit trail**: an append-only, **hash-chained**, server-timestamped `audit_event` table with UPDATE/DELETE blocked by a DB trigger (append-only at the database, not just the app). Every prepare/approve/send-back/lock/settle/carry-forward/login/import writes an event bound to the authenticated identity. `GET /api/audit` (filterable) and `GET /api/audit/verify` (re-walks the chain, proves no tampering).
- **Authentication & access**: local password auth (bcrypt via pgcrypto) with opaque expiring sessions and an OIDC/SAML seam (`auth.py`, `auth_session`); `/api/auth/login|logout|whoami`. The session identity **overrides** any client-supplied `user`, so the trail records the real actor. Periodic **access recertification** (`access_review`, `/api/access-review`) — a revoke disables the user and kills live sessions.
- **Integrity hardening**: `resolve`/`approve`/`settle`/`lock` now **404 on a no-op** so the trail never records a phantom action on a non-existent record.
- **Historical ETL** (`stack/api/etl.py`, `db/07-etl.sql`): backfill prior-year reconciliations into the recon scope — **idempotent** (upsert by account+period), **dry-run → commit**, **provenance-tagged** (`origin='historical_import'`, never confused with live approvals), loaded into closed/locked periods, **reversible by batch**, reviewer/director-gated, fully audited. `/api/import/{dry-run,commit,batches,{id}/rollback}` + a sample `stack/samples/history_2025.csv`.
- **ETL MCP** (`mcp/recon-etl-server.py`): the agent-facing migration cockpit — `inspect_source` · `propose_mapping` · `dry_run_import` · `commit_import` · `list_batches` · `rollback_batch` + a `migrate_history` prompt.
- **Docs**: `docs/CONTROLS.md` (COSO/SOX-404 control → feature mapping + how the tamper-evident chain works); INTAKE **§L** (audit/access/SOX) and **§M** (prior-year migration).
- _Backend/stack only — the static showcase UI is unchanged._ Verified end-to-end on the fleet (login, SoD, append-only trigger, chain verify, access revoke; ETL dry-run/commit/idempotency/provenance/rollback).

## 1.7.0 — 2026-06-21
**Email notifications on send-back** — when a reviewer sends an account back, the assigned **preparer is emailed**.
- **Demographics carry email**: `RECON.team[].email` (UI) and `app_user.email` (DB, already present) are now first-class; `team.html` shows each accountant's address, and `emailOf()` resolves a name → address.
- **Send-back is a notify action**: in the UI (dashboard review queue **and** the account detail's approver bar) "Send back" opens a **compose/preview modal** (To = preparer, subject, body, a rework-reason field), then dispatches and confirms with a toast. Approving stays a one-click action.
- **Backend** `POST /api/account/{id}/send-back` — enforces the approve capability **and** segregation of duties (can't send back your own prep), records `sent_back_by/at/reason`, and emails the preparer via a new `notify.py` SMTP sender. **Fail-open**: unconfigured/disabled/erroring SMTP logs a dry-run and never breaks the send-back. Config via env (`NOTIFY_ENABLED`, `SMTP_*`, `NOTIFY_FROM`) surfaced in `compose.yaml`.
- **INTAKE §I** expanded: email/SMTP delivery roadmarkers + the "sent back / rework" notify trigger; recipient address sourced from the §F user roster.
- Asset cache-bust bumped to `?v=1.7.0`.

## 1.6.0 — 2026-06-20
**Accountant dashboard** — a personalized, permission-aware landing page (`web/home.html`, "My dashboard").
- Each accountant sees **their assigned accounts** (preparing — assigned / prepared, hyperlinked to the prepare page) and **their review queue** (approving — in queue / approved / sent back / pending, with Approve / Send-back actions).
- A **Director / Principal** additionally sees the whole **Team workload** — every accountant's prepared-vs-assigned, approved-vs-queue, sent-back, pending. Regular accountants don't see it. A "logged in as" switcher demos the role-based views.
- Backend: `/api/dashboard?user=` returns the user's prepare workload + (only for reviewers) the team roll-up. Verified on the fleet.
- Asset cache-bust bumped to `?v=1.6.0`.

## 1.5.0 — 2026-06-20
**Roles & access (RBAC)** — a 4-tier org hierarchy gates access; workflow-role capabilities drive assignment with segregation of duties.
- **UI**: a Team & roles page (`web/team.html`) — the org hierarchy (Junior → Senior → Principal → Director), a capability matrix (who can prepare / approve / review), per-person workload (prepares vs approves vs reviews), and a "viewing as" role switcher. Account + project detail pages now show the **preparer / approver / reviewer** for the item and a viewer gate (segregation of duties: approver ≠ preparer).
- **Backend**: `app_user` + `role_capability` schema/seed; API — `/api/users`, `/api/me`, and `/api/account/{id}/approve` enforcing the approve capability **and** segregation of duties. Verified: a senior approves a junior's work (OK), can't approve their own (409), and a junior can't approve at all (403).
- **INTAKE §F**: expanded to the 4-tier org hierarchy + a fillable capability matrix + segregation of duties + access source (SSO / local / HRIS).

## 1.4.0 — 2026-06-20
**Year-end close** — utility-grade annual close.
- **UI**: a close calendar (`web/periods.html`) — monthly / quarterly / annual periods with **lock** (closed = read-only); a **roll-forward continuity** board (`web/yearend.html`) — opening + activity = closing, tied to evidence, with a true-up exception and **carry-forward** to next FY; and an **audit package** binder (`web/audit.html`) of every reconciliation + sign-off + document, with a JSON **export**. Sidebar nav added.
- **Backend**: `close_period` + `rollforward` schema/seed; API — `/api/periods`, `/api/period/{key}/lock`, `/api/rollforward`, `/api/period/{key}/carry-forward`, `/api/period/{key}/audit-package` (aggregates account + project + roll-forward reconciliations, FERC functions derived server-side). Verified end-to-end on the fleet.

## 1.3.0 — 2026-06-20
**Project reconciliation** — one supporting document settles the many (FERC) accounts one expense touches.
- **UI**: a Projects board (`web/projects.html`) and a project detail (`web/project.html`) — the source expense + the one document, the allocation across accounts (each line's Project derived live from its FERC range via `web/assets/ferc.js`), the tie-out (sum of allocations vs source within tolerance), and a single **"Settle all N accounts"** action. Added to the sidebar nav.
- **Backend**: `project_reconciliation` / `project_line` schema + seed; FERC-aware API (`/api/projects`, `/api/project/{id}`, `/api/project/{id}/settle`) that derives each line's FERC function server-side; a `ProjectAdapter` contract + `csv_allocations` reference + `dynamics_gp` stub. Verified end-to-end on the fleet (board, detail, settle; FERC functions + tie-out computed correctly).

## 1.2.1 — 2026-06-20
- FERC mapping is now **authored in the intake**: `INTAKE.md` §K gains a fillable **FERC range → Project assignment table** (range · project · expense type · project association) that becomes `ferc/ferc_map.yaml` — so users assign which FERC ranges roll up to which projects/expense types without touching code.
- The classifier now carries **expense type** (Capital / O&M / Revenue / Income / Balance sheet) and a free-form **association** per range; `classify()` returns the full record, `assign()` stamps project + expense type. Map YAML uses a dict form mirroring the intake table columns. Worked example filled for the utility.

## 1.2.0 — 2026-06-20
- **`ferc/`** — FERC handling. A configurable classifier (`classifier.py`) that assigns a **Project** to each GL account from its **FERC Uniform System of Accounts** range — default map = FERC electric (18 CFR Part 101), overridable via `ferc_map.example.yaml`, with configurable COA→FERC-number extraction. This is the project-derivation rule for **project reconciliation**: accounts sharing a FERC range group into one reconciliation that one supporting document settles. Self-tested (12 cases, all pass).
- **`INTAKE.md` §K** — project / grant / FERC accounting roadmarkers (project accounting? per-account vs **per-project** reconciliations? where allocations come from? FERC USoA jurisdiction + range→project map + COA extraction). The worked example (`INTAKE.example.md`) is filled for a regulated electric utility.
- README: added a Project & FERC accounting note. _(The grouped project-reconciliation engine + UI are the next version.)_

## 1.1.0 — 2026-06-20
- **`mcp/`** — an MCP server section for installing/configuring the software. Adds the **OpenRecon Deployment MCP** (`mcp/recon-deploy-server.py`): tools `intake_status`, `list_adapters`, `scaffold_config`, `stack(up/down/status/logs/build)`, `reconcile`, `verify_deploy`; resources for the intake / deployment guide / adapters / architecture; a `deploy_recon` prompt. Plus a curated list of companion MCPs (Postgres, Docker, filesystem, the target GL/DMS, secrets) an agent connects to wire the business systems. Verified registration on the fleet.
- Reframed from "kit / demo" to **production-deployable software** (UI + backend + adapters + intake + MCP); the standalone zero-backend UI demo mode is retained.

## 1.0.0 — 2026-06-20
The kit becomes a **deployable framework** — a coding agent can stand it up in a real business and wire it to existing systems.
- **`INTAKE.md`** — fillable deployment questionnaire: treasury inputs (and how they arrive), the GL system and how balances are read, the DMS, matching rules, roles/SoD, target environment, and secrets handling.
- **`adapters/`** — three pluggable connection points (treasury / GL / DMS). Reference adapters (CSV export, watched folder, CSV statements, Paperless, filesystem) ready to use; stubs for Dynamics GP, NetSuite, generic ODBC, IMAP, SFTP, bank API, Laserfiche, SharePoint.
- **`stack/`** — deployable backend: Postgres + a FastAPI serving the UI's data contract + the reconciliation engine. `docker compose up` runs against bundled sample adapters; verified end-to-end (board + `POST /api/reconcile`).
- **`docs/DEPLOYMENT.md`** — the coding-agent playbook (read intake → pick/implement adapters → deploy → load accounts → reconcile → wire the UI → harden for PROD).

## 0.2.0 — 2026-06-20
- Added a **document repository** page (`documents.html`) — a faux Paperless/Laserfiche DMS ("DocVault") with a searchable document grid and a viewer that renders the underlying bank statements and treasury wire confirmations.
- Wired each reconciliation's "view source document" and supporting-doc links to open the matching document in the repository.
- Anonymized the sample preparer to a generic persona (Joe B.).

## 0.1.0 — 2026-06-20
Initial kit release.
- 5-page static OpenRecon showcase: landing, workspace overview, account detail, how-it-works pipeline, director dashboard.
- Data-driven from a single client-side dataset (`web/assets/app.js`).
- Per-item work statuses (acknowledged / assigned / in progress / resolved) and a preparer→approver→reviewer role model.
- Deploy options: Docker (nginx), plain Python, or any reverse proxy.
- TEST→PROD promotion guide and architecture/component-mapping docs.

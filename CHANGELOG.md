# Changelog

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

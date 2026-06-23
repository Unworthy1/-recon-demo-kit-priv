# OpenRecon

**Production-deployable automated financial reconciliation software.** Bank/treasury statements come in,
get captured in a document system, and are matched against the general ledger within tolerance; exceptions
surface on a board for preparers to resolve and approvers to sign off — with a director's view over the close.

It ships as a complete, deployable system:
- a **web UI** (the reconciliation board, account detail, document repository, director dashboard),
- a **backend** — Postgres + a FastAPI serving the UI's data contract + the reconciliation engine,
- **pluggable adapters** for any treasury / GL / DMS (reference implementations + enterprise stubs),
- a fillable **deployment intake** ([`INTAKE.md`](INTAKE.md)) that captures a business's systems and rules,
- **MCP servers** ([`mcp/`](mcp/README.md)) that let a coding agent install and configure it into a business.

The UI also runs standalone with embedded sample data as a **zero-backend demo** you can host anywhere.

> **What it demonstrates:** a bank statement is dropped in → OCR reads it → a workflow matches it to the general ledger → exceptions surface on one board, get assigned, resolved, and signed off — with a director's view over the whole close.

---

## The three tiers — POC → TEST → PROD

This platform is **Tier 0**. The same architecture promotes cleanly into a live environment by swapping stand-ins for the systems a business already owns.

| Tier | What it is | Stack | Use |
|------|-----------|-------|-----|
| **0 — POC (this platform)** | Static clickable showcase, sample data, no backend | Plain HTML/CSS/JS | Share, demo, pitch, design review, front-end shell |
| **1 — TEST** | Working demo stack on real services, mock data | Paperless-ngx · n8n · mock GL (Postgres) · a small API/GUI | Prove the pipeline end-to-end on disposable infra |
| **2 — PROD** | Same shape, enterprise systems, real data + controls | Laserfiche · Microsoft Dynamics GP · prod orchestration · SSO/RBAC | Run an actual close |

See [`docs/PROMOTION.md`](docs/PROMOTION.md) for the promotion checklist (what changes between tiers — data sources, secrets, RBAC/SSO, monitoring) and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the pipeline and the demo→enterprise component mapping.

---

## Deploy into a business (the framework)

A coding agent can stand this up in a real environment and wire it to existing systems, driven by a
fillable intake:

1. **[`INTAKE.md`](INTAKE.md)** — the prerequisite questionnaire. The user fills in what treasury
   inputs arrive (and how), which GL system the balances come from, which DMS is used, the matching
   rules, roles, and target environment.
2. **[`adapters/`](adapters/README.md)** — the three connection points (treasury / GL / DMS). Each
   intake choice maps to an adapter; reference ones are ready, named enterprise systems (Dynamics GP,
   NetSuite, Laserfiche, SharePoint, IMAP/SFTP/bank-API …) are stubs the agent implements.
3. **[`stack/`](stack/compose.yaml)** — the deployable backend: Postgres + a FastAPI that serves the
   UI's data contract + the reconciliation engine. `docker compose up` and it runs against the bundled
   sample adapters out of the box.
4. **[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)** — the step-by-step the agent follows: read intake →
   pick/implement adapters → deploy stack → load accounts → reconcile → wire the UI → harden for PROD.
5. **[`mcp/`](mcp/README.md)** — MCP servers for the install itself: a **OpenRecon Deployment MCP**
   (intake → config → stack → reconcile → verify, as callable tools + context) plus the companion MCPs
   (Postgres, Docker, filesystem, the target GL/DMS, secrets) an agent connects to wire the business systems.

```bash
cd stack && DB_PASSWORD=… docker compose up -d --build      # db + api + web
curl localhost:8002/api/accounts        # the board, from the database
curl -X POST localhost:8002/api/reconcile   # pull GL + statements via adapters, match, write
```

The engine only ever talks to the adapter interfaces, so swapping a bank or GL is a one-adapter change —
the UI, the board, and the dashboard never change.

### Project & FERC accounting
For utilities and project-accounting shops where one expense is allocated across many accounts,
[`ferc/`](ferc/README.md) assigns a **Project** to each GL account from its **FERC Uniform System of
Accounts** range (default = FERC electric, 18 CFR Part 101; fully overridable). That's the grouping rule
for **project reconciliation** — one reconciliation + one supporting document that settles the multiple
accounts a project touches. There's a **Projects board + detail UI** (allocation across accounts, the
tie-out of the lines to the source expense, and one "settle all" action), a **FERC-aware API**
(`/api/projects`, `/api/project/{id}`, `/api/project/{id}/settle`), and a **`ProjectAdapter`** for pulling
allocations from the project system (e.g. GP Project Accounting). Configured in [`INTAKE.md`](INTAKE.md) §K.

### Year-end close
Utility-grade annual close: **period types** (monthly / quarterly / annual) with **lock** (a closed period
is read-only); **roll-forward continuity** reconciliations (opening + activity = closing, tied to evidence)
with **carry-forward** of closings into the next fiscal year's openings; and an exportable **audit package**
that binds every reconciliation, sign-off, and supporting document for external audit. UI: `periods.html` ·
`yearend.html` · `audit.html`. API: `/api/periods`, `/api/rollforward`,
`/api/period/{key}/{lock,carry-forward,audit-package}`.

### Roles & access (RBAC)
A 4-tier **org-role hierarchy** (Junior → Senior → Principal → Director) gates access, and a configurable
**capability matrix** decides which tiers may hold each workflow role (prepare / approve / review). An
accountant **prepares** their assigned accounts **and** can **approve others'** — with **segregation of
duties** (no self-approval) enforced in the API. UI: `team.html` (hierarchy + capabilities + per-person
workload + a "viewing as" switcher); preparer/approver/reviewer shown on each reconciliation. API:
`/api/users`, `/api/me`, `/api/account/{id}/approve`. Configured in [`INTAKE.md`](INTAKE.md) §F.

### Accountant dashboard
A personalized, permission-aware landing page (`home.html`, "My dashboard"): each accountant sees **their
assigned accounts** (preparing — how many assigned / prepared, linked to the prepare page) and **their
review queue** (approving — in queue / approved / sent back / pending, with quick Approve / Send-back).
A **Director / Principal** additionally sees the whole **team's workload** (every accountant's prepared-vs-
assigned and approved-vs-queue). API: `/api/dashboard` (returns the team roll-up only for reviewers).

### Email notifications (send-back)
Each user record carries an **email** (§F roster / `app_user.email`). When a reviewer **sends an account
back** for rework — from the dashboard review queue or the account detail's approver bar — the assigned
**preparer is emailed**. The UI composes the message in a preview/compose modal (with a rework reason); the
deployable stack sends it over SMTP (`stack/api/notify.py`, `POST /api/account/{id}/send-back`), enforcing
the approve capability + segregation of duties. SMTP is env-configured and **fails open** (dry-run + log)
until supplied. Configured in [`INTAKE.md`](INTAKE.md) §I.

### Audit trail & access controls (SOX/ICFR)
An **immutable, hash-chained** audit trail (`audit_event`) records every prepare/approve/send-back/lock/
settle/carry-forward/login/import — server-timestamped, bound to the authenticated identity, and **append-
only at the database** (UPDATE/DELETE blocked by a trigger). `GET /api/audit/verify` re-walks the chain to
prove nothing was altered. Real **authentication** (local bcrypt via pgcrypto, OIDC/SAML seam) with expiring
sessions, plus periodic **access recertification**. The session identity overrides any client-supplied user,
so the trail always names the real actor. Full control-objective → feature mapping in
[`docs/CONTROLS.md`](docs/CONTROLS.md); deployment roadmarkers in [`INTAKE.md`](INTAKE.md) §L.

### Historical data migration (ETL)
A prior-year **backfill driver** ([`stack/api/etl.py`](stack/api/etl.py), the `recon_etl` MCP) loads
historical reconciliations into the recon scope so roll-forward continuity, trend reporting, and the
multi-year audit binder have real history. It's **idempotent** (upsert by account+period), **dry-run →
commit**, **provenance-tagged** (`origin='historical_import'` — migrated evidence, never confused with live
approvals), loaded into closed periods, **reversible by batch**, and reviewer/director-gated + audited.
API: `/api/import/{dry-run,commit,batches,{id}/rollback}`. Configured in [`INTAKE.md`](INTAKE.md) §M.

---

## Quick start

**Option A — Docker (recommended, deploy-anywhere):**
```bash
docker compose up -d        # serves the platform on http://localhost:8080
```

**Option B — no Docker, instant preview:**
```bash
./serve.sh                  # python3 -m http.server on http://localhost:8080
# or directly:  cd web && python3 -m http.server 8080
```

**Option C — behind an existing reverse proxy:** copy `web/` to a docroot and point a vhost at it. A ready-to-edit snippet is in [`Caddyfile.example`](Caddyfile.example) (works the same with nginx/Apache — it's just static files).

Then open **http://localhost:8080** and start at the landing page; the nav links the rest together.

---

## What's inside (the application)

| Page | Shows |
|------|-------|
| `index.html` — **Landing** | The pitch, scale stats, the drop→sign-off story, feature cards |
| `home.html` — **My dashboard** | A personalized, permission-aware landing: the accounts you prepare and your review queue, with a team-wide roll-up for directors/principals |
| `workspace.html` — **Overview board** | The reconciliation board: KPI cards (click to filter), close-progress bar, the account table grouped by type, filter chips, and a per-item **work-status** column |
| `account.html` — **Account detail** | GL vs OCR'd bank balance side-by-side, supporting documents, the work-status stepper, the preparer/approver gate, and live resolve/approve/send-back |
| `projects.html` · `project.html` — **Project & FERC reconciliation** | One supporting document settling the many accounts an expense touches, with the FERC-derived allocation tie-out and a single "settle all" action |
| `periods.html` · `yearend.html` — **Year-end close** | The close calendar with period lock, plus roll-forward continuity and carry-forward into the next fiscal year |
| `audit.html` — **Audit package** | The close binder of every reconciliation, sign-off, and document, with a JSON export for external audit |
| `team.html` — **Team & roles** | The org-role hierarchy, capability matrix, per-person workload, and segregation-of-duties model |
| `documents.html` — **Document repository** | A Paperless/Laserfiche-style DMS view: searchable document grid plus a viewer for the underlying bank statements and wire confirmations |
| `how-it-works.html` — **Pipeline** | drop → OCR → match → record → review, plus the demo→enterprise mapping |
| `dashboard.html` — **Director dashboard** | Throughput by preparer, status-mix donut, exceptions by age, variance by group |

Everything is **data-driven from one file** — [`web/assets/app.js`](web/assets/app.js) holds the sample dataset, and every page reads it, so the board, the detail view, and the dashboard can never disagree on the numbers.

---

## Customizing

- **Data:** edit the `RECON` object in `web/assets/app.js` (accounts, balances, statuses, assignees, team). All pages and charts recompute automatically.
- **Branding:** the design tokens live at the top of `web/assets/app.css` (`:root` — colors, the gradient, fonts). Change them in one place to re-skin the whole platform.
- **Roles & workflow:** the work-status values (`acknowledged / assigned / in progress / resolved`) and the role model (preparer → approver → reviewer) are described in `docs/ARCHITECTURE.md`.

---

## Design notes

- **No CDN, no build, no backend** — the charts are hand-rolled SVG / CSS conic-gradients, so the platform works fully offline and ships as plain files.
- **Sample data only.** No real financials, accounts, or people — swap in your own via `app.js`.
- Matches the look of the live reference app by reusing its exact CSS design tokens, so the POC is visually indistinguishable from the product.

---

_Licensed under the [Apache License 2.0](LICENSE) — free to use, modify, and distribute._

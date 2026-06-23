# Security & audit posture

This is a point-in-time summary of OpenRecon's security and audit posture as of **v1.8.0**. The
control-objective → feature mapping lives in [`docs/CONTROLS.md`](docs/CONTROLS.md); this file is the
plain-language "where we stand, and what's still the deployer's job."

> **Tiers matter.** The **static showcase** (`web/`) is a sample-data demo with **no authentication and no
> real financials** — it is meant to be public. The **deployable stack** (`stack/`) is where the security
> controls below live. Don't conflate the two: the showcase intentionally has none of this.

## What's enforced today (deployable stack)

- **Authentication** — local password auth with **bcrypt** hashing (via pgcrypto; passwords never stored
  or compared in plaintext) and **opaque, expiring sessions**. An **OIDC/SAML seam** (`auth_source`,
  `external_subject`) is in place for federating to an IdP. An `mfa_enabled` flag is recorded per user.
- **Authorization** — a 4-tier org hierarchy + a capability matrix (prepare/approve/review), with
  **segregation of duties enforced server-side**: an approver cannot be the preparer, and must be at the
  preparer's tier or above (HTTP 409 on violation). Enforcement is in the API, not just the UI.
- **Identity binding** — the audited actor is taken from the **authenticated session**, which overrides any
  client-supplied `user` parameter. The trail names the real person.
- **Immutable audit trail** — append-only, **hash-chained**, **server-timestamped** `audit_event`; `UPDATE`
  and `DELETE` are blocked by a database trigger (append-only at the DB, independent of the app).
  `GET /api/audit/verify` re-walks the chain and reports any break. Covers prepare/approve/send-back/lock/
  settle/carry-forward/login (success **and** failure)/import.
- **Access recertification** — a reviewer recertifies or revokes a user; a revoke **disables the account and
  kills live sessions**, and is itself audited.
- **Data provenance** — migrated prior-year records are tagged `origin='historical_import'` and are never
  presented as reconciliations that passed live maker-checker. Imports are idempotent, reversible by batch,
  reviewer-gated, and audited.
- **Input & query safety** — SQL is fully parameterized (psycopg); the ETL file source is restricted to a
  basename under a fixed directory (no path traversal).
- **Secrets** — all credentials (DB, SMTP, IdP) come from the **environment / a secret store**, never the
  repo. Outbound email **fails open** (dry-run + log) until SMTP is configured, so a missing secret can't
  break the workflow.

## What is the deployer's responsibility (not shipped, by design)

- **A real identity provider.** The OIDC/SAML seam exists; wiring it to your IdP — **and enforcing MFA** —
  is yours. The `mfa_enabled` flag is recorded but a second factor is not itself implemented in-app.
- **TLS / transport security** — terminate TLS at your reverse proxy or edge; the stack speaks HTTP behind it.
- **ITGCs around the hosting** — database access control, encrypted backups, restore tests, and
  deploy/change approvals are organizational controls the software can't provide.
- **The SOX attestation** — OpenRecon evidences controls; it does not make you compliant. See
  [`docs/CONTROLS.md`](docs/CONTROLS.md) for the honest list of what the software cannot supply.

## Known limitations / hardening backlog (v1.8.0)

- **Demo credentials are seeded** in `db/06-audit-auth.sql` (all demo users share `openrecon-demo`). A real
  deployment must provision from SSO/HRIS and ship **no** seeded passwords.
- **Login has no rate-limiting or account lockout** yet — add brute-force protection (and prefer SSO) for PROD.
- **CORS is `allow_origins=["*"]`** in the demo API — restrict it to the UI origin in a real deployment.
- **MFA is a flag, not a second factor** — enforce it at the IdP.
- Audit-event hashing serializes inserts via an advisory lock (correct, but a single-writer assumption for
  the close workload); high-concurrency deployments should validate throughput.

## Reporting a concern

This is a private repository maintained by the owner. If you find a security issue, contact the repository
maintainer directly — do not open a public issue with exploit detail. No real financial data is present in
this repository; sample data uses placeholder names and reserved `.example` email addresses.

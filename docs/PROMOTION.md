# Promotion — POC → TEST → PROD

This platform (Tier 0) is the front-end shell and the shared mental model. Promoting it into a running close is two steps: stand up the pipeline on disposable infra (TEST), then swap stand-ins for enterprise systems and add controls (PROD).

## Tier 0 → Tier 1 (POC → TEST)

Goal: the pipeline runs end-to-end on real services with mock-but-real data.

- [ ] Stand up the services: document repo (Paperless-ngx), orchestration (n8n), a mock GL database (Postgres seeded with sample accounts), and a thin API the front-end reads.
- [ ] Replace the static `RECON` dataset with a fetch from that API (`GET /accounts`, `GET /reconciliations`). The page rendering already keys off one dataset — point it at the endpoint.
- [ ] Wire intake: a watched folder / upload that lands in the document repo; a post-OCR hook that extracts balance + account + date.
- [ ] Build the match workflow: pull GL balance → compare within tolerance → write verdict + evidence back.
- [ ] Verify the full loop: drop a statement → see the account flip to reconciled/variance on the board.

## Tier 1 → Tier 2 (TEST → PROD)

Goal: same shape, enterprise systems, real data, real controls.

| Concern | TEST | PROD |
|---------|------|------|
| Documents / OCR | Paperless-ngx | **Laserfiche** (repository API + capture) |
| General ledger | Mock Postgres GL | **Microsoft Dynamics GP** (GL views / integration) |
| Orchestration | n8n on a VM | Governed orchestration (n8n prod, Power Automate, or scheduled ETL) with change control |
| Identity / access | none / shared | **SSO + RBAC** — preparer / approver / reviewer roles, segregation of duties |
| Secrets | local env files | a secrets manager / vault; nothing in source |
| Data | sample / mock | real financials — data classification, retention, least-privilege access |
| Audit | implicit | immutable audit trail: who/when on every prepare, approve, resolve |
| Monitoring | manual | uptime + job-success alerting; failed-OCR / unmatched-statement alerts |
| Environments | one box | separate TEST and PROD with a promotion/release process |
| Sign-off | demo button | enforced approval workflow tied to the close calendar |

## Promotion principles

- **The front-end is environment-agnostic.** It reads one dataset; only the *source* of that dataset changes between tiers. Keep it that way — no environment logic in the UI.
- **Swap one component at a time.** Replace Paperless with Laserfiche, or the mock GL with Dynamics GP, independently — the contract between stages (a balance, an account number, a date, a verdict) is what stays fixed.
- **Controls are a PROD concern, designed from the start.** RBAC, segregation of duties, audit trail, and secrets handling are sketched in the demo (roles, work statuses) so they're not bolted on later.
- **Never let real financials touch the POC tier.** Tier 0 is sample data only, by design.

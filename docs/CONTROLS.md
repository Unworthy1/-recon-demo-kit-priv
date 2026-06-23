# OpenRecon — internal controls (SOX 404 / ICFR mapping)

OpenRecon is not "SOX compliant" by itself — SOX 404 compliance is *your organization's* attestation
about its Internal Controls over Financial Reporting (ICFR), assessed under PCAOB **AS 2201** against the
**COSO** framework, with IT general controls (ITGC) on the hosting side. What OpenRecon does is **enforce
and evidence** the controls a reconciliation program relies on, so an auditor's job is pulling evidence,
not archaeology. This maps each control objective to where it lives.

| Control objective (COSO / ICFR) | How OpenRecon supports it | Where |
|---|---|---|
| **Audit trail** — complete, immutable, who/what/when | Append-only `audit_event`, **hash-chained** + **server-timestamped**, with UPDATE/DELETE blocked by a DB trigger. Every prepare/approve/send-back/lock/settle/carry-forward/login/import writes one event. Integrity is re-verifiable. | `db/06-audit-auth.sql`, `GET /api/audit`, `GET /api/audit/verify` |
| **Segregation of duties** | Approver ≠ preparer and approver tier ≥ preparer tier, enforced in the API (not just the UI). | `POST /api/account/{id}/approve` (409 on self-approve) |
| **Authentication & least privilege** | Real sessions (local bcrypt via pgcrypto; OIDC/SAML seam), capability-gated actions, sessions expire/revoke. Every audit event is bound to the authenticated identity, which **overrides** any client-supplied user. | `auth.py`, `app_user`, `auth_session`, `/api/auth/*` |
| **Periodic access recertification** | A manager recertifies or revokes each user's access; a revoke disables the user and kills live sessions. Recorded + audited. | `access_review`, `/api/access-review` |
| **Maker-checker sign-off** | Preparer resolves → independent approver signs; both stamped (`resolved_by/at`, `approved_by/at`) and audited. | `reconciliation`, resolve/approve endpoints |
| **Period immutability** | Closing a period locks it (read-only); the lock is audited. | `close_period`, `/api/period/{key}/lock` |
| **Provenance / data integrity of migrated data** | Backfilled prior-year records are tagged `origin='historical_import'` + a batch id, so migrated **evidence** is never mistaken for a reconciliation that passed live SoD/approval. | `db/07-etl.sql`, `etl.py` |
| **Reversibility of bulk loads** | Historical imports are idempotent and reversible by batch; both commit and rollback are audited. | `import_batch`, `/api/import/*` |

## The tamper-evident trail (how it works)

Each `audit_event` row stores `row_hash = sha256(prev_hash | server_ts | actor | action | entity | before | after | detail)`,
computed by a `BEFORE INSERT` trigger and chained to the previous row (an advisory lock serializes inserts so the
chain is linear). A second trigger raises on any `UPDATE`/`DELETE`, so the table is append-only **at the database**,
independent of the application. `GET /api/audit/verify` re-walks the chain using the *exact same SQL expression* the
trigger used and reports the first broken link if any — so you can prove to an auditor that nothing was altered.

## What the software cannot supply (still the organization's job)

- **ITGCs around the hosting**: database access control, encrypted backups, deploy/change approvals, restored-backup tests.
- **A documented control narrative** and the management assessment itself.
- **The external auditor's attestation.**
- **Real identity provider**: wire `auth_source=oidc|saml` to your IdP (with MFA) — the seam is here, the IdP is yours.

## Verifying the controls (TEST)

```bash
# audit trail is immutable + intact
curl -s localhost:8002/api/audit/verify                     # {"intact": true, ...}
docker exec stack-db-1 psql -U recon -d recon -c \
  "UPDATE audit_event SET actor='x' WHERE id=1;"            # ERROR: audit_event is append-only

# segregation of duties holds
curl -s -X POST "localhost:8002/api/account/1010/approve?user=Joe%20B."   # 409 if Joe prepared 1010

# access recertification disables + cuts sessions
curl -s -X POST "localhost:8002/api/access-review?user_id=u-sam&decision=revoked&reviewer=Robert%20K."
```

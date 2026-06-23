# Architecture

## The pipeline

Every bank statement flows left → right, untouched by hand:

```
   Drop            OCR & extract        Match               Record              Review
┌─────────┐      ┌──────────────┐    ┌──────────┐       ┌──────────────┐    ┌───────────┐
│ folder  │ ───▶ │ OCR the PDF, │──▶ │ pull GL  │ ────▶ │ write verdict│──▶ │ exceptions│
│ · email │      │ extract bal, │    │ balance, │       │ + evidence + │    │ surface,  │
│ · upload│      │ acct #, date │    │ compare  │       │ doc link to  │    │ resolve,  │
└─────────┘      └──────────────┘    │ ± toler. │       │ the recon DB │    │ sign off  │
                                     └──────────┘       └──────────────┘    └───────────┘
```

1. **Drop** — a statement PDF arrives: emailed to a monitored mailbox, dropped in a watched folder, or uploaded from the overview.
2. **OCR & extract** — the document repository OCRs the file; a post-consume hook extracts the statement balance, account number, and statement date.
3. **Match** — an orchestration workflow pulls the GL balance for that account, compares it to the statement within a per-account tolerance, and computes the variance.
4. **Record** — the verdict (reconciled / variance / unmatched) is written back to the reconciliation database with the OCR evidence and a link to the source document.
5. **Review** — exceptions surface on the board for a preparer to resolve, an approver to sign off, and a director to oversee.

## Demo → enterprise component mapping

The architecture is the point; the components are swappable.

| Layer | Tier 1 (TEST) — open-source stand-in | Tier 2 (PROD) — enterprise system |
|-------|--------------------------------------|-----------------------------------|
| Document capture & OCR | Paperless-ngx | **Laserfiche** |
| General ledger | Mock GL (Postgres) | **Microsoft Dynamics GP** |
| Orchestration | n8n workflows | n8n / Power Automate / scheduled ETL |
| Reconciliation board | This web app | BlackLine-style close platform (or this app, productionized) |
| Intake | Watched folder · mailbox · upload | Monitored AP/treasury mailbox |
| Identity | none (demo) | SSO / directory (Entra ID, etc.) |

## Data model

The platform is driven entirely by the `RECON` object in [`web/assets/app.js`](../web/assets/app.js). Each account record:

| Field | Meaning |
|-------|---------|
| `id`, `code` | account identifier / GL code |
| `grp` | account group (Cash, AR, AP, Accruals, Intercompany, …) |
| `name`, `bank`, `mask` | display name, source institution, masked account |
| `gl` | general-ledger balance |
| `stmt` | OCR'd statement balance (`null` = no statement matched yet) |
| `status` | `reconciled` · `variance` · `unreconciled` (derived from `gl`, `stmt`, `tol`) |
| `assigned` | preparer who owns it |
| `work` | per-item work status (see below) |
| `tol` | match tolerance |
| `ocr_acct`, `ocr_date`, `as_of` | OCR evidence + GL as-of date |

`variance` is computed (`gl − stmt`); KPIs, the dashboard, and all charts derive from this one dataset, so every view stays consistent.

## Roles & work status

**Role model** (who acts on what):

| Role | Responsibility |
|------|----------------|
| Preparer — junior / senior | Locates the statement, resolves variances, attaches support |
| Approver — Principal | Reviews the prepared reconciliation and its supporting docs |
| Reviewer — Director | Oversees throughput, aging, and sign-off across the close |

**Work-status state machine** (per reconciliation item):

```
acknowledged → assigned → in progress → resolved
```

Surfaced as a column on the overview and a stepper on the account detail page. In PROD this maps to an approval/segregation-of-duties workflow (preparer cannot approve their own work).

# OpenRecon — Deployment Intake

**Fill this out before deploying.** A coding agent reads your answers and uses them to deploy
the OpenRecon reconciliation software into your environment and wire it into your existing
treasury, general-ledger, and document systems. Anywhere you see **`→`**, replace the example
with your answer. Tick `[x]` the options that apply. If you don't know a field yet, write
`TBD` — the agent will flag it rather than guess.

> 📄 **Worked example:** [`INTAKE.example.md`](INTAKE.example.md) is this form filled out end-to-end for a
> Microsoft Dynamics GP + Laserfiche shop — use it as a reference answer set.
>
> **The model in one line:** statements come in → they're captured/OCR'd in a **DMS** → a
> workflow pulls **GL** balances and matches them to the **statement** balances within tolerance
> → exceptions surface on a board for preparers to resolve and approvers to sign off.
>
> This intake defines the three connection points — **treasury in**, **GL in**, **DMS** — plus
> the rules, roles, and target environment. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for how
> the agent turns these answers into a running system, and [`adapters/README.md`](adapters/README.md)
> for the connector each option maps to.

---

## A. Business context & scope

- **Legal entity / business unit being reconciled:**
  → `Acme Manufacturing, Inc. — US entity`
- **Close cadence:** `[ ]` monthly  `[ ]` weekly  `[ ]` daily  `[ ]` other: → `monthly`
- **Approx. # of GL accounts in scope:** → `600`
- **Approx. # of reconciliations per close:** → `150`
- **Account groups in scope** (tick all): `[ ]` Cash & equivalents `[ ]` Accounts receivable
  `[ ]` Accounts payable `[ ]` Prepaid & other assets `[ ]` Accrued liabilities `[ ]` Intercompany
  `[ ]` Other: → `…`
- **Currencies:** → `USD only` _(or list, e.g. USD, EUR, GBP — see §E for FX handling)_
- **Default materiality / tolerance** (variance below which an item auto-reconciles):
  → `$25 for cash, $100 for sub-ledgers` _(override per account in §E)_

## B. Treasury / bank statement inputs

**How do bank/treasury statements arrive?** Add one block per source (bank or feed). The agent
wires a treasury adapter for each — see `adapters/treasury/`.

> Repeat this block per institution/feed.

### Source 1
- **Institution / feed name:** → `Wells Fargo — operating`
- **Accounts it covers:** → `Operating cash ••4471, Payroll ••8810`
- **Delivery method** (tick one):
  - `[ ]` Manual upload (user drops the file in the UI)
  - `[ ]` Watched folder / network share (path: → `\\fileserver\treasury\incoming`)
  - `[ ]` Email mailbox (IMAP) (address: → `treasury-stmts@acme.com`)
  - `[ ]` SFTP pull (host/path: → `sftp.bank.com:/outbound/`)
  - `[ ]` Direct bank API / aggregator (which: → `Plaid / bank portal API / BAI2 feed`)
- **File format:** `[ ]` PDF `[ ]` CSV `[ ]` BAI2 `[ ]` MT940 `[ ]` OFX/QFX `[ ]` other: → `PDF`
- **Frequency:** → `daily prior-day; month-end statement on the 1st`
- **Who holds the credentials / access** (the human, not the secret): → `Treasury team`

### Source 2
- _(copy the block above)_

## C. General ledger inputs

**Where do GL balances come from, and how does the software read them?**

- **GL / ERP system:** `[ ]` Microsoft Dynamics GP `[ ]` Dynamics 365 BC/F&O `[ ]` NetSuite
  `[ ]` QuickBooks (Online/Desktop) `[ ]` SAP `[ ]` Oracle `[ ]` Sage `[ ]` Workday
  `[ ]` Other: → `Microsoft Dynamics GP`
- **Connection method** (tick one):
  - `[ ]` Direct database / ODBC (read-only) (server/db: → `GPSQL01 / DYNAMICS`)
  - `[ ]` Vendor API (auth type: → `OAuth / API key / service account`)
  - `[ ]` Scheduled export file (trial balance / GL detail) dropped to (path: → `…`), format: → `CSV`
  - `[ ]` Manual export (user uploads a trial balance each close)
- **What's extracted:** `[ ]` period-end balance per account `[ ]` GL detail/transactions
  `[ ]` both → `period-end balance per account`
- **Account/segment identifier** (how an account is keyed): → `account-subaccount, e.g. 1010-00`
- **As-of / period handling:** → `closing balance as of period end (last calendar day)`
- **Extract cadence:** → `nightly during close; on-demand re-pull on the recon board`
- **Read-only guaranteed?** (the software must never write to the GL): `[ ]` yes → `yes`

## D. Document management system (DMS)

**Where do source documents (statements, support) live, and how does recon link to them?**

- **DMS in use:** `[ ]` Paperless-ngx `[ ]` Laserfiche `[ ]` SharePoint / OneDrive
  `[ ]` M-Files `[ ]` Box `[ ]` Plain filesystem / network share `[ ]` None (use the bundled one)
  `[ ]` Other: → `Laserfiche`
- **Capture / OCR:** `[ ]` the DMS OCRs on ingest `[ ]` OpenRecon OCRs then files into the DMS
  `[ ]` no OCR (structured feeds only) → `the DMS OCRs on ingest`
- **How recon references a document** (tick one):
  - `[ ]` Deep link / URL to the document in the DMS UI (URL pattern: → `https://laserfiche.acme.com/doc/{id}`)
  - `[ ]` Document ID stored, fetched via API (API base: → `…`)
  - `[ ]` File path on a share (path pattern: → `…`)
- **Access method for the software:** `[ ]` REST API (auth: → `…`) `[ ]` filesystem `[ ]` none/manual
- **Retention / records policy to honor:** → `7 years; no deletion by the app`

## E. Reconciliation rules

- **Match key** (how a statement is tied to a GL account): → `bank account number → GL account map (table below)`
- **Tolerance** (auto-reconcile if |GL − statement| ≤): → `default per §A; overrides: Cash $25, IC $100`
- **FX handling** (if multi-currency): → `none / translate at period-end rate from <source> / reconcile in local currency`
- **Definition of "reconciled":** → `matched within tolerance OR variance fully explained + approved`
- **Recurring / timing items** (expected to resolve themselves): → `deposits in transit, outstanding checks — flag, don't fail`
- **Exception categories** the team uses: → `timing, unrecorded transaction, error, FX, unknown`
- **Account map** (statement source → GL account → tolerance): provide as a file or table →
  ```
  bank_acct_4471  ->  GL 1010-00  ->  $25
  bank_acct_8810  ->  GL 1020-00  ->  $50
  ```

## F. Roles, access hierarchy & segregation of duties

**Org-role hierarchy** (the access level — ascending). Map your titles to the four tiers (rename as needed):
- Junior Accountant (tier 1) → `…`
- Senior Accountant (tier 2) → `…`
- Principal Accountant (tier 3) → `…`
- Manager / Director (tier 4) → `…`
- **Users & tiers sourced from:** `[ ]` SSO groups (IdP) `[ ]` local accounts `[ ]` HRIS feed → `…`
  _(e.g. `ACME\Recon-Senior`, `ACME\Recon-Principal`, …)_

**Workflow-role capabilities** — which org roles may hold each workflow role. This is your policy; the
default below means *anyone prepares; seniors and above approve others' work; only principals/directors
review*. Tick to match your org:

| Org role | Prepare | Approve | Review |
|---|---|---|---|
| Junior Accountant | `[x]` | `[ ]` | `[ ]` |
| Senior Accountant | `[x]` | `[x]` | `[ ]` |
| Principal Accountant | `[x]` | `[x]` | `[x]` |
| Manager / Director | `[x]` | `[x]` | `[x]` |

- **Assignment model:** an accountant **prepares** their assigned accounts **and** can **approve other**
  accounts (so seniors/principals prepare some and approve others' work). → `…`
- **Segregation of duties:** `[x]` a preparer cannot approve/review their own reconciliation
  `[ ]` an approver's tier must be ≥ the preparer's tier → `…`
- **Sign-off required to close:** `[ ]` per reconciliation `[ ]` per account group `[ ]` per close → `…`
- **Per-item work statuses to track:** `[ ]` acknowledged `[ ]` assigned `[ ]` in progress
  `[ ]` resolved `[ ]` approved `[ ]` reviewed → `all of the above`

## G. Environment & deployment target

- **Where does this run?** `[ ]` On-prem VM(s) `[ ]` Private cloud (AWS/Azure/GCP) `[ ]` Kubernetes
  `[ ]` Single Docker host `[ ]` Other: → `on-prem VM, Docker`
- **OS / runtime available:** → `Ubuntu 22.04, Docker + Compose`
- **Hostname(s) for the app:** → `recon.acme.internal` (internal) / `…` (external, if any)
- **TLS / reverse proxy:** `[ ]` existing proxy (which: → `nginx / Caddy / F5`) `[ ]` none — provision one
- **Identity / SSO:** `[ ]` none (local accounts) `[ ]` SAML/OIDC (IdP: → `Entra ID / Okta`)
  `[ ]` LDAP/AD → `Entra ID (OIDC)`
- **TEST and PROD separation:** → `deploy TEST first on recon-test.acme.internal, then PROD`

## H. Security & secrets

- **How are secrets provided to the app?** `[ ]` Secret manager (which: → `Vault / Azure Key Vault`)
  `[ ]` env files (600) handed over out-of-band `[ ]` other: → `Azure Key Vault`
- **Data classification of the recon data:** → `Confidential — financial`
- **Network constraints:** → `app VLAN can reach GP SQL :1433 and Laserfiche :443; no outbound internet`
- **Audit trail requirements:** → `immutable who/when on every prepare/approve/review; retained 7y`
- **Who may hold credentials** (the human): → `the platform team / a named owner` _(the agent never stores raw secrets in the repo)_

## I. Notifications & reporting

- **Notify on** (tick): `[ ]` new exception `[ ]` assignment `[x]` **sent back / rework**
  `[ ]` sign-off `[ ]` close-at-risk
  _(Send-back is wired: when a reviewer returns an account, the **assigned preparer** is emailed.)_
- **Channel:** `[ ]` Email `[ ]` Microsoft Teams `[ ]` Slack → `Email`
- **Email delivery (SMTP)** — needed for send-back alerts. Fill these into the deployment's secret
  store (never the repo); the app reads them from env and **fails open** (dry-run + log) until set:
  - **SMTP host / port:** → `smtp.office365.com` / `587`
  - **STARTTLS:** `[x]` yes `[ ]` no
  - **Auth user / password:** → `recon-noreply@acme.com` / _(secret manager)_
  - **From address:** → `OpenRecon <recon-noreply@acme.com>`
  - **Recipient address source:** `[x]` the `email` on each user record (§F roster) `[ ]` SSO/HRIS lookup
- **Director dashboard wanted?** `[ ]` yes → `yes`
- **Close calendar / SLA** (when must each reconciliation be done): → `WD+5`

## J. Existing-systems inventory (anything else to wire)

- → `ERP: Dynamics GP. Email: Exchange Online. Ticketing: ServiceNow (optional). BI: Power BI.`

## K. Project / grant / FERC accounting

Fill this if costs are collected against projects and allocated across multiple GL accounts (so one
reconciliation + one supporting doc settles several accounts), and/or if you keep books on FERC.

- **Project / grant / job accounting?** `[ ]` yes `[ ]` no → `…`
- **Project / cost system:** `[ ]` Dynamics GP Project Accounting `[ ]` SAP PS `[ ]` Deltek
  `[ ]` Oracle Projects `[ ]` other: → `…`
- **Reconciliation granularity:** `[ ]` per account (one balance vs one statement) `[ ]` **per project**
  (one reconciliation + one supporting doc settles multiple accounts) `[ ]` both → `…`
- **Where allocation lines come from** (the postings that must tie to the source expense): → `…`
- **FERC books?** keep the chart of accounts on the FERC USoA? `[ ]` no `[ ]` yes —
  `[ ]` electric (18 CFR Part 101) `[ ]` gas (Part 201) `[ ]` oil pipeline (Part 352) → `…`
- **FERC range → Project assignment** — assign each FERC account range to a **Project**, an **expense
  type**, and an optional **association**. This tells the software which FERC accounts roll up to which
  project (and how project reconciliations group the accounts one expense touches). `[ ]` use the bundled
  default as-is, **or** edit/extend the table below (pre-filled with the FERC electric default). Your filled
  table becomes [`ferc/ferc_map.yaml`](ferc/ferc_map.example.yaml).

  | FERC range | Project | Expense type | Project association / notes |
  |---|---|---|---|
  | 106–107 | CWIP — capital projects | Capital | settle by work order |
  | 310–347 | Production plant | Capital | |
  | 350–359 | Transmission plant | Capital | |
  | 360–374 | Distribution plant | Capital | |
  | 389–399 | General plant | Capital | |
  | 500–557 | Production O&M | O&M | |
  | 560–576 | Transmission O&M | O&M | |
  | 580–598 | Distribution O&M | O&M | |
  | 901–935 | Customer / Sales / A&G | O&M | overhead allocation |
  | 440–457 | Operating revenues | Revenue | |
  | 101–191 | Plant & other assets | Capital / Balance sheet | |
  | 201–253 | Liabilities & equity | Balance sheet | |
  | … | … | … | _add rows / split ranges to match your projects_ |

- **FERC number extraction** (which part of your COA code is the 3-digit FERC account): → `standalone
  3-digit, e.g. 01-560-00 -> 560` _(or a regex)_

## L. Audit, access & SOX controls

OpenRecon ships an immutable, hash-chained audit trail and real auth (see [`docs/CONTROLS.md`](docs/CONTROLS.md)).
Fill this so it maps to your control program.

- **Is this in SOX/ICFR scope?** `[ ]` yes `[ ]` no → `…`
- **Authentication source:** `[ ]` local accounts (bcrypt) `[ ]` **OIDC** (IdP: → `Entra ID / Okta`)
  `[ ]` SAML → `…` ; **MFA required?** `[ ]` yes `[ ]` no
- **Access recertification cadence:** `[ ]` quarterly `[ ]` semi-annual `[ ]` annual → `…`
  _(who runs the campaign / approves access: → `…`)_
- **Audit-trail retention:** → `7 years` _(and where the DB + backups live for ITGC: → `…`)_
- **Who may hold the DB / admin credentials** (the human): → `…`
- **Change management** — who approves changes to tolerances, FERC ranges, roles, mappings: → `…`

## M. Prior-year data migration (historical ETL)

To get real opening balances (roll-forward), trend reporting, and a multi-year audit binder, backfill
history with the ETL driver ([`stack/api/etl.py`](stack/api/etl.py), `recon_etl` MCP). Imported records
are tagged `origin='historical_import'` — migrated **evidence**, never presented as live approvals.

- **How many prior years to load?** → `2–3 FY`
- **Source of the history:** `[ ]` prior recon tool export (BlackLine/Trintech/…) `[ ]` GL historical
  trial balance by period `[ ]` spreadsheets `[ ]` other: → `…`
- **Scope to load:** `[ ]` balances only `[ ]` balances + sign-offs (`resolved_by`/`approved_by`)
  `[ ]` + supporting documents → `…`
- **COA / period mapping** — how the source's account codes & period labels map to OpenRecon
  (`account_code`, `period_end`): → `…`
- **Who attests the migration** (a reviewer/director signs off the loaded batches): → `…`

## N. Teams & cross-team collaboration

Reconciliations are rarely settled by Accounting alone — a variance gets resolved by asking Treasury for
a bank confirmation, Operations for a work order, or Audit to attest. OpenRecon models **teams** as a
layer *orthogonal* to the §F org-role hierarchy: the org-role gates access & segregation of duties; a
**team** is the function a person speaks for in a reconciliation's discussion thread. A person can sit on
several teams. Each account *and* project reconciliation carries a thread (comments + attachments), and a
comment can be a **request to another team** that puts the record in an "awaiting <team>" state until they
respond — every comment is written to the immutable audit trail. (`stack/db/09-collab.sql`;
`/api/teams`, `/api/thread/{type}/{id}`, `/api/inbox`.)

- **Which teams participate?** (tick all — these seed the `team` table; you must have ≥2 for cross-team
  requests to mean anything): `[ ]` Accounting (always) `[ ]` Treasury `[ ]` Audit / Controls
  `[ ]` Operations / Business unit `[ ]` Tax `[ ]` FP&A `[ ]` other: → `…`
- **Who sits on each team** (name → team(s); list anyone who's on more than one): → `…`
- **Do you want the "request → awaiting <team>" routing**, or a plain comment thread only? → `request + awaiting`
- **Does a comment/attachment need its own retention/export** in the audit package beyond the control
  actions? → `…`

---

## Minimum to start

If you only fill three things, fill these — the agent can deploy a working TEST instance from them:
1. **§C** — your GL system + how to read balances.
2. **§B (Source 1)** — how at least one bank statement arrives.
3. **§D** — your DMS (or choose the bundled one).

Everything else can be `TBD` and hardened on the way to PROD (see [`docs/PROMOTION.md`](docs/PROMOTION.md)).

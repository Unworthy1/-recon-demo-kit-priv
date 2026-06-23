# OpenRecon — Deployment Intake (WORKED EXAMPLE)

> This is a **filled-in reference** for a mid-size business running **Microsoft Dynamics GP** (GL)
> and **Laserfiche** (DMS). Copy [`INTAKE.md`](INTAKE.md) and fill it like this for your own shop.
> Every field is answered (no `TBD`), so a coding agent could deploy straight from it.

---

## A. Business context & scope

- **Legal entity / business unit being reconciled:** Acme Power & Light, Inc. — regulated electric utility, US entity (company DB `ACME`)
- **Close cadence:** `[x]` monthly
- **Approx. # of GL accounts in scope:** 600
- **Approx. # of reconciliations per close:** 150
- **Account groups in scope:** `[x]` Cash & equivalents `[x]` Accounts receivable `[x]` Accounts payable
  `[x]` Prepaid & other assets `[x]` Accrued liabilities `[x]` Intercompany
- **Currencies:** USD only
- **Default materiality / tolerance:** $25 for cash, $100 for sub-ledgers (overrides in §E)

## B. Treasury / bank statement inputs

### Source 1 — Wells Fargo (operating & payroll)
- **Institution / feed name:** Wells Fargo
- **Accounts it covers:** Operating cash ••4471 (GL 1010-00), Payroll ••8810 (GL 1020-00)
- **Delivery method:** `[x]` SFTP pull — `sftp.wellsfargo.com:/outbound/acme/`
- **File format:** `[x]` BAI2
- **Frequency:** daily prior-day; month-end statement on the 1st business day
- **Who holds the credentials / access:** Treasury team (SFTP key in Azure Key Vault)

### Source 2 — JPMorgan Chase (credit-card clearing)
- **Institution / feed name:** JPMorgan Chase
- **Accounts it covers:** CC clearing ••0091 (GL 1250-00)
- **Delivery method:** `[x]` Email mailbox (IMAP) — `treasury-stmts@acme.com` (Exchange Online, shared mailbox)
- **File format:** `[x]` PDF (OCR'd by Laserfiche on ingest)
- **Frequency:** monthly, 2nd business day
- **Who holds the credentials / access:** Treasury team (app password in Key Vault)

## C. General ledger inputs

- **GL / ERP system:** `[x]` Microsoft Dynamics GP (2018, on-prem)
- **Connection method:** `[x]` Direct database / ODBC (read-only) — server `GPSQL01`, db `ACME` (company), `DYNAMICS` (system)
- **What's extracted:** `[x]` period-end balance per account
- **Account/segment identifier:** main-subaccount, e.g. `1010-00` (GP `ACTNUMST`)
- **As-of / period handling:** period-end balance from `GL20000` (open year) / `GL30000` (history), keyed by `YEAR1` + `PERIODID`
- **Extract cadence:** nightly during close; on-demand re-pull from the recon board
- **Read-only guaranteed?** `[x]` yes — dedicated SQL login `acme_recon_ro` (db_datareader only)

## D. Document management system (DMS)

- **DMS in use:** `[x]` Laserfiche (Rio 11, on-prem; repository `ACME-FINANCE`)
- **Capture / OCR:** `[x]` the DMS OCRs on ingest
- **How recon references a document:** `[x]` Deep link / URL —
  `https://laserfiche.acme.internal/laserfiche/DocView.aspx?id={id}`
- **Access method for the software:** `[x]` REST API — Laserfiche Repository API, OAuth service app `recon-svc`
- **Retention / records policy to honor:** 7 years; no deletion by the app (records-managed in Laserfiche)

## E. Reconciliation rules

- **Match key:** bank account number → GL account map (table below)
- **Tolerance:** default per §A; overrides: Cash $25, Intercompany $100, CC clearing $25
- **FX handling:** none (USD only)
- **Definition of "reconciled":** matched within tolerance OR variance fully explained + approved
- **Recurring / timing items:** deposits in transit, outstanding checks — flag as timing, don't fail
- **Exception categories:** timing, unrecorded transaction, error, unknown
- **Account map** (statement source → GL account → tolerance):
  ```
  bank_4471  ->  GL 1010-00  ->  $25     # Wells Fargo operating
  bank_8810  ->  GL 1020-00  ->  $50     # Wells Fargo payroll
  cc_0091    ->  GL 1250-00  ->  $25     # Chase CC clearing
  ar_dom     ->  GL 1210-00  ->  $100    # AR sub-ledger
  ap_dom     ->  GL 2010-00  ->  $100    # AP sub-ledger
  ```

## F. Roles, access hierarchy & segregation of duties

- **Org-role hierarchy** (Entra ID groups):
  - Junior Accountant (tier 1) → `ACME\Recon-Junior`
  - Senior Accountant (tier 2) → `ACME\Recon-Senior`
  - Principal Accountant (tier 3) → `ACME\Recon-Principal`
  - Manager / Director (tier 4) → `ACME\Recon-Director`
- **Users & tiers sourced from:** `[x]` SSO groups (Entra ID, per §G)
- **Workflow-role capabilities** (our policy):

  | Org role | Prepare | Approve | Review |
  |---|---|---|---|
  | Junior Accountant | ✓ | | |
  | Senior Accountant | ✓ | ✓ | |
  | Principal Accountant | ✓ | ✓ | ✓ |
  | Manager / Director | ✓ | ✓ | ✓ |

- **Assignment model:** seniors and principals prepare their assigned accounts **and** approve other accountants' work; principals/directors review. Juniors prepare only.
- **Segregation of duties:** `[x]` a preparer cannot approve/review their own reconciliation; `[x]` approver tier ≥ preparer tier
- **Sign-off required to close:** `[x]` per reconciliation
- **Per-item work statuses:** `[x]` acknowledged `[x]` assigned `[x]` in progress `[x]` resolved `[x]` approved `[x]` reviewed

## G. Environment & deployment target

- **Where does this run?** `[x]` On-prem VM, Docker (RHEL 9, finance VLAN)
- **OS / runtime available:** RHEL 9, Docker + Compose
- **Hostname(s) for the app:** `recon.acme.internal` (internal only; no external exposure)
- **TLS / reverse proxy:** `[x]` existing proxy — F5 (TLS terminated at the F5; HTTP to the app)
- **Identity / SSO:** `[x]` SAML/OIDC — Entra ID (OIDC), groups from §F
- **TEST and PROD separation:** deploy TEST first on `recon-test.acme.internal`, then PROD after a clean close

## H. Security & secrets

- **How are secrets provided to the app?** `[x]` Secret manager — Azure Key Vault (CSI driver / env injection)
- **Data classification:** Confidential — financial
- **Network constraints:** finance VLAN reaches `GPSQL01:1433` and `laserfiche.acme.internal:443`; no outbound internet
- **Audit trail requirements:** immutable who/when on every prepare/approve/review; retained 7 years
- **Who may hold credentials:** the platform team (the app never stores raw secrets in the repo)

## I. Notifications & reporting

- **Notify on:** `[x]` new exception `[x]` assignment `[x]` sign-off `[x]` close-at-risk
- **Channel:** `[x]` Microsoft Teams (Finance — Close channel, incoming webhook in Key Vault)
- **Director dashboard wanted?** `[x]` yes
- **Close calendar / SLA:** each reconciliation done by WD+5; sign-off by WD+7

## J. Existing-systems inventory (anything else to wire)

- ERP: Dynamics GP 2018. Email: Exchange Online. DMS: Laserfiche Rio 11. Identity: Entra ID.
  Orchestration: existing Windows Task Scheduler (or the bundled n8n in TEST). BI: Power BI (reads the recon DB read-replica).

## K. Project / grant / FERC accounting

- **Project / grant / job accounting?** `[x]` yes — costs collected against capital projects (work orders), settled across multiple FERC accounts
- **Project / cost system:** `[x]` Dynamics GP Project Accounting
- **Reconciliation granularity:** `[x]` both — balance recs per account, **plus per-project** recs where one settlement document closes the multiple FERC accounts a capital project touches
- **Where allocation lines come from:** GP Project Accounting (PA tables) via the read-only GL adapter (`acme_recon_ro`)
- **FERC books?** `[x]` yes — `[x]` electric (18 CFR Part 101)
- **FERC range → Project assignment** (our `ferc/ferc_map.yaml`, customized from the electric default):

  | FERC range | Project | Expense type | Project association / notes |
  |---|---|---|---|
  | 107 | CWIP | Capital | **split by work order** — each capital project is its own grouping |
  | 350–359 | Transmission plant | Capital | settled to transmission capital projects |
  | 360–374 | Distribution plant | Capital | |
  | 500–557 | Production O&M | O&M | by generating station |
  | 560–576 | Transmission O&M | O&M | |
  | 580–598 | Distribution O&M | O&M | |
  | 440–457 | Operating revenues | Revenue | |
  | 920–935 | Administrative & general | O&M | overhead allocation pool |
- **FERC number extraction:** standalone 3-digit (e.g. `01-560-00 -> 560`)

> Note: for a utility, the §E account map keys on FERC accounts (e.g. `350 -> Transmission plant`,
> `560 -> Transmission O&M`), and the FERC classifier stamps each account's Project so project
> reconciliations group by function/work order. See [`ferc/README.md`](ferc/README.md).

---

## Minimum to start (already satisfied above)
- **§C** — Dynamics GP via read-only ODBC (`acme_recon_ro` on `GPSQL01`).
- **§B Source 1** — Wells Fargo BAI2 over SFTP.
- **§D** — Laserfiche via the Repository API.

→ Adapter selection for this example: GL `dynamics_gp`, treasury `sftp` (Wells Fargo) + `imap` (Chase),
DMS `laserfiche`. All three are stubs in `adapters/` with the interface + approach defined — the agent
implements them per the connection details above. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

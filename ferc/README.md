# FERC handling — account-range → Project

Regulated utilities keep their books on the **FERC Uniform System of Accounts (USoA)**, where the
3-digit account number *is* the functional structure (production / transmission / distribution / A&G /
CWIP / …). This module turns that into the **project-derivation rule** OpenRecon uses: it assigns a
**Project** to every GL account from the FERC range it falls in.

That's the missing piece for **project reconciliation** — because accounts sharing a FERC range belong
to the same function/project, the system can group the many accounts one expense touches into a single
reconciliation, justified by one supporting document, and settle them together.

## Use it

```python
from ferc.classifier import FERCClassifier, ferc_project

ferc_project("107")        # -> "CWIP — capital projects"
ferc_project("01-560-00")  # -> "Transmission O&M"
ferc_project("1010")       # -> "Unmapped — review"   (non-FERC)

c = FERCClassifier.from_yaml("ferc/ferc_map.yaml")     # your customized map
c.classify("107")          # -> {"ferc":107, "project":"CWIP — capital projects", "expense_type":"Capital", "note":"settle by work order"}
c.assign(accounts)         # stamps {"project":…, "expense_type":…} on each account dict (groups project recs)
```

**The map is authored in the intake, not in code.** Fill the **FERC range → Project assignment** table in
[`../INTAKE.md`](../INTAKE.md) §K (range · project · expense type · association) — that table *is* your
`ferc_map.yaml`. Each row carries a **Project** (the grouping), an **expense type** (Capital / O&M /
Revenue / Income / Balance sheet — used for grouping + reporting), and a free-form **association** (e.g.
"split CWIP by work order").

## The default map

`ferc_map.example.yaml` ships the **FERC electric** USoA (18 CFR Part 101) functional ranges — e.g.
`350–359 → Transmission plant`, `560–576 → Transmission O&M`, `106–107 → CWIP — capital projects`,
`920–935 → Administrative & general`. It is a **starting point**: review it against your actual chart of
accounts and override freely. **Gas** (18 CFR Part 201) and **oil pipeline** (Part 352) use different
numbers — supply your own ranges.

## Two things that are org-specific (configure, don't assume)

1. **The range → project map.** The default groups by FERC *function*. Your shop may want finer
   categories (e.g. CWIP split by work order, production by unit), or to map ranges to your own internal
   project codes. Edit the `ranges:` in your `ferc_map.yaml`.
2. **Extracting the FERC number from your COA code.** The default grabs the first standalone 3-digit token
   (`560`, `560-00`, `01-560-00`, `560.500`). If your COA *concatenates* the FERC account with a
   sub-account (e.g. `560500`), set `extract.regex: '^(\d{3})'` (or your pattern) in the map.

## How it feeds project reconciliation

```
GL account code ──ferc_project()──▶ Project (FERC function)
                                       │
        accounts sharing a Project ────┘
                                       ▼
   one project reconciliation  ←  one supporting document  →  settle all member accounts
   (sum of the allocated postings ties to the expense, within tolerance)
```

In the project-reconciliation model the `Project` stamped here is the `scope_ref` that groups a
reconciliation's member account lines. Set it in the deployment intake — see **§K** of
[`../INTAKE.md`](../INTAKE.md).

## Caveat

This classifies and groups; it does **not** compute the allocations themselves — those come from your
project/GL system (e.g. Dynamics GP Project Accounting) via the GL/project adapter. OpenRecon reconciles
*against* the books, it doesn't keep them. Validate the default ranges with your accounting team before
relying on them.

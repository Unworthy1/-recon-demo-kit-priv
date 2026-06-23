# Project funding-allocation map

How a project's cost is **spread across GL accounts** — authored by an accountant in a spreadsheet,
validated, and turned into the allocation lines a **project reconciliation** ties out.

A project is "fully funded" when the accounts that fund it add up to **100%**. You author *the spread
once* (a reusable funding model); each period, a project's actual cost × the spread = the expected
per-account allocation, which reconciliation checks against the actuals.

## The spreadsheet ([`funding-map.template.csv`](funding-map.template.csv))

One row per **project × account**. Columns:

| Column | Required | Meaning |
|---|---|---|
| `project_id` | ✓ | Stable project key (e.g. `PRJ-TX4471`) |
| `project_name` | | Human name |
| `account_or_range` | ✓ | A single GL account (`352`) **or** an inclusive numeric range (`560-598`, incl. FERC ranges) |
| `account_name` | | Human name for the account/range |
| `funding_pct` | ✓ | This account's share of the project — **a project's rows must total 100** |
| `expense_type` | | `Capital` / `O&M` / `Revenue` / `Income` / `Balance sheet` |
| `notes` | | Free text |

See [`funding-map.example.csv`](funding-map.example.csv) for a filled utility example (single codes
*and* FERC ranges; every project sums to 100%).

## Validate → emit → allocate ([`funding_map.py`](funding_map.py))

```bash
# 1) check the sheet: totals=100 per project, range syntax, no overlapping accounts
python projects/funding_map.py validate projects/funding-map.example.csv

# 2) emit the machine-readable allocation config (what an AI agent / the engine consumes)
python projects/funding_map.py emit projects/funding-map.example.csv

# 3) turn a project's period cost into allocation lines (they tie out to the total to the penny)
python projects/funding_map.py allocate projects/funding-map.example.csv PRJ-TX4471 2412800
```

**Validation rules:** each project's `funding_pct` totals 100 (±0.01); `account_or_range` parses;
no two rows in a project cover overlapping accounts/ranges; `expense_type` is recognized (warning only).
`emit`/`allocate` refuse to run until `validate` is clean.

## How it wires in

- The emitted config is the source of truth for **project reconciliation** allocations — `allocate()`
  produces the per-account `project_line` rows the engine reconciles (sum of allocations vs the source
  expense, within tolerance).
- Sits alongside the **FERC map** ([`../ferc/`](../ferc/README.md)): FERC ranges classify accounts into
  projects + expense types; this funding map says *by how much* each account funds the project.
- Authored config goes in [`../INTAKE.md`](../INTAKE.md) §K (project / FERC accounting). An agent can read
  the sheet, `validate`, and `emit` straight into the deployment config.

> **Roadmap:** an `.xlsx` version of the template (with per-project 100% sum-check formulas) and a
> `recon-projects` MCP tool (`validate` / `emit` / `allocate`) so an agent applies a customer's funding
> map end-to-end. Tracked in #23.

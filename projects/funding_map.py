"""Account/range → Project funding-allocation map.

An accountant authors a simple spreadsheet (CSV) that says, for each project, which GL accounts
(or account ranges, incl. FERC ranges) fund it and by what **percentage** — the percentages for a
project must sum to 100% to "fully fund" it. This module reads that sheet, validates it, and emits
the allocation config the reconciliation engine uses (and can turn a project's period cost into the
per-account allocation lines a project reconciliation ties out).

Sheet columns (header row required):
    project_id, project_name, account_or_range, account_name, funding_pct, expense_type, notes
Required per row: project_id, account_or_range, funding_pct.
`account_or_range` is a single code ("352") or an inclusive numeric range ("560-598").

CLI:
    python funding_map.py validate <csv>                 # OK / list of problems  (exit 0/1)
    python funding_map.py emit     <csv> [--json]        # the allocation config
    python funding_map.py allocate <csv> <project_id> <total>   # period cost -> allocation lines
"""
from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass

REQUIRED = ["project_id", "account_or_range", "funding_pct"]
KNOWN_EXPENSE_TYPES = {"Capital", "O&M", "Revenue", "Income", "Balance sheet"}
PCT_TOLERANCE = 0.01   # allow a hundredth of a point of rounding slop on the 100% check


@dataclass
class Matcher:
    """A single account code or an inclusive numeric range, matched against a GL account code."""
    raw: str
    kind: str               # "single" | "range"
    lo: int | None = None
    hi: int | None = None
    code: str | None = None

    def contains(self, account_code: str) -> bool:
        if self.kind == "single":
            return account_code.strip() == self.code
        digits = "".join(ch for ch in account_code if ch.isdigit())
        if not digits:
            return False
        return self.lo <= int(digits) <= self.hi

    def interval(self):
        """Numeric [lo, hi] for overlap math, or None for a non-numeric single."""
        if self.kind == "range":
            return (self.lo, self.hi)
        if self.code and self.code.isdigit():
            return (int(self.code), int(self.code))
        return None


def parse_matcher(raw: str) -> Matcher:
    raw = (raw or "").strip()
    if "-" in raw:
        a, b = (s.strip() for s in raw.split("-", 1))
        if a.isdigit() and b.isdigit():
            lo, hi = sorted((int(a), int(b)))
            return Matcher(raw, "range", lo=lo, hi=hi)
    return Matcher(raw, "single", code=raw)


def _overlap(m1: Matcher, m2: Matcher) -> bool:
    i1, i2 = m1.interval(), m2.interval()
    if i1 and i2:
        return i1[0] <= i2[1] and i2[0] <= i1[1]
    return m1.kind == "single" and m2.kind == "single" and m1.code == m2.code


def load(path: str):
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for ln, r in enumerate(csv.DictReader(f), start=2):   # header is line 1
            if not any((v or "").strip() for v in r.values()):
                continue                                       # skip blank lines
            rows.append((ln, r))
    return rows


def validate(rows):
    """Return (projects, errors). projects is keyed by id with parsed rows."""
    errors, warnings, projects = [], [], {}
    for ln, r in rows:
        missing = [c for c in REQUIRED if not (r.get(c) or "").strip()]
        if missing:
            errors.append(f"line {ln}: missing required {', '.join(missing)}")
            continue
        try:
            pct = float(r["funding_pct"])
        except ValueError:
            errors.append(f"line {ln}: funding_pct '{r['funding_pct']}' is not a number")
            continue
        pid = r["project_id"].strip()
        p = projects.setdefault(pid, {"name": (r.get("project_name") or "").strip(), "rows": []})
        p["rows"].append({
            "line": ln, "matcher": parse_matcher(r["account_or_range"]),
            "account_name": (r.get("account_name") or "").strip(), "pct": pct,
            "expense_type": (r.get("expense_type") or "").strip(),
        })

    for pid, p in projects.items():
        total = round(sum(x["pct"] for x in p["rows"]), 4)
        if abs(total - 100.0) > PCT_TOLERANCE:
            errors.append(f"project {pid}: funding %s sum to {total:g}, must total 100")
        ms = [x["matcher"] for x in p["rows"]]
        for a in range(len(ms)):
            for b in range(a + 1, len(ms)):
                if _overlap(ms[a], ms[b]):
                    errors.append(f"project {pid}: overlapping accounts '{ms[a].raw}' and '{ms[b].raw}'")
        for x in p["rows"]:
            if x["expense_type"] and x["expense_type"] not in KNOWN_EXPENSE_TYPES:
                warnings.append(f"project {pid} line {x['line']}: unrecognized expense_type '{x['expense_type']}'")
    return projects, errors, warnings


def to_config(projects) -> dict:
    """The machine-readable allocation config an agent/the engine consumes."""
    return {"projects": {pid: {
        "name": p["name"],
        "funding": [{"match": x["matcher"].raw, "kind": x["matcher"].kind, "pct": x["pct"],
                     "account_name": x["account_name"], "expense_type": x["expense_type"]}
                    for x in p["rows"]],
    } for pid, p in projects.items()}}


def allocate(project_cfg: dict, total: float):
    """Turn a project's period cost into allocation lines (last line absorbs the rounding residual,
    so the lines sum to `total` exactly — what a project reconciliation ties out)."""
    rows, lines, running = project_cfg["funding"], [], 0.0
    for i, x in enumerate(rows):
        amt = round(total - running, 2) if i == len(rows) - 1 else round(total * x["pct"] / 100.0, 2)
        running += amt
        lines.append({"match": x["match"], "account_name": x["account_name"], "pct": x["pct"], "allocated": amt})
    return lines


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    cmd, path = argv[0], argv[1]
    projects, errors, warnings = validate(load(path))
    if cmd == "validate":
        for w in warnings:
            print(f"  warn:  {w}")
        if errors:
            print(f"INVALID — {len(errors)} problem(s):")
            for e in errors:
                print(f"  ERROR: {e}")
            return 1
        n = len(projects)
        print(f"OK — {n} project(s), every funding spread totals 100%."
              + (f" ({len(warnings)} warning(s))" if warnings else ""))
        return 0
    if errors:
        print("Refusing — fix validation errors first (run `validate`).", file=sys.stderr)
        return 1
    if cmd == "emit":
        print(json.dumps(to_config(projects), indent=2))
        return 0
    if cmd == "allocate":
        pid, total = argv[2], float(argv[3])
        cfg = to_config(projects)["projects"][pid]
        lines = allocate(cfg, total)
        print(json.dumps({"project": pid, "total": total, "lines": lines,
                          "ties_out": round(sum(l["allocated"] for l in lines), 2) == round(total, 2)}, indent=2))
        return 0
    print(f"unknown command '{cmd}'"); return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""Generic CSV column-mapper with saved mapping profiles (#37).

Onboarding an odd ERP/bank/budget/billing export becomes CONFIGURATION, not code: a
MappingProfile records which column feeds which field, plus the file's conventions
(date format, decimal comma, debit/credit split columns, parenthesised negatives,
header-skip, sign flip). Profiles serialize to/from plain dicts — the stack stores
them in the `mapping_profile` table (versioned by updated_at) and the ingest API
applies them by name.

Targets and their required fields (everything else rides along in `raw`):
  statement  → source_account, stmt_date, amount            (feeds statement_line / #34)
  gl         → account, balance                             (feeds GLBalance)
  budget     → account, amount                              (feeds BudgetAmount)
  subledger  → account, balance                             (feeds SubledgerBalance)
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

REQUIRED = {
    "statement": ("source_account", "stmt_date", "amount"),
    "gl":        ("account", "balance"),
    "budget":    ("account", "amount"),
    "subledger": ("account", "balance"),
}
_MONEY_JUNK = re.compile(r"[$€£\s,]")


@dataclass
class MappingProfile:
    name: str
    target: str                                   # statement | gl | budget | subledger
    columns: dict = field(default_factory=dict)   # field -> source column header
    date_format: str = "iso"                      # 'iso' or a strptime format
    decimal_comma: bool = False                   # 1.234,56 style amounts
    debit_col: Optional[str] = None               # two-column amount layout:
    credit_col: Optional[str] = None              #   amount = credit − debit
    skip_rows: int = 0                            # junk lines above the header
    sign_flip: bool = False                       # export uses the opposite sign convention
    account_default: Optional[str] = None         # single-account files with no account column

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in (
            "name", "target", "columns", "date_format", "decimal_comma",
            "debit_col", "credit_col", "skip_rows", "sign_flip", "account_default")}

    @classmethod
    def from_dict(cls, d: dict) -> "MappingProfile":
        known = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        return cls(**known)

    def validate(self) -> list[str]:
        errs = []
        if self.target not in REQUIRED:
            return [f"unknown target '{self.target}'"]
        two_col = bool(self.debit_col or self.credit_col)
        for f_ in REQUIRED[self.target]:
            mapped = f_ in self.columns
            if f_ in ("amount", "balance") and two_col:
                mapped = True
            if f_ == "source_account" and self.account_default:
                mapped = True
            if f_ == "account" and self.account_default:
                mapped = True
            if not mapped:
                errs.append(f"required field '{f_}' has no column mapping")
        return errs


def _amount(raw: str, profile: MappingProfile) -> Optional[float]:
    s = (raw or "").strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    if profile.decimal_comma:
        s = s.replace(".", "").replace(",", ".")
    s = _MONEY_JUNK.sub("", s)
    if not s or s in ("-", "+"):
        return None
    v = float(s)
    if neg:
        v = -abs(v)
    return v


def _date(raw: str, profile: MappingProfile) -> date:
    s = (raw or "").strip()
    if profile.date_format == "iso":
        return date.fromisoformat(s[:10])
    return datetime.strptime(s, profile.date_format).date()


def parse_csv(content: bytes, profile: MappingProfile) -> dict:
    """Apply a profile to a CSV export. Returns {rows: [...], errors: [...], skipped: n}.
    Rows are normalized dicts for the profile's target; bad rows are reported with their
    line number and reason — never silently dropped."""
    errs = profile.validate()
    if errs:
        return {"rows": [], "errors": [{"row": 0, "error": e} for e in errs], "skipped": 0}
    text = content.decode("utf-8-sig", "replace")
    lines = text.splitlines()[profile.skip_rows:]
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    rows, errors = [], []
    for n, rec in enumerate(reader, 1):
        try:
            out = {"raw": dict(rec)}
            for f_, col in profile.columns.items():
                if col not in rec:
                    raise KeyError(f"column '{col}' not in file")
                out[f_] = (rec[col] or "").strip()
            # amount: single mapped column, or debit/credit split
            amt_field = "amount" if profile.target in ("statement", "budget") else "balance"
            if profile.debit_col or profile.credit_col:
                dr = _amount(rec.get(profile.debit_col or "", ""), profile) or 0.0
                cr = _amount(rec.get(profile.credit_col or "", ""), profile) or 0.0
                out[amt_field] = round(cr - dr, 2)
            elif amt_field in out:
                v = _amount(out[amt_field], profile)
                if v is None:
                    raise ValueError(f"unparseable {amt_field}: '{out[amt_field]}'")
                out[amt_field] = v
            if profile.sign_flip:
                out[amt_field] = -out[amt_field]
            if "stmt_date" in out:
                out["stmt_date"] = _date(out["stmt_date"], profile)
            for acct_field in ("source_account", "account"):
                if acct_field in REQUIRED[profile.target] and not out.get(acct_field):
                    if profile.account_default:
                        out[acct_field] = profile.account_default
                    else:
                        raise ValueError(f"empty {acct_field}")
            rows.append(out)
        except (KeyError, ValueError, TypeError) as e:
            errors.append({"row": n, "error": str(e)})
    return {"rows": rows, "errors": errors, "skipped": profile.skip_rows}

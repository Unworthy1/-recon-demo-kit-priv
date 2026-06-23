"""FERC account-range -> Project classifier.

Regulated utilities keep their books on the FERC Uniform System of Accounts (USoA), where the
3-digit account number encodes the function (production / transmission / distribution / A&G / …).
This module assigns a **Project** (plus an **expense type** and free-form **association**) to a GL
account from the FERC range it falls in — the project-derivation rule that lets project
reconciliations group the many accounts one expense touches (see ferc/README.md).

The mapping is meant to be authored by the user in INTAKE.md §K (a fillable table) and dropped here
as ferc_map.yaml. The default below is the FERC **electric** USoA (18 CFR Part 101) as a starting
point — review it against your actual chart of accounts; gas (Part 201) / oil pipeline (Part 352)
use different numbers.
"""
from __future__ import annotations

import re
from pathlib import Path

# (low, high, project, expense_type) — inclusive 3-digit FERC ranges. expense_type is one of
# Capital / O&M / Revenue / Income / Balance sheet (free text; used for grouping + reporting).
DEFAULT_ELECTRIC = [
    (101, 101, "Plant in service (control)", "Capital"),
    (105, 105, "Plant held for future use", "Capital"),
    (106, 107, "CWIP — capital projects", "Capital"),         # 107 = Construction Work In Progress
    (108, 115, "Accumulated depreciation & plant adjustments", "Capital"),
    (151, 174, "Materials, inventory & current assets", "Balance sheet"),
    (181, 191, "Deferred debits / regulatory assets", "Balance sheet"),
    (201, 253, "Liabilities & equity", "Balance sheet"),
    (301, 303, "Intangible plant", "Capital"),
    (310, 347, "Production plant", "Capital"),
    (350, 359, "Transmission plant", "Capital"),
    (360, 374, "Distribution plant", "Capital"),
    (380, 388, "Regional transmission & market plant", "Capital"),
    (389, 399, "General plant", "Capital"),
    (400, 432, "Income accounts", "Income"),
    (440, 457, "Operating revenues", "Revenue"),
    (500, 557, "Production O&M", "O&M"),
    (560, 576, "Transmission O&M", "O&M"),
    (580, 598, "Distribution O&M", "O&M"),
    (901, 905, "Customer accounts", "O&M"),
    (907, 910, "Customer service & information", "O&M"),
    (911, 917, "Sales", "O&M"),
    (920, 935, "Administrative & general (A&G)", "O&M"),
]

DEFAULT_EXTRACT = r"(?<!\d)(\d{3})(?!\d)"


def _norm(r) -> dict:
    """Accept a range as a dict or a [low, high, project, expense_type?, note?] list."""
    if isinstance(r, dict):
        return {"low": int(r["low"]), "high": int(r["high"]), "project": r["project"],
                "expense_type": r.get("expense_type", ""), "note": r.get("note", "")}
    return {"low": int(r[0]), "high": int(r[1]), "project": r[2],
            "expense_type": r[3] if len(r) > 3 else "", "note": r[4] if len(r) > 4 else ""}


class FERCClassifier:
    def __init__(self, ranges=None, default="Unmapped — review", extract=DEFAULT_EXTRACT):
        self.ranges = sorted((_norm(r) for r in (ranges or DEFAULT_ELECTRIC)), key=lambda d: d["low"])
        self.default = default
        self.extract = extract if hasattr(extract, "search") else re.compile(extract)

    def ferc_number(self, account) -> int | None:
        """Pull the 3-digit FERC account number out of a COA code string (or int)."""
        if isinstance(account, int):
            return account if 100 <= account <= 999 else None
        m = self.extract.search(str(account))
        if not m:
            return None
        n = int(m.group(1))
        return n if 100 <= n <= 999 else None

    def classify(self, account) -> dict:
        """Full classification: {ferc, project, expense_type, note}. Falls to default if non-FERC."""
        n = self.ferc_number(account)
        if n is not None:
            for r in self.ranges:
                if r["low"] <= n <= r["high"]:
                    return {"ferc": n, "project": r["project"],
                            "expense_type": r["expense_type"], "note": r["note"]}
        return {"ferc": n, "project": self.default, "expense_type": "", "note": ""}

    def project_for(self, account) -> str:
        """The Project (functional category) for a GL account, by its FERC range."""
        return self.classify(account)["project"]

    def assign(self, accounts) -> list[dict]:
        """Stamp project + expense_type onto each account dict (expects a 'code' key)."""
        out = []
        for a in accounts:
            c = self.classify(a.get("code", a.get("id", "")))
            out.append({**a, "project": c["project"], "expense_type": c["expense_type"]})
        return out

    @classmethod
    def from_yaml(cls, path: str) -> "FERCClassifier":
        import yaml  # lazy — only needed when loading a custom map
        cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        ex = (cfg.get("extract") or {}).get("regex")
        return cls(ranges=cfg.get("ranges") or None, default=cfg.get("default", "Unmapped — review"),
                   extract=re.compile(ex) if ex else DEFAULT_EXTRACT)


# module-level convenience using the default electric map
_default = FERCClassifier()
def ferc_project(account) -> str:
    """Project for a FERC account using the default electric USoA map."""
    return _default.project_for(account)

"""Project-cost allocation adapters (INTAKE §K).

Reference: CSVProjectAdapter. Stub: DynamicsGPProjectAdapter.
Each returns, per project/expense, the one source amount + the allocation lines across (FERC)
accounts that a project reconciliation ties out and settles together. The FERC range -> Project
grouping is applied above this layer (see ferc/classifier.py).
"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Iterable

from .base import AllocationLine, ProjectAdapter, ProjectExpense, register


@register("project", "csv_allocations")
class CSVProjectAdapter(ProjectAdapter):
    """READY. Reads from two CSVs:
       projects.csv      — project_id,name,wo,vendor,source_amount,source_doc,source_ref
       project_lines.csv — project_id,gl_code,gl_name,allocated_amount
    """
    name = "project:csv_allocations"

    def __init__(self, projects_path: str, lines_path: str):
        self.projects_path, self.lines_path = projects_path, lines_path

    def fetch_projects(self, period_end: date) -> Iterable[ProjectExpense]:
        lines = defaultdict(list)
        with open(Path(self.lines_path), newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                lines[r["project_id"]].append(AllocationLine(
                    gl_account=r["gl_code"].strip(),
                    amount=float(str(r["allocated_amount"]).replace(",", "").replace("$", "")),
                    name=r.get("gl_name", "")))
        with open(Path(self.projects_path), newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                yield ProjectExpense(
                    project_id=r["project_id"], name=r["name"],
                    source_amount=float(str(r["source_amount"]).replace(",", "").replace("$", "")),
                    lines=lines.get(r["project_id"], []),
                    wo=r.get("wo", ""), vendor=r.get("vendor", ""),
                    source_doc=r.get("source_doc", ""), source_ref=r.get("source_ref", ""))


@register("project", "dynamics_gp")
class DynamicsGPProjectAdapter(ProjectAdapter):
    """STUB — Dynamics GP Project Accounting (INTAKE §K 'GP Project Accounting'). Implement
    fetch_projects() against the PA tables (e.g. PA01301 projects + PA cost-transaction tables) to
    return each project's source cost and its GL allocation lines. Read-only service account."""
    name = "project:dynamics_gp"

    def __init__(self, dsn: str, company_db: str = "DYNAMICS"):
        self.dsn, self.company_db = dsn, company_db

    def fetch_projects(self, period_end: date) -> Iterable[ProjectExpense]:
        raise NotImplementedError("Implement DynamicsGPProjectAdapter.fetch_projects via the GP PA tables (read-only).")

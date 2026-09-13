"""Prep rules (#42) — the transformation layer between parsing and load.

An ordered, declarative rule list turns what a bank or ERP export *says* into what matching
*needs*: a check number pulled out of a memo, a bank alias mapped to the canonical account, a
composite reference, net = gross − fee, a default for an empty field, zero-amount memo lines
dropped. Rules are data (JSON) saved as a named rule set — onboarding a quirk is configuration,
not a release.

    out = prep.apply(rows, rules)
    out["rows"]      # transformed rows, each with a `_trace` of what changed and which rule did it
    out["dropped"]   # rows removed by a filter — kept as evidence, never silently lost
    out["errors"]    # rows a rule could not process (they are NOT loaded)
    out["stats"]     # per-rule applied / dropped / error counts

Rows are plain dicts. Statement rows carry source_account, stmt_date, amount, description,
bank_ref (+ currency for bank formats); CSV rows also carry `raw` — the source columns, addressable
as `raw.<Column>`. Any other name is a scratch field: rules may write and read it, and it is
discarded at load (still visible in the trace).

Ops (every rule also accepts `when` — a condition — and `label`, free text shown when a line is
explained):
  lookup   {field, into?, map, case_insensitive?, on_missing: keep|default|error, default?}
  extract  {field, pattern, into, group? (int or name, default 1), overwrite?, required?}
  concat   {template: "CHK-{bank_ref}", into, overwrite?}   — skipped if a referenced field is empty
  calc     {expr: "amount - raw.Fee", into, round? (default 2)}   — + − × ÷, parentheses, numbers,
           field names, f("raw.Column With Spaces"); an empty operand is a row error
  fill     {field, value, overwrite?}                        — default: only when empty
  filter   {when}                                            — drop matching rows

Conditions: {field, op, value?} with op in eq ne gt gte lt lte empty not_empty contains matches in;
compose with {all: [...]}, {any: [...]}, {not: {...}}.

Safety: no eval. calc parses with `ast` and walks a whitelist; templates substitute `{name}` by
regex (no str.format attribute access); regex patterns are length-capped, compiled at validation,
and only ever searched against the first 1,000 characters of a field.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

MAX_RULES = 100
MAX_PATTERN = 200
MAX_SCAN = 1000
OPS = ("lookup", "extract", "concat", "calc", "fill", "filter")
COND_OPS = ("eq", "ne", "gt", "gte", "lt", "lte", "empty", "not_empty", "contains", "matches", "in")
_NAME = r"[A-Za-z_][\w]*(?:\.[^{}]+)?"
_TEMPLATE_REF = re.compile(r"\{(" + _NAME + r")\}")


class RuleError(ValueError):
    """A rule could not process a row (the row is reported, not loaded)."""


# ─────────────────────────── field access ───────────────────────────

def get(row: dict, name: str) -> Any:
    if name.startswith("raw."):
        return (row.get("raw") or {}).get(name[4:])
    return row.get(name)


def _put(row: dict, name: str, value: Any) -> None:
    if name.startswith("raw."):
        row.setdefault("raw", {})[name[4:]] = value
    else:
        row[name] = value


def _empty(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, float):
        return format(Decimal(str(v)).normalize(), "f")
    return str(v)


def _num(v: Any) -> Decimal | None:
    if isinstance(v, bool) or _empty(v):
        return None
    try:
        return Decimal(str(v).strip())
    except InvalidOperation:
        return None


def jsonable(v: Any) -> Any:
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    return v


# ─────────────────────────── conditions ───────────────────────────

def _cmp(a: Any, b: Any) -> tuple:
    na, nb = _num(a), _num(b)
    if na is not None and nb is not None:
        return na, nb
    return _text(a), _text(b)


def test(row: dict, cond: dict | None) -> bool:
    if not cond:
        return True
    if "all" in cond:
        return all(test(row, c) for c in cond["all"])
    if "any" in cond:
        return any(test(row, c) for c in cond["any"])
    if "not" in cond:
        return not test(row, cond["not"])
    v, op, want = get(row, cond["field"]), cond["op"], cond.get("value")
    if op == "empty":
        return _empty(v)
    if op == "not_empty":
        return not _empty(v)
    if op == "contains":
        return _text(want).lower() in _text(v).lower()
    if op == "matches":
        return re.search(want, _text(v)[:MAX_SCAN]) is not None
    if op == "in":
        return _text(v) in {_text(x) for x in want}
    a, b = _cmp(v, want)
    try:
        return {"eq": a == b, "ne": a != b, "gt": a > b, "gte": a >= b,
                "lt": a < b, "lte": a <= b}[op]
    except TypeError:                                   # mixed number/text comparison
        return False


# ─────────────────────────── calc (whitelisted AST) ───────────────────────────

_BIN = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b}


def _dotted(node) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


def _check_expr(node) -> None:
    if isinstance(node, ast.Expression):
        return _check_expr(node.body)
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        _check_expr(node.left); _check_expr(node.right); return
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return _check_expr(node.operand)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return
    if _dotted(node):
        return
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "f"
            and len(node.args) == 1 and not node.keywords
            and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
        return
    raise ValueError(f"calc: unsupported syntax '{ast.dump(node)[:60]}'")


def _eval(node, row: dict) -> Decimal:
    if isinstance(node, ast.Expression):
        return _eval(node.body, row)
    if isinstance(node, ast.BinOp):
        a, b = _eval(node.left, row), _eval(node.right, row)
        if isinstance(node.op, ast.Div) and b == 0:
            raise RuleError("calc: division by zero")
        return _BIN[type(node.op)](a, b)
    if isinstance(node, ast.UnaryOp):
        v = _eval(node.operand, row)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.Constant):
        return Decimal(str(node.value))
    name = _dotted(node) or node.args[0].value
    v = _num(get(row, name))
    if v is None:
        raw = get(row, name)
        raise RuleError(f"calc: '{name}' is {'empty' if _empty(raw) else 'not a number: ' + repr(raw)}")
    return v


# ─────────────────────────── validation ───────────────────────────

def _validate_cond(cond, where: str, errs: list) -> None:
    if not isinstance(cond, dict):
        errs.append(f"{where}: condition must be an object"); return
    for k in ("all", "any"):
        if k in cond:
            if not isinstance(cond[k], list) or not cond[k]:
                errs.append(f"{where}: '{k}' needs a non-empty list")
            else:
                for c in cond[k]:
                    _validate_cond(c, where, errs)
            return
    if "not" in cond:
        return _validate_cond(cond["not"], where, errs)
    if not isinstance(cond.get("field"), str) or not cond["field"]:
        errs.append(f"{where}: condition needs a 'field'")
    op = cond.get("op")
    if op not in COND_OPS:
        errs.append(f"{where}: condition op must be one of {', '.join(COND_OPS)}"); return
    if op not in ("empty", "not_empty") and "value" not in cond:
        errs.append(f"{where}: condition op '{op}' needs a 'value'")
    if op == "in" and not isinstance(cond.get("value"), list):
        errs.append(f"{where}: 'in' needs a list value")
    if op == "matches":
        _validate_pattern(cond.get("value"), where, errs)


def _validate_pattern(p, where: str, errs: list):
    if not isinstance(p, str) or not p:
        errs.append(f"{where}: pattern must be a non-empty string"); return None
    if len(p) > MAX_PATTERN:
        errs.append(f"{where}: pattern longer than {MAX_PATTERN} characters"); return None
    try:
        return re.compile(p)
    except re.error as e:
        errs.append(f"{where}: invalid regex ({e})"); return None


def validate(rules: Any) -> list[str]:
    """Every problem with a rule list, human-readable. Empty list = valid."""
    if not isinstance(rules, list):
        return ["rules must be a list"]
    if len(rules) > MAX_RULES:
        return [f"at most {MAX_RULES} rules"]
    errs: list[str] = []
    for i, r in enumerate(rules, 1):
        w = f"rule {i}"
        if not isinstance(r, dict):
            errs.append(f"{w}: must be an object"); continue
        op = r.get("op")
        if op not in OPS:
            errs.append(f"{w}: op must be one of {', '.join(OPS)}"); continue
        w = f"rule {i} ({op})"
        if "when" in r:
            _validate_cond(r["when"], w, errs)

        def need(*keys, kind=str):
            for k in keys:
                if not isinstance(r.get(k), kind) or (kind is str and not r[k]):
                    errs.append(f"{w}: '{k}' is required")

        if op == "lookup":
            need("field")
            if not isinstance(r.get("map"), dict) or not r["map"]:
                errs.append(f"{w}: 'map' must be a non-empty object")
            if r.get("on_missing", "keep") not in ("keep", "default", "error"):
                errs.append(f"{w}: on_missing must be keep | default | error")
            if r.get("on_missing") == "default" and "default" not in r:
                errs.append(f"{w}: on_missing=default needs a 'default'")
        elif op == "extract":
            need("field", "into")
            rx = _validate_pattern(r.get("pattern"), w, errs)
            g = r.get("group", 1)
            if rx is not None:
                if isinstance(g, int) and not isinstance(g, bool):
                    if g < 0 or g > rx.groups:
                        errs.append(f"{w}: group {g} does not exist (pattern has {rx.groups})")
                elif isinstance(g, str):
                    if g not in rx.groupindex:
                        errs.append(f"{w}: named group '{g}' not in pattern")
                else:
                    errs.append(f"{w}: group must be a number or a name")
        elif op == "concat":
            need("template", "into")
            if isinstance(r.get("template"), str) and not _TEMPLATE_REF.search(r["template"]):
                errs.append(f"{w}: template references no {{field}}")
        elif op == "calc":
            need("expr", "into")
            if isinstance(r.get("expr"), str) and r["expr"]:
                try:
                    _check_expr(ast.parse(r["expr"], mode="eval"))
                except (SyntaxError, ValueError) as e:
                    errs.append(f"{w}: {e}")
            rd = r.get("round", 2)
            if not isinstance(rd, int) or isinstance(rd, bool) or not 0 <= rd <= 6:
                errs.append(f"{w}: round must be an integer 0-6")
        elif op == "fill":
            need("field")
            if "value" not in r:
                errs.append(f"{w}: 'value' is required")
        elif op == "filter":
            if "when" not in r:
                errs.append(f"{w}: a filter needs a 'when' condition")
    return errs


def fingerprint(rules: list) -> str:
    """Stable hash of a rule list — recorded per batch so an explanation names the exact version."""
    return hashlib.sha256(json.dumps(rules, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


# ─────────────────────────── application ───────────────────────────

def _record(row: dict, i: int, rule: dict, field: str, before: Any, after: Any) -> None:
    if before == after:
        return
    row["_trace"].append({"rule": i, "op": rule["op"], "label": rule.get("label", ""),
                          "field": field, "before": jsonable(before), "after": jsonable(after)})


def _apply_one(row: dict, i: int, r: dict) -> bool:
    """Apply one rule to a row in place. Returns False when the row is dropped."""
    op = r["op"]
    if op == "filter":
        return False
    if op == "lookup":
        into = r.get("into") or r["field"]
        key = _text(get(row, r["field"])).strip()
        table = r["map"]
        if r.get("case_insensitive"):
            table = {str(k).lower(): v for k, v in table.items()}
            key = key.lower()
        before = get(row, into)
        if key in table:
            _put(row, into, table[key])
        elif r.get("on_missing", "keep") == "default":
            _put(row, into, r["default"])
        elif r.get("on_missing") == "error":
            raise RuleError(f"lookup: no entry for '{key}' in {r['field']}")
        _record(row, i, r, into, before, get(row, into))
    elif op == "extract":
        before = get(row, r["into"])
        if not _empty(before) and not r.get("overwrite"):
            return True
        m = re.search(r["pattern"], _text(get(row, r["field"]))[:MAX_SCAN])
        if not m:
            if r.get("required"):
                raise RuleError(f"extract: pattern did not match {r['field']}")
            return True
        val = m.group(r.get("group", 1))
        if val is None:
            return True
        _put(row, r["into"], val.strip())
        _record(row, i, r, r["into"], before, get(row, r["into"]))
    elif op == "concat":
        before = get(row, r["into"])
        if not _empty(before) and not r.get("overwrite", True):
            return True
        refs = _TEMPLATE_REF.findall(r["template"])
        if any(_empty(get(row, n)) for n in refs):
            return True
        _put(row, r["into"], _TEMPLATE_REF.sub(lambda m: _text(get(row, m.group(1))).strip(), r["template"]))
        _record(row, i, r, r["into"], before, get(row, r["into"]))
    elif op == "calc":
        before = get(row, r["into"])
        v = _eval(ast.parse(r["expr"], mode="eval"), row)
        q = Decimal(1).scaleb(-r.get("round", 2))
        _put(row, r["into"], float(v.quantize(q, rounding=ROUND_HALF_UP)))
        _record(row, i, r, r["into"], before, get(row, r["into"]))
    elif op == "fill":
        before = get(row, r["field"])
        if _empty(before) or r.get("overwrite"):
            _put(row, r["field"], r["value"])
            _record(row, i, r, r["field"], before, get(row, r["field"]))
    return True


def apply(rows: list[dict], rules: list[dict]) -> dict:
    """Run the rules in order over every row. Rules must already be valid (see validate())."""
    stats = [{"rule": i, "op": r["op"], "label": r.get("label", ""), "applied": 0, "dropped": 0, "errors": 0}
             for i, r in enumerate(rules, 1)]
    out, dropped, errors = [], [], []
    for n, src in enumerate(rows, 1):
        row = dict(src)
        if isinstance(src.get("raw"), dict):
            row["raw"] = dict(src["raw"])
        row["_trace"] = []
        keep = True
        for i, r in enumerate(rules, 1):
            try:
                if not test(row, r.get("when")):
                    continue
                n_before = len(row["_trace"])
                if not _apply_one(row, i, r):
                    stats[i - 1]["dropped"] += 1
                    dropped.append({"row": n, "rule": i, "label": r.get("label", ""),
                                    "data": {k: jsonable(v) for k, v in src.items()}})
                    keep = False
                    break
                if len(row["_trace"]) > n_before:
                    stats[i - 1]["applied"] += 1
            except (RuleError, re.error) as e:
                stats[i - 1]["errors"] += 1
                errors.append({"row": n, "rule": i, "error": str(e)})
                keep = False
                break
        if keep:
            out.append(row)
    return {"rows": out, "dropped": dropped, "errors": errors, "stats": stats}


# ─────────────────────────── statement target ───────────────────────────

def finalize_statement(row: dict) -> dict:
    """Coerce a prepped row back to the statement_line contract; raise RuleError if a rule left it
    unloadable. Scratch fields are discarded here (they survive in `_trace`)."""
    acct = _text(row.get("source_account")).strip()
    if not acct:
        raise RuleError("source_account is empty after prep")
    amt = _num(row.get("amount"))
    if amt is None:
        raise RuleError(f"amount is not a number after prep: {row.get('amount')!r}")
    d = row.get("stmt_date")
    if isinstance(d, datetime):
        d = d.date()
    elif not isinstance(d, date):
        try:
            d = date.fromisoformat(_text(d)[:10])
        except ValueError:
            raise RuleError(f"stmt_date is not a date after prep: {d!r}")
    ref = row.get("bank_ref")
    return {"source_account": acct, "stmt_date": d, "amount": float(amt),
            "description": _text(row.get("description")),
            "bank_ref": _text(ref).strip() or None, "_trace": row.get("_trace", [])}

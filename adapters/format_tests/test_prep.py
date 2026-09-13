"""Prep rule tests (#42) — offline, no deps, in the test_formats idiom.

Run:  py -3 adapters/format_tests/test_prep.py
"""
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from adapters.formats import csvmap, prep                     # noqa: E402

_R = []
def check(name, cond, detail=""):
    _R.append((name, bool(cond), "" if cond else str(detail)))


def row(**kw):
    base = {"source_account": "bank_4471", "stmt_date": date(2026, 5, 29), "amount": -2450.00,
            "description": "CHECK 2201 VENDOR", "bank_ref": None}
    base.update(kw)
    return base


def run(rows, rules):
    errs = prep.validate(rules)
    assert not errs, errs
    return prep.apply(rows, rules)


# ─────────────────────────── ops ───────────────────────────
def test_extract():
    rules = [{"op": "extract", "field": "description", "pattern": r"CHECK\s+(\d+)", "into": "bank_ref",
              "label": "check number from memo"}]
    out = run([row(), row(description="WIRE IN", bank_ref=None)], rules)
    r0, r1 = out["rows"]
    check("extract: check number pulled", r0["bank_ref"] == "2201", r0)
    check("extract: trace names rule + label",
          r0["_trace"] == [{"rule": 1, "op": "extract", "label": "check number from memo",
                            "field": "bank_ref", "before": None, "after": "2201"}], r0["_trace"])
    check("extract: no match is a no-op, not an error", r1["bank_ref"] is None and not out["errors"])
    check("extract: stats", out["stats"][0]["applied"] == 1, out["stats"])

    keep = run([row(bank_ref="CHK-2201")], rules)["rows"][0]
    check("extract: existing value kept without overwrite", keep["bank_ref"] == "CHK-2201" and not keep["_trace"])
    named = run([row()], [{"op": "extract", "field": "description", "pattern": r"CHECK\s+(?P<no>\d+)",
                           "into": "check_no", "group": "no"}])["rows"][0]
    check("extract: named group into scratch field", named["check_no"] == "2201", named)
    req = run([row(description="ACH")], [dict(rules[0], required=True)])
    check("extract: required + no match = row error, row not loaded",
          not req["rows"] and req["errors"][0]["rule"] == 1, req)


def test_lookup():
    rules = [{"op": "lookup", "field": "source_account", "map": {"WF-OPER-4471": "bank_4471"},
              "case_insensitive": True}]
    out = run([row(source_account="wf-oper-4471"), row(source_account="other")], rules)
    check("lookup: alias mapped case-insensitively", out["rows"][0]["source_account"] == "bank_4471", out)
    check("lookup: miss kept by default", out["rows"][1]["source_account"] == "other")
    d = run([row(source_account="zzz")], [dict(rules[0], on_missing="default", default="suspense")])
    check("lookup: on_missing=default", d["rows"][0]["source_account"] == "suspense", d)
    e = run([row(source_account="zzz")], [dict(rules[0], on_missing="error")])
    check("lookup: on_missing=error → row error", not e["rows"] and "no entry" in e["errors"][0]["error"], e)
    into = run([row(description="ACME CORP")], [{"op": "lookup", "field": "description", "into": "vendor",
                                                  "map": {"ACME CORP": "V-100"}}])["rows"][0]
    check("lookup: into a separate field", into["vendor"] == "V-100" and into["description"] == "ACME CORP")


def test_concat():
    rules = [{"op": "concat", "template": "CHK-{bank_ref}", "into": "bank_ref"}]
    out = run([row(bank_ref="2201"), row(bank_ref="")], rules)
    check("concat: prefix composed", out["rows"][0]["bank_ref"] == "CHK-2201", out["rows"][0])
    check("concat: skipped when a referenced field is empty (no bare 'CHK-')",
          out["rows"][1]["bank_ref"] == "", out["rows"][1])
    key = run([{"raw": {"Batch No": "B7", "Seq": "3"}, **row()}],
              [{"op": "concat", "template": "{raw.Batch No}/{raw.Seq}", "into": "bank_ref"}])["rows"][0]
    check("concat: raw columns with spaces", key["bank_ref"] == "B7/3", key)


def test_calc():
    csv_row = {**row(amount=1000.00), "raw": {"Fee": "12.35", "Gross Amt": "1012.35"}}
    out = run([csv_row], [{"op": "calc", "expr": "amount - raw.Fee", "into": "net"},
                          {"op": "calc", "expr": 'f("raw.Gross Amt") - raw.Fee', "into": "amount"}])
    r = out["rows"][0]
    check("calc: net = amount - fee", r["net"] == 987.65, r)
    check("calc: f() for columns with spaces", r["amount"] == 1000.00, r)
    check("calc: decimal-safe", run([row(amount=0.1)], [{"op": "calc", "expr": "amount + 0.2",
                                                         "into": "amount"}])["rows"][0]["amount"] == 0.3)
    e = run([row()], [{"op": "calc", "expr": "amount - fee", "into": "amount"}])
    check("calc: empty operand is a row error", not e["rows"] and "'fee' is empty" in e["errors"][0]["error"], e)
    z = run([row()], [{"op": "calc", "expr": "amount / 0", "into": "x"}])
    check("calc: division by zero is a row error", z["errors"], z)
    check("calc: rounding", run([row(amount=10)], [{"op": "calc", "expr": "amount / 3", "into": "x",
                                                     "round": 4}])["rows"][0]["x"] == 3.3333)


def test_fill_filter_when():
    rules = [{"op": "filter", "when": {"field": "amount", "op": "eq", "value": 0}, "label": "memo lines"},
             {"op": "fill", "field": "description", "value": "(no memo)"},
             {"op": "fill", "field": "bank_ref", "value": "WIRE", "overwrite": True,
              "when": {"field": "description", "op": "contains", "value": "wire"}}]
    src = [row(amount=0, description="BALANCE MEMO"), row(description=""), row(description="Wire in", bank_ref="X")]
    out = run(src, rules)
    check("filter: zero-amount memo dropped", len(out["rows"]) == 2 and len(out["dropped"]) == 1, out)
    check("filter: dropped row kept as evidence with rule + label",
          out["dropped"][0]["rule"] == 1 and out["dropped"][0]["label"] == "memo lines"
          and out["dropped"][0]["data"]["description"] == "BALANCE MEMO"
          and out["dropped"][0]["data"]["stmt_date"] == "2026-05-29", out["dropped"])
    check("fill: only when empty", out["rows"][0]["description"] == "(no memo)"
          and out["rows"][1]["description"] == "Wire in")
    check("when: case-insensitive contains gates overwrite", out["rows"][1]["bank_ref"] == "WIRE", out["rows"][1])
    check("filter stops later rules for that row", out["stats"][1]["applied"] == 1, out["stats"])


def test_conditions():
    r = row(amount=-2450.0, description="CHECK 2201 VENDOR", bank_ref=None)
    T = lambda c: prep.test(r, c)
    check("cond: numeric lt", T({"field": "amount", "op": "lt", "value": "0"}))
    check("cond: numeric vs text never raises", T({"field": "description", "op": "gt", "value": 5}) in (True, False))
    check("cond: date compares as ISO", T({"field": "stmt_date", "op": "gte", "value": "2026-05-01"}))
    check("cond: matches", T({"field": "description", "op": "matches", "value": r"^CHECK \d{4}"}))
    check("cond: in", T({"field": "source_account", "op": "in", "value": ["bank_4471", "bank_8810"]}))
    check("cond: empty", T({"field": "bank_ref", "op": "empty"}))
    check("cond: all/any/not",
          T({"all": [{"field": "amount", "op": "lt", "value": 0},
                     {"any": [{"field": "bank_ref", "op": "not_empty"}, {"not": {"field": "description", "op": "empty"}}]}]}))


# ─────────────────────────── validation & safety ───────────────────────────
def test_validate():
    bad = [
        ({"op": "nope"}, "op must be one of"),
        ({"op": "extract", "field": "description", "into": "bank_ref", "pattern": "("}, "invalid regex"),
        ({"op": "extract", "field": "description", "into": "bank_ref", "pattern": "x" * 201}, "longer than"),
        ({"op": "extract", "field": "description", "into": "bank_ref", "pattern": r"(\d+)", "group": 2}, "does not exist"),
        ({"op": "calc", "expr": "__import__('os').system('x')", "into": "a"}, "unsupported"),
        ({"op": "calc", "expr": "amount.__class__", "into": "a"}, None),     # dotted name → just an (empty) field
        ({"op": "calc", "expr": "amount ** 2", "into": "a"}, "unsupported"),
        ({"op": "calc", "expr": "[1][0]", "into": "a"}, "unsupported"),
        ({"op": "filter"}, "needs a 'when'"),
        ({"op": "lookup", "field": "x", "map": {}}, "non-empty"),
        ({"op": "lookup", "field": "x", "map": {"a": "b"}, "on_missing": "default"}, "needs a 'default'"),
        ({"op": "concat", "template": "static", "into": "x"}, "references no"),
        ({"op": "fill", "field": "x"}, "'value' is required"),
        ({"op": "fill", "field": "x", "value": 1, "when": {"field": "a", "op": "in", "value": "abc"}}, "list value"),
    ]
    for rule, expect in bad:
        errs = prep.validate([rule])
        if expect is None:
            check(f"validate: accepted {rule['expr']}", not errs, errs)
        else:
            check(f"validate: rejects → {expect}", any(expect in e for e in errs), errs)
    check("validate: not a list", prep.validate({"op": "fill"}) == ["rules must be a list"])
    check("validate: too many", prep.validate([{"op": "fill", "field": "a", "value": 1}] * 101) != [])
    out = prep.apply([row()], [{"op": "calc", "expr": "amount.__class__", "into": "a"}])
    check("calc: attribute access resolves as a field name, never Python", out["errors"]
          and "amount.__class__" in out["errors"][0]["error"], out)
    tmpl = prep.apply([row()], [{"op": "concat", "template": "{description.__class__}", "into": "x"}])
    check("concat: no str.format attribute access", "x" not in tmpl["rows"][0], tmpl["rows"][0])
    check("fingerprint stable + order-sensitive",
          prep.fingerprint([{"op": "fill", "field": "a", "value": 1}]) == prep.fingerprint([{"value": 1, "field": "a", "op": "fill"}])
          and prep.fingerprint([{"op": "fill", "field": "a", "value": 1}, {"op": "fill", "field": "b", "value": 1}])
          != prep.fingerprint([{"op": "fill", "field": "b", "value": 1}, {"op": "fill", "field": "a", "value": 1}]))


def test_no_rules_and_immutability():
    src = [row()]
    out = prep.apply(src, [])
    check("no rules: rows pass through unchanged", {k: v for k, v in out["rows"][0].items() if k != "_trace"} == src[0])
    run(src, [{"op": "fill", "field": "bank_ref", "value": "X"}])
    check("apply never mutates the input rows", src[0]["bank_ref"] is None and "_trace" not in src[0], src)


# ─────────────────────────── finalize + CSV end-to-end ───────────────────────────
def test_finalize_and_csv():
    f = prep.finalize_statement({**row(amount="12.50", stmt_date="2026-05-30", bank_ref="  "), "check_no": "9", "_trace": []})
    check("finalize: coerces amount/date, blank ref → None, drops scratch",
          f["amount"] == 12.5 and f["stmt_date"] == date(2026, 5, 30) and f["bank_ref"] is None and "check_no" not in f, f)
    for bad, msg in (({"amount": "abc"}, "amount"), ({"source_account": ""}, "source_account"),
                     ({"stmt_date": "soon"}, "stmt_date")):
        try:
            prep.finalize_statement(row(**bad)); check(f"finalize rejects bad {msg}", False)
        except prep.RuleError as e:
            check(f"finalize rejects bad {msg}", msg in str(e), e)

    csvb = (b"Acct,Date,Amount,Memo,Ref,Fee\n"
            b"WF-OPER,2026-05-29,\"$1,000.00\",LOCKBOX 7781 RECEIPTS,,12.35\n"
            b"WF-OPER,2026-05-30,0.00,BALANCE MEMO,,0\n")
    prof = csvmap.MappingProfile(name="t", target="statement", columns={
        "source_account": "Acct", "stmt_date": "Date", "amount": "Amount", "description": "Memo", "bank_ref": "Ref"})
    parsed = csvmap.parse_csv(csvb, prof)
    rules = [{"op": "lookup", "field": "source_account", "map": {"WF-OPER": "bank_4471"}, "on_missing": "error"},
             {"op": "filter", "when": {"field": "amount", "op": "eq", "value": 0}},
             {"op": "extract", "field": "description", "pattern": r"LOCKBOX\s+(\d+)", "into": "bank_ref"},
             {"op": "concat", "template": "LBX-{bank_ref}", "into": "bank_ref"},
             {"op": "calc", "expr": "amount - raw.Fee", "into": "amount"}]
    out = run(parsed["rows"], rules)
    fin = [prep.finalize_statement(r) for r in out["rows"]]
    check("csv e2e: one row loaded, memo line dropped", len(fin) == 1 and len(out["dropped"]) == 1, out)
    check("csv e2e: account aliased, ref composed, net of fee",
          fin[0]["source_account"] == "bank_4471" and fin[0]["bank_ref"] == "LBX-7781" and fin[0]["amount"] == 987.65, fin)
    check("csv e2e: trace explains all three changes",
          [t["rule"] for t in fin[0]["_trace"]] == [1, 3, 4, 5], fin[0]["_trace"])


if __name__ == "__main__":
    for fn in (test_extract, test_lookup, test_concat, test_calc, test_fill_filter_when, test_conditions,
               test_validate, test_no_rules_and_immutability, test_finalize_and_csv):
        fn()
    failed = [(n, d) for n, ok, d in _R if not ok]
    for n, ok, d in _R:
        print(("PASS " if ok else "FAIL ") + n + ("" if ok else f"  — {d}"))
    print(f"\n{len(_R) - len(failed)}/{len(_R)} passed")
    sys.exit(1 if failed else 0)

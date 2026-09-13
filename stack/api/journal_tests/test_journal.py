"""Proposed journal entries (#43) — offline tests for the pure core (no DB, no FastAPI).

Covers: line validation (the API mirror of the DB constraints), sign convention for statement
items on asset and liability accounts, offset-rule selection, GR/IR aging threshold, residual
direction, the status machine, export-profile validation, CSV rendering (sign options, date
format, formula-injection neutralising, constant columns).

Run:  py -3 stack/api/journal_tests/test_journal.py
"""
import csv
import io
import os
import sys
from datetime import date
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))            # stack/api → import journal
import journal as J                                   # noqa: E402

_R = []
def check(name, cond, detail=""):
    _R.append((name, bool(cond), "" if cond else str(detail)))


RULES = [
    {"id": 1, "source_kind": "stmt_open_item", "pattern": r"\b(fee|fees|service charge)\b", "account_code": "6510",
     "account_name": "Bank service charges", "priority": 10, "active": True},
    {"id": 2, "source_kind": "stmt_open_item", "pattern": r"\binterest\b", "account_code": "4910",
     "account_name": "Interest income", "priority": 20, "active": True},
    {"id": 3, "source_kind": "stmt_open_item", "pattern": None, "account_code": "9999",
     "account_name": "Suspense", "priority": 1000, "active": True},
    {"id": 6, "source_kind": "grir", "pattern": r"^(grni|invoiced_not_received)$", "account_code": "@po_gl_code",
     "account_name": "PO account", "priority": 10, "active": True},
    {"id": 4, "source_kind": "grir", "pattern": None, "account_code": "5990",
     "account_name": "Purchase price variance", "priority": 1000, "active": True},
    {"id": 5, "source_kind": "residual", "pattern": None, "account_code": "9999",
     "account_name": "Suspense", "priority": 1000, "active": True},
]
CASH = {"id": "1010", "code": "1010", "name": "Operating cash"}
CARD = {"id": "2020", "code": "2020", "name": "Corporate cards"}
D = Decimal


def side(lines, code):
    ln = [l for l in lines if l["account_code"] == code][0]
    return ("Dr", ln["debit"]) if ln["debit"] > 0 else ("Cr", ln["credit"])


def test_validate_lines():
    ok = [{"account_code": "6510", "debit": 25, "credit": 0}, {"account_code": "1010", "debit": 0, "credit": "25.00"}]
    check("valid two-line entry", J.validate_lines(ok) == [], J.validate_lines(ok))
    cases = [
        ([ok[0]], "at least two"),
        ([ok[0], {"account_code": "1010", "credit": 24.99}], "unbalanced"),
        ([ok[0], {"account_code": "", "credit": 25}], "account_code"),
        ([{"account_code": "1", "debit": 25, "credit": 25}, {"account_code": "2", "credit": 0}], "exactly one"),
        ([{"account_code": "1", "debit": -25}, {"account_code": "2", "credit": -25}], "negative"),
        ([{"account_code": "1", "debit": "25.001"}, {"account_code": "2", "credit": "25.001"}], "2 decimal"),
        ([{"account_code": "1", "debit": "abc"}, {"account_code": "2", "credit": 1}], "numbers"),
        ("nope", "at least two"),
    ]
    for lines, expect in cases:
        errs = J.validate_lines(lines)
        check(f"validate_lines rejects → {expect}", any(expect in e for e in errs), errs)


def test_stmt_item_signs():
    fee = {"id": 41, "amount": D("-25.00"), "description": "MONTHLY SERVICE CHARGE", "ref": "SC-0531"}
    p = J.propose_stmt_item(fee, CASH, RULES)
    check("bank fee on cash: Dr 6510 / Cr 1010",
          side(p["lines"], "6510") == ("Dr", D("25.00")) and side(p["lines"], "1010") == ("Cr", D("25.00")), p["lines"])
    check("fee proposal balanced", J.totals(p["lines"])["balanced"])
    check("fee proposal keyed to the statement line", p["source_kind"] == "stmt_open_item" and p["source_ref"] == "41")
    check("rationale names the rule", "/\\b(fee|fees|service charge)\\b/" in p["rationale"], p["rationale"])
    check("cash line carries gl_account_id; offset does not",
          [l["gl_account_id"] for l in p["lines"]] == ["1010", None])

    intr = J.propose_stmt_item({"id": 42, "amount": D("12.40"), "description": "Interest paid", "ref": None}, CASH, RULES)
    check("interest on cash: Dr 1010 / Cr 4910",
          side(intr["lines"], "1010") == ("Dr", D("12.40")) and side(intr["lines"], "4910") == ("Cr", D("12.40")), intr["lines"])

    annual = J.propose_stmt_item({"id": 43, "amount": D("-2500.00"), "description": "Annual card fee", "ref": "FEE-ANNUAL"},
                                 CARD, RULES)
    check("card fee on a liability: Dr 6510 / Cr 2020 (liability grows)",
          side(annual["lines"], "6510") == ("Dr", D("2500.00")) and side(annual["lines"], "2020") == ("Cr", D("2500.00")))

    unk = J.propose_stmt_item({"id": 44, "amount": D("300"), "description": "MISC CREDIT", "ref": "X"}, CASH, RULES)
    check("unclassified item falls back to suspense and says so",
          side(unk["lines"], "9999") == ("Cr", D("300.00")) and "fallback" in unk["rationale"], unk)
    check("zero-amount item → no proposal", J.propose_stmt_item({"id": 45, "amount": 0, "description": "x"}, CASH, RULES) is None)
    check("no rules → no proposal", J.propose_stmt_item(fee, CASH, []) is None)


def test_pick_offset():
    check("priority order: fee before interest",
          J.pick_offset(RULES, "stmt_open_item", "interest fee")["account_code"] == "6510")
    check("case-insensitive", J.pick_offset(RULES, "stmt_open_item", "WIRE FEE")["account_code"] == "6510")
    check("word boundary: 'coffee' is not a fee", J.pick_offset(RULES, "stmt_open_item", "coffee shop")["account_code"] == "9999")
    inactive = [dict(RULES[0], active=False)] + RULES[1:]
    check("inactive rule skipped", J.pick_offset(inactive, "stmt_open_item", "fee")["account_code"] == "9999")
    check("kind-scoped", J.pick_offset(RULES, "grir", "fee")["account_code"] == "5990")


def test_grir():
    clearing = {"id": "2150", "code": "2150", "name": "GR/IR clearing"}
    asof = date(2026, 5, 31)
    grni = {"po_id": "PO-7", "vendor": "Acme", "open_amount": D("64000.00"), "reason": "grni",
            "last_activity": date(2026, 1, 15), "gl_code": "364", "gl_name": "Poles, towers & fixtures"}
    p = J.propose_grir(grni, clearing, RULES, asof, 90)
    # clearing GL balance ties to −Σopen, i.e. −64,000 (a credit); clearing it debits the clearing account
    # and reverses the receipt against the account the goods were received into
    check("aged GRNI: Dr clearing 64,000 / Cr the PO's own account 364",
          side(p["lines"], "2150") == ("Dr", D("64000.00")) and side(p["lines"], "364") == ("Cr", D("64000.00")), p["lines"])
    check("GRNI offset carries the PO account name", [l["account_name"] for l in p["lines"]][1] == "Poles, towers & fixtures")
    check("GRNI rationale says it reverses and asks for confirmation",
          "reverses the receipt that was never invoiced" in p["rationale"] and "136 days" in p["rationale"] and "confirm" in p["rationale"], p["rationale"])
    over = dict(grni, po_id="PO-8", open_amount=D("-4500.00"), reason="over_invoiced")
    q = J.propose_grir(over, clearing, RULES, asof, 90)
    check("aged over-invoice: Cr clearing / Dr 5990 price variance",
          side(q["lines"], "2150") == ("Cr", D("4500.00")) and side(q["lines"], "5990") == ("Dr", D("4500.00")), q["lines"])
    inr = dict(grni, po_id="PO-9", open_amount=D("-3200.00"), reason="invoiced_not_received", gl_code="921", gl_name="Office supplies")
    ir = J.propose_grir(inr, clearing, RULES, asof, 90)
    check("aged invoice with no receipt: Cr clearing / Dr the PO's expense account 921",
          side(ir["lines"], "2150") == ("Cr", D("3200.00")) and side(ir["lines"], "921") == ("Dr", D("3200.00"))
          and "expenses the invoice" in ir["rationale"], ir)
    check("@po_gl_code rule on a PO with no account → no proposal (never a blank account)",
          J.propose_grir(dict(grni, gl_code=None), clearing, RULES, asof, 90) is None)
    young = dict(grni, last_activity=date(2026, 5, 1))
    check("younger than threshold → no proposal", J.propose_grir(young, clearing, RULES, asof, 90) is None)
    check("threshold is inclusive at exactly N days",
          J.propose_grir(dict(grni, last_activity=date(2026, 3, 2)), clearing, RULES, asof, 90) is not None)
    check("ISO-string last_activity accepted",
          J.propose_grir(dict(grni, last_activity="2026-01-15"), clearing, RULES, asof, 90) is not None)


def test_residual():
    # variance = GL − statement; residual > 0 means the GL is higher than open items explain → credit cash
    p = J.propose_residual(CASH, 17, 3500.0, RULES, date(2026, 5, 31))
    check("positive residual: Cr account / Dr suspense",
          side(p["lines"], "1010") == ("Cr", D("3500.00")) and side(p["lines"], "9999") == ("Dr", D("3500.00")), p["lines"])
    n = J.propose_residual(CASH, 17, -0.5, RULES, date(2026, 5, 31))
    check("negative residual: Dr account", side(n["lines"], "1010") == ("Dr", D("0.50")))
    check("zero / None residual → no proposal",
          J.propose_residual(CASH, 17, 0, RULES, date(2026, 5, 31)) is None
          and J.propose_residual(CASH, 17, None, RULES, date(2026, 5, 31)) is None)


def test_transitions():
    ok = [("draft", "submitted"), ("submitted", "approved"), ("submitted", "draft"), ("approved", "exported"),
          ("draft", "void"), ("submitted", "void"), ("approved", "void")]
    bad = [("draft", "approved"), ("draft", "exported"), ("exported", "void"), ("exported", "draft"),
           ("void", "draft"), ("approved", "draft"), ("approved", "submitted")]
    check("allowed transitions", all(J.can_transition(a, b) for a, b in ok))
    check("refused transitions (no skipping approval, exported/void are final)",
          not any(J.can_transition(a, b) for a, b in bad), [p for p in bad if J.can_transition(*p)])
    sql = open(os.path.join(os.path.dirname(os.path.dirname(HERE)), "db", "20-journal-entries.sql"), encoding="utf-8").read()
    check("DB trigger allows exactly the same transitions",
          all(f"('{a}', '{b}')" in sql for a, b in ok) and not any(f"('{a}', '{b}')" in sql for a, b in bad))


def _entries():
    return [{"id": 14, "period_end": date(2026, 5, 31), "memo": "=HYPERLINK(\"http://x\")", "source_kind": "stmt_open_item",
             "source_ref": "41", "created_by": "Joe B.", "approved_by": "Maria L.",
             "lines": [{"line_no": 1, "account_code": "6510", "account_name": "Bank service charges", "gl_account_id": None,
                        "fund_id": None, "description": "-SERVICE CHARGE", "debit": D("25.00"), "credit": D("0")},
                       {"line_no": 2, "account_code": "1010", "account_name": "Operating cash", "gl_account_id": "1010",
                        "fund_id": None, "description": "SERVICE CHARGE", "debit": D("0"), "credit": D("25.00")}]}]


def test_export():
    cfg = {"columns": [{"header": "JournalNumber", "field": "entry_number"}, {"header": "Date", "field": "posting_date"},
                       {"header": "Account", "field": "account_code"}, {"header": "Debit", "field": "debit"},
                       {"header": "Credit", "field": "credit"}, {"header": "Amount", "field": "amount"},
                       {"header": "Memo", "field": "memo"}, {"header": "Desc", "field": "description"},
                       {"header": "Ledger", "value": "ACTUALS"}],
           "date_format": "%m/%d/%Y", "line_ending": "lf"}
    check("profile valid", J.validate_profile(cfg) == [], J.validate_profile(cfg))
    out = J.render_csv(_entries(), cfg)
    rows = list(csv.reader(io.StringIO(out)))
    check("header + one row per line", len(rows) == 3 and rows[0][0] == "JournalNumber", rows)
    check("entry number + date format", rows[1][:2] == ["JE-000014", "05/31/2026"], rows[1])
    check("debit/credit columns, blank on the other side", rows[1][3:5] == ["25.00", ""] and rows[2][3:5] == ["", "25.00"], rows)
    check("signed amount debit-positive", rows[1][5] == "25.00" and rows[2][5] == "-25.00", rows)
    check("formula injection neutralised in text cells",
          rows[1][6].startswith("'=") and rows[1][7] == "'-SERVICE CHARGE", rows[1])
    check("numeric cells are not quoted/prefixed (a negative amount stays a number)", rows[2][5] == "-25.00")
    check("constant column", rows[1][8] == "ACTUALS")
    check("lf line endings", "\r\n" not in out)
    flipped = J.render_csv(_entries(), dict(cfg, amount_sign="credit_positive", include_header=False, line_ending="crlf"))
    frows = list(csv.reader(io.StringIO(flipped)))
    check("credit_positive flips the signed amount; no header; crlf",
          frows[0][5] == "-25.00" and frows[1][5] == "25.00" and len(frows) == 2 and "\r\n" in flipped, frows)
    check("render is deterministic (same bytes → same hash)",
          J.sha256(J.render_csv(_entries(), cfg)) == J.sha256(out))
    for bad, expect in [({"columns": []}, "non-empty"), ({"columns": [{"header": "A", "field": "nope"}]}, "unknown field"),
                        ({"columns": [{"header": "A", "field": "memo", "value": "x"}]}, "exactly one"),
                        ({"columns": [{"field": "memo"}]}, "needs a header"),
                        (dict(cfg, amount_sign="up"), "amount_sign"), (dict(cfg, delimiter=";;"), "delimiter"),
                        (dict(cfg, line_ending="cr"), "line_ending")]:
        check(f"profile rejects → {expect}", any(expect in e for e in J.validate_profile(bad)), J.validate_profile(bad))
    seed = open(os.path.join(os.path.dirname(os.path.dirname(HERE)), "db", "20-journal-entries.sql"), encoding="utf-8").read()
    import json, re
    blob = re.search(r"\('generic-csv', '(\{.*?\})', 'system'\)", seed, re.S).group(1)
    check("seeded generic-csv profile validates", J.validate_profile(json.loads(blob)) == [], J.validate_profile(json.loads(blob)))


def test_helpers():
    check("entry_number zero-padded", J.entry_number(7) == "JE-000007")
    check("period_key", J.period_key(date(2026, 5, 31)) == "2026-05")
    check("money rounds half-up to cents", J.money("0.125") == D("0.13") and J.money(2.675) == D("2.68"))
    check("signed_line splits sides", J.signed_line("1", "", -3)["credit"] == D("3.00") and J.signed_line("1", "", 3)["debit"] == D("3.00"))


if __name__ == "__main__":
    for fn in (test_validate_lines, test_stmt_item_signs, test_pick_offset, test_grir, test_residual,
               test_transitions, test_export, test_helpers):
        fn()
    failed = [(n, d) for n, ok, d in _R if not ok]
    for n, ok, d in _R:
        print(("PASS " if ok else "FAIL ") + n + ("" if ok else f"  — {d}"))
    print(f"\n{len(_R) - len(failed)}/{len(_R)} passed")
    sys.exit(1 if failed else 0)

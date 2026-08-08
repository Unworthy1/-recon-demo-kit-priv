"""Matching engine (#34) — offline tests for the pure core (no DB, no FastAPI).

Covers: the three passes (exact / rule / suggestion), greedy 1:1 consumption, determinism,
rule ordering, ref-pattern gating, aging buckets, and the variance tie-out arithmetic.

Run:  py -3 stack/api/matching_tests/test_matching.py
"""
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))            # stack/api → import matching
import matching                                       # noqa: E402

_R = []
def check(name, cond, detail=""):
    _R.append((name, bool(cond), "" if cond else str(detail)))


def gl(i, amt, d, ref=None):
    return {"id": i, "amount": amt, "date": d, "ref": ref}


D = date(2026, 7, 15)


def test_exact_pass():
    m = matching.match_passes(
        [gl(1, -500.00, D, "CHK-1102")],
        [gl(101, -500.00, date(2026, 7, 18), "chk-1102")],   # case differs, dates differ — still exact
        rules=[])
    check("exact: amount+ref, case-insensitive", len(m) == 1 and m[0]["match_type"] == "auto_exact", m)
    m = matching.match_passes([gl(1, -500.00, D, "")], [gl(101, -500.00, D, "")], rules=[])
    check("exact: empty refs never exact-match (falls to suggestion)",
          m and m[0]["match_type"] == "suggested", m)
    m = matching.match_passes([gl(1, -500.00, D, "A")], [gl(101, -500.01, D, "A")], rules=[])
    check("exact: 1 cent off is not exact", not any(x["match_type"] == "auto_exact" for x in m), m)


def test_rule_pass():
    rules = [{"id": 7, "amount_tol": 1.00, "date_window": 5, "ref_pattern": None, "priority": 100}]
    m = matching.match_passes([gl(1, 96500.00, D, "INV-4002")],
                              [gl(101, 96499.40, date(2026, 7, 18), "WIRE-88")], rules)
    check("rule: within tol+window fires", m and m[0]["match_type"] == "auto_rule" and m[0]["rule_id"] == 7, m)
    m = matching.match_passes([gl(1, 96500.00, D, None)],
                              [gl(101, 96498.00, date(2026, 7, 18), None)], rules)
    check("rule: outside tolerance does not fire",
          not any(x["match_type"] == "auto_rule" for x in m), m)
    m = matching.match_passes([gl(1, 100.00, D, None)],
                              [gl(101, 100.50, date(2026, 7, 25), None)], rules)
    check("rule: outside date window does not fire",
          not any(x["match_type"] == "auto_rule" for x in m), m)
    pat = [{"id": 8, "amount_tol": 0, "date_window": 10, "ref_pattern": r"CHK-\d+", "priority": 50}]
    m = matching.match_passes([gl(1, -75.00, D, "CHK-9001")],
                              [gl(101, -75.00, date(2026, 7, 17), "CHK-9001X")], pat)
    check("rule: ref_pattern must hit BOTH refs", m and m[0]["match_type"] == "auto_rule", m)
    m = matching.match_passes([gl(1, -75.00, D, "WIRE")],
                              [gl(101, -75.00, date(2026, 7, 17), "CHK-9001")], pat)
    check("rule: pattern missing one side → no rule match (suggestion instead)",
          m and m[0]["match_type"] == "suggested", m)


def test_suggestion_pass():
    m = matching.match_passes([gl(1, 800.00, D, "J-1")], [gl(101, 800.00, date(2026, 8, 1), "F-9")], [])
    check("suggest: same amount in window, refs differ", m and m[0]["status"] == "suggested", m)
    m = matching.match_passes([gl(1, 800.00, D, None)], [gl(101, 800.00, date(2026, 9, 20), None)], [])
    check("suggest: outside 30-day window → stays open", m == [], m)


def test_greedy_and_deterministic():
    # two identical GL checks, one statement line — only one may claim it, the OLDER one
    gls = [gl(2, -50.00, date(2026, 7, 10), "CHK-1"), gl(1, -50.00, date(2026, 7, 2), "CHK-1")]
    sts = [gl(101, -50.00, date(2026, 7, 11), "CHK-1")]
    m = matching.match_passes(gls, sts, [])
    check("greedy: one stmt line claimed once", len(m) == 1, m)
    check("deterministic: oldest GL line wins", m[0]["gl_ids"] == [1], m)
    m2 = matching.match_passes(list(reversed(gls)), sts, [])
    check("deterministic: input order irrelevant", m2 == m, (m, m2))


def test_pass_precedence():
    # a line that could exact-match must not be consumed by an earlier-listed rule
    rules = [{"id": 1, "amount_tol": 5, "date_window": 30, "ref_pattern": None, "priority": 1}]
    m = matching.match_passes([gl(1, -20.00, D, "R-1")], [gl(101, -20.00, D, "R-1")], rules)
    check("precedence: exact wins over rule", m[0]["match_type"] == "auto_exact", m)


def test_aging_and_tie_out():
    check("age: 0-30", matching.age_bucket(date(2026, 7, 10), date(2026, 7, 31)) == "0-30")
    check("age: 31-60", matching.age_bucket(date(2026, 6, 10), date(2026, 7, 31)) == "31-60")
    check("age: 61-90", matching.age_bucket(date(2026, 5, 10), date(2026, 7, 31)) == "61-90")
    check("age: 90+", matching.age_bucket(date(2026, 1, 10), date(2026, 7, 31)) == "90+")
    # classic bank rec: variance 1,000 = outstanding GL entries (-2,000 checks) vs bank items?
    # variance := gl − stmt must equal gl_open − stmt_open
    t = matching.tie_out(variance=1500.00, gl_open_sum=2000.00, stmt_open_sum=500.00)
    check("tie: explained variance ties", t["ties"] and t["residual"] == 0.0, t)
    t = matching.tie_out(variance=1500.00, gl_open_sum=2000.00, stmt_open_sum=800.00)
    check("tie: unexplained residual surfaces", not t["ties"] and t["residual"] == 300.00, t)
    t = matching.tie_out(variance=0, gl_open_sum=0, stmt_open_sum=0)
    check("tie: clean account ties at zero", t["ties"], t)


if __name__ == "__main__":
    for fn in (test_exact_pass, test_rule_pass, test_suggestion_pass,
               test_greedy_and_deterministic, test_pass_precedence, test_aging_and_tie_out):
        fn()
    failed = [(n, d) for n, ok, d in _R if not ok]
    for n, ok, d in _R:
        print(("PASS " if ok else "FAIL ") + n + ("" if ok else f"  — {d}"))
    print(f"\n{len(_R) - len(failed)}/{len(_R)} passed")
    sys.exit(1 if failed else 0)

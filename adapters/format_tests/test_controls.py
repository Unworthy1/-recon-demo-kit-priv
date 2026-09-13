"""Ingest data control tests (#41) — offline, no deps, in the test_formats idiom.

Every control gets a passing case and a failing case; the BAI2 trailer check is exercised under
both sign interpretations, on truncated / tampered / trailing-garbage files, and with funds-type
extensions on the 03 record.

Run:  py -3 adapters/format_tests/test_controls.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
from adapters import formats                                  # noqa: E402
from adapters.formats import ParsedStatement, controls        # noqa: E402
from adapters.base import StatementLine                       # noqa: E402
import test_formats as fx                                     # noqa: E402  (shared fixtures)

_R = []
def check(name, cond, detail=""):
    _R.append((name, bool(cond), "" if cond else str(detail)))


def run(blob, fmt=None):
    fmt = fmt or formats.detect(blob)
    return controls.evaluate(blob, fmt, formats.parse(blob, fmt))


def by(results, control):
    return [r for r in results if r.control == control]


def status_of(results, control):
    return [r.status for r in by(results, control)]


# ─────────────────────────── BAI2 ───────────────────────────
def test_bai2_good():
    res = run(fx.BAI2)
    check("bai2 good: account trailer pass", status_of(res, "bai2.account_trailer") == ["pass"],
          [r.to_dict() for r in res])
    check("bai2 good: reading recorded", "as written" in by(res, "bai2.account_trailer")[0].detail)
    check("bai2 good: group + file pass",
          status_of(res, "bai2.group_trailer") == ["pass"] and status_of(res, "bai2.file_trailer") == ["pass"])
    check("bai2 good: 88 counted in records", "records=6" in by(res, "bai2.account_trailer")[0].actual)
    check("bai2 good: committed", controls.outcome(res) == "committed")
    sample = open(os.path.join(os.path.dirname(os.path.dirname(HERE)),
                               "stack", "samples", "statements-2026-05.bai2"), "rb").read()
    check("bai2 demo sample: committed", controls.outcome(run(sample)) == "committed",
          [r.to_dict() for r in run(sample) if r.status != "pass"])


def test_bai2_negated_reading():
    # Same file, trailers computed by a bank that applies the debit sign: 210750025 + 15000000
    # + 250025 − 4500000 = 221500050.
    blob = fx.BAI2.replace(b"230500050", b"221500050")
    res = run(blob)
    acct = by(res, "bai2.account_trailer")[0]
    check("bai2 negated: pass", acct.status == "pass", acct.to_dict())
    check("bai2 negated: reading recorded", "debit detail negated" in acct.detail, acct.detail)
    check("bai2 negated: committed", controls.outcome(res) == "committed")


def test_bai2_tampered():
    blob = fx.BAI2.replace(b"16,165,15000000,", b"16,165,15000001,")
    res = run(blob)
    check("bai2 tampered amount: account trailer fail",
          status_of(res, "bai2.account_trailer") == ["fail"], [r.to_dict() for r in res])
    check("bai2 tampered amount: quarantined", controls.outcome(res) == "quarantined")
    check("bai2 tampered amount: continuity warns",
          [(r.status, r.severity) for r in by(res, "balance.continuity")] == [("fail", "warning")])

    dropped = fx.BAI2.replace(b"16,175,250025,0,DEP889,,LOCKBOX DEPOSIT/\n", b"")
    dropped = dropped.replace(b"88,SUPPLEMENTAL RECEIPTS\n", b"")
    res = run(dropped)
    acct = by(res, "bai2.account_trailer")[0]
    check("bai2 dropped line: fail on total and count",
          acct.status == "fail" and "records declared 6" in acct.detail and "control total" in acct.detail,
          acct.to_dict())
    check("bai2 dropped line: quarantined", controls.outcome(res) == "quarantined")


def test_bai2_truncated():
    lines = fx.BAI2.splitlines(keepends=True)
    no_99 = b"".join(lines[:-1])
    res = run(no_99)
    check("bai2 no 99: file trailer fail",
          any(r.status == "fail" and "truncated" in r.detail for r in by(res, "bai2.file_trailer")))
    check("bai2 no 99: quarantined", controls.outcome(res) == "quarantined")

    mid = b"".join(lines[:6])                      # cut after the second 16/88 — no 49/98/99
    res = run(mid)
    fails = {r.control for r in res if r.status == "fail"}
    check("bai2 cut mid-account: account, group, file all fail",
          {"bai2.account_trailer", "bai2.group_trailer", "bai2.file_trailer"} <= fails, fails)

    extra = fx.BAI2 + b"16,165,99999900,0,EVIL,,APPENDED/\n"
    res = run(extra)
    check("bai2 content after 99: fail",
          any(r.status == "fail" and "after the 99" in r.detail for r in res), [r.to_dict() for r in res])


def test_bai2_malformed_and_blank():
    res = controls.bai2_trailers(fx.BAI2.replace(b"49,230500050,6/", b"49,2305X0050,6/"))
    check("bai2 malformed trailer amount: structure fail",
          any(r.control == "bai2.structure" and r.status == "fail" for r in res), [r.to_dict() for r in res])

    blank = (fx.BAI2.replace(b"49,230500050,6/", b"49,,/")
                    .replace(b"98,230500050,1,8/", b"98,,,/")
                    .replace(b"99,230500050,1,10/", b"99,,,/"))
    res = controls.bai2_trailers(blank)
    acct = [r for r in res if r.control == "bai2.account_trailer"][0]
    check("bai2 blank 49: not_available, not pass", acct.status == "not_available", acct.to_dict())
    check("bai2 blank trailers: not quarantined", controls.outcome(res) == "committed",
          [r.to_dict() for r in res])


def test_bai2_funds_types():
    # 03 with an S (availability) group and a V (value-dated) group: primary amounts only are
    # summed, and the walk must land on 015 correctly.
    blob = b"""01,B,C,260731,1200,1,80,80,2/
02,C,B,1,260731,1200,USD,2/
03,acct9,USD,010,100000,,S,40000,30000,30000,015,112000,,V,260731,1200/
16,165,12000,0,R1,,IN/
49,224000,3/
98,224000,1,5/
99,224000,1,7/
"""
    res = controls.bai2_trailers(blob)
    check("bai2 S/V funds on 03: all pass", all(r.status == "pass" for r in res), [r.to_dict() for r in res])
    s = list(formats.parse(blob))[0]
    check("bai2 parser S/V funds: balances read correctly",
          s.opening == 1000.00 and s.closing == 1120.00 and s.ties() is True, (s.opening, s.closing))
    d = blob.replace(b"16,165,12000,0,R1,,IN/", b"16,165,12000,D,2,0,6000,1,6000,R1,,IN/")
    s = list(formats.parse(d))[0]
    check("bai2 parser D funds on 16: bank ref after distribution", s.lines[0].bank_ref == "R1",
          s.lines[0].bank_ref)
    check("bai2 D funds on 16: trailers still tie",
          all(r.status == "pass" for r in controls.bai2_trailers(d)))


# ─────────────────────────── camt.053 ───────────────────────────
SUMMARY = (b"<TxsSummry><TtlNtries><NbOfNtries>2</NbOfNtries><Sum>4151.50</Sum>"
           b"</TtlNtries></TxsSummry>\n  <Ntry>")


def with_summary(blob, summary=SUMMARY):
    return blob.replace(b"<Ntry>", summary, 1)


def test_camt():
    res = run(fx.CAMT)
    check("camt no summary: not_available", status_of(res, "camt053.entry_summary") == ["not_available"])
    check("camt no summary: committed", controls.outcome(res) == "committed")

    res = run(with_summary(fx.CAMT))
    check("camt summary ties: pass", status_of(res, "camt053.entry_summary") == ["pass"],
          [r.to_dict() for r in by(res, "camt053.entry_summary")])

    bad = with_summary(fx.CAMT, SUMMARY.replace(b"<NbOfNtries>2", b"<NbOfNtries>3"))
    res = run(bad)
    check("camt count mismatch: fail + quarantined",
          status_of(res, "camt053.entry_summary") == ["fail"] and controls.outcome(res) == "quarantined")

    bad = with_summary(fx.CAMT, SUMMARY.replace(b"4151.50", b"4151.51"))
    check("camt sum mismatch: fail", status_of(run(bad), "camt053.entry_summary") == ["fail"])


# ─────────────────────────── continuity + other formats ───────────────────────────
def test_continuity_and_others():
    res = run(fx.MT940)
    check("mt940: continuity pass", status_of(res, "balance.continuity") == ["pass"])
    check("mt940: integrity not_available", status_of(res, "mt940.integrity") == ["not_available"])

    res = run(fx.OFX)
    check("ofx: continuity not_available (no opening)",
          status_of(res, "balance.continuity") == ["not_available"], [r.to_dict() for r in res])
    check("ofx: committed", controls.outcome(res) == "committed")

    bad = fx.CAMT.replace(b"48249.50", b"48249.00")
    res = run(bad)
    check("camt closing off: continuity warning only, still committed",
          status_of(res, "balance.continuity") == ["fail"] and controls.outcome(res) == "committed")

    summary_only = ParsedStatement("acctZ", opening=100.0, closing=250.0, lines=[])
    check("summary-only account: not_available",
          [r.status for r in controls.balance_continuity([summary_only])] == ["not_available"])
    flat = ParsedStatement("acctY", opening=100.0, closing=100.0, lines=[])
    check("no activity, flat balance: pass",
          [r.status for r in controls.balance_continuity([flat])] == ["pass"])

    res = controls.evaluate(b"", "ofx", [])
    check("nothing parsed: nonempty fail + quarantined",
          status_of(res, "file.nonempty") == ["fail"] and controls.outcome(res) == "quarantined")


# ─────────────────────────── CSV ───────────────────────────
def test_csv():
    ok = {"rows": [{"amount": 10.10}, {"amount": -2.05}], "errors": [], "skipped": 1}
    res = controls.csv_controls(ok)
    check("csv clean, nothing declared: committed",
          controls.outcome(res) == "committed" and status_of(res, "csv.declared_total") == ["not_available"])

    res = controls.csv_controls(ok, expected_rows=2, control_total=8.05)
    check("csv declared rows+total tie: all pass", all(r.status == "pass" for r in res),
          [r.to_dict() for r in res])

    res = controls.csv_controls(ok, expected_rows=3, control_total=8.06)
    check("csv declared mismatch: both fail",
          status_of(res, "csv.declared_rows") == ["fail"] and status_of(res, "csv.declared_total") == ["fail"])

    partial = {"rows": ok["rows"], "errors": [{"row": 4, "error": "bad date"}], "skipped": 0}
    res = controls.csv_controls(partial)
    check("csv row errors: quarantined",
          status_of(res, "csv.row_errors") == ["fail"] and controls.outcome(res) == "quarantined")

    res = controls.csv_controls({"rows": [], "errors": [], "skipped": 0})
    check("csv header-only: nonempty warning, still committed",
          [(r.status, r.severity) for r in by(res, "csv.nonempty")] == [("fail", "warning")]
          and controls.outcome(res) == "committed")

    # float trap: 0.1 + 0.2 must tie to 0.30 exactly
    res = controls.csv_controls({"rows": [{"amount": 0.1}, {"amount": 0.2}], "errors": []}, control_total=0.3)
    check("csv total is decimal-safe", status_of(res, "csv.declared_total") == ["pass"])


def test_hash():
    check("sha256 stable", controls.sha256(fx.BAI2) == controls.sha256(bytes(fx.BAI2)))
    check("sha256 sensitive", controls.sha256(fx.BAI2) != controls.sha256(fx.BAI2 + b"\n"))


if __name__ == "__main__":
    for fn in (test_bai2_good, test_bai2_negated_reading, test_bai2_tampered, test_bai2_truncated,
               test_bai2_malformed_and_blank, test_bai2_funds_types, test_camt,
               test_continuity_and_others, test_csv, test_hash):
        fn()
    failed = [(n, d) for n, ok, d in _R if not ok]
    for n, ok, d in _R:
        print(("PASS " if ok else "FAIL ") + n + ("" if ok else f"  — {d}"))
    print(f"\n{len(_R) - len(failed)}/{len(_R)} passed")
    sys.exit(1 if failed else 0)

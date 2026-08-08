"""CSV mapping-profile tests (#37) — offline, no deps.

Run:  py -3 adapters/format_tests/test_csvmap.py
"""
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from adapters.formats import csvmap                    # noqa: E402

_R = []
def check(name, cond, detail=""):
    _R.append((name, bool(cond), "" if cond else str(detail)))


def P(**kw):
    base = dict(name="t", target="statement",
                columns={"source_account": "Acct", "stmt_date": "Date",
                         "amount": "Amount", "description": "Memo", "bank_ref": "Ref"})
    base.update(kw)
    return csvmap.MappingProfile(**base)


def test_basic_and_money_cleaning():
    csvb = b"Acct,Date,Amount,Memo,Ref\nbank_4471,2026-05-31,\"$1,250.75\",Deposit,DEP-1\nbank_4471,2026-05-30,(300.00),Chargeback,CB-9\n"
    out = csvmap.parse_csv(csvb, P())
    check("basic: 2 rows no errors", len(out["rows"]) == 2 and not out["errors"], out)
    check("basic: $ and thousands stripped", out["rows"][0]["amount"] == 1250.75, out["rows"][0])
    check("basic: parenthesised negative", out["rows"][1]["amount"] == -300.00, out["rows"][1])
    check("basic: iso date parsed", out["rows"][0]["stmt_date"] == date(2026, 5, 31), out["rows"][0])


def test_date_format_and_decimal_comma():
    csvb = "Acct;Date;Amount\n".replace(";", ",").encode() + b"bank_4471,31/05/2026,\"1.234,56\"\n"
    p = P(columns={"source_account": "Acct", "stmt_date": "Date", "amount": "Amount"},
          date_format="%d/%m/%Y", decimal_comma=True)
    out = csvmap.parse_csv(csvb, p)
    check("eu: dd/mm/yyyy date", out["rows"][0]["stmt_date"] == date(2026, 5, 31), out)
    check("eu: decimal comma", out["rows"][0]["amount"] == 1234.56, out)


def test_debit_credit_split_and_sign_flip():
    csvb = b"Acct,Date,DR,CR\nbank_4471,2026-05-31,500.00,\nbank_4471,2026-05-30,,750.25\n"
    p = P(columns={"source_account": "Acct", "stmt_date": "Date"},
          debit_col="DR", credit_col="CR")
    out = csvmap.parse_csv(csvb, p)
    check("drcr: debit negative", out["rows"][0]["amount"] == -500.00, out["rows"][0])
    check("drcr: credit positive", out["rows"][1]["amount"] == 750.25, out["rows"][1])
    p2 = P(columns={"source_account": "Acct", "stmt_date": "Date"},
           debit_col="DR", credit_col="CR", sign_flip=True)
    out2 = csvmap.parse_csv(csvb, p2)
    check("drcr: sign_flip inverts", out2["rows"][0]["amount"] == 500.00, out2["rows"][0])


def test_skip_rows_and_account_default():
    csvb = b"Meridian Power - Treasury Export\nGenerated 2026-06-01\nDate,Amount\n2026-05-31,42.00\n"
    p = P(columns={"stmt_date": "Date", "amount": "Amount"}, skip_rows=2,
          account_default="bank_8810")
    out = csvmap.parse_csv(csvb, p)
    check("skip: banner rows skipped", len(out["rows"]) == 1 and out["skipped"] == 2, out)
    check("skip: account_default applied", out["rows"][0]["source_account"] == "bank_8810", out)


def test_row_errors_reported_not_dropped():
    csvb = b"Acct,Date,Amount\nbank_4471,2026-05-31,10.00\nbank_4471,not-a-date,20.00\nbank_4471,2026-05-29,garbage\n"
    p = P(columns={"source_account": "Acct", "stmt_date": "Date", "amount": "Amount"})
    out = csvmap.parse_csv(csvb, p)
    check("errors: good row kept", len(out["rows"]) == 1, out)
    check("errors: 2 bad rows reported with line numbers",
          len(out["errors"]) == 2 and {e["row"] for e in out["errors"]} == {2, 3}, out["errors"])


def test_validation():
    bad = csvmap.MappingProfile(name="x", target="statement", columns={"amount": "Amt"})
    errs = bad.validate()
    check("validate: missing mappings reported", len(errs) == 2, errs)
    check("validate: unknown target", csvmap.MappingProfile(name="x", target="nope").validate(), "no error")
    ok = P(columns={"source_account": "A", "stmt_date": "D"}, debit_col="DR", credit_col="CR")
    check("validate: dr/cr satisfies amount", ok.validate() == [], ok.validate())
    rt = csvmap.MappingProfile.from_dict(P().to_dict())
    check("roundtrip: to_dict/from_dict", rt.to_dict() == P().to_dict(), rt)


if __name__ == "__main__":
    for fn in (test_basic_and_money_cleaning, test_date_format_and_decimal_comma,
               test_debit_credit_split_and_sign_flip, test_skip_rows_and_account_default,
               test_row_errors_reported_not_dropped, test_validation):
        fn()
    failed = [(n, d) for n, ok, d in _R if not ok]
    for n, ok, d in _R:
        print(("PASS " if ok else "FAIL ") + n + ("" if ok else "  - " + str(d)))
    print(f"\n{len(_R) - len(failed)}/{len(_R)} passed")
    sys.exit(1 if failed else 0)

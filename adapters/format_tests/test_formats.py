"""Format parser tests (#37) — offline, no deps, in the copilot_tests idiom.

One realistic fixture per format. Each asserts: detection, account id, currency, line count,
signed line sum, closing balance, and the tie-out opening + sum(lines) == closing where the
format carries both balances.

Run:  py -3 adapters/format_tests/test_formats.py   (or python3 inside the api image)
"""
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))   # repo root → `adapters` package
from adapters import formats                                  # noqa: E402

_R = []
def check(name, cond, detail=""):
    _R.append((name, bool(cond), "" if cond else str(detail)))


# ─────────────────────────── BAI2 ───────────────────────────
# Opening 010 = 1,000,000.00 · two credits (+150,000, +2,500.25) · one debit (−45,000)
# Closing 015 = 1,107,500.25. Includes an 88 continuation on the second detail's text.
BAI2 = b"""01,BANKOFTEST,ACME,260731,1200,1,80,80,2/
02,ACME,BANKOFTEST,1,260731,1200,USD,2/
03,4471001234,USD,010,100000000,,,015,110750025,,/
16,165,15000000,0,WIRE123,,WIRE IN - PARTICIPANT CITY A/
16,175,250025,0,DEP889,,LOCKBOX DEPOSIT/
88,SUPPLEMENTAL RECEIPTS
16,455,4500000,0,CHK2211,,CHECK 2211 VENDOR PAYMENT/
49,230500050,6/
98,230500050,1,8/
99,230500050,1,10/
"""

def test_bai2():
    check("bai2: detect", formats.detect(BAI2) == "bai2")
    stmts = list(formats.parse(BAI2))
    check("bai2: one account", len(stmts) == 1, stmts)
    s = stmts[0]
    check("bai2: account", s.source_account == "4471001234", s.source_account)
    check("bai2: as_of from 02", s.as_of == date(2026, 7, 31), s.as_of)
    check("bai2: opening", s.opening == 1_000_000.00, s.opening)
    check("bai2: closing", s.closing == 1_107_500.25, s.closing)
    check("bai2: 3 lines", len(s.lines) == 3, len(s.lines))
    check("bai2: signs", s.lines[0].amount > 0 and s.lines[2].amount < 0,
          [l.amount for l in s.lines])
    check("bai2: 88 continuation in text", "SUPPLEMENTAL" in s.lines[1].description,
          s.lines[1].description)
    check("bai2: ties", s.ties() is True,
          f"open {s.opening} + sum {sum(l.amount for l in s.lines)} vs close {s.closing}")


# ─────────────────────────── camt.053 ───────────────────────────
CAMT = b"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.08">
 <BkToCstmrStmt><Stmt>
  <Acct><Id><Othr><Id>8810005678</Id></Othr></Id><Ccy>USD</Ccy>
    <Svcr><FinInstnId><Nm>Bank of Test</Nm></FinInstnId></Svcr></Acct>
  <Bal><Tp><CdOrPrtry><Cd>OPBD</Cd></CdOrPrtry></Tp>
    <Amt Ccy="USD">50000.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Dt><Dt>2026-07-01</Dt></Dt></Bal>
  <Bal><Tp><CdOrPrtry><Cd>CLBD</Cd></CdOrPrtry></Tp>
    <Amt Ccy="USD">48249.50</Amt><CdtDbtInd>CRDT</CdtDbtInd><Dt><Dt>2026-07-31</Dt></Dt></Bal>
  <Ntry><Amt Ccy="USD">1200.50</Amt><CdtDbtInd>CRDT</CdtDbtInd><Sts>BOOK</Sts>
    <BookgDt><Dt>2026-07-10</Dt></BookgDt><NtryRef>REF-1</NtryRef>
    <AddtlNtryInf>ACH RECEIPT</AddtlNtryInf></Ntry>
  <Ntry><Amt Ccy="USD">2951.00</Amt><CdtDbtInd>DBIT</CdtDbtInd><Sts>BOOK</Sts>
    <BookgDt><Dt>2026-07-22</Dt></BookgDt><NtryRef>REF-2</NtryRef>
    <AddtlNtryInf>PAYROLL FUNDING</AddtlNtryInf></Ntry>
 </Stmt></BkToCstmrStmt></Document>
"""

def test_camt():
    check("camt: detect", formats.detect(CAMT) == "camt053")
    s = list(formats.parse(CAMT))[0]
    check("camt: account", s.source_account == "8810005678", s.source_account)
    check("camt: bank name", s.bank_name == "Bank of Test", s.bank_name)
    check("camt: opening", s.opening == 50000.00, s.opening)
    check("camt: closing + as_of", s.closing == 48249.50 and s.as_of == date(2026, 7, 31),
          (s.closing, s.as_of))
    check("camt: debit negative", s.lines[1].amount == -2951.00, s.lines[1].amount)
    check("camt: ties", s.ties() is True,
          f"open {s.opening} + sum {sum(l.amount for l in s.lines)} vs close {s.closing}")


# ─────────────────────────── MT940 ───────────────────────────
# Opening C 25,000.00 · credit 5,000.00 · debit 1,250.75 · closing C 28,749.25
MT940 = b""":20:STMT-2026-07
:25:BOFT/9944002211
:28C:7/1
:60F:C260701USD25000,00
:61:2607150715C5000,00NTRFCUSTREF-77//BK555
:86:INCOMING WIRE PARTICIPANT CITY B
:61:2607200720D1250,75NCHKCHK-1102//BK556
:86:CHECK 1102 OFFICE SUPPLY
:62F:C260731USD28749,25
-
"""

def test_mt940():
    check("mt940: detect", formats.detect(MT940) == "mt940")
    s = list(formats.parse(MT940))[0]
    check("mt940: account", s.source_account == "9944002211", s.source_account)
    check("mt940: currency", s.currency == "USD", s.currency)
    check("mt940: opening", s.opening == 25000.00, s.opening)
    check("mt940: closing + as_of", s.closing == 28749.25 and s.as_of == date(2026, 7, 31),
          (s.closing, s.as_of))
    check("mt940: 2 lines", len(s.lines) == 2, len(s.lines))
    check("mt940: debit negative", s.lines[1].amount == -1250.75, s.lines[1].amount)
    check("mt940: :86: description", "PARTICIPANT CITY B" in s.lines[0].description,
          s.lines[0].description)
    check("mt940: cust ref", s.lines[0].bank_ref == "CUSTREF-77", s.lines[0].bank_ref)
    check("mt940: ties", s.ties() is True,
          f"open {s.opening} + sum {sum(l.amount for l in s.lines)} vs close {s.closing}")


# ─────────────────────────── OFX (1.x SGML — unclosed tags) ───────────────────────────
OFX = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX><SIGNONMSGSRSV1><SONRS><FI><ORG>Bank of Test</ORG></FI></SONRS></SIGNONMSGSRSV1>
<BANKMSGSRSV1><STMTTRNRS><STMTRS>
<CURDEF>USD
<BANKACCTFROM><ACCTID>77120099</ACCTID></BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260705120000<TRNAMT>800.00<FITID>F-1<NAME>DEPOSIT</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260718120000<TRNAMT>-320.40<FITID>F-2<NAME>UTILITY PMT<MEMO>JULY</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL><BALAMT>10479.60<DTASOF>20260731</LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""

def test_ofx():
    check("ofx: detect", formats.detect(OFX) == "ofx")
    s = list(formats.parse(OFX))[0]
    check("ofx: account", s.source_account == "77120099", s.source_account)
    check("ofx: bank", s.bank_name == "Bank of Test", s.bank_name)
    check("ofx: closing + as_of", s.closing == 10479.60 and s.as_of == date(2026, 7, 31),
          (s.closing, s.as_of))
    check("ofx: 2 lines, signed", len(s.lines) == 2 and s.lines[1].amount == -320.40,
          [l.amount for l in s.lines])
    check("ofx: name+memo joined", s.lines[1].description == "UTILITY PMT — JULY",
          s.lines[1].description)
    check("ofx: fitid ref", s.lines[0].bank_ref == "F-1", s.lines[0].bank_ref)


# ─────────────────────────── dispatcher ───────────────────────────
def test_dispatch():
    for name, blob in (("bai2", BAI2), ("camt053", CAMT), ("mt940", MT940), ("ofx", OFX)):
        got = list(formats.parse(blob))
        check(f"dispatch: {name} via sniff", len(got) >= 1 and got[0].source_account, got)
    try:
        formats.detect(b"hello,world\n1,2,3\n")
        check("dispatch: garbage rejected", False, "no exception")
    except ValueError:
        check("dispatch: garbage rejected", True)


if __name__ == "__main__":
    for fn in (test_bai2, test_camt, test_mt940, test_ofx, test_dispatch):
        fn()
    failed = [(n, d) for n, ok, d in _R if not ok]
    for n, ok, d in _R:
        print(("PASS " if ok else "FAIL ") + n + ("" if ok else f"  — {d}"))
    print(f"\n{len(_R) - len(failed)}/{len(_R)} passed")
    sys.exit(1 if failed else 0)

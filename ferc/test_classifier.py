"""Quick self-test for the FERC classifier. Run: python ferc/test_classifier.py"""
from classifier import FERCClassifier, ferc_project

c = FERCClassifier()

CASES = {
    "101": "Plant in service (control)",
    "107": "CWIP — capital projects",
    "107-00": "CWIP — capital projects",
    "350": "Transmission plant",
    "359": "Transmission plant",
    "360-12": "Distribution plant",
    "01-560-00": "Transmission O&M",
    "560.500": "Transmission O&M",
    "920": "Administrative & general (A&G)",
    "440": "Operating revenues",
    "1010": "Unmapped — review",   # non-FERC 4-digit -> default
    "ar_dom": "Unmapped — review", # non-numeric -> default
}

failures = []
for code, expected in CASES.items():
    got = c.project_for(code)
    ok = got == expected
    print(f"{'ok ' if ok else 'FAIL'} {code:<12} -> {got}")
    if not ok:
        failures.append((code, expected, got))

# expense-type classification
EXP = {"107": "Capital", "350": "Capital", "560": "O&M", "440": "Revenue", "201": "Balance sheet"}
for code, et in EXP.items():
    got = c.classify(code)["expense_type"]
    ok = got == et
    print(f"{'ok ' if ok else 'FAIL'} {code:<12} expense_type -> {got}")
    if not ok:
        failures.append((code, et, got))

# grouping demo: many accounts, one project + expense type each
accts = [{"code": "560-00"}, {"code": "562-00"}, {"code": "107"}, {"code": "350"}]
print("\nproject assignment:")
for a in c.assign(accts):
    print(f"  {a['code']:<10} -> {a['project']:<28} [{a['expense_type']}]")

assert ferc_project("566") == "Transmission O&M"
print("\nRESULT:", "ALL PASS" if not failures else f"{len(failures)} FAILURES")

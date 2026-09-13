"""#38 transport tests — SFTP + IMAP treasury adapters, offline (fake clients, no network).

Run:  py -3 adapters/format_tests/test_transports.py
"""
import io
import os
import sys
import tempfile
from datetime import date
from email.message import EmailMessage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from adapters.treasury import SFTPTreasury, IMAPTreasury          # noqa: E402

_R = []
def check(name, cond, detail=""):
    _R.append((name, bool(cond), "" if cond else str(detail)))


BAI2 = b"""01,BANKOFTEST,ACME,260531,1200,1,80,80,2/
02,ACME,BANKOFTEST,1,260531,1200,USD,2/
03,bank_4471,USD,010,45000000,,,015,57630000,,/
16,165,15000000,0,WIRE-501,,CUSTOMER WIRE RECEIPT/
16,475,2450000,0,CHK-2201,,CHECK 2201 VENDOR/
16,175,80000,0,DEP-77,,COUNTER DEPOSIT/
49,120160000,5/
98,120160000,1,7/
99,120160000,1,9/
"""
OFX = b"""OFXHEADER:100

<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>
<CURDEF>USD
<BANKACCTFROM><ACCTID>77120099</ACCTID></BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260705<TRNAMT>800.00<FITID>F-1<NAME>DEPOSIT</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL><BALAMT>10479.60<DTASOF>20260731</LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


# ─────────────────────────── fake SFTP ───────────────────────────
class _FakeFile(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False

class FakeSFTP:
    def __init__(self, files):
        self.files = dict(files)          # path -> bytes
        self.renames = []
        self.mkdirs = []
        self.closed = False
    def listdir(self, d):
        names = [p.split("/")[-1] for p in self.files if p.rsplit("/", 1)[0] == d.rstrip("/")]
        if not names and not any(p.startswith(d.rstrip("/") + "/") for p in self.files) \
           and d.rstrip("/") not in self.mkdirs:
            raise IOError(d)
        return names
    def open(self, path, mode="rb"):
        if path not in self.files: raise IOError(path)
        return _FakeFile(self.files[path])
    def rename(self, src, dst):
        self.renames.append((src, dst)); self.files[dst] = self.files.pop(src)
    def mkdir(self, d): self.mkdirs.append(d)
    def close(self): self.closed = True


def test_sftp():
    fake = FakeSFTP({"/outbound/stmt-may.bai2": BAI2,
                     "/outbound/notes.pdf": b"%PDF-1.4 not a statement"})
    t = SFTPTreasury(host="h", user="u", key_file="k", remote_dir="/outbound",
                     client_factory=lambda: fake)
    bals = list(t.fetch_statements(date(2026, 5, 31)))
    check("sftp: balance parsed", len(bals) == 1 and bals[0].balance == 576300.00 and
          bals[0].source_account == "bank_4471", bals)
    check("sftp: unparseable file skipped + reported", t.skipped == ["notes.pdf"], t.skipped)
    check("sftp: parsed file archived, junk left in place",
          fake.renames == [("/outbound/stmt-may.bai2", "/outbound/processed/stmt-may.bai2")]
          and "/outbound/notes.pdf" in fake.files, fake.renames)
    check("sftp: connection closed", fake.closed)
    fake2 = FakeSFTP({"/outbound/stmt-may.bai2": BAI2})
    t2 = SFTPTreasury(host="h", user="u", key_file="k", remote_dir="/outbound",
                      client_factory=lambda: fake2)
    lines = list(t2.fetch_lines(date(2026, 5, 31)))
    check("sftp: fetch_lines yields transaction detail", len(lines) == 3 and
          lines[1].amount == -24500.00, [(l.bank_ref, l.amount) for l in lines])
    # idempotency: re-run against the post-archive state finds nothing new
    t3 = SFTPTreasury(host="h", user="u", key_file="k", remote_dir="/outbound",
                      client_factory=lambda: fake2)
    check("sftp: re-run is idempotent (archived files not reprocessed)",
          list(t3.fetch_statements(date(2026, 5, 31))) == [], "reprocessed")


# ─────────────────────────── fake IMAP ───────────────────────────
def _mail_with_attachment(fname, blob):
    m = EmailMessage()
    m["From"] = "statements@bank.example"
    m["Subject"] = "Your statement"
    m.set_content("attached")
    m.add_attachment(blob, maintype="application", subtype="octet-stream", filename=fname)
    return m.as_bytes()

class FakeIMAP:
    def __init__(self, messages):
        self.messages = messages          # num -> rfc822 bytes
        self.logged_in = None
        self.selected = None
        self.copies = []
        self.searches = []
        self.logged_out = False
    def login(self, u, p): self.logged_in = (u, p); return "OK", []
    def select(self, mb): self.selected = mb; return "OK", []
    def search(self, cs, criteria):
        self.searches.append(criteria)
        return "OK", [b" ".join(k for k in self.messages)]
    def fetch(self, num, spec): return "OK", [(num + b" (RFC822)", self.messages[num])]
    def copy(self, num, folder): self.copies.append((num, folder)); return "OK", []
    def logout(self): self.logged_out = True; return "BYE", []


def test_imap():
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("s3cret\n"); pwfile = f.name
    try:
        fake = FakeIMAP({b"1": _mail_with_attachment("stmt.ofx", OFX),
                         b"2": _mail_with_attachment("scan.pdf", b"%PDF junk")})
        t = IMAPTreasury(host="h", user="treasury@acme", password_file=pwfile,
                         sender="statements@bank.example", processed_folder="Processed",
                         client_factory=lambda: fake)
        bals = list(t.fetch_statements(date(2026, 7, 31)))
        check("imap: OFX attachment parsed", len(bals) == 1 and bals[0].balance == 10479.60 and
              bals[0].source_account == "77120099", bals)
        check("imap: password read from file, never stored on the adapter",
              fake.logged_in == ("treasury@acme", "s3cret") and
              not any("s3cret" in str(v) for v in vars(t).values()), vars(t))
        check("imap: sender criteria applied",
              fake.searches and 'FROM "statements@bank.example"' in fake.searches[0], fake.searches)
        check("imap: processed copies to folder (both messages)",
              fake.copies == [(b"1", "Processed"), (b"2", "Processed")], fake.copies)
        check("imap: logout on completion", fake.logged_out)
        fake2 = FakeIMAP({b"1": _mail_with_attachment("stmt.ofx", OFX)})
        t2 = IMAPTreasury(host="h", user="u", password_file=pwfile, client_factory=lambda: fake2)
        lines = list(t2.fetch_lines(date(2026, 7, 31)))
        check("imap: fetch_lines yields detail", len(lines) == 1 and lines[0].amount == 800.00, lines)
    finally:
        os.unlink(pwfile)


if __name__ == "__main__":
    for fn in (test_sftp, test_imap):
        fn()
    failed = [(n, d) for n, ok, d in _R if not ok]
    for n, ok, d in _R:
        print(("PASS " if ok else "FAIL ") + n + ("" if ok else "  - " + str(d)))
    print(f"\n{len(_R) - len(failed)}/{len(_R)} passed")
    sys.exit(1 if failed else 0)

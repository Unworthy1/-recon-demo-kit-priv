-- #43 Proposed journal entries (free tier). Reconciling items become DRAFT entries that a person
-- reviews, a different person approves, and an export hands to the ERP. Nothing is ever posted
-- automatically. The database — not just the API — enforces the accounting invariants:
--   * every entry has >= 2 lines and balances (sum debits = sum credits), checked at COMMIT
--   * each line is a debit OR a credit, never both, never negative
--   * lines are frozen once an entry leaves draft
--   * status moves only along draft -> submitted -> approved -> exported (return to draft / void)
--   * one live entry per reconciling item (no double-booking the same bank fee)

CREATE TABLE je_export_profile (
  id          serial PRIMARY KEY,
  name        text NOT NULL UNIQUE,
  config      jsonb NOT NULL,                  -- journal.validate_profile()d
  active      boolean NOT NULL DEFAULT true,
  created_by  text,
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE je_export (
  id              bigserial PRIMARY KEY,
  profile_name    text NOT NULL,
  profile         jsonb NOT NULL,              -- snapshot: the exact layout this file was rendered with
  created_by      text NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  entry_count     int NOT NULL,
  line_count      int NOT NULL,
  content_sha256  text NOT NULL,
  content         text NOT NULL                -- the file itself: re-download is byte-identical
);

CREATE TABLE journal_entry (
  id             bigserial PRIMARY KEY,
  period_end     date NOT NULL,
  gl_account_id  text REFERENCES gl_account(id),        -- the reconciliation this entry resolves
  memo           text NOT NULL,
  source_kind    text NOT NULL CHECK (source_kind IN ('stmt_open_item', 'grir', 'residual', 'manual')),
  source_ref     text,                                   -- statement_line id / po id / reconciliation id
  rationale      text NOT NULL DEFAULT '',               -- why the engine proposed it (deterministic)
  status         text NOT NULL DEFAULT 'draft'
                   CHECK (status IN ('draft', 'submitted', 'approved', 'exported', 'void')),
  created_by     text NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  submitted_by   text,  submitted_at  timestamptz,
  approved_by    text,  approved_at   timestamptz,
  returned_by    text,  returned_at   timestamptz,  return_reason text,
  voided_by      text,  voided_at     timestamptz,  void_reason   text,
  export_id      bigint REFERENCES je_export(id),
  exported_at    timestamptz
);
CREATE UNIQUE INDEX journal_entry_live_source ON journal_entry (source_kind, source_ref)
  WHERE source_ref IS NOT NULL AND status <> 'void';
CREATE INDEX journal_entry_status ON journal_entry (status, period_end);

CREATE TABLE journal_entry_line (
  id             bigserial PRIMARY KEY,
  entry_id       bigint NOT NULL REFERENCES journal_entry(id),
  line_no        int NOT NULL,
  account_code   text NOT NULL CHECK (account_code <> ''),
  account_name   text NOT NULL DEFAULT '',
  gl_account_id  text REFERENCES gl_account(id),        -- set when the line hits a reconciled account
  fund_id        text,                                   -- optional fund tag; no FK in the core schema
  description    text NOT NULL DEFAULT '',
  debit          numeric(18,2) NOT NULL DEFAULT 0 CHECK (debit >= 0),
  credit         numeric(18,2) NOT NULL DEFAULT 0 CHECK (credit >= 0),
  CHECK ((debit > 0) <> (credit > 0)),                  -- exactly one side
  UNIQUE (entry_id, line_no)
);

-- Balance: deferred to COMMIT so an entry and its lines can be written in one transaction.
-- (PL/pgSQL resolves every record field an expression names, even in an untaken CASE branch —
--  so OLD/NEW are only touched inside IF branches where that record exists.)
CREATE FUNCTION je_assert_balanced() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  eid bigint; n int; dr numeric; cr numeric;
BEGIN
  IF TG_TABLE_NAME = 'journal_entry' THEN
    eid := NEW.id;
  ELSIF TG_OP = 'DELETE' THEN
    eid := OLD.entry_id;
  ELSE
    eid := NEW.entry_id;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM journal_entry WHERE id = eid) THEN RETURN NULL; END IF;
  SELECT count(*), coalesce(sum(debit), 0), coalesce(sum(credit), 0) INTO n, dr, cr
    FROM journal_entry_line WHERE entry_id = eid;
  IF n < 2 THEN
    RAISE EXCEPTION 'journal entry % needs at least two lines (has %)', eid, n USING ERRCODE = 'check_violation';
  END IF;
  IF dr <> cr THEN
    RAISE EXCEPTION 'journal entry % is unbalanced: debits % <> credits %', eid, dr, cr USING ERRCODE = 'check_violation';
  END IF;
  RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER je_balanced_lines AFTER INSERT OR UPDATE OR DELETE ON journal_entry_line
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION je_assert_balanced();
CREATE CONSTRAINT TRIGGER je_balanced_entry AFTER INSERT ON journal_entry
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION je_assert_balanced();

-- Lines are editable only while the entry is a draft.
CREATE FUNCTION je_lines_frozen() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE st text; eid bigint;
BEGIN
  IF TG_OP = 'DELETE' THEN
    eid := OLD.entry_id;
  ELSE
    eid := NEW.entry_id;
  END IF;
  SELECT status INTO st FROM journal_entry WHERE id = eid;
  IF TG_OP = 'UPDATE' AND OLD.entry_id <> NEW.entry_id THEN
    RAISE EXCEPTION 'journal entry lines cannot move between entries' USING ERRCODE = 'check_violation';
  END IF;
  IF st IS DISTINCT FROM 'draft' THEN
    RAISE EXCEPTION 'journal entry lines are frozen once the entry is %', st USING ERRCODE = 'check_violation';
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER je_lines_frozen BEFORE INSERT OR UPDATE OR DELETE ON journal_entry_line
  FOR EACH ROW EXECUTE FUNCTION je_lines_frozen();

-- Status machine + header immutability outside draft. Entries are never deleted.
CREATE FUNCTION je_transition() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'journal entries are never deleted — void them' USING ERRCODE = 'check_violation';
  END IF;
  IF OLD.status <> NEW.status AND (OLD.status, NEW.status) NOT IN (
       ('draft', 'submitted'), ('submitted', 'approved'), ('submitted', 'draft'),
       ('approved', 'exported'), ('draft', 'void'), ('submitted', 'void'), ('approved', 'void')) THEN
    RAISE EXCEPTION 'journal entry % cannot move from % to %', OLD.id, OLD.status, NEW.status
      USING ERRCODE = 'check_violation';
  END IF;
  IF OLD.status <> 'draft' AND (OLD.period_end, OLD.memo, OLD.gl_account_id, OLD.source_kind, OLD.source_ref)
       IS DISTINCT FROM (NEW.period_end, NEW.memo, NEW.gl_account_id, NEW.source_kind, NEW.source_ref) THEN
    RAISE EXCEPTION 'journal entry % is % — its header can no longer change', OLD.id, OLD.status
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER je_transition BEFORE UPDATE OR DELETE ON journal_entry
  FOR EACH ROW EXECUTE FUNCTION je_transition();

-- Where the other side of a proposed entry goes. Configuration: first matching rule by priority;
-- a NULL pattern is the fallback for its kind. Every proposal still needs human review.
-- stmt_open_item / residual patterns match the item description; grir patterns match the residue
-- reason (grni | over_invoiced | invoiced_not_received). account_code '@po_gl_code' means "the
-- purchase order's own GL account" — an aged receipt with no invoice reverses against the account
-- it was received into, and an invoice with no receipt is expensed there; only a genuine price
-- difference (over-invoicing) belongs in purchase price variance.
CREATE TABLE je_offset_rule (
  id            serial PRIMARY KEY,
  source_kind   text NOT NULL CHECK (source_kind IN ('stmt_open_item', 'grir', 'residual')),
  pattern       text,                          -- case-insensitive Python regex on the item description
  account_code  text NOT NULL,
  account_name  text NOT NULL DEFAULT '',
  priority      int  NOT NULL DEFAULT 100,
  active        boolean NOT NULL DEFAULT true
);

INSERT INTO je_offset_rule (source_kind, pattern, account_code, account_name, priority) VALUES
 ('stmt_open_item', '\b(fee|fees|service charge|maint(enance)? charge|analysis charge)\b', '6510', 'Bank service charges', 10),
 ('stmt_open_item', '\binterest\b',                                                    '4910', 'Interest income', 20),
 ('stmt_open_item', NULL,                                                              '9999', 'Suspense — needs classification', 1000),
 ('grir',           '^(grni|invoiced_not_received)$',                                  '@po_gl_code', 'PO account', 10),
 ('grir',           NULL,                                                              '5990', 'Purchase price variance', 1000),
 ('residual',       NULL,                                                              '9999', 'Suspense — needs classification', 1000);

INSERT INTO je_export_profile (name, config, created_by) VALUES
 ('generic-csv', '{
    "columns": [
      {"header": "JournalNumber",   "field": "entry_number"},
      {"header": "PostingDate",     "field": "posting_date"},
      {"header": "LineNo",          "field": "line_no"},
      {"header": "AccountCode",     "field": "account_code"},
      {"header": "AccountName",     "field": "account_name"},
      {"header": "Debit",           "field": "debit"},
      {"header": "Credit",          "field": "credit"},
      {"header": "LineDescription", "field": "description"},
      {"header": "Memo",            "field": "memo"},
      {"header": "Source",          "field": "source_kind"},
      {"header": "PreparedBy",      "field": "prepared_by"},
      {"header": "ApprovedBy",      "field": "approved_by"}
    ],
    "date_format": "%Y-%m-%d", "delimiter": ",", "include_header": true,
    "amount_sign": "debit_positive", "line_ending": "crlf"
  }', 'system');

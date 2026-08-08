-- #34 Transaction-level matching substrate (see docs/FUND-MATCHING-DESIGN.md).
-- Balance-level reconciliation (01-schema) keeps working untouched; accounts gain
-- transaction matching only when lines are ingested for them (progressive disclosure).
-- Matching is always scoped per (gl_account, period) — 350 accounts = 350 small problems.

CREATE TABLE gl_transaction (
  id             bigserial PRIMARY KEY,
  gl_account_id  text NOT NULL REFERENCES gl_account(id),
  txn_date       date NOT NULL,
  post_date      date,
  amount         numeric NOT NULL,        -- signed: debits negative by bank-statement convention
  description    text,
  doc_ref        text,                    -- check no / journal id / wire ref
  source         text,                    -- gl | ap | payroll | manual | ...
  counterparty_fund_id text,              -- interfund lines (#33; FK added with 14-funds.sql)
  transfer_group text,                    -- interfund pairing key (#33), e.g. 'IT-2026-07-014'
  import_batch_id text REFERENCES import_batch(id)
);
CREATE INDEX gl_transaction_acct_date_idx ON gl_transaction (gl_account_id, txn_date);
CREATE INDEX gl_transaction_transfer_idx  ON gl_transaction (transfer_group)
  WHERE transfer_group IS NOT NULL;

CREATE TABLE statement_line (
  id             bigserial PRIMARY KEY,
  gl_account_id  text NOT NULL REFERENCES gl_account(id),  -- resolved via the §E source_account map
  stmt_date      date NOT NULL,
  amount         numeric NOT NULL,        -- signed: credits positive, debits negative
  description    text,
  bank_ref       text,                    -- bank reference / check number / FITID
  import_batch_id text REFERENCES import_batch(id)
);
CREATE INDEX statement_line_acct_date_idx ON statement_line (gl_account_id, stmt_date);

-- Many-to-many: one deposit ↔ several GL lines, one GL entry ↔ several bank fees, etc.
CREATE TABLE txn_match (
  id          bigserial PRIMARY KEY,
  match_type  text NOT NULL,              -- auto_exact | auto_rule | suggested | manual
  status      text NOT NULL DEFAULT 'matched',   -- matched | suggested | rejected
  rule_id     int,                        -- which match_rule fired (NULL = manual/exact)
  matched_by  text NOT NULL,              -- app_user, or 'engine'
  matched_at  timestamptz NOT NULL DEFAULT now(),
  decided_by  text,                       -- who confirmed/rejected a suggestion (maker-checker)
  decided_at  timestamptz
);

CREATE TABLE txn_match_member (
  match_id     bigint NOT NULL REFERENCES txn_match(id) ON DELETE CASCADE,
  gl_txn_id    bigint REFERENCES gl_transaction(id),
  stmt_line_id bigint REFERENCES statement_line(id),
  CHECK ((gl_txn_id IS NULL) <> (stmt_line_id IS NULL))    -- each member row is exactly one side
);
CREATE INDEX txn_match_member_match_idx ON txn_match_member (match_id);
-- A line may belong to at most one live (non-rejected) match. Enforced by the engine at
-- match time inside a transaction; these indexes make the lookup cheap and catch races.
CREATE INDEX txn_match_member_gl_idx   ON txn_match_member (gl_txn_id)    WHERE gl_txn_id IS NOT NULL;
CREATE INDEX txn_match_member_stmt_idx ON txn_match_member (stmt_line_id) WHERE stmt_line_id IS NOT NULL;

-- Matching rules are config, not code (INTAKE §E addendum).
CREATE TABLE match_rule (
  id            serial PRIMARY KEY,
  gl_account_id text REFERENCES gl_account(id),  -- NULL = global default
  amount_tol    numeric NOT NULL DEFAULT 0,
  date_window   int NOT NULL DEFAULT 5,          -- days
  ref_pattern   text,                            -- regex over bank_ref/doc_ref (e.g. check numbers)
  priority      int NOT NULL DEFAULT 100,
  active        boolean NOT NULL DEFAULT true
);

-- Open items = lines not in any live match: outstanding checks / deposits in transit, aged.
CREATE VIEW open_item AS
SELECT 'gl'  AS side, t.id, t.gl_account_id, t.txn_date AS item_date, t.amount,
       t.description, t.doc_ref AS ref
FROM gl_transaction t
WHERE NOT EXISTS (SELECT 1 FROM txn_match_member m JOIN txn_match x ON x.id = m.match_id
                  WHERE m.gl_txn_id = t.id AND x.status <> 'rejected')
UNION ALL
SELECT 'stmt' AS side, s.id, s.gl_account_id, s.stmt_date AS item_date, s.amount,
       s.description, s.bank_ref AS ref
FROM statement_line s
WHERE NOT EXISTS (SELECT 1 FROM txn_match_member m JOIN txn_match x ON x.id = m.match_id
                  WHERE m.stmt_line_id = s.id AND x.status <> 'rejected');

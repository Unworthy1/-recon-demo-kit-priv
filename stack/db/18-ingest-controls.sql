-- #41 Ingest data controls (free tier). A statement file must prove it is complete and unaltered
-- before its lines can feed matching. Controls are evaluated in adapters/formats/controls.py;
-- this schema records the evidence and gates the data.
--
-- import_batch.status gains two values:
--   quarantined : a blocking control failed — lines are loaded (evidence preserved) but excluded
--                 from matching and open items until a reviewer who is not the uploader releases it
--   rejected    : the exact file was already loaded — no lines inserted, results kept for audit

ALTER TABLE import_batch
  ADD COLUMN content_sha256 text,
  ADD COLUMN released_by    text,
  ADD COLUMN released_at    timestamptz,
  ADD COLUMN release_reason text,
  ADD CONSTRAINT import_batch_status_chk
    CHECK (status IN ('committed', 'rolled_back', 'quarantined', 'rejected'));

-- The duplicate guard, enforced by the database and not just the API: one live batch per file.
CREATE UNIQUE INDEX import_batch_live_sha ON import_batch (content_sha256)
  WHERE content_sha256 IS NOT NULL AND status IN ('committed', 'quarantined');

CREATE TABLE ingest_control_result (
  id               bigserial PRIMARY KEY,
  import_batch_id  text NOT NULL REFERENCES import_batch(id),
  control          text NOT NULL,            -- e.g. bai2.account_trailer
  scope            text NOT NULL,            -- file | group:N | account:<id> | statement:<id>
  status           text NOT NULL CHECK (status IN ('pass', 'fail', 'not_available')),
  severity         text NOT NULL CHECK (severity IN ('blocking', 'warning')),
  expected         text,
  actual           text,
  detail           text NOT NULL DEFAULT '',
  created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ingest_control_result_batch ON ingest_control_result (import_batch_id);

-- Open items must not surface lines from a quarantined / rejected / rolled-back batch.
-- Same columns as 13-matching.sql; only the statement side gains the batch-status filter.
CREATE OR REPLACE VIEW open_item AS
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
                  WHERE m.stmt_line_id = s.id AND x.status <> 'rejected')
  AND (s.import_batch_id IS NULL
       OR EXISTS (SELECT 1 FROM import_batch b
                  WHERE b.id = s.import_batch_id AND b.status = 'committed'));

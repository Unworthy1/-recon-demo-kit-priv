-- OpenRecon reference schema. The same shape the static UI uses (web/assets/app.js),
-- now backed by a database the engine writes and the API reads.

CREATE TABLE gl_account (
  id             text PRIMARY KEY,        -- stable id used in URLs
  code           text NOT NULL,           -- GL account key (matches the INTAKE §E account map)
  name           text NOT NULL,
  grp            text NOT NULL,           -- account group (Cash & equivalents, Accounts receivable, ...)
  bank           text,                    -- institution / sub-ledger label
  mask           text,                    -- masked account / "sub-ledger"
  source_account text,                    -- bank statement source id (INTAKE §E map); NULL = no statement
  tolerance      numeric NOT NULL DEFAULT 25,
  assigned_to    text
);

CREATE TABLE reconciliation (
  id                serial PRIMARY KEY,
  gl_account_id     text NOT NULL REFERENCES gl_account(id),
  period_end        date NOT NULL,
  gl_balance        numeric,
  statement_balance numeric,             -- NULL = no statement matched yet
  variance          numeric,             -- gl_balance - statement_balance
  status            text NOT NULL DEFAULT 'unreconciled',  -- reconciled | variance | unreconciled
  work_status       text NOT NULL DEFAULT 'assigned',      -- ack | assigned | progress | resolved | approved | reviewed | sent_back
  ocr_account       text,
  ocr_date          date,
  document_ref      text,                -- DMS doc id/url for the source statement
  note              text,
  resolved_by       text,
  resolved_at       timestamptz,
  approved_by       text,
  approved_at       timestamptz,
  sent_back_by      text,                -- reviewer who sent it back
  sent_back_at      timestamptz,
  sent_back_reason  text,                -- rework note, included in the preparer's email
  UNIQUE (gl_account_id, period_end)
);

CREATE TABLE supporting_document (
  id            serial PRIMARY KEY,
  gl_account_id text NOT NULL REFERENCES gl_account(id),
  filename      text NOT NULL,
  uploaded_by   text,
  uploaded_at   timestamptz NOT NULL DEFAULT now(),
  note          text,
  dms_doc_id    text,
  dms_url       text
);

CREATE INDEX ON reconciliation (period_end, status);
CREATE INDEX ON supporting_document (gl_account_id);

-- Historical ETL: provenance so backfilled prior-year records are distinguishable from records that
-- went through the live maker-checker workflow, plus a batch ledger for idempotent, reversible loads.

CREATE TABLE import_batch (
  id               text PRIMARY KEY,                 -- e.g. imp-a1b2c3d4
  source           text,                             -- the source file / system
  created_by       text NOT NULL,
  created_at       timestamptz NOT NULL DEFAULT now(),
  status           text NOT NULL DEFAULT 'committed',-- committed | rolled_back
  rows_loaded      int  NOT NULL DEFAULT 0,
  accounts_created int  NOT NULL DEFAULT 0,
  periods_created  int  NOT NULL DEFAULT 0,
  note             text
);

-- origin marks how a record entered the system. 'native' = prepared/approved in OpenRecon;
-- 'historical_import' = migrated evidence (did NOT pass live SoD/approval — never present it as if it did).
ALTER TABLE reconciliation
  ADD COLUMN origin          text NOT NULL DEFAULT 'native',
  ADD COLUMN import_batch_id text REFERENCES import_batch(id),
  ADD COLUMN source_ref      text;

ALTER TABLE gl_account
  ADD COLUMN origin          text NOT NULL DEFAULT 'native',
  ADD COLUMN import_batch_id text REFERENCES import_batch(id);

ALTER TABLE close_period
  ADD COLUMN origin          text NOT NULL DEFAULT 'native',
  ADD COLUMN import_batch_id text REFERENCES import_batch(id);

-- #42 Prep rules (free tier). Named, declarative rule sets (adapters/formats/prep.py) that transform
-- parsed rows between parsing and load: lookup, extract, concat, calc, fill, filter. A rule set is
-- configuration, not code; every change to one is audited, every batch records the exact version
-- it ran, every line records which rule changed which field, and filtered rows are kept.

CREATE TABLE prep_ruleset (
  id           serial PRIMARY KEY,
  name         text NOT NULL UNIQUE,
  target       text NOT NULL DEFAULT 'statement' CHECK (target IN ('statement')),
  rules        jsonb NOT NULL,                       -- ordered rule list (prep.validate()d)
  fingerprint  text NOT NULL,                        -- prep.fingerprint(rules)
  description  text NOT NULL DEFAULT '',
  active       boolean NOT NULL DEFAULT true,
  created_by   text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_by   text,
  updated_at   timestamptz NOT NULL DEFAULT now()
);

-- What ran on this batch: rule set name, fingerprint, a snapshot of the rules, per-rule counts.
-- The snapshot keeps explanations valid after the rule set is edited.
ALTER TABLE import_batch ADD COLUMN prep_summary jsonb;

-- Per line: [{rule, op, label, field, before, after}, ...] — NULL when no rule touched the line.
ALTER TABLE statement_line ADD COLUMN prep_trace jsonb;

-- Rows a filter rule removed. Never loaded, never lost.
CREATE TABLE prep_dropped_row (
  id               bigserial PRIMARY KEY,
  import_batch_id  text NOT NULL REFERENCES import_batch(id),
  source_row       int  NOT NULL,              -- 1-based position in the parsed file
  rule_index       int  NOT NULL,
  rule_label       text NOT NULL DEFAULT '',
  data             jsonb NOT NULL,             -- the row as parsed, before any rule
  created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX prep_dropped_row_batch ON prep_dropped_row (import_batch_id);

-- #37 Saved CSV mapping profiles (free tier). A profile records how one system's CSV export
-- maps onto a target (statement | gl | budget | subledger) — column map, date format,
-- decimal/sign conventions, debit/credit split. Onboarding an odd export = a config row,
-- not code. Applied by adapters/formats/csvmap.py via the ingest API.

CREATE TABLE mapping_profile (
  id         serial PRIMARY KEY,
  name       text NOT NULL UNIQUE,
  target     text NOT NULL,                 -- statement | gl | budget | subledger
  config     jsonb NOT NULL,                -- MappingProfile.to_dict()
  active     boolean NOT NULL DEFAULT true,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

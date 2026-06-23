-- Project funding-allocation map: the % spread of each project across GL accounts/ranges.
-- Authored in a spreadsheet (projects/funding-map.*.csv), loaded via POST /api/projects/funding-map,
-- and used by POST /api/project/{id}/allocate to generate the project_line rows a project
-- reconciliation ties out. A project's funding_pct rows total 100.

CREATE TABLE project_funding (
  id            bigserial PRIMARY KEY,
  project_id    text NOT NULL,
  project_name  text,
  account_match text NOT NULL,        -- "352" (single) or "360-369" (inclusive range)
  match_kind    text NOT NULL,        -- single | range
  account_name  text,
  funding_pct   numeric NOT NULL,
  expense_type  text
);
CREATE INDEX project_funding_pid_idx ON project_funding (project_id);

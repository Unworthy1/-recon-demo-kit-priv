-- Year-end close: period types + lock, and the annual roll-forward (continuity) reconciliations.

CREATE TABLE close_period (
  period_key  text PRIMARY KEY,        -- 2026-05, 2026-Q2, 2026-FY
  label       text NOT NULL,
  period_type text NOT NULL,           -- monthly | quarterly | annual
  status      text NOT NULL DEFAULT 'open',   -- open | locked
  progress    int  NOT NULL DEFAULT 0,
  closed_by   text,
  closed_at   timestamptz
);

CREATE TABLE rollforward (
  id          serial PRIMARY KEY,
  period_key  text NOT NULL REFERENCES close_period(period_key),
  gl_code     text NOT NULL,           -- FERC account; Project derived at read time
  gl_name     text,
  opening     numeric NOT NULL,        -- prior-FY closing, carried forward
  activity    numeric NOT NULL,        -- current-FY movement
  evidence    numeric NOT NULL         -- external (subledger/statement) closing to tie to
  -- closing = opening + activity; tie = closing - evidence  (computed on read)
);
CREATE INDEX ON rollforward (period_key);

INSERT INTO close_period (period_key, label, period_type, status, progress, closed_by, closed_at) VALUES
 ('2026-01','January 2026','monthly','locked',100,'Dana P.','2026-02-05'),
 ('2026-02','February 2026','monthly','locked',100,'Dana P.','2026-03-05'),
 ('2026-03','March 2026','monthly','locked',100,'Joe B.','2026-04-06'),
 ('2026-04','April 2026','monthly','locked',100,'Joe B.','2026-05-05'),
 ('2026-05','May 2026','monthly','open',60,NULL,NULL),
 ('2026-Q1','Q1 2026 (Jan-Mar)','quarterly','locked',100,'Sam R.','2026-04-10'),
 ('2026-Q2','Q2 2026 (Apr-Jun)','quarterly','open',33,NULL,NULL),
 ('2026-FY','FY 2026 - annual close','annual','open',62,NULL,NULL);

INSERT INTO rollforward (period_key, gl_code, gl_name, opening, activity, evidence) VALUES
 ('2026-FY','101','Electric plant in service',842000000,2412800,844412800),
 ('2026-FY','107','Construction work in progress (CWIP)',18400000,-2412800,15987200),
 ('2026-FY','108','Accumulated depreciation',-310000000,-28500000,-338500000),
 ('2026-FY','232','Long-term debt',-420000000,0,-420000000),
 ('2026-FY','216','Retained earnings',-95000000,-12400000,-107000000);

-- Project reconciliation: one supporting document settles the many (FERC) accounts one expense
-- touches. Parallel to the per-account reconciliation tables; the API serves both.

CREATE TABLE project_reconciliation (
  id            text PRIMARY KEY,
  name          text NOT NULL,
  wo            text,                       -- work order / allocation id
  period_end    date NOT NULL,
  assigned_to   text,
  vendor        text,
  source_amount numeric NOT NULL,           -- the one expense the lines must tie to
  source_doc    text,                       -- the one supporting document
  source_ref    text,
  tolerance     numeric NOT NULL DEFAULT 100,
  work_status   text NOT NULL DEFAULT 'assigned',
  settled_by    text,
  settled_at    timestamptz
);

CREATE TABLE project_line (
  id               serial PRIMARY KEY,
  project_id       text NOT NULL REFERENCES project_reconciliation(id),
  gl_code          text NOT NULL,           -- FERC account; its Project is derived at read time
  gl_name          text,
  allocated_amount numeric NOT NULL
);
CREATE INDEX ON project_line (project_id);

INSERT INTO project_reconciliation (id, name, wo, period_end, assigned_to, vendor, source_amount, source_doc, source_ref, work_status) VALUES
 ('PRJ-TX4471','Substation 7 transmission upgrade','WO# TX-4471','2026-05-31','Joe B.','Burns & McDonnell',2412800.00,'EPC_invoice_TX-4471.pdf','INV-TX-4471','progress'),
 ('PRJ-FUEL-0526','Fleet fuel — May allocation','Alloc# FUEL-0526','2026-05-31','Dana P.','Regional Fuel Co.',48250.00,'fuel_invoice_May2026.pdf','INV-FUEL-0526','ack'),
 ('PRJ-IT-0526','IT shared services — May','Alloc# IT-0526','2026-05-31','Sam R.','Managed IT Partners',31500.00,'it_services_invoice_May.pdf','INV-IT-0526','assigned');

INSERT INTO project_line (project_id, gl_code, gl_name, allocated_amount) VALUES
 ('PRJ-TX4471','352','Structures & improvements',412800.00),
 ('PRJ-TX4471','353','Station equipment',1480000.00),
 ('PRJ-TX4471','355','Poles & fixtures',240000.00),
 ('PRJ-TX4471','356','Overhead conductors & devices',280000.00),
 ('PRJ-FUEL-0526','560','Transmission — operation supervision',14200.00),
 ('PRJ-FUEL-0526','580','Distribution — operation supervision',22050.00),
 ('PRJ-FUEL-0526','588','Distribution — miscellaneous expenses',6000.00),
 ('PRJ-FUEL-0526','920','Administrative & general salaries',6000.00),
 ('PRJ-IT-0526','921','Office supplies & expenses',12000.00),
 ('PRJ-IT-0526','923','Outside services employed',14250.00),
 ('PRJ-IT-0526','935','Maintenance of general plant',4800.00);

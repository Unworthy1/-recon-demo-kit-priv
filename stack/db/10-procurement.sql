-- Procurement evidence chain: Requisition → Purchase Order → Work Order / Goods Receipt → Vendor Invoice.
-- Ties spend back to its authorization — the evidence trail behind an AP / expense reconciliation, and a
-- three-way-match check (PO ↔ received ↔ invoiced) that surfaces unmatched documents. (#26, evidence-chain
-- scope: the GR/IR *clearing-account reconciliation* is intentionally deferred — see docs / task notes.)

CREATE TABLE requisition (
  id          text PRIMARY KEY,                 -- PR-1001
  title       text NOT NULL,
  requestor   text,
  department  text,
  amount      numeric NOT NULL,
  status      text NOT NULL DEFAULT 'approved', -- draft | approved | converted | closed
  period_end  date,
  created_at  date
);

CREATE TABLE purchase_order (
  id              text PRIMARY KEY,             -- PO-2001
  requisition_id  text REFERENCES requisition(id),   -- NULL = PO with no requisition (maverick/exception)
  vendor          text NOT NULL,
  amount          numeric NOT NULL,
  gl_code         text,                         -- the expense/asset account it lands on
  gl_name         text,
  status          text NOT NULL DEFAULT 'open', -- open | received | invoiced | closed
  period_end      date,
  created_at      date
);

CREATE TABLE work_order (                       -- fulfillment: WO completion / goods receipt
  id             text PRIMARY KEY,              -- WO-3001 (or GR-3001)
  po_id          text REFERENCES purchase_order(id),
  description    text,
  amount_received numeric NOT NULL,
  received_date  date,
  status         text NOT NULL DEFAULT 'received'   -- received | partial
);

CREATE TABLE vendor_invoice (
  id           text PRIMARY KEY,                -- INV-4001
  po_id        text REFERENCES purchase_order(id),  -- NULL = invoice with no PO (maverick/exception)
  vendor       text NOT NULL,
  invoice_ref  text,
  amount       numeric NOT NULL,
  invoice_date date,
  status       text NOT NULL DEFAULT 'received',    -- received | matched | posted | paid
  doc_ref      text                             -- DMS link to the scanned invoice
);

CREATE INDEX purchase_order_req_idx  ON purchase_order (requisition_id);
CREATE INDEX work_order_po_idx       ON work_order (po_id);
CREATE INDEX vendor_invoice_po_idx   ON vendor_invoice (po_id);

-- A reviewer's confirmation that a chain's three-way match was accepted (maker-checker over procurement).
CREATE TABLE procurement_match (
  po_id        text PRIMARY KEY REFERENCES purchase_order(id),
  accepted_by  text NOT NULL,
  accepted_at  timestamptz NOT NULL DEFAULT now(),
  note         text
);

-- ─────────────────────────── seed: a representative mix (utility flavor) ───────────────────────────
-- Matched, over-invoiced, received-not-invoiced (GRNI), maverick invoice (no PO), and awaiting-PO.
INSERT INTO requisition (id, title, requestor, department, amount, status, period_end, created_at) VALUES
 ('PR-1001','Substation 7 — replacement breakers','Joe B.','Operations',148000,'converted','2026-05-31','2026-05-04'),
 ('PR-1002','Fleet — 3 service trucks','Glen M.','Operations',92000,'converted','2026-05-31','2026-05-06'),
 ('PR-1003','Distribution poles — restock','Dana P.','Operations',64000,'converted','2026-05-31','2026-05-08'),
 ('PR-1005','GIS software renewal','Sam R.','IT',38000,'approved','2026-05-31','2026-05-20');

INSERT INTO purchase_order (id, requisition_id, vendor, amount, gl_code, gl_name, status, period_end, created_at) VALUES
 ('PO-2001','PR-1001','Burns & McDonnell',148000,'353','Station equipment','invoiced','2026-05-31','2026-05-09'),
 ('PO-2002','PR-1002','Regional Fleet Co.',92000,'392','Transportation equipment','invoiced','2026-05-31','2026-05-10'),
 ('PO-2003','PR-1003','Stelpro Supply',64000,'364','Poles, towers & fixtures','received','2026-05-31','2026-05-12'),
 ('PO-2004',NULL,'Quick Office Supplies',3200,'921','Office supplies & expenses','invoiced','2026-05-31','2026-05-22');

INSERT INTO work_order (id, po_id, description, amount_received, received_date, status) VALUES
 ('WO-3001','PO-2001','Breakers delivered & accepted',148000,'2026-05-18','received'),
 ('WO-3002','PO-2002','3 trucks received',92000,'2026-05-19','received'),
 ('WO-3003','PO-2003','Poles received',64000,'2026-05-21','received');

INSERT INTO vendor_invoice (id, po_id, vendor, invoice_ref, amount, invoice_date, status, doc_ref) VALUES
 ('INV-4001','PO-2001','Burns & McDonnell','BMcD-55821',148000,'2026-05-24','matched','DMS-55821'),
 ('INV-4002','PO-2002','Regional Fleet Co.','RFC-7741',96500,'2026-05-26','received','DMS-77410'),
 ('INV-4005','PO-2004','Quick Office Supplies','QOS-3320',3200,'2026-05-23','received','DMS-33200');
-- (PO-2003 received but NOT invoiced → GRNI; PR-1005 approved but no PO yet → awaiting PO;
--  PO-2002 invoiced 96,500 vs PO/received 92,000 → over-invoiced exception;
--  PO-2004 has no requisition → maverick-spend exception.)

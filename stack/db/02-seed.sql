-- Minimal seed so the stack runs end-to-end out of the box (sample data, anonymized).
-- Replace via your GL/treasury adapters once the INTAKE is filled.

INSERT INTO gl_account (id, code, name, grp, bank, mask, source_account, tolerance, assigned_to) VALUES
 ('1010','1010','Operating cash — Wells Fargo','Cash & equivalents','Wells Fargo','••4471','bank_4471',25,'Joe B.'),
 ('1020','1020','Payroll cash — Chase','Cash & equivalents','JPMorgan Chase','••8810','bank_8810',50,'Joe B.'),
 ('1210','1210','Trade AR — domestic','Accounts receivable','AR aging','sub-ledger','ar_dom',100,'Dana P.'),
 ('2010','2010','Trade AP — domestic','Accounts payable','AP aging','sub-ledger','ap_dom',100,'Dana P.'),
 ('1040','1040','FBO escrow — Mercury','Cash & equivalents','Mercury','••5567',NULL,25,'Sam R.');

-- Reconciliations for the current period. Balances/variance/status shown populated so the
-- board renders immediately; `POST /api/reconcile` recomputes them from the wired adapters.
INSERT INTO reconciliation
  (gl_account_id, period_end, gl_balance, statement_balance, variance, status, work_status, ocr_account, ocr_date, document_ref) VALUES
 ('1010','2026-05-31', 2840114.22, 2840114.22,    0.00,'reconciled','resolved','…4471','2026-05-31','STMT-1010'),
 ('1020','2026-05-31',  486220.00,  483220.00, 3000.00,'variance',  'progress','…8810','2026-05-31','STMT-1020'),
 ('1210','2026-05-31', 1894220.10, 1894220.10,    0.00,'reconciled','resolved','AR-DOM','2026-05-31','STMT-1210'),
 ('2010','2026-05-31', -934118.00, -934118.00,    0.00,'reconciled','resolved','AP-DOM','2026-05-31','STMT-2010'),
 ('1040','2026-05-31',   75500.00,        NULL,    NULL,'unreconciled','assigned',NULL,NULL,NULL);

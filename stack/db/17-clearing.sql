-- #35 GR/IR clearing-account reconciliation (free tier) — closes the #26 deferral.
-- Generalizes what an account reconciles AGAINST (recon_type), and gives the GR/IR
-- clearing account its reconciliation: goods receipt credits the clearing account,
-- invoice posting debits it, so per PO the open residue is received − invoiced and
-- the account's GL balance must tie to −sum(open residue), aged.

ALTER TABLE gl_account ADD COLUMN recon_type text NOT NULL DEFAULT 'bank';
-- bank      : vs a bank statement (today's default behavior)
-- subledger : vs a subledger extract (AP / AR / payroll — SubledgerAdapter, INTAKE §R)
-- interfund : vs the counterparty fund's ledger (premium, #33)
-- clearing  : vs itself — the account must age to zero (GR/IR)

CREATE VIEW grir_open_item AS
SELECT po.id AS po_id, po.vendor, po.gl_code,
       coalesce(gr.received, 0)  AS received,
       coalesce(iv.invoiced, 0)  AS invoiced,
       coalesce(gr.received, 0) - coalesce(iv.invoiced, 0) AS open_amount,  -- >0 GRNI · <0 IR ahead of GR
       CASE WHEN coalesce(gr.received,0) > coalesce(iv.invoiced,0) THEN 'grni'
            WHEN coalesce(gr.received,0) = 0                       THEN 'invoiced_not_received'
            ELSE 'over_invoiced' END AS reason,
       gr.last_receipt, iv.last_invoice,
       greatest(coalesce(gr.last_receipt, '1900-01-01'),
                coalesce(iv.last_invoice, '1900-01-01')) AS last_activity
FROM purchase_order po
LEFT JOIN (SELECT po_id, sum(amount_received) AS received, max(received_date) AS last_receipt
           FROM work_order GROUP BY po_id) gr ON gr.po_id = po.id
LEFT JOIN (SELECT po_id, sum(amount) AS invoiced, max(invoice_date) AS last_invoice
           FROM vendor_invoice GROUP BY po_id) iv ON iv.po_id = po.id
WHERE coalesce(gr.received, 0) <> coalesce(iv.invoiced, 0);

-- Demo clearing account over the procurement seed (10-procurement): open residue is
-- +64,000 (PO-2003 GRNI) − 4,500 (PO-2002 over-invoiced) − 3,200 (PO-2004 no GR) = +56,300,
-- so the clearing account carries a −56,300 (credit) balance that ties to −sum(open).
INSERT INTO gl_account (id, code, name, grp, bank, mask, source_account, tolerance, assigned_to, recon_type)
VALUES ('2055', '2055', 'GR/IR clearing — received vs invoiced', 'Accounts payable',
        'Procurement subledger', 'clearing', NULL, 0, 'Dana P.', 'clearing');

INSERT INTO reconciliation (gl_account_id, period_end, gl_balance, statement_balance, variance, status, work_status)
VALUES ('2055', '2026-05-31', -56300, NULL, NULL, 'unreconciled', 'assigned');

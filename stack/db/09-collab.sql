-- Multi-team collaboration: teams (a grouping orthogonal to the org-role SoD hierarchy) +
-- a conversation thread on each reconciliation (comments, attachments, and cross-team requests).
-- Runs after 06-audit-auth.sql, so app_user + pgcrypto already exist.

-- ─────────────────────────── teams (the "who you collaborate as" layer) ───────────────────────────
-- Distinct from org_role: org_role (junior→director) gates access + segregation of duties; a team is
-- the function a person speaks for in a thread. A user can sit on more than one team.
CREATE TABLE team (
  id    text PRIMARY KEY,                 -- accounting | treasury | audit | operations
  name  text NOT NULL,
  descr text
);
INSERT INTO team (id, name, descr) VALUES
 ('accounting','Accounting','Owns the reconciliations — prepares, reviews, and approves the close'),
 ('treasury','Treasury','Bank relationships, statements, wires & balance confirmations'),
 ('audit','Audit & Controls','Internal audit / SOX — reviews evidence and attests to controls'),
 ('operations','Operations','Project & business-unit owners — explain variances, supply WO/PO/invoices');

CREATE TABLE user_team (
  user_id text NOT NULL REFERENCES app_user(id),
  team_id text NOT NULL REFERENCES team(id),
  is_lead boolean NOT NULL DEFAULT false,
  PRIMARY KEY (user_id, team_id)
);

-- The existing accountants are Accounting.
INSERT INTO user_team (user_id, team_id, is_lead) VALUES
 ('u-sam','accounting',false),('u-priya','accounting',false),('u-joe','accounting',false),
 ('u-dana','accounting',false),('u-maria','accounting',true),('u-rob','accounting',true);

-- Cross-functional counterparts, so the thread is genuinely multi-team (share the demo password).
INSERT INTO app_user (id, name, email, org_role, password_hash, mfa_enabled) VALUES
 ('u-tara','Tara V.','tara.v@acme.com','senior',    crypt('openrecon-demo', gen_salt('bf')), true),
 ('u-nina','Nina O.','nina.o@acme.com','principal', crypt('openrecon-demo', gen_salt('bf')), true),
 ('u-glen','Glen M.','glen.m@acme.com','senior',    crypt('openrecon-demo', gen_salt('bf')), true);
INSERT INTO user_team (user_id, team_id, is_lead) VALUES
 ('u-tara','treasury',true),
 ('u-nina','audit',true),
 ('u-glen','operations',true),
 ('u-rob','audit',false);   -- the director also sits on Audit

-- ─────────────────────────── conversation thread (one stream per reconciliation) ───────────────────────────
-- Keyed by (entity_type, entity_id) so the SAME thread works on an account reconciliation
-- (entity_type='reconciliation', entity_id=gl_account.id) and a project reconciliation
-- (entity_type='project', entity_id=project_reconciliation.id).
CREATE TABLE recon_comment (
  id              bigserial PRIMARY KEY,
  entity_type     text NOT NULL,                       -- reconciliation | project
  entity_id       text NOT NULL,
  period_end      date,
  author          text NOT NULL,                       -- resolved real identity
  author_role     text,                                -- org_role at time of posting
  author_team     text REFERENCES team(id),            -- the team they posted as
  kind            text NOT NULL DEFAULT 'comment',     -- comment | request | response
  to_team         text REFERENCES team(id),            -- a request addressed to this team (kind='request')
  resolves_id     bigint REFERENCES recon_comment(id), -- a response that closes a specific request
  body            text NOT NULL,
  attachment_name text,                                -- optional attachment (the file lives in the DMS)
  attachment_ref  text,                                -- dms doc id / url
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX recon_comment_entity_idx ON recon_comment (entity_type, entity_id, created_at);
CREATE INDEX recon_comment_toteam_idx ON recon_comment (to_team) WHERE kind='request';

-- A reconciliation is "awaiting <team>" while a request to that team has no resolving response.
CREATE VIEW recon_open_request AS
  SELECT r.entity_type, r.entity_id, r.period_end, r.to_team,
         r.id AS request_id, r.author AS requested_by, r.body AS ask, r.created_at AS requested_at
  FROM recon_comment r
  WHERE r.kind = 'request'
    AND NOT EXISTS (SELECT 1 FROM recon_comment x WHERE x.resolves_id = r.id);

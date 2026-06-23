-- SOX/ICFR foundation: an immutable audit trail + real authentication & access controls.
-- Runs after 05-rbac.sql (initdb applies files alphabetically), so app_user already exists.

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- digest() for the hash chain, crypt()/gen_salt() for passwords

-- ─────────────────────────── immutable audit trail ───────────────────────────
-- Append-only, tamper-evident: every row is hash-chained to the previous one, server-stamped,
-- and UPDATE/DELETE are blocked at the database. This is the keystone SOX 404 evidence object.
CREATE TABLE audit_event (
  id          bigserial PRIMARY KEY,
  event_ts    timestamptz NOT NULL,                 -- set server-side by the trigger (not the client)
  actor       text        NOT NULL,                 -- who (resolved real identity from the session)
  actor_role  text,
  action      text        NOT NULL,                 -- e.g. account.approve | account.send_back | period.lock | auth.login | import.commit
  entity_type text,                                 -- reconciliation | project | period | user | config | import
  entity_id   text,
  period_end  date,
  before      jsonb,                                -- prior state (for changes)
  after       jsonb,                                -- new state
  detail      jsonb,                                -- free-form context (reason, assertion text, counts, …)
  source_ip   text,
  prev_hash   text        NOT NULL,                 -- chain link to the previous row
  row_hash    text        NOT NULL                  -- sha256(prev_hash | canonical(this row))
);
CREATE INDEX audit_event_entity_idx ON audit_event (entity_type, entity_id);
CREATE INDEX audit_event_actor_idx  ON audit_event (actor);
CREATE INDEX audit_event_ts_idx     ON audit_event (event_ts);

-- Compute the chain on insert. An advisory lock serializes concurrent inserts so the chain is linear.
CREATE OR REPLACE FUNCTION audit_chain() RETURNS trigger AS $$
DECLARE prev text;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtext('openrecon.audit_event'));
  NEW.event_ts := now();                            -- server-authoritative timestamp
  SELECT row_hash INTO prev FROM audit_event ORDER BY id DESC LIMIT 1;
  NEW.prev_hash := COALESCE(prev, 'GENESIS');
  NEW.row_hash  := encode(digest(
       NEW.prev_hash || '|' || NEW.event_ts::text || '|' || NEW.actor || '|' || NEW.action || '|' ||
       COALESCE(NEW.entity_type,'') || '|' || COALESCE(NEW.entity_id,'') || '|' ||
       COALESCE(NEW.period_end::text,'') || '|' || COALESCE(NEW.before::text,'') || '|' ||
       COALESCE(NEW.after::text,'') || '|' || COALESCE(NEW.detail::text,''), 'sha256'), 'hex');
  RETURN NEW;
END$$ LANGUAGE plpgsql;
CREATE TRIGGER audit_chain_ins BEFORE INSERT ON audit_event FOR EACH ROW EXECUTE FUNCTION audit_chain();

-- Block mutation of the trail entirely (append-only at the DB, regardless of app role).
CREATE OR REPLACE FUNCTION audit_immutable() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'audit_event is append-only — % is not permitted', TG_OP; END$$ LANGUAGE plpgsql;
CREATE TRIGGER audit_no_modify BEFORE UPDATE OR DELETE ON audit_event
  FOR EACH ROW EXECUTE FUNCTION audit_immutable();

-- ─────────────────────────── authentication & access ───────────────────────────
-- Bind every audited action to a real, authenticated identity. Local password auth (bcrypt via
-- pgcrypto) is the default; auth_source switches a user to an external IdP (OIDC/SAML) where the
-- session is minted from the IdP subject instead of a local password.
ALTER TABLE app_user
  ADD COLUMN password_hash    text,
  ADD COLUMN auth_source      text NOT NULL DEFAULT 'local',   -- local | oidc | saml
  ADD COLUMN external_subject text,                            -- IdP subject (sub) when federated
  ADD COLUMN mfa_enabled      boolean NOT NULL DEFAULT false,
  ADD COLUMN status           text NOT NULL DEFAULT 'active',  -- active | disabled
  ADD COLUMN last_login_at    timestamptz,
  ADD COLUMN created_at       timestamptz NOT NULL DEFAULT now();

-- Demo local credentials (showcase only). All demo users share the password 'openrecon-demo'.
-- A real deployment provisions these from SSO/HRIS and never ships seeded passwords.
UPDATE app_user SET password_hash = crypt('openrecon-demo', gen_salt('bf')), mfa_enabled = true;

CREATE TABLE auth_session (
  token       text        PRIMARY KEY,              -- opaque bearer token (server-generated)
  user_id     text        NOT NULL REFERENCES app_user(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  expires_at  timestamptz NOT NULL,
  source_ip   text,
  revoked_at  timestamptz
);
CREATE INDEX auth_session_user_idx ON auth_session (user_id);

-- Periodic access recertification (a SOX access control): a manager attests each user's access.
CREATE TABLE access_review (
  id          bigserial   PRIMARY KEY,
  campaign    text        NOT NULL,                 -- e.g. '2026-Q2 access recertification'
  user_id     text        NOT NULL REFERENCES app_user(id),
  reviewer    text        NOT NULL,
  decision    text        NOT NULL DEFAULT 'pending',  -- recertified | revoked | pending
  reviewed_at timestamptz,
  note        text
);
CREATE INDEX access_review_user_idx ON access_review (user_id);

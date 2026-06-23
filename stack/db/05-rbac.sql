-- RBAC: org-role hierarchy (access) + workflow-role capabilities (assignment + segregation of duties).

CREATE TABLE app_user (
  id       text PRIMARY KEY,
  name     text NOT NULL,
  email    text,
  org_role text NOT NULL,          -- junior | senior | principal | director  (ascending access)
  active   boolean NOT NULL DEFAULT true
);

CREATE TABLE role_capability (
  org_role   text NOT NULL,        -- which org role may hold a workflow role
  capability text NOT NULL,        -- prepare | approve | review
  PRIMARY KEY (org_role, capability)
);

INSERT INTO app_user (id, name, email, org_role) VALUES
 ('u-sam','Sam R.','sam.r@acme.com','junior'),
 ('u-priya','Priya N.','priya.n@acme.com','junior'),
 ('u-joe','Joe B.','joe.b@acme.com','senior'),
 ('u-dana','Dana P.','dana.p@acme.com','senior'),
 ('u-maria','Maria L.','maria.l@acme.com','principal'),
 ('u-rob','Robert K.','robert.k@acme.com','director');

-- the org's policy: anyone prepares; seniors+ approve OTHERS' work; only principals/directors review.
INSERT INTO role_capability (org_role, capability) VALUES
 ('junior','prepare'),
 ('senior','prepare'),('senior','approve'),
 ('principal','prepare'),('principal','approve'),('principal','review'),
 ('director','prepare'),('director','approve'),('director','review');

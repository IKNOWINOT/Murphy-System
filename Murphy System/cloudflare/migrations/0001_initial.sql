-- Murphy System D1 Schema Migration
-- 0001_initial.sql

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  active_context_type TEXT NOT NULL DEFAULT 'personal' CHECK(active_context_type IN ('personal', 'organization')),
  active_org_id TEXT,
  roles_json TEXT NOT NULL DEFAULT '[]',
  stripe_account_id TEXT,
  stripe_onboarding_complete INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS organizations (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  max_concurrent_tasks INTEGER NOT NULL DEFAULT 10,
  budget_limit REAL,
  compliance_frameworks TEXT,
  settings TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS memberships (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  org_id TEXT NOT NULL REFERENCES organizations(id),
  position_title TEXT,
  hierarchy_level INTEGER NOT NULL DEFAULT 0,
  reports_to_membership_id TEXT REFERENCES memberships(id),
  employment_contract_ref TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'suspended', 'detached')),
  attached_at TEXT NOT NULL DEFAULT (datetime('now')),
  detached_at TEXT,
  UNIQUE(user_id, org_id)
);

CREATE TABLE IF NOT EXISTS shadow_agents (
  id TEXT PRIMARY KEY,
  owner_user_id TEXT NOT NULL REFERENCES users(id),
  primary_role_id TEXT,
  department TEXT,
  position_context TEXT,
  training_infra_fingerprint TEXT,
  model_artifact_r2_key TEXT,
  is_marketplace_listed INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'idle' CHECK(status IN ('active', 'suspended', 'revoked', 'idle', 'licensed')),
  governance_boundary TEXT,
  permissions TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_org_assignments (
  id TEXT PRIMARY KEY,
  shadow_agent_id TEXT NOT NULL REFERENCES shadow_agents(id),
  membership_id TEXT NOT NULL REFERENCES memberships(id),
  target_role_id TEXT,
  scope TEXT,
  decision_scope TEXT,
  requires_human_approval INTEGER NOT NULL DEFAULT 1,
  active INTEGER NOT NULL DEFAULT 1,
  assigned_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_llm_keys (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  provider TEXT NOT NULL,
  encrypted_key TEXT NOT NULL,
  display_label TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(user_id, provider)
);

CREATE TABLE IF NOT EXISTS negotiations (
  id TEXT PRIMARY KEY,
  initiator_org_id TEXT NOT NULL REFERENCES organizations(id),
  responder_org_id TEXT NOT NULL REFERENCES organizations(id),
  subject TEXT,
  durable_object_id TEXT,
  status TEXT NOT NULL DEFAULT 'proposed' CHECK(status IN ('proposed', 'active', 'accepted', 'rejected', 'expired')),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at TEXT
);

CREATE TABLE IF NOT EXISTS marketplace_listings (
  id TEXT PRIMARY KEY,
  shadow_agent_id TEXT NOT NULL REFERENCES shadow_agents(id),
  listed_by_user_id TEXT NOT NULL REFERENCES users(id),
  title TEXT NOT NULL,
  description TEXT,
  infra_requirements TEXT,
  license_terms TEXT,
  human_in_loop_required INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS marketplace_licenses (
  id TEXT PRIMARY KEY,
  listing_id TEXT NOT NULL REFERENCES marketplace_listings(id),
  licensee_org_id TEXT NOT NULL REFERENCES organizations(id),
  license_terms_snapshot TEXT,
  infra_compatibility_score REAL,
  stripe_payment_intent_id TEXT,
  status TEXT NOT NULL DEFAULT 'pending_owner_approval' CHECK(status IN ('pending_owner_approval', 'pending_licensee_approval', 'pending_payment', 'awaiting_payment', 'active', 'expired', 'revoked', 'payment_failed')),
  licensed_at TEXT,
  expires_at TEXT
);

CREATE TABLE IF NOT EXISTS pending_decisions (
  id TEXT PRIMARY KEY,
  agent_assignment_id TEXT NOT NULL REFERENCES agent_org_assignments(id),
  decision_type TEXT NOT NULL,
  description TEXT,
  priority INTEGER NOT NULL DEFAULT 0,
  context TEXT,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected', 'expired')),
  decided_by TEXT REFERENCES users(id),
  decided_at TEXT,
  notes TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
  id TEXT PRIMARY KEY,
  event TEXT NOT NULL,
  user_id TEXT REFERENCES users(id),
  details TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS provider_acknowledgements (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  provider TEXT NOT NULL,
  terms_url TEXT NOT NULL,
  acknowledged_at TEXT NOT NULL DEFAULT (datetime('now')),
  ip_address TEXT,
  UNIQUE(user_id, provider)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_memberships_user_status ON memberships(user_id, status);
CREATE INDEX IF NOT EXISTS idx_memberships_org_status ON memberships(org_id, status);
CREATE INDEX IF NOT EXISTS idx_shadow_agents_owner ON shadow_agents(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_agent_org_assignments_agent_active ON agent_org_assignments(shadow_agent_id, active);
CREATE INDEX IF NOT EXISTS idx_marketplace_listings_status ON marketplace_listings(status);
CREATE INDEX IF NOT EXISTS idx_pending_decisions_status_priority ON pending_decisions(status, priority);
CREATE INDEX IF NOT EXISTS idx_audit_log_event_created ON audit_log(event, created_at);
CREATE INDEX IF NOT EXISTS idx_user_llm_keys_user_provider ON user_llm_keys(user_id, provider);
CREATE INDEX IF NOT EXISTS idx_provider_ack_user_provider ON provider_acknowledgements(user_id, provider);

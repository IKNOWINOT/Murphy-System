-- Add encryption columns to client_integrations
ALTER TABLE client_integrations 
ADD COLUMN IF NOT EXISTS encrypted_credentials bytea,
ADD COLUMN IF NOT EXISTS encryption_key_id integer,
ADD COLUMN IF NOT EXISTS is_encrypted boolean DEFAULT false;

-- Create encryption keys table
CREATE TABLE IF NOT EXISTS encryption_keys (
    key_id SERIAL PRIMARY KEY,
    key_name VARCHAR(100) NOT NULL UNIQUE,
    encrypted_key bytea NOT NULL,
    key_hash VARCHAR(255) NOT NULL,
    algorithm VARCHAR(50) DEFAULT 'aes256',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    active BOOLEAN DEFAULT true,
    created_by VARCHAR(100)
);

-- Create roles table
CREATE TABLE IF NOT EXISTS roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE,
    role_code VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    permissions jsonb DEFAULT '{}',
    is_system_role BOOLEAN DEFAULT false,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create user_roles table
CREATE TABLE IF NOT EXISTS user_roles (
    user_role_id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    role_id INTEGER NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
    client_id INTEGER REFERENCES clients(client_id) ON DELETE CASCADE,
    assigned_at TIMESTAMP NOT NULL DEFAULT NOW(),
    assigned_by VARCHAR(100),
    expires_at TIMESTAMP,
    UNIQUE(user_id, role_id, client_id)
);

-- Create security_events table
CREATE TABLE IF NOT EXISTS security_events (
    security_event_id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    event_category VARCHAR(50) NOT NULL,
    severity VARCHAR(20) DEFAULT 'info',
    user_id VARCHAR(100),
    client_id INTEGER REFERENCES clients(client_id) ON DELETE CASCADE,
    ip_address VARCHAR(45),
    user_agent TEXT,
    event_details jsonb DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'success',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create audit_logs_enhanced table
CREATE TABLE IF NOT EXISTS audit_logs_enhanced (
    audit_log_id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id INTEGER,
    action VARCHAR(50) NOT NULL,
    actor_type VARCHAR(20) NOT NULL,
    actor_id VARCHAR(100),
    client_id INTEGER REFERENCES clients(client_id) ON DELETE CASCADE,
    old_values jsonb,
    new_values jsonb,
    changes_detected jsonb,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    request_id VARCHAR(100),
    session_id VARCHAR(100)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_encryption_keys_active ON encryption_keys(active);
CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_role_id ON user_roles(role_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_client_id ON user_roles(client_id);
CREATE INDEX IF NOT EXISTS idx_security_events_type ON security_events(event_type);
CREATE INDEX IF NOT EXISTS idx_security_events_category ON security_events(event_category);
CREATE INDEX IF NOT EXISTS idx_security_events_created_at ON security_events(created_at);
CREATE INDEX IF NOT EXISTS idx_security_events_client_id ON security_events(client_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs_enhanced(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs_enhanced(actor_type, actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs_enhanced(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_logs_client_id ON audit_logs_enhanced(client_id);

-- Insert default system roles
INSERT INTO roles (role_name, role_code, description, permissions, is_system_role) VALUES
('Super Admin', 'super_admin', 'Full system access with all permissions', 
 '{"all": true, "clients": ["read", "write", "delete"], "workflows": ["read", "write", "delete", "execute"], "credentials": ["read", "write", "delete"], "users": ["read", "write", "delete"], "reports": ["read", "write", "delete"], "security": ["read", "write", "delete"]}'::jsonb,
 true),
('Admin', 'admin', 'Administrative access for client management', 
 '{"clients": ["read", "write"], "workflows": ["read", "write", "execute"], "credentials": ["read", "write"], "users": ["read", "write"], "reports": ["read", "write"]}'::jsonb,
 true),
('User', 'user', 'Standard user access', 
 '{"workflows": ["read", "execute"], "credentials": [], "reports": ["read"]}'::jsonb,
 true),
('Viewer', 'viewer', 'Read-only access', 
 '{"workflows": ["read"], "credentials": [], "reports": ["read"]}'::jsonb,
 true)
ON CONFLICT (role_code) DO NOTHING;

-- Insert default admin user for Acme Corp
INSERT INTO user_roles (user_id, role_id, client_id, assigned_by)
VALUES 
('admin@acmecorp.com', (SELECT role_id FROM roles WHERE role_code = 'admin'), 1, 'system')
ON CONFLICT (user_id, role_id, client_id) DO NOTHING;
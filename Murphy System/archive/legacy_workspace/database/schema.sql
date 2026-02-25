-- Database Schema for Client-Facing Automation System
-- Created: 2024-01-29
-- Version: 1.0.0

-- ============================================
-- CORE CONFIGURATION TABLES
-- ============================================

-- Table: clients
-- Purpose: Client master record with basic information and status
CREATE TABLE IF NOT EXISTS clients (
    client_id SERIAL PRIMARY KEY,
    client_uuid UUID NOT NULL DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'inactive')),
    billing_provider VARCHAR(20) NOT NULL CHECK (billing_provider IN ('quickbooks', 'square')),
    billing_customer_id VARCHAR(100),
    timezone VARCHAR(50) NOT NULL DEFAULT 'America/New_York',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for clients
CREATE INDEX idx_clients_status ON clients(status);
CREATE INDEX idx_clients_slug ON clients(slug);

-- ============================================
-- Table: client_packs
-- Purpose: Track which automation packs are enabled for each client
CREATE TABLE IF NOT EXISTS client_packs (
    client_pack_id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    pack_name VARCHAR(50) NOT NULL CHECK (pack_name IN ('INTAKE_v1', 'DOCS_v1', 'TASKS_v1')),
    pack_version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    enabled BOOLEAN NOT NULL DEFAULT true,
    enabled_at TIMESTAMP,
    enabled_by INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(client_id, pack_name)
);

-- Indexes for client_packs
CREATE INDEX idx_client_packs_client_id ON client_packs(client_id);
CREATE INDEX idx_client_packs_enabled ON client_packs(enabled);

-- ============================================
-- Table: client_config
-- Purpose: Key-value store for client-specific configuration
CREATE TABLE IF NOT EXISTS client_config (
    config_id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    pack_name VARCHAR(50),
    config_key VARCHAR(100) NOT NULL,
    config_value JSONB NOT NULL,
    value_type VARCHAR(20) NOT NULL DEFAULT 'string' CHECK (value_type IN ('string', 'boolean', 'number', 'json', 'array')),
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(client_id, pack_name, config_key)
);

-- Indexes for client_config
CREATE INDEX idx_client_config_client_id ON client_config(client_id);
CREATE INDEX idx_client_config_pack_name ON client_config(pack_name);
CREATE INDEX idx_client_config_key ON client_config(config_key);

-- ============================================
-- Table: client_integrations
-- Purpose: Store credentials and endpoints for external services
CREATE TABLE IF NOT EXISTS client_integrations (
    integration_id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    integration_name VARCHAR(100) NOT NULL,
    integration_type VARCHAR(50) NOT NULL,
    auth_type VARCHAR(20) NOT NULL CHECK (auth_type IN ('api_key', 'oauth', 'basic', 'custom')),
    credentials JSONB NOT NULL,
    endpoint_url TEXT,
    webhook_url TEXT,
    enabled BOOLEAN NOT NULL DEFAULT true,
    rate_limit_per_minute INTEGER,
    last_verified_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(client_id, integration_name)
);

-- Indexes for client_integrations
CREATE INDEX idx_client_integrations_client_id ON client_integrations(client_id);
CREATE INDEX idx_client_integrations_enabled ON client_integrations(enabled);

-- ============================================
-- Table: client_workflows
-- Purpose: Track workflow instances and status per client
CREATE TABLE IF NOT EXISTS client_workflows (
    workflow_id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    pack_name VARCHAR(50) NOT NULL,
    workflow_name VARCHAR(100) NOT NULL,
    workflow_uuid UUID NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,
    version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    last_execution_at TIMESTAMP,
    last_execution_status VARCHAR(20),
    total_executions BIGINT DEFAULT 0,
    success_executions BIGINT DEFAULT 0,
    failure_executions BIGINT DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(client_id, pack_name, workflow_name)
);

-- Indexes for client_workflows
CREATE INDEX idx_client_workflows_client_id ON client_workflows(client_id);
CREATE INDEX idx_client_workflows_enabled ON client_workflows(enabled);
CREATE INDEX idx_client_workflows_pack_name ON client_workflows(pack_name);

-- ============================================
-- INTAKE_v1 PACK TABLES
-- ============================================

-- Table: leads
-- Purpose: Store normalized lead records
CREATE TABLE IF NOT EXISTS leads (
    lead_id SERIAL PRIMARY KEY,
    lead_uuid UUID NOT NULL DEFAULT gen_random_uuid(),
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    full_name VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    company_name VARCHAR(255),
    job_title VARCHAR(150),
    source VARCHAR(100) NOT NULL,
    source_details JSONB,
    lead_score INTEGER DEFAULT 0 CHECK (lead_score >= 0 AND lead_score <= 100),
    status VARCHAR(50) NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'processing', 'enriched', 'routed', 'duplicate', 'error')),
    custom_fields JSONB,
    received_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(client_id, email)
);

-- Indexes for leads
CREATE INDEX idx_leads_client_id ON leads(client_id);
CREATE INDEX idx_leads_email ON leads(email);
CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_source ON leads(source);
CREATE INDEX idx_leads_created_at ON leads(created_at);
CREATE INDEX idx_leads_lead_score ON leads(lead_score);

-- ============================================
-- Table: lead_enrichment
-- Purpose: Track enrichment results and status
CREATE TABLE IF NOT EXISTS lead_enrichment (
    enrichment_id SERIAL PRIMARY KEY,
    lead_id INTEGER NOT NULL REFERENCES leads(lead_id) ON DELETE CASCADE,
    enrichment_type VARCHAR(50) NOT NULL,
    service_provider VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'skipped')),
    result JSONB,
    confidence_score DECIMAL(3,2),
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for lead_enrichment
CREATE INDEX idx_lead_enrichment_lead_id ON lead_enrichment(lead_id);
CREATE INDEX idx_lead_enrichment_status ON lead_enrichment(status);
CREATE INDEX idx_lead_enrichment_type ON lead_enrichment(enrichment_type);

-- ============================================
-- Table: lead_routing
-- Purpose: Track routing decisions and destinations
CREATE TABLE IF NOT EXISTS lead_routing (
    routing_id SERIAL PRIMARY KEY,
    lead_id INTEGER NOT NULL REFERENCES leads(lead_id) ON DELETE CASCADE,
    routing_rule_id VARCHAR(100) NOT NULL,
    destination_system VARCHAR(100) NOT NULL,
    destination_type VARCHAR(50) NOT NULL,
    destination_record_id VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')),
    payload JSONB,
    response JSONB,
    error_message TEXT,
    routed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for lead_routing
CREATE INDEX idx_lead_routing_lead_id ON lead_routing(lead_id);
CREATE INDEX idx_lead_routing_status ON lead_routing(status);
CREATE INDEX idx_lead_routing_destination ON lead_routing(destination_system);

-- ============================================
-- DOCS_v1 PACK TABLES
-- ============================================

-- Table: documents
-- Purpose: Store document metadata and processing status
CREATE TABLE IF NOT EXISTS documents (
    document_id SERIAL PRIMARY KEY,
    document_uuid UUID NOT NULL DEFAULT gen_random_uuid(),
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    original_filename VARCHAR(500) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    mime_type VARCHAR(100),
    storage_path TEXT NOT NULL,
    source VARCHAR(50) NOT NULL,
    source_metadata JSONB,
    document_type VARCHAR(50),
    confidence_score DECIMAL(3,2),
    status VARCHAR(50) NOT NULL DEFAULT 'intake' CHECK (status IN ('intake', 'classifying', 'classified', 'extracting', 'extracted', 'validating', 'validated', 'routed', 'review_required', 'completed', 'error')),
    requires_review BOOLEAN DEFAULT false,
    review_assigned_to INTEGER,
    reviewed_at TIMESTAMP,
    received_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(client_id, file_hash)
);

-- Indexes for documents
CREATE INDEX idx_documents_client_id ON documents(client_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_type ON documents(document_type);
CREATE INDEX idx_documents_created_at ON documents(created_at);
CREATE INDEX idx_documents_file_hash ON documents(file_hash);

-- ============================================
-- Table: document_extractions
-- Purpose: Store extracted data from documents
CREATE TABLE IF NOT EXISTS document_extractions (
    extraction_id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    extraction_method VARCHAR(50) NOT NULL,
    extraction_type VARCHAR(50) NOT NULL,
    extracted_data JSONB NOT NULL,
    field_confidences JSONB,
    validation_status VARCHAR(20) DEFAULT 'pending' CHECK (validation_status IN ('pending', 'valid', 'invalid', 'partial')),
    validation_errors JSONB,
    extraction_started_at TIMESTAMP,
    extraction_completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for document_extractions
CREATE INDEX idx_document_extractions_document_id ON document_extractions(document_id);
CREATE INDEX idx_document_extractions_status ON document_extractions(validation_status);

-- ============================================
-- Table: document_routing
-- Purpose: Track document destination routing
CREATE TABLE IF NOT EXISTS document_routing (
    routing_id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    destination_system VARCHAR(100) NOT NULL,
    destination_type VARCHAR(50) NOT NULL,
    destination_record_id VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')),
    payload JSONB,
    response JSONB,
    error_message TEXT,
    routed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for document_routing
CREATE INDEX idx_document_routing_document_id ON document_routing(document_id);
CREATE INDEX idx_document_routing_status ON document_routing(status);

-- ============================================
-- TASKS_v1 PACK TABLES
-- ============================================

-- Table: tasks
-- Purpose: Main task records across all sources
CREATE TABLE IF NOT EXISTS tasks (
    task_id SERIAL PRIMARY KEY,
    task_uuid UUID NOT NULL DEFAULT gen_random_uuid(),
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL,
    source_id INTEGER,
    source_reference_id VARCHAR(255),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    priority VARCHAR(20) NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    status VARCHAR(50) NOT NULL DEFAULT 'created' CHECK (status IN ('created', 'assigned', 'in_progress', 'completed', 'cancelled', 'expired')),
    task_type VARCHAR(100),
    due_date TIMESTAMP,
    assigned_to INTEGER,
    assigned_at TIMESTAMP,
    completed_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    custom_fields JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for tasks
CREATE INDEX idx_tasks_client_id ON tasks(client_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_assigned_to ON tasks(assigned_to);
CREATE INDEX idx_tasks_priority ON tasks(priority);
CREATE INDEX idx_tasks_due_date ON tasks(due_date);
CREATE INDEX idx_tasks_source ON tasks(source_type);

-- ============================================
-- Table: team_members
-- Purpose: Team members for task assignment
CREATE TABLE IF NOT EXISTS team_members (
    member_id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    member_uuid UUID NOT NULL DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    skills JSONB,
    working_hours JSONB,
    max_concurrent_tasks INTEGER DEFAULT 10,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(client_id, email)
);

-- Indexes for team_members
CREATE INDEX idx_team_members_client_id ON team_members(client_id);
CREATE INDEX idx_team_members_email ON team_members(email);
CREATE INDEX idx_team_members_active ON team_members(active);

-- ============================================
-- Table: task_assignments
-- Purpose: Track assignment history and workload
CREATE TABLE IF NOT EXISTS task_assignments (
    assignment_id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    member_id INTEGER NOT NULL REFERENCES team_members(member_id) ON DELETE CASCADE,
    assignment_method VARCHAR(50) NOT NULL,
    workload_at_assignment INTEGER,
    assigned_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for task_assignments
CREATE INDEX idx_task_assignments_task_id ON task_assignments(task_id);
CREATE INDEX idx_task_assignments_member_id ON task_assignments(member_id);
CREATE INDEX idx_task_assignments_assigned_at ON task_assignments(assigned_at);

-- ============================================
-- Table: sla_events
-- Purpose: Track SLA monitoring and escalation events
CREATE TABLE IF NOT EXISTS sla_events (
    sla_event_id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    sla_type VARCHAR(50) NOT NULL,
    sla_threshold_minutes INTEGER NOT NULL,
    triggered_at TIMESTAMP NOT NULL,
    escalated BOOLEAN DEFAULT false,
    escalation_level INTEGER DEFAULT 0,
    escalation_recipients JSONB,
    notification_sent BOOLEAN DEFAULT false,
    notification_method VARCHAR(50),
    resolved_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for sla_events
CREATE INDEX idx_sla_events_task_id ON sla_events(task_id);
CREATE INDEX idx_sla_events_client_id ON sla_events(client_id);
CREATE INDEX idx_sla_events_triggered_at ON sla_events(triggered_at);

-- ============================================
-- Table: reports
-- Purpose: Store generated report metadata
CREATE TABLE IF NOT EXISTS reports (
    report_id SERIAL PRIMARY KEY,
    report_uuid UUID NOT NULL DEFAULT gen_random_uuid(),
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    report_type VARCHAR(50) NOT NULL,
    report_format VARCHAR(20) NOT NULL CHECK (report_format IN ('html', 'pdf', 'csv')),
    report_period_start TIMESTAMP NOT NULL,
    report_period_end TIMESTAMP NOT NULL,
    file_path TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'generating' CHECK (status IN ('generating', 'completed', 'failed')),
    generated_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for reports
CREATE INDEX idx_reports_client_id ON reports(client_id);
CREATE INDEX idx_reports_type ON reports(report_type);
CREATE INDEX idx_reports_created_at ON reports(created_at);

-- ============================================
-- AUDIT & MONITORING TABLES
-- ============================================

-- Table: workflow_executions
-- Purpose: Log all workflow executions for observability
CREATE TABLE IF NOT EXISTS workflow_executions (
    execution_id SERIAL PRIMARY KEY,
    execution_uuid UUID NOT NULL DEFAULT gen_random_uuid(),
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    pack_name VARCHAR(50) NOT NULL,
    workflow_name VARCHAR(100) NOT NULL,
    workflow_uuid UUID NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('started', 'running', 'completed', 'failed', 'cancelled')),
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    retry_count INTEGER DEFAULT 0,
    idempotency_key VARCHAR(255)
);

-- Indexes for workflow_executions
CREATE INDEX idx_workflow_executions_client_id ON workflow_executions(client_id);
CREATE INDEX idx_workflow_executions_status ON workflow_executions(status);
CREATE INDEX idx_workflow_executions_started_at ON workflow_executions(started_at);
CREATE INDEX idx_workflow_executions_workflow ON workflow_executions(pack_name, workflow_name);
CREATE INDEX idx_workflow_executions_idempotency ON workflow_executions(idempotency_key);

-- ============================================
-- Table: config_audit_log
-- Purpose: Track all configuration changes
CREATE TABLE IF NOT EXISTS config_audit_log (
    audit_id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(client_id) ON DELETE SET NULL,
    table_name VARCHAR(50) NOT NULL,
    record_id INTEGER,
    action VARCHAR(20) NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    old_values JSONB,
    new_values JSONB,
    changed_by VARCHAR(100),
    changed_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for config_audit_log
CREATE INDEX idx_config_audit_log_client_id ON config_audit_log(client_id);
CREATE INDEX idx_config_audit_log_table ON config_audit_log(table_name);
CREATE INDEX idx_config_audit_log_changed_at ON config_audit_log(changed_at);

-- ============================================
-- Table: dead_letter_queue
-- Purpose: Store failed operations for retry and analysis
CREATE TABLE IF NOT EXISTS dead_letter_queue (
    dlq_id SERIAL PRIMARY KEY,
    dlq_uuid UUID NOT NULL DEFAULT gen_random_uuid(),
    client_id INTEGER REFERENCES clients(client_id) ON DELETE SET NULL,
    pack_name VARCHAR(50),
    workflow_name VARCHAR(100),
    operation_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    error_message TEXT,
    error_code VARCHAR(50),
    stack_trace TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_retry_at TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'retrying', 'failed', 'resolved')),
    resolved_by VARCHAR(100),
    resolved_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for dead_letter_queue
CREATE INDEX idx_dlq_client_id ON dead_letter_queue(client_id);
CREATE INDEX idx_dlq_status ON dead_letter_queue(status);
CREATE INDEX idx_dlq_next_retry ON dead_letter_queue(next_retry_at);
CREATE INDEX idx_dlq_created_at ON dead_letter_queue(created_at);

-- ============================================
-- Table: notifications
-- Purpose: Track sent notifications
CREATE TABLE IF NOT EXISTS notifications (
    notification_id SERIAL PRIMARY KEY,
    notification_uuid UUID NOT NULL DEFAULT gen_random_uuid(),
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    recipient VARCHAR(255) NOT NULL,
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('email', 'slack', 'sms', 'webhook')),
    notification_type VARCHAR(50) NOT NULL,
    subject VARCHAR(500),
    body TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
    error_message TEXT,
    sent_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for notifications
CREATE INDEX idx_notifications_client_id ON notifications(client_id);
CREATE INDEX idx_notifications_status ON notifications(status);
CREATE INDEX idx_notifications_created_at ON notifications(created_at);

-- ============================================
-- SAMPLE DATA
-- ============================================

-- Insert sample clients
INSERT INTO clients (name, slug, status, billing_provider, timezone) VALUES
('Acme Corp', 'acme-corp', 'active', 'quickbooks', 'America/New_York'),
('TechStart Inc', 'techstart-inc', 'active', 'square', 'America/Los_Angeles');

-- Insert sample client packs
INSERT INTO client_packs (client_id, pack_name, enabled, enabled_at) VALUES
(1, 'INTAKE_v1', true, NOW()),
(1, 'DOCS_v1', true, NOW()),
(1, 'TASKS_v1', true, NOW()),
(2, 'INTAKE_v1', true, NOW()),
(2, 'DOCS_v1', true, NOW()),
(2, 'TASKS_v1', false, NOW());

-- Insert sample configuration
INSERT INTO client_config (client_id, pack_name, config_key, config_value, value_type, description) VALUES
(1, 'INTAKE_v1', 'enabled_input_channels', '["web_form", "email", "api"]', 'array', 'Active lead input channels'),
(1, 'INTAKE_v1', 'min_lead_score_threshold', '50', 'number', 'Minimum lead score for routing'),
(1, 'DOCS_v1', 'confidence_threshold', '0.8', 'number', 'Minimum confidence for auto-processing'),
(1, 'TASKS_v1', 'sla_assignment_minutes', '120', 'number', 'SLA for task assignment in minutes');

-- Insert sample team member
INSERT INTO team_members (client_id, name, email, skills, working_hours, max_concurrent_tasks) VALUES
(1, 'John Smith', 'john@acme.com', '["sales", "support"]', '{"timezone": "America/New_York", "start": "09:00", "end": "17:00", "days": [1,2,3,4,5]}', 15);

-- Insert sample lead
INSERT INTO leads (client_id, email, full_name, company_name, source, lead_score, status) VALUES
(1, 'jane@example.com', 'Jane Doe', 'Example Corp', 'web_form', 75, 'new');

-- ============================================
-- END OF SCHEMA
-- ============================================
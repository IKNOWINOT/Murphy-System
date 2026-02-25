
-- Murphy System Unified Schema
-- Combines all schemas from uploaded files and current system

-- ============================================
-- CORE TABLES (from uploaded schema)
-- ============================================
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

-- ============================================
-- MONITORING TABLES
-- ============================================
-- Monitoring, Error Handling & DLQ Enhancement Tables
-- Day 7 Implementation

-- 1. Metrics Collection Table
CREATE TABLE IF NOT EXISTS metrics (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id),
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(20,4) NOT NULL,
    metric_unit VARCHAR(50),
    tags JSONB,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for metrics
CREATE INDEX IF NOT EXISTS idx_metrics_client ON metrics(client_id);
CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_metrics_recorded ON metrics(recorded_at);

-- 2. Error Tracking Table
CREATE TABLE IF NOT EXISTS errors (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id),
    workflow_id VARCHAR(255),
    execution_id VARCHAR(255),
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    error_stack TEXT,
    error_severity VARCHAR(20) NOT NULL CHECK (error_severity IN ('critical', 'high', 'medium', 'low')),
    error_category VARCHAR(50) NOT NULL CHECK (error_category IN ('validation', 'network', 'api', 'database', 'system', 'business', 'other')),
    context JSONB,
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT
);

-- Create indexes for errors
CREATE INDEX IF NOT EXISTS idx_errors_client ON errors(client_id);
CREATE INDEX IF NOT EXISTS idx_errors_workflow ON errors(workflow_id);
CREATE INDEX IF NOT EXISTS idx_errors_severity ON errors(error_severity);
CREATE INDEX IF NOT EXISTS idx_errors_category ON errors(error_category);
CREATE INDEX IF NOT EXISTS idx_errors_occurred ON errors(occurred_at);

-- 3. Alerts Table
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id),
    alert_type VARCHAR(100) NOT NULL,
    alert_severity VARCHAR(20) NOT NULL CHECK (alert_severity IN ('critical', 'high', 'medium', 'low')),
    alert_title VARCHAR(255) NOT NULL,
    alert_message TEXT NOT NULL,
    source_workflow VARCHAR(255),
    source_entity_type VARCHAR(100),
    source_entity_id INTEGER,
    metadata JSONB,
    triggered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(255),
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    notification_channels JSONB DEFAULT '[]'::JSONB
);

-- Create indexes for alerts
CREATE INDEX IF NOT EXISTS idx_alerts_client ON alerts(client_id);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(alert_severity);
CREATE INDEX IF NOT EXISTS idx_alerts_triggered ON alerts(triggered_at);
CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged ON alerts(acknowledged);

-- 4. Performance Metrics Table
CREATE TABLE IF NOT EXISTS performance_aggregates (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id),
    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    workflow_name VARCHAR(255),
    total_executions INTEGER DEFAULT 0,
    successful_executions INTEGER DEFAULT 0,
    failed_executions INTEGER DEFAULT 0,
    avg_execution_time DECIMAL(10,2),
    max_execution_time DECIMAL(10,2),
    min_execution_time DECIMAL(10,2),
    error_rate DECIMAL(5,2)
);

-- Create indexes for performance aggregates
CREATE INDEX IF NOT EXISTS idx_perf_client ON performance_aggregates(client_id);
CREATE INDEX IF NOT EXISTS idx_perf_workflow ON performance_aggregates(workflow_name);
CREATE INDEX IF NOT EXISTS idx_perf_period ON performance_aggregates(period_start, period_end);

-- Create unique constraint for performance aggregates
ALTER TABLE performance_aggregates DROP CONSTRAINT IF EXISTS perf_aggregates_unique;
ALTER TABLE performance_aggregates ADD CONSTRAINT perf_aggregates_unique UNIQUE (client_id, workflow_name, period_start, period_end);

-- 5. Dependency Health Table
CREATE TABLE IF NOT EXISTS dependency_health (
    id SERIAL PRIMARY KEY,
    dependency_name VARCHAR(100) NOT NULL UNIQUE,
    dependency_type VARCHAR(50) NOT NULL CHECK (dependency_type IN ('database', 'api', 'service', 'storage', 'queue')),
    health_status VARCHAR(20) NOT NULL CHECK (health_status IN ('healthy', 'degraded', 'unhealthy', 'unknown')),
    last_check TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_success TIMESTAMP WITH TIME ZONE,
    last_failure TIMESTAMP WITH TIME ZONE,
    response_time_ms DECIMAL(10,2),
    error_message TEXT,
    uptime_percentage DECIMAL(5,2),
    total_checks INTEGER DEFAULT 0,
    successful_checks INTEGER DEFAULT 0,
    failed_checks INTEGER DEFAULT 0,
    metadata JSONB
);

-- Create indexes for dependency health
CREATE INDEX IF NOT EXISTS idx_dep_name ON dependency_health(dependency_name);
CREATE INDEX IF NOT EXISTS idx_dep_status ON dependency_health(health_status);

-- Insert initial dependency records
INSERT INTO dependency_health (dependency_name, dependency_type, health_status, last_check, response_time_ms, total_checks, successful_checks, failed_checks, uptime_percentage)
VALUES 
    ('postgresql', 'database', 'healthy', CURRENT_TIMESTAMP, 7.5, 1, 1, 0, 100.00),
    ('n8n', 'service', 'healthy', CURRENT_TIMESTAMP, 15.2, 1, 1, 0, 100.00),
    ('storage', 'storage', 'healthy', CURRENT_TIMESTAMP, 2.1, 1, 1, 0, 100.00)
ON CONFLICT (dependency_name) DO NOTHING;

-- Sample metrics for testing
INSERT INTO metrics (metric_name, metric_value, metric_unit, tags)
VALUES 
    ('workflow_executions_total', 150, 'count', '{"workflow_pack": "INTAKE_v1"}'::JSONB),
    ('workflow_executions_success', 142, 'count', '{"workflow_pack": "INTAKE_v1"}'::JSONB),
    ('workflow_executions_failed', 8, 'count', '{"workflow_pack": "INTAKE_v1"}'::JSONB),
    ('avg_execution_time_ms', 1250.5, 'ms', '{"workflow_pack": "INTAKE_v1"}'::JSONB),
    ('active_leads', 45, 'count', '{"metric_type": "business"}'::JSONB),
    ('documents_processed', 234, 'count', '{"metric_type": "business"}'::JSONB),
    ('tasks_created', 89, 'count', '{"metric_type": "business"}'::JSONB),
    ('system_cpu_percent', 45.2, 'percent', '{"resource": "cpu"}'::JSONB),
    ('system_memory_percent', 62.8, 'percent', '{"resource": "memory"}'::JSONB),
    ('disk_usage_percent', 77.7, 'percent', '{"resource": "disk"}'::JSONB);

-- Sample alerts for testing
INSERT INTO alerts (client_id, alert_type, alert_severity, alert_title, alert_message, source_workflow, metadata, notification_channels)
VALUES 
    (1, 'high_error_rate', 'high', 'High Error Rate Detected', 'INTAKE_v1_Capture_Leads workflow has 10% error rate in last hour', 'INTAKE_v1_Capture_Leads', '{"error_count": 5, "total_executions": 50, "error_rate": 0.10}'::JSONB, '["email", "slack"]'::JSONB),
    (1, 'sla_warning', 'medium', 'SLA Warning', '3 tasks are approaching SLA deadline', 'TASKS_v1_Monitor_SLA', '{"task_count": 3, "sla_type": "warning"}'::JSONB, '["email"]'::JSONB);

-- Sample errors for testing
INSERT INTO errors (client_id, workflow_id, error_type, error_message, error_severity, error_category, context)
VALUES 
    (1, 'INTAKE_v1_Capture_Leads', 'ValidationError', 'Missing required field: email', 'medium', 'validation', '{"lead_data": "{&quot;name&quot;: &quot;John&quot;}", "missing_fields": ["email"]}'::JSONB),
    (1, 'DOCS_v1_Extract_Data', 'NetworkError', 'Failed to connect to OCR service', 'high', 'network', '{"document_id": 123, "retry_count": 3}'::JSONB),
    (1, 'TASKS_v1_Assign_Tasks', 'AssignmentError', 'No available team members with required skills', 'medium', 'business', '{"task_id": 456, "required_skills": ["python", "data_analysis"]}'::JSONB);

-- ============================================
-- SECURITY TABLES
-- ============================================
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


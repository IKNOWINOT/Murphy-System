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
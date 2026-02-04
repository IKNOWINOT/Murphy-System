# Client-Facing Automation Product Templates - Complete System Design

## 1. EXECUTIVE SUMMARY

**What We're Building in v1**

This system delivers three production-ready, versioned automation packs that can be deployed to B2B clients through configuration only—no custom code per client. The foundation is a PostgreSQL-based configuration engine that manages client settings, enabled packs, workflow parameters, and integration credentials. Three n8n workflow collections (INTAKE_v1, DOCS_v1, TASKS_v1) provide end-to-end automation for lead processing, document handling, and task management. Each pack is idempotent, observable, and secure by design, with configurable routing rules, validation logic, and notification preferences stored in the database.

The architecture prioritizes simplicity and reliability: n8n orchestrates all workflows, PostgreSQL serves as the single source of truth for configuration and state, and external integrations (email validation, OCR, LLMs, billing systems) are accessed through standardized credential management. We avoid Stripe entirely, using QuickBooks or Square for billing. The system supports self-hosted or VPS deployment, minimizing dependencies and operational complexity. All workflows include comprehensive logging, retry logic with exponential backoff, dead-letter queues for failures, and configurable alerting thresholds.

**Key Design Decisions**

**PostgreSQL as Configuration Engine**: Rather than hard-coding client-specific logic into n8n workflows, we store all client configuration in relational tables. This enables rapid onboarding (add client row, enable packs, configure parameters), version control of settings through audit tables, and easy bulk updates across clients. The configuration is read by n8n workflows at execution time, eliminating the need for workflow redeployment when client settings change.

**Pack-Based Architecture**: Each automation pack (INTAKE, DOCS, TASKS) is a self-contained collection of n8n workflows that can be independently enabled/disabled per client. This modular approach allows clients to adopt capabilities incrementally, simplifies testing and debugging, and provides clear upgrade paths. Packs are versioned (INTAKE_v1) to support backward compatibility during updates.

**Idempotency by Default**: All workflows are designed to be safely retryable. We use database constraints (unique constraints on lead emails, document hashes, task IDs), idempotency keys in workflow execution, and state validation before external API calls. Failed operations are logged with detailed context and can be retried manually or automatically.

**Configuration-Only Deployment**: The system deliberately avoids per-client code changes. All business logic variations—field mappings, routing rules, validation checklists, SLA thresholds—are stored as configuration data. This ensures rapid scalability and prevents configuration drift, as all changes are tracked in the database with timestamps and audit trails.

**Success Criteria for v1**

The v1 system will be considered successful when: (1) A new client can be fully onboarded in under 60 minutes through database configuration only; (2) All three automation packs process at least 1,000 records per day with 99.9% success rate; (3) Failed operations are automatically retried 3 times with exponential backoff before escalating to dead-letter queues; (4) All configuration changes are auditable with rollback capability; (5) The system supports at least 50 concurrent clients on a single VPS instance; (6) SLA breaches generate automated notifications within 5 minutes; (7) Document classification achieves >90% accuracy at >80% confidence threshold; (8) Lead enrichment completes within 10 seconds with <1% failure rate.

---

## 2. ARCHITECTURE DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL DATA SOURCES                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │ Web Forms   │  │ Email       │  │ API Webhooks│  │ Cloud Storage│      │
│  │ (HTTP POST) │  │ (IMAP/POP3) │  │ (REST)      │  │ (Drive/Dropbox)│     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
│         │                │                │                │               │
└─────────┼────────────────┼────────────────┼────────────────┼───────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              N8N WORKFLOW ENGINE                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    INTAKE_v1 PACK (4 Workflows)                     │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │   │
│  │  │Capture   │→ │Normalize │→ │Enrich    │→ │Route     │           │   │
│  │  │Leads     │  │Data      │  │Leads     │  │Leads     │           │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     DOCS_v1 PACK (5 Workflows)                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │   │
│  │  │Intake    │→ │Classify  │→ │Extract   │→ │Validate  │→ │Route     │   │
│  │  │Docs      │  │Docs      │  │Data      │  │Data      │  │Docs     │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │   │
│  │                           ↓                                           │   │
│  │                    ┌──────────┐                                       │   │
│  │                    │Human     │ (if confidence < 80%)                │   │
│  │                    │Review Q  │                                       │   │
│  │                    └──────────┘                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    TASKS_v1 PACK (3 Workflows)                       │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────────────────┐  │   │
│  │  │Create    │→ │Assign    │→ │Monitor SLAs & Generate Reports   │  │   │
│  │  │Tasks     │  │Tasks     │  │                                  │  │   │
│  │  └──────────┘  └──────────┘  └──────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        POSTGRESQL DATABASE (SYNC)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │                      CONFIGURATION LAYER                              │ │
│  │  clients, client_packs, client_config, client_integrations,         │ │
│  │  client_workflows                                                     │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │                         OPERATIONAL DATA                              │ │
│  │  leads, lead_enrichment, documents, document_extractions,            │ │
│  │  tasks, task_assignments, sla_events                                  │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │                      AUDIT & STATE TRACKING                          │ │
│  │  workflow_executions, config_audit_log, dead_letter_queue            │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL INTEGRATIONS                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │Email Valid. │  │Company     │  │OCR/LLM      │  │CRM/Task     │       │
│  │(NeverBounce)│  │Lookup      │  │(Tesseract/  │  │Systems      │       │
│  │             │  │(Clearbit)  │  │OpenAI)      │  │(HubSpot/    │       │
│  └─────────────┘  └─────────────┘  └─────────────┘  │Asana)       │       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┘  └─────────────┘       │
│  │QuickBooks   │  │Square       │  │Email/Slack   │  ┌─────────────┐      │
│  │Billing      │  │Billing      │  │Notifications │  │File Storage │      │
│  │             │  │             │  │              │  │(S3/MinIO)   │      │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘      │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MONITORING & LOGGING                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │Metrics      │  │Alerting    │  │Log Aggreg.  │  │Dashboard    │       │
│  │(Prometheus) │  │(PagerDuty) │  │(Loki/ELK)   │  │(Grafana)    │       │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘

LEGEND:
→ Synchronous operation (blocking)
↔ Asynchronous operation (non-blocking)
─┼─ Database transaction boundary
┌─┐ Component boundary
│  Data flow direction
```

**Key Architectural Patterns**

**Sync vs Async Operations**: Lead capture, normalization, and enrichment are synchronous (must complete before routing) to ensure data integrity. Document processing (classification, extraction) is asynchronous due to OCR/LLM processing time. SLA monitoring runs asynchronously on scheduled intervals (every 5 minutes). All database writes are synchronous within transactions to maintain consistency.

**Configuration Read Pattern**: n8n workflows read client configuration at workflow start via PostgreSQL node, cache for workflow duration, and use dynamic expressions to apply settings. This pattern minimizes database queries while ensuring configuration changes take effect on next workflow execution.

**Dead-Letter Queue Pattern**: Failed workflow executions are written to `dead_letter_queue` table with full context, error details, and retry count. A scheduled workflow monitors this queue every 10 minutes, applies retry logic (exponential backoff), and escalates to human review after 3 failed attempts.

---

## 3. DATA MODELS

### Core Configuration Tables

```sql
-- Table: clients
-- Purpose: Client master record with basic information and status
CREATE TABLE clients (
    client_id SERIAL PRIMARY KEY,
    client_uuid UUID NOT NULL DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'inactive')),
    billing_provider VARCHAR(20) NOT NULL CHECK (billing_provider IN ('quickbooks', 'square')),
    billing_customer_id VARCHAR(100),
    timezone VARCHAR(50) NOT NULL DEFAULT 'America/New_York',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_clients_status (status),
    INDEX idx_clients_slug (slug)
);

-- Table: client_packs
-- Purpose: Track which automation packs are enabled for each client
CREATE TABLE client_packs (
    client_pack_id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    pack_name VARCHAR(50) NOT NULL CHECK (pack_name IN ('INTAKE_v1', 'DOCS_v1', 'TASKS_v1')),
    pack_version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    enabled BOOLEAN NOT NULL DEFAULT true,
    enabled_at TIMESTAMP,
    enabled_by INTEGER, -- Reference to internal user/admin
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(client_id, pack_name),
    INDEX idx_client_packs_client_id (client_id),
    INDEX idx_client_packs_enabled (enabled)
);

-- Table: client_config
-- Purpose: Key-value store for client-specific configuration
CREATE TABLE client_config (
    config_id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    pack_name VARCHAR(50), -- NULL if applies to all packs
    config_key VARCHAR(100) NOT NULL,
    config_value JSONB NOT NULL,
    value_type VARCHAR(20) NOT NULL DEFAULT 'string' CHECK (value_type IN ('string', 'boolean', 'number', 'json', 'array')),
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(client_id, pack_name, config_key),
    INDEX idx_client_config_client_id (client_id),
    INDEX idx_client_config_pack_name (pack_name),
    INDEX idx_client_config_key (config_key)
);

-- Table: client_integrations
-- Purpose: Store credentials and endpoints for external services
CREATE TABLE client_integrations (
    integration_id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    integration_name VARCHAR(100) NOT NULL, -- e.g., 'hubspot', 'neverbounce', 'openai'
    integration_type VARCHAR(50) NOT NULL, -- e.g., 'crm', 'email_validation', 'llm'
    auth_type VARCHAR(20) NOT NULL CHECK (auth_type IN ('api_key', 'oauth', 'basic', 'custom')),
    credentials JSONB NOT NULL, -- Encrypted at rest
    endpoint_url TEXT,
    webhook_url TEXT,
    enabled BOOLEAN NOT NULL DEFAULT true,
    rate_limit_per_minute INTEGER,
    last_verified_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(client_id, integration_name),
    INDEX idx_client_integrations_client_id (client_id),
    INDEX idx_client_integrations_enabled (enabled)
);

-- Table: client_workflows
-- Purpose: Track workflow instances and status per client
CREATE TABLE client_workflows (
    workflow_id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    pack_name VARCHAR(50) NOT NULL,
    workflow_name VARCHAR(100) NOT NULL,
    workflow_uuid UUID NOT NULL, -- n8n workflow UUID
    enabled BOOLEAN NOT NULL DEFAULT true,
    version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    last_execution_at TIMESTAMP,
    last_execution_status VARCHAR(20),
    total_executions BIGINT DEFAULT 0,
    success_executions BIGINT DEFAULT 0,
    failure_executions BIGINT DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(client_id, pack_name, workflow_name),
    INDEX idx_client_workflows_client_id (client_id),
    INDEX idx_client_workflows_enabled (enabled),
    INDEX idx_client_workflows_pack_name (pack_name)
);
```

### INTAKE_v1 Pack Tables

```sql
-- Table: leads
-- Purpose: Store normalized lead records
CREATE TABLE leads (
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
    source VARCHAR(100) NOT NULL, -- e.g., 'web_form', 'email', 'api', 'csv_upload'
    source_details JSONB, -- Additional source-specific metadata
    lead_score INTEGER DEFAULT 0 CHECK (lead_score >= 0 AND lead_score <= 100),
    status VARCHAR(50) NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'processing', 'enriched', 'routed', 'duplicate', 'error')),
    custom_fields JSONB, -- Flexible field storage for client-specific data
    received_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(client_id, email),
    INDEX idx_leads_client_id (client_id),
    INDEX idx_leads_email (email),
    INDEX idx_leads_status (status),
    INDEX idx_leads_source (source),
    INDEX idx_leads_created_at (created_at),
    INDEX idx_leads_lead_score (lead_score)
);

-- Table: lead_enrichment
-- Purpose: Track enrichment results and status
CREATE TABLE lead_enrichment (
    enrichment_id SERIAL PRIMARY KEY,
    lead_id INTEGER NOT NULL REFERENCES leads(lead_id) ON DELETE CASCADE,
    enrichment_type VARCHAR(50) NOT NULL, -- e.g., 'email_validation', 'company_lookup', 'duplicate_check'
    service_provider VARCHAR(50), -- e.g., 'neverbounce', 'clearbit'
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'skipped')),
    result JSONB, -- Enrichment data returned by service
    confidence_score DECIMAL(3,2), -- 0.00 to 1.00
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_lead_enrichment_lead_id (lead_id),
    INDEX idx_lead_enrichment_status (status),
    INDEX idx_lead_enrichment_type (enrichment_type)
);

-- Table: lead_routing
-- Purpose: Track routing decisions and destinations
CREATE TABLE lead_routing (
    routing_id SERIAL PRIMARY KEY,
    lead_id INTEGER NOT NULL REFERENCES leads(lead_id) ON DELETE CASCADE,
    routing_rule_id VARCHAR(100) NOT NULL, -- Reference to configured rule
    destination_system VARCHAR(100) NOT NULL, -- e.g., 'hubspot', 'salesforce', 'asana'
    destination_type VARCHAR(50) NOT NULL, -- e.g., 'contact', 'task', 'pipeline'
    destination_record_id VARCHAR(255), -- External system record ID
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')),
    payload JSONB, -- Data sent to destination
    response JSONB, -- Response from destination
    error_message TEXT,
    routed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_lead_routing_lead_id (lead_id),
    INDEX idx_lead_routing_status (status),
    INDEX idx_lead_routing_destination (destination_system)
);
```

### DOCS_v1 Pack Tables

```sql
-- Table: documents
-- Purpose: Store document metadata and processing status
CREATE TABLE documents (
    document_id SERIAL PRIMARY KEY,
    document_uuid UUID NOT NULL DEFAULT gen_random_uuid(),
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    original_filename VARCHAR(500) NOT NULL,
    file_hash VARCHAR(64) NOT NULL, -- SHA-256 hash for deduplication
    file_size_bytes BIGINT NOT NULL,
    mime_type VARCHAR(100),
    storage_path TEXT NOT NULL, -- S3/MinIO object key
    source VARCHAR(50) NOT NULL, -- e.g., 'email_attachment', 'api_upload', 'drive_webhook'
    source_metadata JSONB,
    document_type VARCHAR(50), -- e.g., 'invoice', 'contract', 'id', 'receipt'
    confidence_score DECIMAL(3,2), -- 0.00 to 1.00
    status VARCHAR(50) NOT NULL DEFAULT 'intake' CHECK (status IN ('intake', 'classifying', 'classified', 'extracting', 'extracted', 'validating', 'validated', 'routed', 'review_required', 'completed', 'error')),
    requires_review BOOLEAN DEFAULT false,
    review_assigned_to INTEGER, -- Reference to team member
    reviewed_at TIMESTAMP,
    received_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(client_id, file_hash),
    INDEX idx_documents_client_id (client_id),
    INDEX idx_documents_status (status),
    INDEX idx_documents_type (document_type),
    INDEX idx_documents_created_at (created_at),
    INDEX idx_documents_file_hash (file_hash)
);

-- Table: document_extractions
-- Purpose: Store extracted data from documents
CREATE TABLE document_extractions (
    extraction_id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    extraction_method VARCHAR(50) NOT NULL, -- e.g., 'ocr_tesseract', 'llm_openai', 'llm_anthropic'
    extraction_type VARCHAR(50) NOT NULL, -- e.g., 'structured_data', 'text_content'
    extracted_data JSONB NOT NULL, -- Key-value pairs of extracted fields
    field_confidences JSONB, -- Confidence scores per field
    validation_status VARCHAR(20) DEFAULT 'pending' CHECK (validation_status IN ('pending', 'valid', 'invalid', 'partial')),
    validation_errors JSONB, -- List of validation failures
    extraction_started_at TIMESTAMP,
    extraction_completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_document_extractions_document_id (document_id),
    INDEX idx_document_extractions_status (validation_status)
);

-- Table: document_routing
-- Purpose: Track document destination routing
CREATE TABLE document_routing (
    routing_id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    destination_system VARCHAR(100) NOT NULL, -- e.g., 'quickbooks', 'hubspot', 'sharepoint'
    destination_type VARCHAR(50) NOT NULL, -- e.g., 'invoice', 'file', 'record'
    destination_record_id VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')),
    payload JSONB,
    response JSONB,
    error_message TEXT,
    routed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_document_routing_document_id (document_id),
    INDEX idx_document_routing_status (status)
);
```

### TASKS_v1 Pack Tables

```sql
-- Table: tasks
-- Purpose: Main task records across all sources
CREATE TABLE tasks (
    task_id SERIAL PRIMARY KEY,
    task_uuid UUID NOT NULL DEFAULT gen_random_uuid(),
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL, -- e.g., 'lead_followup', 'document_review', 'exception'
    source_id INTEGER, -- Reference to lead_id, document_id, etc.
    source_reference_id VARCHAR(255), -- External reference
    title VARCHAR(500) NOT NULL,
    description TEXT,
    priority VARCHAR(20) NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    status VARCHAR(50) NOT NULL DEFAULT 'created' CHECK (status IN ('created', 'assigned', 'in_progress', 'completed', 'cancelled', 'expired')),
    task_type VARCHAR(100), -- e.g., 'lead_followup', 'document_review', 'sla_breach'
    due_date TIMESTAMP,
    assigned_to INTEGER, -- Reference to team member ID
    assigned_at TIMESTAMP,
    completed_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    custom_fields JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_tasks_client_id (client_id),
    INDEX idx_tasks_status (status),
    INDEX idx_tasks_assigned_to (assigned_to),
    INDEX idx_tasks_priority (priority),
    INDEX idx_tasks_due_date (due_date),
    INDEX idx_tasks_source (source_type)
);

-- Table: team_members
-- Purpose: Team members for task assignment
CREATE TABLE team_members (
    member_id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    member_uuid UUID NOT NULL DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    skills JSONB, -- Array of skill tags
    working_hours JSONB, -- {timezone: 'America/New_York', start: '09:00', end: '17:00', days: [1,2,3,4,5]}
    max_concurrent_tasks INTEGER DEFAULT 10,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(client_id, email),
    INDEX idx_team_members_client_id (client_id),
    INDEX idx_team_members_email (email),
    INDEX idx_team_members_active (active)
);

-- Table: task_assignments
-- Purpose: Track assignment history and workload
CREATE TABLE task_assignments (
    assignment_id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    member_id INTEGER NOT NULL REFERENCES team_members(member_id) ON DELETE CASCADE,
    assignment_method VARCHAR(50) NOT NULL, -- e.g., 'round_robin', 'skill_based', 'manual'
    workload_at_assignment INTEGER, -- Number of active tasks for member at assignment time
    assigned_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_task_assignments_task_id (task_id),
    INDEX idx_task_assignments_member_id (member_id),
    INDEX idx_task_assignments_assigned_at (assigned_at)
);

-- Table: sla_events
-- Purpose: Track SLA monitoring and escalation events
CREATE TABLE sla_events (
    sla_event_id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    sla_type VARCHAR(50) NOT NULL, -- e.g., 'assignment', 'completion', 'response'
    sla_threshold_minutes INTEGER NOT NULL,
    triggered_at TIMESTAMP NOT NULL,
    escalated BOOLEAN DEFAULT false,
    escalation_level INTEGER DEFAULT 0,
    escalation_recipients JSONB, -- List of recipient emails/IDs
    notification_sent BOOLEAN DEFAULT false,
    notification_method VARCHAR(50), -- e.g., 'email', 'slack', 'sms'
    resolved_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_sla_events_task_id (task_id),
    INDEX idx_sla_events_client_id (client_id),
    INDEX idx_sla_events_triggered_at (triggered_at)
);

-- Table: reports
-- Purpose: Store generated report metadata
CREATE TABLE reports (
    report_id SERIAL PRIMARY KEY,
    report_uuid UUID NOT NULL DEFAULT gen_random_uuid(),
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    report_type VARCHAR(50) NOT NULL, -- e.g., 'daily_summary', 'weekly_rollup', 'sla_report'
    report_format VARCHAR(20) NOT NULL, -- e.g., 'html', 'pdf', 'csv'
    report_period_start TIMESTAMP NOT NULL,
    report_period_end TIMESTAMP NOT NULL,
    file_path TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'generating' CHECK (status IN ('generating', 'completed', 'failed')),
    generated_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_reports_client_id (client_id),
    INDEX idx_reports_type (report_type),
    INDEX idx_reports_created_at (created_at)
);
```

### Audit & Monitoring Tables

```sql
-- Table: workflow_executions
-- Purpose: Log all workflow executions for observability
CREATE TABLE workflow_executions (
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
    idempotency_key VARCHAR(255),
    INDEX idx_workflow_executions_client_id (client_id),
    INDEX idx_workflow_executions_status (status),
    INDEX idx_workflow_executions_started_at (started_at),
    INDEX idx_workflow_executions_workflow (pack_name, workflow_name),
    INDEX idx_workflow_executions_idempotency (idempotency_key)
);

-- Table: config_audit_log
-- Purpose: Track all configuration changes
CREATE TABLE config_audit_log (
    audit_id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(client_id) ON DELETE SET NULL,
    table_name VARCHAR(50) NOT NULL,
    record_id INTEGER,
    action VARCHAR(20) NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    old_values JSONB,
    new_values JSONB,
    changed_by VARCHAR(100),
    changed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_config_audit_log_client_id (client_id),
    INDEX idx_config_audit_log_table (table_name),
    INDEX idx_config_audit_log_changed_at (changed_at)
);

-- Table: dead_letter_queue
-- Purpose: Store failed operations for retry and analysis
CREATE TABLE dead_letter_queue (
    dlq_id SERIAL PRIMARY KEY,
    dlq_uuid UUID NOT NULL DEFAULT gen_random_uuid(),
    client_id INTEGER REFERENCES clients(client_id) ON DELETE SET NULL,
    pack_name VARCHAR(50),
    workflow_name VARCHAR(100),
    operation_type VARCHAR(100) NOT NULL, -- e.g., 'email_validation', 'ocr_extraction', 'api_call'
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
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_dlq_client_id (client_id),
    INDEX idx_dlq_status (status),
    INDEX idx_dlq_next_retry (next_retry_at),
    INDEX idx_dlq_created_at (created_at)
);

-- Table: notifications
-- Purpose: Track sent notifications
CREATE TABLE notifications (
    notification_id SERIAL PRIMARY KEY,
    notification_uuid UUID NOT NULL DEFAULT gen_random_uuid(),
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    recipient VARCHAR(255) NOT NULL,
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('email', 'slack', 'sms', 'webhook')),
    notification_type VARCHAR(50) NOT NULL, -- e.g., 'sla_breach', 'task_assigned', 'error_alert'
    subject VARCHAR(500),
    body TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
    error_message TEXT,
    sent_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_notifications_client_id (client_id),
    INDEX idx_notifications_status (status),
    INDEX idx_notifications_created_at (created_at)
);
```

### Sample Data Examples

```sql
-- Sample client configuration
INSERT INTO clients (name, slug, status, billing_provider, timezone) VALUES
('Acme Corp', 'acme-corp', 'active', 'quickbooks', 'America/New_York'),
('TechStart Inc', 'techstart-inc', 'active', 'square', 'America/Los_Angeles');

INSERT INTO client_packs (client_id, pack_name, enabled) VALUES
(1, 'INTAKE_v1', true),
(1, 'DOCS_v1', true),
(1, 'TASKS_v1', true),
(2, 'INTAKE_v1', true),
(2, 'TASKS_v1', false);

INSERT INTO client_config (client_id, pack_name, config_key, config_value, value_type, description) VALUES
(1, 'INTAKE_v1', 'enabled_input_channels', '["web_form", "email", "api"]', 'array', 'Active lead input channels'),
(1, 'INTAKE_v1', 'min_lead_score_threshold', '50', 'number', 'Minimum lead score for routing'),
(1, 'DOCS_v1', 'confidence_threshold', '0.8', 'number', 'Minimum confidence for auto-processing'),
(1, 'TASKS_v1', 'sla_assignment_minutes', '120', 'number', 'SLA for task assignment in minutes');

-- Sample integration credentials (encrypted in production)
INSERT INTO client_integrations (client_id, integration_name, integration_type, auth_type, credentials) VALUES
(1, 'neverbounce', 'email_validation', 'api_key', '{"api_key": "encrypted_key_here"}'),
(1, 'clearbit', 'company_lookup', 'api_key', '{"api_key": "encrypted_key_here"}'),
(1, 'openai', 'llm', 'api_key', '{"api_key": "encrypted_key_here"}'),
(2, 'square', 'billing', 'oauth', '{"access_token": "encrypted_token_here"}');

-- Sample team member
INSERT INTO team_members (client_id, name, email, skills, working_hours, max_concurrent_tasks) VALUES
(1, 'John Smith', 'john@acme.com', '["sales", "support"]', '{"timezone": "America/New_York", "start": "09:00", "end": "17:00", "days": [1,2,3,4,5]}', 15);

-- Sample lead
INSERT INTO leads (client_id, email, full_name, company_name, source, lead_score, status) VALUES
(1, 'jane@example.com', 'Jane Doe', 'Example Corp', 'web_form', 75, 'new');
```

### Migration Strategy

**Phase 1: Schema Creation**
- Run all CREATE TABLE statements in dependency order (core → pack-specific → audit)
- Create database indexes after data load to speed up initial migration
- Set up foreign key constraints after all tables exist

**Phase 2: Data Validation**
- Run sample inserts to validate referential integrity
- Test unique constraints and check constraints
- Verify index creation with EXPLAIN ANALYZE queries

**Phase 3: Audit Triggers**
- Create PostgreSQL triggers to populate `config_audit_log` automatically
- Implement timestamp update triggers for `updated_at` fields

**Phase 4: Rollback Plan**
- Export schema before migration (pg_dump --schema-only)
- Create migration rollback scripts (DROP TABLE in reverse dependency order)
- Test rollback in development environment

---

## 4. WORKFLOW INVENTORY

### INTAKE_v1 Pack Workflows

#### Workflow 1: INTAKE_v1_Capture_Leads
**Workflow ID**: INTAKE_v1_001
**Trigger**: Multiple (webhook, scheduled, manual)
**Steps**:
1. **Trigger Router**: Accepts input from web form webhook, email parser, API endpoint, or CSV upload
2. **Client Identification**: Extract client_id from webhook headers, API key, or filename pattern
3. **Idempotency Check**: Query `leads` table for duplicate email + client_id; skip if exists
4. **Initial Validation**: Validate required fields (email is present, valid format); return 400 if invalid
5. **Source Normalization**: Map source-specific fields to standard schema using `client_config` mappings
6. **Write to Database**: INSERT into `leads` table with status='processing'
7. **Trigger Enrichment**: Call INTAKE_v1_Enrich_Leads workflow via webhook
8. **Return Response**: Return 200 with lead_uuid to caller

**Outputs**: New lead record in `leads` table; triggers enrichment workflow
**Dependencies**: PostgreSQL, client_config table
**Expected Execution Time**: 100-500ms
**Idempotency Strategy**: Check for existing lead by email + client_id; use idempotency_key from request header

#### Workflow 2: INTAKE_v1_Normalize_Data
**Workflow ID**: INTAKE_v1_002
**Trigger**: Called by INTAKE_v1_Capture_Leads
**Steps**:
1. **Read Configuration**: Fetch field mappings from `client_config` for client_id
2. **Apply Transformations**: 
   - Standardize phone format (E.164)
   - Split full_name into first_name, last_name
   - Normalize company name (remove common suffixes)
   - Convert custom field values to appropriate types
3. **Calculate Initial Lead Score**: Based on source weight, completion percentage, custom scoring rules
4. **Update Lead**: UPDATE `leads` table with normalized data and initial score
5. **Trigger Enrichment**: Call INTAKE_v1_Enrich_Leads if not already triggered
6. **Log Execution**: Write to `workflow_executions` table

**Outputs**: Normalized lead data with initial score
**Dependencies**: client_config table, leads table
**Expected Execution Time**: 50-200ms
**Idempotency Strategy**: Update operation is idempotent; re-run produces same result

#### Workflow 3: INTAKE_v1_Enrich_Leads
**Workflow ID**: INTAKE_v1_003
**Trigger**: Called by INTAKE_v1_Capture_Leads or INTAKE_v1_Normalize_Data
**Steps**:
1. **Read Configuration**: Fetch enabled enrichment services from `client_config`
2. **Parallel Enrichment** (async branches):
   - **Branch A - Email Validation**: Call NeverBounce API; parse deliverability status
   - **Branch B - Company Lookup**: Call Clearbit API; fetch company data (industry, size, location)
   - **Branch C - Duplicate Check**: Fuzzy match against existing leads in `leads` table
3. **Aggregate Results**: Combine enrichment data; update lead_score based on results
4. **Write Enrichment Records**: INSERT into `lead_enrichment` table for each service
5. **Update Lead**: UPDATE `leads` table with enriched data and status='enriched'
6. **Error Handling**: If any enrichment fails, log to `dead_letter_queue` but continue with others
7. **Trigger Routing**: Call INTAKE_v1_Route_Leads workflow
8. **Log Execution**: Write to `workflow_executions` table

**Outputs**: Enriched lead data with updated score
**Dependencies**: NeverBounce API, Clearbit API, client_config, lead_enrichment table
**Expected Execution Time**: 3-10 seconds (API dependent)
**Idempotency Strategy**: Check for existing enrichment records by lead_id + enrichment_type; skip if exists

#### Workflow 4: INTAKE_v1_Route_Leads
**Workflow ID**: INTAKE_v1_004
**Trigger**: Called by INTAKE_v1_Enrich_Leads
**Steps**:
1. **Read Routing Rules**: Fetch routing configuration from `client_config`
2. **Evaluate Rules**: Process rules in priority order (IF lead_score > X AND source = Y THEN route_to Z)
3. **Select Destination**: Match first rule that evaluates to true
4. **API Call**: Send lead data to destination system (HubSpot, Salesforce, etc.)
5. **Handle Response**: 
   - Success: Record destination_record_id, status='completed'
   - Failure: Log error, retry with exponential backoff (max 3 attempts)
6. **Write Routing Record**: INSERT into `lead_routing` table
7. **Update Lead Status**: UPDATE `leads` set status='routed'
8. **Send Notification**: Notify configured recipients of new lead
9. **Log Execution**: Write to `workflow_executions` table

**Outputs**: Lead routed to destination system
**Dependencies**: client_config, lead_routing table, external CRM APIs
**Expected Execution Time**: 1-3 seconds (API dependent)
**Idempotency Strategy**: Check for existing routing record by lead_id; skip if already routed

### DOCS_v1 Pack Workflows

#### Workflow 1: DOCS_v1_Intake_Docs
**Workflow ID**: DOCS_v1_001
**Trigger**: Multiple (email monitoring, file upload webhook, cloud storage webhooks)
**Steps**:
1. **Trigger Router**: Accept input from email attachment, API upload, or Drive/Dropbox webhook
2. **Client Identification**: Extract client_id from email address, API key, or folder structure
3. **File Download**: Download file from source (email attachment, API, cloud storage)
4. **Generate Hash**: Calculate SHA-256 hash of file
5. **Idempotency Check**: Query `documents` table for existing hash + client_id; skip if exists
6. **Store File**: Upload to S3/MinIO with path: `{client_uuid}/{year}/{month}/{document_uuid}.{ext}`
7. **Write Document Record**: INSERT into `documents` table with status='intake'
8. **Trigger Classification**: Call DOCS_v1_Classify_Docs workflow
9. **Send Acknowledgment**: Return 200 with document_uuid

**Outputs**: New document record in `documents` table; triggers classification workflow
**Dependencies**: S3/MinIO, PostgreSQL, email/cloud storage APIs
**Expected Execution Time**: 500ms-2 seconds (file size dependent)
**Idempotency Strategy**: Check for existing document by file_hash; skip if exists

#### Workflow 2: DOCS_v1_Classify_Docs
**Workflow ID**: DOCS_v1_002
**Trigger**: Called by DOCS_v1_Intake_Docs
**Steps**:
1. **Read Configuration**: Fetch document type definitions from `client_config`
2. **Extract Text**: Use OCR (Tesseract) to extract text from document
3. **Call LLM**: Send text to OpenAI/Anthropic with classification prompt
4. **Parse Response**: Extract document_type and confidence_score from LLM response
5. **Apply Thresholds**: 
   - If confidence >= configured_threshold: auto-classify
   - If confidence < configured_threshold: mark for human review
6. **Update Document**: UPDATE `documents` table with document_type, confidence_score, status
7. **Trigger Extraction**: Call DOCS_v1_Extract_Data workflow if confidence >= threshold
8. **Trigger Review Queue**: If requires_review=true, add to human review queue
9. **Log Execution**: Write to `workflow_executions` table

**Outputs**: Classified document with type and confidence
**Dependencies**: Tesseract OCR, OpenAI/Anthropic API, client_config
**Expected Execution Time**: 2-10 seconds (document size dependent)
**Idempotency Strategy**: Check document.status; skip if already classified

#### Workflow 3: DOCS_v1_Extract_Data
**Workflow ID**: DOCS_v1_003
**Trigger**: Called by DOCS_v1_Classify_Docs (if confidence >= threshold)
**Steps**:
1. **Read Configuration**: Fetch extraction schema for document_type from `client_config`
2. **Extract Text**: Use OCR if not already done
3. **Call LLM**: Send text + extraction schema to OpenAI/Anthropic with extraction prompt
4. **Parse Response**: Extract structured data fields and per-field confidence scores
5. **Write Extraction Record**: INSERT into `document_extractions` table
6. **Trigger Validation**: Call DOCS_v1_Validate_Data workflow
7. **Log Execution**: Write to `workflow_executions` table

**Outputs**: Structured data extracted from document
**Dependencies**: Tesseract OCR, OpenAI/Anthropic API, client_config
**Expected Execution Time**: 3-15 seconds (document size dependent)
**Idempotency Strategy**: Check for existing extraction by document_id; skip if exists

#### Workflow 4: DOCS_v1_Validate_Data
**Workflow ID**: DOCS_v1_004
**Trigger**: Called by DOCS_v1_Extract_Data
**Steps**:
1. **Read Configuration**: Fetch validation rules for document_type from `client_config`
2. **Check Required Fields**: Verify all required fields are present and not null
3. **Validate Field Formats**: Apply format rules (email, phone, date, amount, etc.)
4. **Business Rule Validation**: Apply custom validation rules (e.g., invoice date <= today)
5. **Calculate Validation Status**:
   - All valid: validation_status='valid'
   - Some invalid: validation_status='partial'
   - Critical failures: validation_status='invalid'
6. **Update Extraction**: UPDATE `document_extractions` with validation_status and validation_errors
7. **Decision Point**:
   - If valid: Trigger DOCS_v1_Route_Docs workflow
   - If invalid/partial: Update document.status='review_required', notify team
8. **Log Execution**: Write to `workflow_executions` table

**Outputs**: Validated extraction data with status
**Dependencies**: client_config, document_extractions table
**Expected Execution Time**: 100-500ms
**Idempotency Strategy**: Update operation is idempotent

#### Workflow 5: DOCS_v1_Route_Docs
**Workflow ID**: DOCS_v1_005
**Trigger**: Called by DOCS_v1_Validate_Data (if valid)
**Steps**:
1. **Read Routing Rules**: Fetch routing configuration for document_type from `client_config`
2. **Format Payload**: Transform extracted data to destination system format
3. **API Call**: Send data to destination system (QuickBooks, HubSpot, etc.)
4. **Handle Response**:
   - Success: Record destination_record_id, status='completed'
   - Failure: Log error, retry with exponential backoff (max 3 attempts)
5. **Write Routing Record**: INSERT into `document_routing` table
6. **Update Document Status**: UPDATE `documents` set status='completed'
7. **Send Notification**: Notify configured recipients of successful processing
8. **Log Execution**: Write to `workflow_executions` table

**Outputs**: Document data routed to destination system
**Dependencies**: client_config, document_routing table, external APIs
**Expected Execution Time**: 1-3 seconds (API dependent)
**Idempotency Strategy**: Check for existing routing by document_id; skip if exists

#### Workflow 6: DOCS_v1_Human_Review_Queue
**Workflow ID**: DOCS_v1_006
**Trigger**: Scheduled (every 10 minutes)
**Steps**:
1. **Query Review Queue**: SELECT documents WHERE requires_review=true AND review_assigned_to IS NULL
2. **Assign Reviewer**: Select team member based on workload and skills
3. **Update Document**: SET review_assigned_to=member_id
4. **Send Notification**: Email/Slack reviewer with document details and review link
5. **Wait for Review**: Poll for review completion (manual update via API)
6. **On Review Complete**:
   - If approved: Trigger DOCS_v1_Extract_Data workflow
   - If rejected: Update document.status='error', log rejection reason
7. **Log Execution**: Write to `workflow_executions` table

**Outputs**: Documents assigned for human review
**Dependencies**: team_members table, notification system
**Expected Execution Time**: 5-10 seconds (batch processing)
**Idempotency Strategy**: Check review_assigned_to before assignment

### TASKS_v1 Pack Workflows

#### Workflow 1: TASKS_v1_Create_Tasks
**Workflow ID**: TASKS_v1_001
**Trigger**: Multiple (webhooks from INTAKE/DOCS packs, API calls)
**Steps**:
1. **Parse Input**: Extract task data (source_type, source_id, title, description, priority)
2. **Client Identification**: Extract client_id from input
3. **Read Configuration**: Fetch task creation rules from `client_config`
4. **Calculate Urgency Score**: Based on source_type, priority, SLA requirements
5. **Insert Task**: INSERT into `tasks` table with status='created', calculated priority
6. **Trigger Assignment**: Call TASKS_v1_Assign_Tasks workflow
7. **Log Execution**: Write to `workflow_executions` table

**Outputs**: New task record in `tasks` table
**Dependencies**: tasks table, client_config
**Expected Execution Time**: 100-300ms
**Idempotency Strategy**: Check for existing task by source_type + source_id; skip if exists

#### Workflow 2: TASKS_v1_Assign_Tasks
**Workflow ID**: TASKS_v1_002
**Trigger**: Called by TASKS_v1_Create_Tasks, scheduled (every 5 minutes for unassigned)
**Steps**:
1. **Query Unassigned Tasks**: SELECT tasks WHERE status='created'
2. **Read Assignment Rules**: Fetch assignment strategy from `client_config` (round_robin, skill_based, workload_balanced)
3. **For Each Task**:
   - Calculate candidate team members (active, matching skills, within working hours)
   - Calculate current workload for each candidate (active task count)
   - Select assignee based on strategy:
     - Round-robin: Use last assignment index, increment
     - Skill-based: Match task_type to member skills
     - Workload-balanced: Select member with lowest workload
   - Update task: SET assigned_to=member_id, status='assigned', assigned_at=NOW()
   - Insert assignment record into `task_assignments`
   - Send notification to assignee
4. **Log Execution**: Write to `workflow_executions` table

**Outputs**: Tasks assigned to team members
**Dependencies**: tasks table, team_members table, task_assignments table, client_config
**Expected Execution Time**: 1-3 seconds (batch dependent)
**Idempotency Strategy**: Check task.status before assignment; skip if already assigned

#### Workflow 3: TASKS_v1_Monitor_SLA
**Workflow ID**: TASKS_v1_003
**Trigger**: Scheduled (every 5 minutes)
**Steps**:
1. **Read SLA Configuration**: Fetch SLA definitions from `client_config` per task_type
2. **Query Active Tasks**: SELECT tasks WHERE status IN ('created', 'assigned', 'in_progress')
3. **For Each Task**:
   - Calculate elapsed time since creation/assignment
   - Compare to SLA threshold:
     - Assignment SLA: Check if created_at > X minutes ago and still unassigned
     - Completion SLA: Check if assigned_at > Y minutes ago and not completed
     - Response SLA: Check if in_progress started > Z minutes ago without update
   - If SLA breached:
     - Check for existing SLA event (avoid duplicate notifications)
     - Insert SLA event into `sla_events` table
     - Calculate escalation level (increment on repeated breach)
     - Fetch escalation recipients from configuration
     - Send notification via configured channel (email, Slack, SMS)
     - Update sla_event.notification_sent=true
   - If SLA approaching warning threshold (80%):
     - Send warning notification to assignee
4. **Log Execution**: Write to `workflow_executions` table

**Outputs**: SLA monitoring and escalation events
**Dependencies**: tasks table, sla_events table, client_config
**Expected Execution Time**: 2-5 seconds (batch dependent)
**Idempotency Strategy**: Check for existing SLA event before creating new one

#### Workflow 4: TASKS_v1_Generate_Reports
**Workflow ID**: TASKS_v1_004
**Trigger**: Scheduled (daily at 8 AM client timezone, weekly on Monday at 8 AM)
**Steps**:
1. **Read Report Configuration**: Fetch report schedules and formats from `client_config`
2. **For Each Due Report**:
   - Query tasks and SLA events for report period
   - Calculate metrics: completed tasks, average completion time, SLA breaches, workload distribution
   - Generate report in configured format:
     - HTML: Use template engine with metrics
     - PDF: Convert HTML to PDF using wkhtmltopdf
     - CSV: Export raw data
   - Write report record to `reports` table
   - Upload report file to storage
   - Send report to configured recipients
   - Update report.status='completed', generated_at=NOW()
3. **Log Execution**: Write to `workflow_executions` table

**Outputs**: Generated reports delivered to recipients
**Dependencies**: tasks table, sla_events table, reports table, wkhtmltopdf
**Expected Execution Time**: 5-15 seconds (report complexity dependent)
**Idempotency Strategy**: Check report.status; skip if already completed for period

---

## 5. SECURITY & COMPLIANCE

### Secrets Management Approach

**Environment Variables + Database Encryption Hybrid Strategy**

**Environment Variables** (for infrastructure secrets):
- Database connection strings (POSTGRES_URL)
- S3/MinIO access keys and secrets
- n8n encryption keys (N8N_ENCRYPTION_KEY)
- SMTP credentials for notifications
- OAuth secrets for authentication providers

**PostgreSQL pgcrypto Extension** (for client-specific secrets):
- Enable pgcrypto extension: `CREATE EXTENSION IF NOT EXISTS pgcrypto;`
- Encrypt client integration credentials using AES-256-GCM
- Store encryption keys in environment variables (one key per client or master key)
- Use `pgp_sym_encrypt()` and `pgp_sym_decrypt()` functions for transparent encryption/decryption

**Credential Storage Schema**:
```sql
-- Encrypted credential example
UPDATE client_integrations 
SET credentials = pgp_sym_encrypt(
    '{"api_key": "actual_key_here"}'::jsonb,
    current_setting('app.encryption_key')
)
WHERE integration_id = 1;

-- Decryption in n8n workflow
SELECT pgp_sym_decrypt(credentials::bytea, current_setting('app.encryption_key'))::jsonb
FROM client_integrations WHERE integration_id = 1;
```

### Access Control Model

**Role-Based Access Control (RBAC)**

**Roles**:
1. **Super Admin**: Full system access (internal use only)
2. **Client Admin**: Full access to their client's data and configuration
3. **Client Operator**: Read-only access to their client's data
4. **Team Member**: Access to assigned tasks only
5. **API Client**: Limited access via API keys

**Database Row-Level Security (RLS)**:
```sql
-- Enable RLS on sensitive tables
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;

-- Policy: Client admins can CRUD their own data
CREATE POLICY client_admin_full_access ON leads
    FOR ALL
    TO client_admin_role
    USING (client_id = current_client_id());

-- Policy: Team members can only see assigned tasks
CREATE POLICY team_member_tasks ON tasks
    FOR SELECT
    TO team_member_role
    USING (assigned_to = current_member_id());

-- Policy: API clients can insert leads only for authorized client
CREATE POLICY api_client_insert ON leads
    FOR INSERT
    TO api_client_role
    WITH CHECK (client_id = authorized_client_id());
```

**n8n Workflow Access Control**:
- Use PostgreSQL node with connection pool per client
- Set `current_setting('app.current_client_id')` before query execution
- Apply RLS policies automatically at database level
- Log all data access with client_id and user context

### Data Encryption

**At Rest**:
- **Database**: Transparent Data Encryption (TDE) via PostgreSQL encryption at filesystem level or using LUKS on disk
- **Files**: All documents stored in S3/MinIO with server-side encryption (SSE-S3 or SSE-KMS)
- **Backups**: Encrypted using GPG or cloud provider encryption
- **Configuration**: Client credentials encrypted with pgcrypto

**In Transit**:
- **All API calls**: HTTPS/TLS 1.3 enforced
- **Database connections**: SSL/TLS required (sslmode=require)
- **n8n webhooks**: HTTPS with certificate validation
- **Email**: SMTP with STARTTLS or implicit SSL

**Encryption Configuration**:
```nginx
# Nginx reverse proxy configuration (example)
server {
    listen 443 ssl http2;
    ssl_certificate /etc/ssl/certs/n8n.crt;
    ssl_certificate_key /etc/ssl/private/n8n.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    location / {
        proxy_pass http://localhost:5678;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# PostgreSQL connection string
postgresql://user:pass@host:5432/db?sslmode=require&sslcert=/path/to/cert.pem
```

### PII Handling and Data Retention

**PII Classification**:
- **High Sensitivity**: Email addresses, phone numbers, SSN, financial data
- **Medium Sensitivity**: Names, addresses, job titles
- **Low Sensitivity**: Company names, generic metadata

**PII Handling Policies**:
- Encrypt high-sensitivity PII at rest and in transit
- Log PII access with audit trail
- Implement data anonymization for reports (mask emails, truncate phone numbers)
- Support right to be forgotten (GDPR Article 17):
  - Soft delete (mark as deleted, retain for audit)
  - Hard delete after retention period (30 days)

**Data Retention Policies**:
```sql
-- Data retention table
CREATE TABLE data_retention_policies (
    table_name VARCHAR(50) PRIMARY KEY,
    retention_months INTEGER NOT NULL,
    soft_delete BOOLEAN DEFAULT true,
    hard_delete_after_months INTEGER
);

INSERT INTO data_retention_policies VALUES
('leads', 36, true, 6),              -- Keep leads 3 years, hard delete after 6 months soft-delete
('documents', 84, true, 12),         -- Keep documents 7 years, hard delete after 1 year soft-delete
('tasks', 60, true, 6),              -- Keep tasks 5 years, hard delete after 6 months soft-delete
('workflow_executions', 12, false, 1), -- Keep execution logs 1 year
('dead_letter_queue', 6, false, 1);  -- Keep DLQ items 6 months
```

**Scheduled Retention Workflow**:
- Runs daily at 3 AM
- Identifies records past retention period
- Performs soft delete (update status='deleted')
- Performs hard delete for records past hard_delete_after_months
- Logs all deletions to audit log

### Compliance Considerations

**GDPR (General Data Protection Regulation)**:
- Data processing agreements with all clients
- Data subject access request (DSAR) support
- Data portability export (JSON/CSV format)
- Right to erasure implementation
- Data breach notification within 72 hours
- Data protection officer (DPO) contact

**SOC 2 Type II (if applicable)**:
- Access control logging
- Change management procedures
- Incident response plan
- Regular security audits
- Third-party penetration testing
- Background checks for personnel with data access

**CCPA (California Consumer Privacy Act)**:
- Do Not Sell My Information notice
- Opt-out mechanism for data sharing
- Data deletion rights
- Data disclosure tracking

**HIPAA (if processing healthcare data)**:
- Business Associate Agreements (BAAs)
- PHI encryption and access controls
- Audit logging for PHI access
- Risk assessments and security controls

### API Authentication Methods

**API Keys** (for client integrations):
```sql
-- API keys table
CREATE TABLE api_keys (
    api_key_id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    key_name VARCHAR(100) NOT NULL,
    api_key_hash VARCHAR(255) NOT NULL, -- SHA-256 hash of key
    scopes JSONB, -- e.g., ["leads:read", "tasks:write"]
    rate_limit_per_minute INTEGER DEFAULT 100,
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_api_keys_client_id (client_id)
);
```

**Authentication Flow**:
1. Client sends API key in header: `X-API-Key: client_api_key`
2. n8n workflow hashes the key and queries database
3. Validate key is active, not expired, and has required scopes
4. Set `current_setting('app.current_client_id')` for RLS
5. Log API key usage for audit

**JWT Tokens** (for internal admin access):
- Short-lived tokens (15 minutes)
- Refresh tokens (7 days)
- Claims: user_id, role, client_id (if applicable), scopes
- Signed with RS256 (asymmetric encryption)

**Webhook Authentication**:
- HMAC signature verification for webhooks
- Shared secret per client stored encrypted
- Timestamp validation to prevent replay attacks

---

## 6. MONITORING & RELIABILITY

### Key Metrics to Track

**System-Level Metrics**:
- **Throughput**: Records processed per minute (leads, documents, tasks)
- **Latency**: Average workflow execution time (p50, p95, p99)
- **Error Rate**: Percentage of failed workflow executions (target <1%)
- **Queue Depth**: Number of pending items in processing queues
- **Database Performance**: Query execution time, connection pool utilization
- **API Rate Limits**: Usage rate vs. limits per integration

**Business-Level Metrics**:
- **Client-Specific Throughput**: Records processed per client
- **SLA Breach Rate**: Percentage of tasks missing SLA (target <5%)
- **Enrichment Success Rate**: Email validation, company lookup success rates
- **Document Classification Accuracy**: Percentage of correct classifications
- **Task Assignment Time**: Average time from task creation to assignment

**Infrastructure Metrics**:
- **CPU/Memory Usage**: Server resource utilization
- **Disk Space**: Storage usage for documents and logs
- **Network I/O**: Bandwidth consumption
- **Process Health**: n8n, PostgreSQL, Redis (if used) status

### Alert Thresholds and Notification Channels

**Critical Alerts** (immediate notification within 5 minutes):
- Workflow execution error rate >5% for 5 consecutive minutes
- Database connection failures >3 in 10 minutes
- Disk space >85% utilization
- API key rate limit exceeded (blocking operations)
- SLA breach rate >10% for any client
- n8n process not responding for >5 minutes

**Warning Alerts** (notification within 30 minutes):
- Workflow execution latency >2x baseline for 10 minutes
- Database query time >1 second for 5% of queries
- API rate limit usage >80% of limit
- Queue depth >1000 items for >5 minutes
- Document classification confidence <80% for 20% of documents

**Notification Channels**:
- **Primary**: Slack channel #ops-alerts
- **Secondary**: PagerDuty (on-call rotation)
- **Fallback**: Email to ops-team@company.com
- **Client-Specific**: Email to client contact for SLA breaches

### Logging Strategy

**What to Log**:
- All workflow executions (start, end, duration, status)
- All database transactions (INSERT, UPDATE, DELETE with before/after values)
- All external API calls (request, response, duration, status code)
- All configuration changes (who changed what, when)
- All authentication attempts (success, failure, IP address)
- All errors with full stack traces and context

**Log Levels**:
- **ERROR**: Workflow failures, API errors, database errors
- **WARN**: Retryable failures, approaching rate limits, SLA warnings
- **INFO**: Workflow starts/completes, configuration changes, successful API calls
- **DEBUG**: Detailed execution steps, intermediate values (dev environment only)

**Log Retention**:
- Production: 90 days (hot storage), 1 year (cold storage/archive)
- Development: 30 days

**Log Aggregation**:
- Use Loki or ELK Stack for centralized logging
- Structured JSON logging format
- Include correlation IDs across workflow steps
- Log search and filtering by client_id, workflow_name, status

**Log Format Example**:
```json
{
  "timestamp": "2024-01-15T10:30:45Z",
  "level": "INFO",
  "workflow": "INTAKE_v1_Enrich_Leads",
  "execution_id": "uuid-here",
  "client_id": 1,
  "lead_id": 12345,
  "message": "Lead enrichment completed successfully",
  "duration_ms": 5234,
  "context": {
    "enrichment_services": ["email_validation", "company_lookup"],
    "lead_score": 75,
    "routing_destination": "hubspot"
  }
}
```

### SLA Targets for v1

**System Availability**: 99% uptime (approximately 7.3 hours downtime per month allowed)
- Maintenance windows: Sunday 2-4 AM UTC (planned downtime excluded from SLA)

**Workflow Performance**:
- Lead capture: <500ms (p95)
- Lead enrichment: <10 seconds (p95)
- Document classification: <15 seconds (p95)
- Task assignment: <5 seconds (p95)

**Data Integrity**:
- Zero data loss
- Duplicate detection accuracy: >99%
- Data validation accuracy: >99%

**Support Response**:
- Critical issues: Response within 1 hour, resolution within 4 hours
- High priority: Response within 4 hours, resolution within 24 hours
- Medium priority: Response within 24 hours, resolution within 72 hours
- Low priority: Response within 48 hours, resolution within 5 business days

**Data Processing**:
- Throughput: 1000+ records per hour per client
- API error rate: <1%
- Retry success rate: >80% (after initial failure)

### Health Check Endpoints

**System Health Check** (`GET /health`):
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "checks": {
    "database": {
      "status": "healthy",
      "latency_ms": 15
    },
    "n8n": {
      "status": "healthy",
      "active_executions": 23
    },
    "storage": {
      "status": "healthy",
      "disk_usage_percent": 42
    }
  }
}
```

**Readiness Check** (`GET /ready`):
- Check if database is accepting connections
- Check if n8n is ready to accept webhooks
- Check if all required environment variables are set

**Liveness Check** (`GET /live`):
- Check if main processes are running (n8n, PostgreSQL)
- Check if server is responsive (HTTP 200)

**Dependency Health Check** (`GET /health/dependencies`):
- Check external API health (NeverBounce, Clearbit, OpenAI)
- Check billing integration status (QuickBooks, Square)
- Check notification service status (SMTP, Slack)

**Monitoring Integration**:
- Configure Prometheus to scrape health endpoints every 30 seconds
- Set up Grafana dashboards for visual monitoring
- Alert on health check failures

---

## 7. ERROR HANDLING STRATEGY

### Retry Logic

**Exponential Backoff Parameters**:
- Initial delay: 1 second
- Backoff multiplier: 2
- Maximum delay: 60 seconds
- Maximum retry attempts: 3 (configurable per integration)
- Jitter: ±20% random variation to avoid thundering herd

**Retry Configuration per Integration**:
```sql
-- Retry policies table
CREATE TABLE retry_policies (
    integration_name VARCHAR(100) PRIMARY KEY,
    max_retries INTEGER NOT NULL DEFAULT 3,
    initial_delay_seconds INTEGER NOT NULL DEFAULT 1,
    max_delay_seconds INTEGER NOT NULL DEFAULT 60,
    backoff_multiplier DECIMAL(3,2) NOT NULL DEFAULT 2.0,
    retryable_status_codes JSONB -- e.g., [429, 500, 502, 503, 504]
);

INSERT INTO retry_policies VALUES
('neverbounce', 3, 1, 60, 2.0, '[429, 500, 502, 503, 504]'),
('clearbit', 2, 1, 60, 2.0, '[429, 500, 502, 503, 504]'),
('openai', 3, 2, 60, 2.0, '[429, 500, 502, 503, 504]'),
('hubspot', 3, 1, 60, 2.0, '[429, 500, 502, 503, 504]');
```

**Retry Implementation in n8n**:
```javascript
// n8n function node for retry logic
const maxRetries = $node["Config"].json.max_retries;
const initialDelay = $node["Config"].json.initial_delay_seconds;
const maxDelay = $node["Config"].json.max_delay_seconds;
const backoffMultiplier = $node["Config"].json.backoff_multiplier;
const retryCount = $node["Previous"].json.retry_count || 0;

if (retryCount >= maxRetries) {
  throw new Error('Max retries exceeded');
}

const delay = Math.min(
  initialDelay * Math.pow(backoffMultiplier, retryCount),
  maxDelay
);

// Add jitter (±20%)
const jitter = delay * 0.2 * (Math.random() * 2 - 1);
const finalDelay = Math.max(0, delay + jitter);

// Wait before retry
await new Promise(resolve => setTimeout(resolve, finalDelay * 1000));

// Increment retry count
return [{
  json: {
    ...$node["Previous"].json,
    retry_count: retryCount + 1
  }
}];
```

### Fallback Mechanisms

**Degraded Mode Operations**:

1. **Email Validation Fallback**:
   - Primary: NeverBounce API
   - Fallback: Regex syntax validation (deliverability unknown)
   - Action: Flag lead for manual review if API fails

2. **Company Lookup Fallback**:
   - Primary: Clearbit API
   - Fallback: Google Search API or manual research
   - Action: Leave company fields null, continue processing

3. **OCR/LLM Fallback**:
   - Primary: Tesseract + OpenAI
   - Fallback: Cloud-based OCR (Google Vision, AWS Textract)
   - Action: Use secondary service; if both fail, mark for human review

4. **Database Write Fallback**:
   - Primary: PostgreSQL write
   - Fallback: Write to local file system, queue for later sync
   - Action: Alert ops team, attempt sync when database recovers

5. **Notification Fallback**:
   - Primary: Email (SMTP)
   - Fallback: Slack webhook
   - Secondary Fallback: Log to database, manual notification

**Fallback Configuration**:
```sql
-- Fallback strategies table
CREATE TABLE fallback_strategies (
    strategy_id SERIAL PRIMARY KEY,
    operation_type VARCHAR(100) NOT NULL,
    primary_service VARCHAR(100) NOT NULL,
    fallback_service VARCHAR(100),
    fallback_action VARCHAR(50) NOT NULL CHECK (fallback_action IN ('retry', 'queue', 'manual_review', 'skip', 'flag')),
    fallback_timeout_seconds INTEGER DEFAULT 300
);

INSERT INTO fallback_strategies VALUES
(1, 'email_validation', 'neverbounce', 'regex_syntax', 'flag', 30),
(2, 'company_lookup', 'clearbit', NULL, 'skip', 60),
(3, 'document_ocr', 'tesseract', 'google_vision', 'retry', 120),
(4, 'notification_send', 'smtp', 'slack_webhook', 'retry', 60);
```

### Dead-Letter Queue Design

**DLQ Schema** (already defined in Data Models section):
```sql
CREATE TABLE dead_letter_queue (
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
```

**DLQ Processing Workflow**:
1. **Scheduled Workflow** (every 10 minutes):
   - Query DLQ for items WHERE status='pending' AND next_retry_at <= NOW()
   - For each item:
     - Load payload
     - Retry operation with same context
     - If success: UPDATE status='resolved', resolved_at=NOW()
     - If fail: Increment retry_count, calculate next_retry_at using exponential backoff
     - If retry_count >= max_retries: UPDATE status='failed', notify ops team

2. **Manual Resolution Interface**:
   - Simple web UI or API endpoint to view DLQ items
   - Allow manual retry with modified payload
   - Allow marking as resolved with notes
   - Export DLQ items for analysis

3. **DLQ Monitoring**:
   - Alert on DLQ depth >100 items
   - Alert on failed items increasing rapidly
   - Daily report of DLQ stats (new, retried, resolved, failed)

**DLQ Retry Calculation**:
```javascript
// Calculate next retry time
const baseDelay = 60; // seconds
const backoffMultiplier = 2;
const maxDelay = 3600; // 1 hour max
const retryCount = item.retry_count;

const delay = Math.min(
  baseDelay * Math.pow(backoffMultiplier, retryCount),
  maxDelay
);

const nextRetryAt = new Date(Date.now() + delay * 1000);
```

### User Notifications

**When to Alert Users**:

1. **Client-Facing Notifications**:
   - SLA breaches (task not assigned within threshold)
   - Document processing failures (requiring human review)
   - Lead routing failures (lead not delivered to CRM)
   - Daily/weekly summary reports

2. **Internal Ops Team Notifications**:
   - System-wide failures (database down, n8n not responding)
   - API rate limit exceeded
   - DLQ items exceeding threshold
   - Security alerts (unusual access patterns, failed authentication attempts)

3. **Critical Alerts** (immediate notification):
   - Data loss or corruption
   - Security breach detected
   - Payment processing failures
   - Compliance violations

**How to Alert Users**:

**Notification Channels**:
1. **Email**: Primary channel for non-urgent notifications
   - Use transactional email service (SendGrid, AWS SES)
   - HTML email templates with clear formatting
   - Include action buttons (e.g., "View Lead", "Resolve Issue")

2. **Slack**: Primary channel for internal ops alerts
   - Channel-specific routing (#ops-alerts, #client-{client_id})
   - Rich formatting with buttons and attachments
   - Integration with PagerDuty for on-call escalation

3. **SMS**: Critical alerts only (SLA breaches, system outages)
   - Use Twilio or similar
   - Limit to 10 SMS per recipient per day

4. **Webhook**: For clients with custom notification systems
   - Retry on failure with exponential backoff
   - Timeout after 30 seconds

**Notification Templates**:
```sql
-- Notification templates table
CREATE TABLE notification_templates (
    template_id SERIAL PRIMARY KEY,
    notification_type VARCHAR(50) NOT NULL UNIQUE,
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('email', 'slack', 'sms', 'webhook')),
    subject_template TEXT,
    body_template TEXT,
    priority VARCHAR(20) DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'critical')),
    enabled BOOLEAN DEFAULT true
);

INSERT INTO notification_templates VALUES
(1, 'sla_breach', 'email', 'SLA Breach Alert: Task #{{task_id}}', 'Task {{task_id}} has breached SLA for {{sla_type}}. Current age: {{age_minutes}} minutes.', 'high', true),
(2, 'sla_breach', 'slack', 'SLA Breach Alert', '*SLA Breach*: Task #{{task_id}} - {{sla_type}} breached ({{age_minutes}} minutes)', 'high', true),
(3, 'document_review_required', 'email', 'Document Review Required', 'Document {{document_uuid}} requires review. Confidence: {{confidence}}', 'normal', true);
```

### Manual Intervention Procedures

**Escalation Tiers**:

**Tier 1: Automated Retry** (0-5 minutes)
- System automatically retries failed operations
- Exponential backoff applied
- No human intervention required

**Tier 2: DLQ Processing** (5-30 minutes)
- Scheduled workflow processes DLQ items
- Automatic retry with updated context
- Ops team notified if DLQ depth >100

**Tier 3: Manual Review** (30 minutes - 4 hours)
- Ops team reviews DLQ items
- Investigates root cause
- Applies manual fixes or configuration updates
- Updates DLQ item status to 'resolved'

**Tier 4: Escalation to Engineering** (4+ hours)
- If Tier 3 cannot resolve
- Engineering team investigates code bugs
- Hotfix deployment if needed
- Root cause analysis document created

**Manual Intervention SOP**:

1. **Access DLQ Dashboard**:
   - Navigate to `/admin/dlq` (authenticated)
   - Filter by client, pack_name, operation_type, status
   - Sort by created_at (newest first)

2. **Analyze Failed Item**:
   - Review payload and error message
   - Check stack trace for clues
   - Verify configuration in database
   - Test external API connectivity

3. **Determine Resolution Strategy**:
   - **Retry**: If transient error (rate limit, timeout) → Click "Retry"
   - **Fix Payload**: If data issue → Edit payload → Click "Retry with Changes"
   - **Update Config**: If configuration issue → Update `client_config` → Click "Retry"
   - **Skip**: If not critical → Click "Skip" with reason
   - **Manual Action**: If requires human work → Click "Mark for Manual Processing"

4. **Execute Resolution**:
   - Apply chosen resolution strategy
   - Monitor result (success/failure)
   - Add notes to DLQ item for audit trail

5. **Post-Incident Review**:
   - Identify root cause
   - Update configuration to prevent recurrence
   - Improve error handling if needed
   - Document lessons learned

**Common Issues and Solutions**:

| Issue | Likely Cause | Resolution |
|-------|--------------|------------|
| API rate limit exceeded | High volume, missing rate limit handling | Increase rate limit, implement throttling |
| Invalid API credentials | Credentials expired or revoked | Update credentials in `client_integrations` |
| Database connection failed | Database down, network issue | Restart PostgreSQL, check network connectivity |
| Validation failed | Invalid data format | Update field mappings in `client_config` |
| External service down | Third-party outage | Check status page, implement fallback |
| Workflow timeout | Long-running operation | Increase timeout, make operation async |

---

## 8. IMPLEMENTATION PLAN

### Day 1: Environment Setup & Infrastructure
**Focus Area**: Set up development and production environments
**Tasks**:
1. Provision VPS (DigitalOcean, AWS, or similar) - 4GB RAM, 2 CPU cores minimum
2. Install dependencies: PostgreSQL 15, Node.js 20, Docker (for S3/MinIO)
3. Configure PostgreSQL:
   - Create database `automation_platform`
   - Enable pgcrypto extension
   - Create application user with least privileges
4. Install n8n:
   - Self-hosted installation via npm or Docker
   - Configure environment variables (encryption key, database connection)
   - Set up SSL certificate (Let's Encrypt)
5. Install MinIO for file storage:
   - Create buckets for documents and reports
   - Configure access keys
6. Set up reverse proxy (Nginx) for SSL termination
7. Configure backup strategy (pg_dump for database, rsync for files)
8. Set up monitoring stack (Prometheus, Grafana, Loki) - optional for v1, can use simple logging first

**Dependencies**: None
**Estimated Hours**: 8 hours
**Validation Checkpoints**:
- PostgreSQL accepts connections and can run queries
- n8n web interface accessible via HTTPS
- MinIO can upload/download files
- Backup script runs successfully
- Health check endpoint returns 200

### Day 2: Database Schema Implementation
**Focus Area**: Create all database tables and indexes
**Tasks**:
1. Create core configuration tables (clients, client_packs, client_config, client_integrations, client_workflows)
2. Create INTAKE_v1 pack tables (leads, lead_enrichment, lead_routing)
3. Create DOCS_v1 pack tables (documents, document_extractions, document_routing)
4. Create TASKS_v1 pack tables (tasks, team_members, task_assignments, sla_events, reports)
5. Create audit and monitoring tables (workflow_executions, config_audit_log, dead_letter_queue, notifications)
6. Create all indexes for performance
7. Set up foreign key constraints and check constraints
8. Create audit triggers for automatic logging
9. Insert sample data for testing
10. Test database with sample queries

**Dependencies**: Day 1 complete
**Estimated Hours**: 6 hours
**Validation Checkpoints**:
- All tables created without errors
- Foreign key constraints enforced (test with invalid data)
- Indexes created and used by query planner (EXPLAIN ANALYZE)
- Audit triggers populate audit_log on INSERT/UPDATE/DELETE
- Sample data queries return expected results

### Day 3: INTAKE_v1 Pack Development
**Focus Area**: Build all INTAKE_v1 workflows
**Tasks**:
1. Create INTAKE_v1_Capture_Leads workflow:
   - Set up webhook trigger for web forms
   - Set up email trigger (IMAP/POP3 polling)
   - Set up API webhook trigger
   - Implement client identification logic
   - Implement idempotency check
   - Write to database
   - Return response
2. Create INTAKE_v1_Normalize_Data workflow:
   - Read configuration from database
   - Apply field transformations
   - Calculate initial lead score
   - Update lead record
3. Create INTAKE_v1_Enrich_Leads workflow:
   - Set up parallel branches for email validation and company lookup
   - Integrate NeverBounce API
   - Integrate Clearbit API
   - Implement duplicate detection (fuzzy matching)
   - Aggregate results
   - Update lead record
4. Create INTAKE_v1_Route_Leads workflow:
   - Read routing rules from configuration
   - Implement rule evaluation logic
   - Integrate with HubSpot/Salesforce (placeholder for v1)
   - Handle API responses
   - Update routing status
5. Create INTAKE_v1_DLQ_Processor workflow (scheduled):
   - Query dead_letter_queue
   - Retry failed operations
   - Update status
6. Test all workflows with sample data
7. Configure sample client with test settings

**Dependencies**: Day 2 complete
**Estimated Hours**: 10 hours
**Validation Checkpoints**:
- Webhook receives data and returns 200
- Lead appears in database with correct data
- Enrichment completes and updates lead record
- Routing succeeds (or logs to DLQ for review)
- DLQ processor retries failed items
- Idempotency verified (duplicate lead rejected)

### Day 4: DOCS_v1 Pack Development
**Focus Area**: Build all DOCS_v1 workflows
**Tasks**:
1. Create DOCS_v1_Intake_Docs workflow:
   - Set up email attachment monitoring
   - Set up file upload webhook
   - Implement file download and hash generation
   - Upload to MinIO
   - Write to database
2. Install and configure Tesseract OCR:
   - Install Tesseract on server
   - Test OCR with sample documents
3. Create DOCS_v1_Classify_Docs workflow:
   - Extract text using OCR
   - Integrate OpenAI API for classification
   - Parse classification response
   - Apply confidence threshold
   - Update document status
4. Create DOCS_v1_Extract_Data workflow:
   - Read extraction schema from configuration
   - Call LLM with extraction prompt
   - Parse extraction response
   - Write to document_extractions table
5. Create DOCS_v1_Validate_Data workflow:
   - Read validation rules
   - Check required fields
   - Validate field formats
   - Update extraction status
6. Create DOCS_v1_Route_Docs workflow:
   - Read routing configuration
   - Format payload for destination
   - Send to destination (placeholder for v1)
   - Update routing status
7. Create DOCS_v1_Human_Review_Queue workflow (scheduled):
   - Query review queue
   - Assign reviewers
   - Send notifications
8. Test all workflows with sample documents
9. Configure sample client with document type definitions

**Dependencies**: Day 3 complete
**Estimated Hours**: 12 hours
**Validation Checkpoints**:
- Document uploaded via webhook appears in database
- OCR extracts text successfully
- LLM classifies document with confidence score
- Extraction extracts structured data correctly
- Validation identifies missing/invalid fields
- Routing succeeds (or marks for review)
- Review queue assigns documents to team members

### Day 5: TASKS_v1 Pack Development
**Focus Area**: Build all TASKS_v1 workflows
**Tasks**:
1. Create TASKS_v1_Create_Tasks workflow:
   - Set up webhook triggers from INTAKE and DOCS packs
   - Parse task data
   - Calculate urgency score
   - Insert into database
2. Create TASKS_v1_Assign_Tasks workflow:
   - Query unassigned tasks
   - Read assignment strategy from configuration
   - Implement round-robin assignment
   - Implement skill-based assignment
   - Implement workload-balanced assignment
   - Send notifications to assignees
3. Create TASKS_v1_Monitor_SLA workflow (scheduled):
   - Read SLA configuration
   - Query active tasks
   - Calculate elapsed time
   - Check SLA thresholds
   - Create SLA events for breaches
   - Send notifications
4. Create TASKS_v1_Generate_Reports workflow (scheduled):
   - Read report configuration
   - Query tasks and SLA events
   - Calculate metrics
   - Generate HTML report
   - Convert to PDF (using wkhtmltopdf)
   - Send report to recipients
5. Create simple task dashboard (read-only):
   - HTML page querying database
   - Filter by client, status, priority
   - Display task list with SLA status
6. Test all workflows with sample tasks
7. Configure sample client with team members and SLA rules

**Dependencies**: Day 4 complete
**Estimated Hours**: 10 hours
**Validation Checkpoints**:
- Task created from webhook appears in database
- Assignment workflow assigns task to team member
- SLA monitoring detects breaches and sends notifications
- Report generation completes and sends email
- Dashboard displays tasks correctly

### Day 6: Security & Configuration System
**Focus Area**: Implement security, access control, and configuration management
**Tasks**:
1. Implement secrets management:
   - Set up environment variables for infrastructure secrets
   - Create database encryption key
   - Implement pgcrypto encryption for client credentials
2. Set up Row-Level Security (RLS):
   - Enable RLS on sensitive tables
   - Create policies for different roles
   - Test RLS with different user contexts
3. Implement API key authentication:
   - Create api_keys table
   - Generate API keys for test clients
   - Implement authentication middleware in n8n workflows
4. Set up notification system:
   - Configure SMTP for email notifications
   - Configure Slack webhook for ops alerts
   - Create notification templates
5. Implement configuration management UI (simple):
   - HTML page to view/edit client configuration
   - Form to add/edit clients
   - Form to enable/disable packs
   - Form to configure integration credentials
6. Test security features:
   - Test RLS prevents unauthorized access
   - Test API key authentication
   - Test credential encryption/decryption
   - Test notifications

**Dependencies**: Day 5 complete
**Estimated Hours**: 8 hours
**Validation Checkpoints**:
- API key authentication works correctly
- RLS prevents cross-client data access
- Credentials encrypted in database
- Notifications sent successfully
- Configuration UI saves and retrieves settings

### Day 7: Monitoring, Error Handling, & DLQ
**Focus Area**: Implement monitoring, logging, and error handling
**Tasks**:
1. Set up centralized logging:
   - Configure n8n to write logs to files
   - Set up log rotation
   - (Optional) Install Loki for log aggregation
2. Implement health check endpoints:
   - Create simple HTTP server for health checks
   - Implement /health endpoint
   - Implement /ready endpoint
   - Implement /live endpoint
3. Implement dead-letter queue processing:
   - Create DLQ workflow (scheduled)
   - Implement retry logic with exponential backoff
   - Implement max retry limits
   - Implement escalation to failed status
4. Set up monitoring dashboards:
   - Install Prometheus (if using)
   - Configure metrics collection
   - Create Grafana dashboards
   - Set up alerting rules
5. Implement alert notifications:
   - Configure Slack alerts for critical issues
   - Configure email alerts for warnings
   - Test alert scenarios
6. Create DLQ dashboard (simple):
   - HTML page to view DLQ items
   - Buttons to retry, skip, or mark resolved
   - Filter and search functionality
7. Test error handling:
   - Test retry logic with failed API calls
   - Test DLQ processing
   - Test alert notifications
   - Test fallback mechanisms

**Dependencies**: Day 6 complete
**Estimated Hours**: 8 hours
**Validation Checkpoints**:
- Health checks return correct status
- Logs written and rotated correctly
- DLQ items processed and retried
- Alerts triggered and sent correctly
- DLQ dashboard displays and manages items

### Day 8: Integration Testing & Validation
**Focus Area**: End-to-end testing of all systems
**Tasks**:
1. Create test data set:
   - Sample leads (valid, duplicate, invalid)
   - Sample documents (invoice, contract, ID)
   - Sample tasks (various priorities and types)
2. Test INTAKE_v1 pack end-to-end:
   - Submit lead via webhook
   - Verify normalization and enrichment
   - Verify routing to destination
   - Test error scenarios (invalid data, API failures)
3. Test DOCS_v1 pack end-to-end:
   - Upload document via webhook
   - Verify classification and extraction
   - Verify validation and routing
   - Test human review queue
   - Test error scenarios (low confidence, OCR failures)
4. Test TASKS_v1 pack end-to-end:
   - Create tasks from various sources
   - Verify assignment logic
   - Verify SLA monitoring
   - Verify report generation
5. Test pack interactions:
   - Lead creates follow-up task
   - Document review task created
   - SLA breach notifications
6. Test security:
   - Test API key authentication
   - Test RLS prevents unauthorized access
   - Test credential encryption
7. Load testing:
   - Process 100 leads in batch
   - Process 50 documents in batch
   - Create 100 tasks
   - Monitor performance metrics
8. Document any issues and fixes

**Dependencies**: Day 7 complete
**Estimated Hours**: 10 hours
**Validation Checkpoints**:
- All workflows complete successfully
- Error scenarios handled correctly
- Pack interactions work as expected
- Security controls effective
- System handles expected load

### Day 9: Documentation & Operations Setup
**Focus Area**: Create documentation and operational procedures
**Tasks**:
1. Create system documentation:
   - Architecture overview
   - Data model documentation
   - Workflow inventory
   - API documentation (if exposing public API)
2. Create operations documentation:
   - Deployment checklist
   - Configuration guide
   - Troubleshooting guide
   - Runbook for common issues
3. Create SOPs:
   - Onboarding new client
   - Enabling/disabling packs
   - Configuring integrations
   - Managing DLQ items
   - Backup and restore procedures
4. Create monitoring setup guide:
   - How to set up monitoring
   - How to configure alerts
   - How to interpret dashboards
5. Create training materials:
   - How to use configuration UI
   - How to troubleshoot issues
   - How to escalate problems
6. Review and validate all documentation
7. Set up documentation site (simple HTML or wiki)

**Dependencies**: Day 8 complete
**Estimated Hours**: 6 hours
**Validation Checkpoints**:
- All documentation complete and accurate
- SOPs tested and validated
- Team members understand procedures
- Documentation accessible and searchable

### Day 10: Final Testing, Deployment & Handoff
**Focus Area**: Production deployment and handoff to operations team
**Tasks**:
1. Final integration testing:
   - Run full test suite
   - Verify all features working
   - Fix any remaining issues
2. Prepare production environment:
   - Provision production VPS
   - Configure all services (PostgreSQL, n8n, MinIO, Nginx)
   - Set up SSL certificates
   - Configure backups
3. Deploy to production:
   - Run database migrations
   - Deploy n8n workflows
   - Configure production clients
   - Test production deployment
4. Set up production monitoring:
   - Configure monitoring dashboards
   - Set up alerting
   - Test health checks
5. Handoff to operations team:
   - Walk through all systems
   - Train on monitoring and troubleshooting
   - Provide documentation access
   - Establish escalation procedures
6. Post-deployment validation:
   - Monitor system for 24 hours
   - Process live test data
   - Verify all functionality
7. Create final summary document:
   - What was built
   - Known limitations
   - Next steps for v1.1

**Dependencies**: Day 9 complete
**Estimated Hours**: 8 hours
**Validation Checkpoints**:
- Production deployment successful
- All monitoring working
- Team trained and ready
- System stable for 24 hours

### Total Estimated Timeline: 10 Days (80 hours)

**Critical Path**:
Day 1 → Day 2 → Day 3 → Day 4 → Day 5 → Day 6 → Day 7 → Day 8 → Day 9 → Day 10

**Parallel Opportunities** (if team size >1):
- Documentation can be written in parallel with development
- Monitoring setup can start before Day 7
- Test data creation can happen during development

---

## 9. TEST PLAN

### Unit Tests

**Database Functions and Triggers**:
- Test audit triggers populate audit_log on INSERT/UPDATE/DELETE
- Test RLS policies prevent unauthorized access
- Test check constraints validate data
- Test foreign key constraints enforce referential integrity
- Test unique constraints prevent duplicates

**n8n Workflow Components**:
- Test idempotency check functions
- Test field normalization logic (phone, email, name formatting)
- Test lead score calculation
- Test rule evaluation logic (IF/THEN conditions)
- Test confidence threshold comparison
- Test validation rule application
- Test SLA breach detection
- Test retry delay calculation with exponential backoff

**Utility Functions**:
- Test file hash generation (SHA-256)
- Test encryption/decryption with pgcrypto
- Test API key hashing and verification
- Test timestamp parsing and timezone conversion
- Test fuzzy matching for duplicate detection

**Test Tools**:
- PostgreSQL unit tests using pgTAP or plpgsql
- n8n workflow testing using manual execution with test data
- JavaScript function tests using n8n function node testing

**Success Criteria**:
- All unit tests pass with >95% code coverage
- No critical bugs found

### Integration Tests

**End-to-End Scenarios**:

**Test 1: Lead Processing Pipeline**
- Input: Submit lead via webhook with valid data
- Expected Flow: Capture → Normalize → Enrich → Route
- Validation:
  - Lead appears in database with normalized data
  - Enrichment records created for email validation and company lookup
  - Lead score updated based on enrichment results
  - Routing record created with destination response
  - Lead status = 'routed'
  - Workflow execution logged with status='completed'
- Test Data:
  ```json
  {
    "email": "test@example.com",
    "name": "John Doe",
    "company": "Acme Corp",
    "source": "web_form"
  }
  ```

**Test 2: Duplicate Lead Detection**
- Input: Submit lead with email that already exists
- Expected Flow: Capture → Idempotency Check → Skip
- Validation:
  - No new lead created
  - Existing lead unchanged
  - Workflow returns 200 with message about duplicate
  - Idempotency key logged

**Test 3: Document Processing Pipeline**
- Input: Upload invoice document via webhook
- Expected Flow: Intake → Classify → Extract → Validate → Route
- Validation:
  - Document stored in MinIO with correct path
  - Document record created with file_hash
  - Classification result: document_type='invoice', confidence > 0.9
  - Extraction record created with structured data
  - Validation passes (all required fields present)
  - Routing record created with destination response
  - Document status = 'completed'

**Test 4: Low Confidence Document Routing**
- Input: Upload document with unclear type
- Expected Flow: Intake → Classify (low confidence) → Review Queue
- Validation:
  - Document classified with confidence < 0.8
  - Document status = 'review_required'
  - Review queue assigns document to team member
  - Notification sent to reviewer
  - No extraction or routing attempted

**Test 5: Task Assignment and SLA Monitoring**
- Input: Create task with high priority
- Expected Flow: Create → Assign → Monitor SLA
- Validation:
  - Task created with status='created'
  - Assignment workflow assigns to team member
  - Task status = 'assigned', assigned_at populated
  - Assignment record created
  - Notification sent to assignee
  - SLA monitoring calculates elapsed time
  - No SLA breach created (within threshold)

**Test 6: SLA Breach Detection**
- Input: Create task, wait past SLA threshold
- Expected Flow: Create → Monitor SLA (breach detected)
- Validation:
  - Task remains unassigned past SLA threshold
  - SLA event created with escalated=true
  - Escalation notification sent to manager
  - Task status updated (if configured)

**Test 7: Error Handling and Retry**
- Input: Submit lead, mock API failure
- Expected Flow: Capture → Enrich (API failure) → DLQ → Retry
- Validation:
  - Initial enrichment attempt fails
  - Error logged to dead_letter_queue
  - Retry count = 1, next_retry_at calculated
  - Scheduled DLQ processor retries operation
  - On success: status='resolved', enrichment completes
  - On final failure: status='failed', ops team notified

**Test 8: Configuration Change Impact**
- Input: Update client configuration (enable new input channel)
- Expected Flow: Configuration change → Workflow reads new config → New channel active
- Validation:
  - Configuration updated in database
  - Audit log records change
  - Next workflow execution uses new configuration
  - New input channel accepts data

**Test 9: Cross-Pack Integration**
- Input: Submit lead → triggers follow-up task
- Expected Flow: Lead processed → Task created → Task assigned
- Validation:
  - Lead routing completes
  - Follow-up task created with source_reference_id = lead_uuid
  - Task assigned to sales team member
  - Link between lead and task established

**Test 10: Report Generation**
- Input: Schedule report generation (daily/weekly)
- Expected Flow: Query data → Calculate metrics → Generate report → Send
- Validation:
  - Report record created with status='generating'
  - Metrics calculated correctly
  - HTML report generated
  - PDF report created (if configured)
  - Report sent to recipients
  - Report status = 'completed', file_path populated

**Test Data Requirements**:
- 5 sample leads (valid, duplicate, invalid, high score, low score)
- 5 sample documents (invoice, contract, ID, receipt, unclear)
- 3 sample team members with different skills
- Various task types and priorities
- Test client with multiple integration credentials

**Success Criteria**:
- All integration tests pass
- End-to-end workflows complete without manual intervention
- Error scenarios handled correctly
- Cross-pack integration working

### Performance Benchmarks

**Load Testing Scenarios**:

**Test 1: High Volume Lead Ingestion**
- Input: Submit 100 leads simultaneously via webhook
- Expected Results:
  - All leads processed within 60 seconds
  - Zero data loss
  - Error rate <1%
  - Database queries complete within 100ms (p95)
  - n8n workflow execution time <2 seconds (p95)

**Test 2: Document Processing Throughput**
- Input: Process 50 documents (mix of types and sizes)
- Expected Results:
  - All documents processed within 10 minutes
  - OCR accuracy >95%
  - LLM classification accuracy >90%
  - Extraction accuracy >85%
  - Memory usage stable (no leaks)

**Test 3: Task Assignment Performance**
- Input: Create 200 tasks simultaneously
- Expected Results:
  - All tasks created within 30 seconds
  - All tasks assigned within 2 minutes
  - Assignment load balanced across team members
  - SLA monitoring completes within 5 minutes

**Test 4: Database Query Performance**
- Input: Run common queries with 10,000 records
- Queries to test:
  - SELECT leads WHERE client_id = 1 AND status = 'new' (should use index)
  - SELECT tasks WHERE assigned_to = 5 AND status = 'in_progress' (should use index)
  - SELECT workflow_executions WHERE started_at > NOW() - INTERVAL '1 day' (should use index)
- Expected Results:
  - All queries complete within 50ms (p95)
  - Query plans show index usage (EXPLAIN ANALYZE)

**Test 5: Concurrent User Access**
- Input: 10 users accessing system simultaneously (configuration UI, dashboards)
- Expected Results:
  - All page loads complete within 2 seconds
  - No database connection errors
  - No authentication failures
  - RLS policies enforced correctly

**Success Criteria**:
- System meets all performance benchmarks
- No memory leaks or resource exhaustion
- Database indexes utilized correctly
- System scales linearly with load

---

## 10. OPERATIONS HANDOFF

### Standard Operating Procedures (SOPs)

**SOP 1: Onboarding a New Client**
**Purpose**: Add new client to system and configure automation packs
**Prerequisites**: Client billing account created in QuickBooks or Square
**Steps**:
1. **Create Client Record**:
   - INSERT into `clients` table with name, slug, status='active', billing_provider
   - Generate client_uuid (auto-generated)
   - Record billing_customer_id from QuickBooks/Square
2. **Enable Automation Packs**:
   - INSERT into `client_packs` for each pack to enable (INTAKE_v1, DOCS_v1, TASKS_v1)
   - Set enabled=true, enabled_at=NOW(), enabled_by=current_user
3. **Configure Integration Credentials**:
   - INSERT into `client_integrations` for each required service
   - Encrypt credentials using pgcrypto before storing
   - Test credentials by calling external APIs
4. **Set Up Default Configuration**:
   - INSERT into `client_config` with default settings
   - Customize based on client requirements
5. **Add Team Members**:
   - INSERT into `team_members` table
   - Define skills, working hours, max_concurrent_tasks
6. **Test Client Setup**:
   - Submit test lead via webhook
   - Upload test document
   - Create test task
   - Verify all workflows execute successfully
7. **Notify Client**:
   - Send onboarding email with API documentation
   - Provide webhook URLs and authentication details
   - Schedule training session if needed
8. **Document Client Setup**:
   - Record configuration choices
   - Note any custom requirements
   - Store in client documentation folder

**Time Estimate**: 2-3 hours per client
**Success Criteria**: Client can submit leads and documents via webhooks successfully

---

**SOP 2: Enabling/Disabling Automation Packs**
**Purpose**: Enable or disable packs for a client without affecting other packs
**Steps**:
1. **Backup Current Configuration**:
   - Export current `client_config` for the pack
   - Export `client_packs` settings
2. **Update Pack Status**:
   - UPDATE `client_packs` SET enabled=false (or true) WHERE client_id=X AND pack_name='PACK_v1'
   - Set enabled_at=NOW() if enabling
3. **Update Workflow Status**:
   - UPDATE `client_workflows` SET enabled=false (or true) WHERE client_id=X AND pack_name='PACK_v1'
4. **Test Status Change**:
   - Trigger workflow for the pack
   - Verify it is skipped (if disabled) or executes (if enabled)
5. **Notify Client**:
   - Send notification about pack status change
   - Explain any impact on operations
6. **Document Change**:
   - Record reason for change
   - Note effective date/time

**Time Estimate**: 30 minutes
**Success Criteria**: Pack status updated, workflows behave as expected

---

**SOP 3: Configuring Integration Credentials**
**Purpose**: Add or update external service credentials for a client
**Steps**:
1. **Obtain Credentials**:
   - Request API keys or OAuth tokens from client
   - Verify credentials are valid and have required permissions
2. **Encrypt Credentials**:
   - Use pgcrypto to encrypt credentials: `pgp_sym_encrypt(credential_json, encryption_key)`
   - Store encrypted credentials in `client_integrations` table
3. **Test Credentials**:
   - Make test API call to external service
   - Verify authentication succeeds
   - Check rate limits and permissions
4. **Update Integration Record**:
   - INSERT or UPDATE `client_integrations` table
   - Set last_verified_at=NOW()
5. **Document Credential Details**:
   - Note service version and API endpoints
   - Record any rate limits or special requirements
   - Store in secure location (encrypted notes)

**Time Estimate**: 30 minutes per integration
**Success Criteria**: API calls to service succeed with credentials

---

**SOP 4: Managing Dead-Letter Queue Items**
**Purpose**: Monitor and resolve failed operations in DLQ
**Steps**:
1. **Access DLQ Dashboard**:
   - Navigate to `/admin/dlq`
   - Filter by status='pending' or 'retrying'
   - Sort by created_at (newest first)
2. **Analyze Failed Item**:
   - Review payload and error message
   - Check error_code for clues
   - Verify configuration in database
   - Test external API connectivity
3. **Choose Resolution Strategy**:
   - **Retry**: If transient error → Click "Retry Now"
   - **Edit Payload**: If data issue → Edit JSON → Click "Retry with Changes"
   - **Update Config**: If configuration issue → Update `client_config` → Click "Retry"
   - **Skip**: If not critical → Click "Skip" with reason and notes
   - **Manual**: If requires human work → Click "Mark for Manual Processing"
4. **Execute Resolution**:
   - Apply chosen action
   - Monitor result in DLQ
   - Verify operation completed successfully
5. **Investigate Root Cause** (if multiple failures):
   - Check if configuration issue affects other clients
   - Check if external service is down
   - Check if rate limit exceeded
   - Update configuration or code to prevent recurrence
6. **Document Resolution**:
   - Add notes to DLQ item
   - Update knowledge base with lessons learned

**Time Estimate**: 5-15 minutes per item
**Success Criteria**: Failed operation resolved, DLQ item marked as resolved

---

**SOP 5: Backup and Restore Procedures**
**Purpose**: Backup data and restore in case of failure
**Steps**:
**Daily Backup** (automated):
1. **Database Backup**:
   - Run `pg_dump -Fc automation_platform > backup_YYYYMMDD.dump`
   - Upload to cloud storage (S3, Backblaze)
   - Retain for 30 days
2. **File Backup**:
   - Sync MinIO buckets to backup location using `rsync`
   - Retain for 30 days
3. **Configuration Backup**:
   - Export `client_config`, `client_integrations`, `client_packs` tables
   - Store as JSON files in backup location
4. **Verify Backups**:
   - Check backup file sizes
   - Verify backup completion in logs
   - Test restore of backup to staging environment weekly

**Restore Procedure**:
1. **Stop Services**:
   - Stop n8n: `systemctl stop n8n`
   - Stop web server: `systemctl stop nginx`
2. **Restore Database**:
   - Drop existing database: `DROP DATABASE automation_platform`
   - Create new database: `CREATE DATABASE automation_platform`
   - Restore from backup: `pg_restore -d automation_platform backup_YYYYMMDD.dump`
3. **Restore Files**:
   - Sync files from backup to MinIO buckets
   - Verify file integrity
4. **Start Services**:
   - Start PostgreSQL: `systemctl start postgresql`
   - Start n8n: `systemctl start n8n`
   - Start web server: `systemctl start nginx`
5. **Verify Restore**:
   - Check database connectivity
   - Verify data integrity (row counts)
   - Test workflow execution
   - Check monitoring dashboards

**Time Estimate**: 30 minutes (backup), 1 hour (restore)
**Success Criteria**: Backup completes successfully, restore verified in staging

---

### Runbook for Common Issues

**Issue 1: n8n Workflow Not Triggering**
**Symptoms**: Webhook returns 200 but workflow doesn't execute, or workflow times out
**Possible Causes**:
- n8n process not running
- Database connection failed
- Workflow disabled or misconfigured
- Rate limit exceeded
**Troubleshooting Steps**:
1. Check n8n process status: `systemctl status n8n`
2. Check n8n logs: `journalctl -u n8n -f`
3. Check database connection: `psql -c "SELECT 1"`
4. Check workflow status in `client_workflows` table
5. Check webhook URL is correct
6. Check rate limits in `client_integrations` table
7. Verify workflow is active and enabled in n8n UI
8. Test webhook with simple payload
**Resolution**:
- If n8n not running: Start service with `systemctl start n8n`
- If database connection failed: Restart PostgreSQL, check credentials
- If workflow disabled: Enable in `client_workflows` table
- If rate limit exceeded: Wait or increase limit

---

**Issue 2: Database Query Slow**
**Symptoms**: Workflow execution takes >10 seconds, database CPU high
**Possible Causes**:
- Missing indexes
- Large table scans
- Lock contention
- Connection pool exhaustion
**Troubleshooting Steps**:
1. Check slow query log in PostgreSQL
2. Run `EXPLAIN ANALYZE` on slow query
3. Check table sizes: `SELECT pg_size_pretty(pg_total_relation_size('table_name'))`
4. Check active connections: `SELECT count(*) FROM pg_stat_activity;`
5. Check for locks: `SELECT * FROM pg_locks;`
6. Check index usage: `SELECT * FROM pg_stat_user_indexes;`
**Resolution**:
- Add missing indexes based on EXPLAIN output
- VACUUM and ANALYZE tables
- Increase connection pool size in n8n
- Kill long-running queries if necessary

---

**Issue 3: External API Rate Limit Exceeded**
**Symptoms**: API calls fail with 429 status, enrichment/routing failures
**Possible Causes**:
- High volume of requests
- Rate limit not properly configured
- Concurrent requests exceeding limit
**Troubleshooting Steps**:
1. Check error messages in `dead_letter_queue` table
2. Check `client_integrations` table for rate_limit_per_minute setting
3. Check API provider documentation for rate limits
4. Check current request rate in logs
5. Verify retry logic is working correctly
**Resolution**:
- Reduce request rate or implement throttling
- Increase rate_limit_per_minute if API allows
- Use API key with higher rate limit
- Implement queueing for batch operations

---

**Issue 4: Document Classification Accuracy Low**
**Symptoms**: Documents misclassified or confidence scores <80%
**Possible Causes**:
- Poor quality documents
- OCR extraction errors
- LLM prompt not optimized
- Insufficient training examples
**Troubleshooting Steps**:
1. Review document samples in `documents` table with low confidence
2. Check OCR output for text quality
3. Test LLM classification manually with sample text
4. Review classification prompt in n8n workflow
5. Check document type definitions in `client_config`
**Resolution**:
- Improve OCR quality (adjust preprocessing, try different OCR engine)
- Refine LLM prompt with better examples
- Add more document type examples to prompt
- Lower confidence threshold temporarily
- Implement human review for low-confidence documents

---

**Issue 5: SLA Breaches Not Detected**
**Symptoms**: Tasks past SLA threshold but no notifications sent
**Possible Causes**:
- SLA monitoring workflow not running
- SLA configuration incorrect
- Timezone mismatch
- SLA events already created (duplicate check too strict)
**Troubleshooting Steps**:
1. Check `sla_events` table for recent events
2. Check SLA monitoring workflow execution logs
3. Check `client_config` for SLA thresholds
4. Verify timezone settings in `clients` table
5. Check task timestamps (created_at, assigned_at)
6. Check SLA monitoring workflow schedule
**Resolution**:
- Restart SLA monitoring workflow
- Update SLA thresholds in `client_config`
- Fix timezone configuration
- Adjust duplicate check logic
- Manually trigger SLA monitoring for testing

---

**Issue 6: High Memory Usage**
**Symptoms**: Server swap usage high, OOM errors, processes killed
**Possible Causes**:
- Memory leak in n8n or Node.js
- Large document processing in memory
- Too many concurrent workflows
- PostgreSQL work_mem too high
**Troubleshooting Steps**:
1. Check memory usage: `free -h`, `top`
2. Check n8n process memory: `ps aux | grep n8n`
3. Check PostgreSQL memory settings in `postgresql.conf`
4. Check workflow execution logs for memory spikes
5. Check document sizes being processed
6. Check number of concurrent workflow executions
**Resolution**:
- Restart n8n service to free memory
- Reduce work_mem in PostgreSQL
- Implement streaming for large document processing
- Limit concurrent workflow executions in n8n settings
- Add swap space if needed
- Upgrade server memory if consistently high

---

### Deployment Checklist

**Pre-Flight Checklist**:
- [ ] Backup production database (pg_dump)
- [ ] Backup MinIO buckets
- [ ] Export current configuration (client_config, client_integrations)
- [ ] Verify all tests passing in staging environment
- [ ] Review and approve deployment plan
- [ ] Notify team of deployment window
- [ ] Prepare rollback plan

**Deployment Steps**:
1. **Stop Services**:
   - [ ] Stop n8n: `systemctl stop n8n`
   - [ ] Stop web server: `systemctl stop nginx`
2. **Database Migrations**:
   - [ ] Run migration scripts in test environment first
   - [ ] Run migration scripts in production
   - [ ] Verify schema changes
   - [ ] Update `client_config` with new settings if needed
3. **Deploy Workflows**:
   - [ ] Export workflows from staging
   - [ ] Import workflows to production n8n
   - [ ] Verify workflow versions
   - [ ] Enable workflows in `client_workflows` table
4. **Update Configuration**:
   - [ ] Update environment variables if needed
   - [ ] Restart PostgreSQL: `systemctl restart postgresql`
   - [ ] Update n8n configuration if needed
5. **Start Services**:
   - [ ] Start n8n: `systemctl start n8n`
   - [ ] Start web server: `systemctl start nginx`
6. **Post-Deployment Checks**:
   - [ ] Verify n8n is running: `systemctl status n8n`
   - [ ] Check n8n logs for errors: `journalctl -u n8n -n 100`
   - [ ] Check database connectivity
   - [ ] Test health check endpoint: `curl https://your-domain.com/health`
   - [ ] Test workflow execution with sample data
   - [ ] Verify monitoring dashboards
   - [ ] Check alert notifications

**Rollback Plan**:
1. Stop services (n8n, nginx)
2. Restore database from pre-deployment backup
3. Restore previous workflow versions in n8n
4. Restore previous configuration
5. Start services
6. Verify system is operational

**Success Criteria**:
- All services running without errors
- Health check returns "healthy" status
- Workflows execute successfully
- Monitoring shows normal metrics
- No critical alerts triggered

---

### Training Requirements

**Role-Based Training**:

**For Operations Team**:
- **Duration**: 4 hours
- **Topics**:
  - System architecture overview (1 hour)
  - Configuration management (1 hour)
  - Monitoring and alerting (1 hour)
  - Troubleshooting common issues (1 hour)
- **Materials**:
  - System documentation
  - SOPs for routine tasks
  - Troubleshooting runbook
  - Monitoring dashboard guide

**For Client Support Team**:
- **Duration**: 2 hours
- **Topics**:
  - Client onboarding process (1 hour)
  - Client configuration management (1 hour)
- **Materials**:
  - Client onboarding checklist
  - Configuration guide
  - API documentation
  - Troubleshooting guide for client issues

**For Developers (Future Enhancements)**:
- **Duration**: 6 hours
- **Topics**:
  - Architecture deep dive (2 hours)
  - Database schema and relationships (1 hour)
  - Workflow development best practices (2 hours)
  - Security and access control (1 hour)
- **Materials**:
  - Complete architecture documentation
  - Data model documentation
  - Workflow inventory and design patterns
  - Security guidelines

**Training Delivery**:
- Live training sessions with hands-on exercises
- Recorded video sessions for reference
- Knowledge base articles for self-paced learning
- Regular refresher training (quarterly)

**Training Validation**:
- Quiz after training
- Hands-on exercise: Onboard test client
- Hands-on exercise: Troubleshoot simulated issue
- Sign-off on completion

---

### Documentation Links

**System Documentation**:
- Architecture Overview: `/docs/architecture.md`
- Data Models: `/docs/data_models.md`
- Workflow Inventory: `/docs/workflows.md`
- API Documentation: `/docs/api.md`

**Operations Documentation**:
- Deployment Guide: `/docs/operations/deployment.md`
- Configuration Guide: `/docs/operations/configuration.md`
- Troubleshooting Guide: `/docs/operations/troubleshooting.md`
- Backup and Restore: `/docs/operations/backup_restore.md`
- Security Guidelines: `/docs/operations/security.md`

**Standard Operating Procedures**:
- Client Onboarding: `/docs/sops/client_onboarding.md`
- Pack Management: `/docs/sops/pack_management.md`
- Integration Configuration: `/docs/sops/integrations.md`
- DLQ Management: `/docs/sops/dlq_management.md`
- Backup and Restore: `/docs/sops/backup_restore.md`

**Runbooks**:
- Common Issues: `/docs/runbooks/common_issues.md`
- Incident Response: `/docs/runbooks/incident_response.md`
- Emergency Procedures: `/docs/runbooks/emergency.md`

**Monitoring**:
- Monitoring Setup: `/docs/monitoring/setup.md`
- Dashboard Guide: `/docs/monitoring/dashboards.md`
- Alert Configuration: `/docs/monitoring/alerts.md`

---

## 11. ROADMAP

### v1.1 Enhancements (Quick Wins, 2-4 weeks)

**Enhancement 1: Advanced Lead Scoring**
**Description**: Implement machine learning-based lead scoring using historical conversion data
**Implementation**:
- Track lead conversion events (became customer, rejected, etc.)
- Train simple ML model (random forest) on historical data
- Integrate model into lead enrichment workflow
- Provide scoring insights in dashboard
**Benefits**: Improved lead prioritization, higher conversion rates
**Effort**: 1 week
**Dependencies**: Collect 6 months of historical conversion data

---

**Enhancement 2: Document Version Control**
**Description**: Track document versions and changes for audit trail
**Implementation**:
- Add `document_versions` table to track changes
- Implement document diff functionality
- Show version history in dashboard
- Allow rollback to previous versions
**Benefits**: Better audit trail, recover from mistakes
**Effort**: 3 days
**Dependencies**: None

---

**Enhancement 3: Webhook Subscriptions**
**Description**: Allow clients to subscribe to webhook notifications for events
**Implementation**:
- Create `webhook_subscriptions` table
- Implement webhook dispatcher workflow
- Retry failed webhooks with exponential backoff
- Provide webhook testing tool
**Benefits**: Real-time client notifications, flexibility
**Effort**: 4 days
**Dependencies**: None

---

**Enhancement 4: Bulk Operations UI**
**Description**: Simple web UI for bulk operations (mass retry, bulk assign, bulk update)
**Implementation**:
- Create HTML/JS interface for bulk operations
- Implement API endpoints for bulk actions
- Add progress tracking for bulk operations
- Provide export of operation results
**Benefits**: Faster operations, better productivity
**Effort**: 1 week
**Dependencies**: None

---

**Enhancement 5: Enhanced SLA Reporting**
**Description**: More detailed SLA reports with trends and insights
**Implementation**:
- Add SLA metrics tracking (breach rate, average time to assign, etc.)
- Implement SLA trend analysis (week over week, month over month)
- Create SLA comparison reports (by team member, by task type)
- Generate actionable insights and recommendations
**Benefits**: Better SLA management, identify improvement areas
**Effort**: 5 days
**Dependencies**: Collect SLA historical data

---

### v1.2 Improvements (Medium Complexity, 1-2 months)

**Improvement 1: Multi-Language Support**
**Description**: Support document classification and extraction for multiple languages
**Implementation**:
- Add language detection using LLM or dedicated service
- Update OCR configuration for multiple languages
- Translate LLM prompts for each language
- Store detected language in document metadata
- Configure language-specific extraction schemas
**Benefits**: Serve international clients, expand market
**Effort**: 2 weeks
**Dependencies**: None

---

**Improvement 2: Advanced Analytics Dashboard**
**Description**: Interactive dashboard with charts and metrics
**Implementation**:
- Integrate Grafana for advanced visualizations
- Create custom dashboards for:
  - Lead funnel analysis
  - Document processing metrics
  - Task performance analytics
  - SLA compliance trends
- Add drill-down capabilities
- Implement date range filtering
- Export dashboards as PDF reports
**Benefits**: Better insights, data-driven decisions
**Effort**: 3 weeks
**Dependencies**: Set up Grafana

---

**Improvement 3: Workflow Designer UI**
**Description**: Simple web UI for clients to design custom workflows
**Implementation**:
- Create visual workflow builder (drag-and-drop)
- Pre-built workflow templates (intake, processing, routing)
- Workflow validation and testing
- Version control for custom workflows
- Deploy custom workflows to n8n
**Benefits**: Client self-service, reduced support burden
**Effort**: 4 weeks
**Dependencies**: None

---

**Improvement 4: Intelligent Task Prioritization**
**Description**: Use machine learning to prioritize tasks based on historical data
**Implementation**:
- Track task completion times and outcomes
- Train ML model to predict task importance
- Integrate model into task creation workflow
- Provide priority recommendations
- Learn from feedback (override priority)
**Benefits**: Better task management, improved efficiency
**Effort**: 3 weeks
**Dependencies**: Collect task historical data

---

**Improvement 5: Integration Marketplace**
**Description**: Pre-built integrations for popular SaaS platforms
**Implementation**:
- Build integrations for: Salesforce, Pipedrive, Xero, QuickBooks, Slack, Microsoft Teams
- Create integration templates
- One-click integration setup
- Integration health monitoring
- Integration usage analytics
**Benefits**: Faster client onboarding, broader integration support
**Effort**: 6 weeks
**Dependencies**: None

---

### v2.0 Vision (Major Features, 3-6 months)

**Feature 1: AI-Powered Document Intelligence**
**Description**: Advanced AI for document understanding and extraction
**Implementation**:
- Fine-tune custom LLM models for document extraction
- Implement document layout understanding (tables, forms, signatures)
- Add document sentiment analysis
- Detect document anomalies and fraud indicators
- Provide extraction confidence heatmaps
- Support handwritten text recognition
**Benefits**: Higher accuracy, support complex documents
**Effort**: 8 weeks
**Dependencies**: Collect training data, access to fine-tuning infrastructure

---

**Feature 2: Predictive Analytics**
**Description**: Predict future outcomes and recommend actions
**Implementation**:
- Lead conversion prediction (probability scoring)
- Churn prediction for clients
- SLA breach prediction (proactive alerting)
- Resource demand forecasting
- Capacity planning recommendations
- Anomaly detection (unusual patterns)
**Benefits**: Proactive management, better planning
**Effort**: 10 weeks
**Dependencies**: Collect comprehensive historical data, ML infrastructure

---

**Feature 3: Multi-Tenant SaaS Platform**
**Description**: Transform into true multi-tenant SaaS with self-service
**Implementation**:
- Build client-facing web application (React/Vue)
- Implement self-service onboarding (sign up, configure, pay)
- Add subscription management (plans, usage-based billing)
- Implement client isolation at infrastructure level
- Add client marketplace (templates, integrations)
- Provide client portal for monitoring and configuration
**Benefits**: Scalability, self-service revenue model
**Effort**: 12 weeks
**Dependencies**: Web development team, billing integration

---

**Feature 4: Advanced Security & Compliance**
**Description**: Enterprise-grade security and compliance features
**Implementation**:
- Implement SSO (SAML, OAuth)
- Add MFA for all users
- Implement field-level encryption
- Add data masking for PII
- Implement compliance reporting (GDPR, SOC2, HIPAA)
- Add audit log analysis and anomaly detection
- Implement data loss prevention (DLP)
- Obtain SOC2 Type II certification
**Benefits**: Enterprise clients, compliance requirements
**Effort**: 8 weeks
**Dependencies**: Security audit, certification process

---

**Feature 5: Workflow Orchestration Engine**
**Description**: Custom workflow engine for complex orchestration
**Implementation**:
- Replace or augment n8n with custom engine
- Support complex branching and parallel execution
- Implement workflow state machine
- Add workflow simulation and testing
- Support workflow templates and versioning
- Provide workflow analytics and optimization
**Benefits**: More flexibility, better performance, custom features
**Effort**: 12 weeks
**Dependencies**: Development team

---

**Feature 6: Mobile App**
**Description**: Mobile application for task management and notifications
**Implementation**:
- Build native mobile apps (iOS/Android) or React Native
- Push notifications for tasks and SLAs
- Mobile task assignment and completion
- Mobile document review and approval
- Offline mode with sync
- Mobile analytics dashboard
**Benefits**: Mobility, real-time updates, better user experience
**Effort**: 10 weeks
**Dependencies**: Mobile development team

---

**v2.0 Success Criteria**:
- 500+ active clients
- 99.5% uptime
- Multi-tenant SaaS revenue model
- SOC2 Type II certified
- AI-powered features delivering measurable ROI
- Mobile app with 80% user adoption

---

## CONCLUSION

This comprehensive system design provides a production-ready foundation for your B2B automation business. The architecture prioritizes simplicity, reliability, and scalability while adhering to your constraints (no Stripe, configuration-only deployment, self-hosted or VPS deployment).

The three automation packs (INTAKE_v1, DOCS_v1, TASKS_v1) provide end-to-end automation for lead processing, document handling, and task management. The PostgreSQL-based configuration engine enables rapid client onboarding and configuration changes without code modifications.

The implementation plan provides a realistic 10-day timeline to deliver a working v1 system, with clear validation checkpoints and success criteria. The test plan ensures quality and performance, while the operations handoff provides the tools and knowledge needed to maintain and operate the system.

The roadmap outlines a clear path for future enhancements, from quick wins in v1.1 to major features in v2.0. The system is designed to evolve with your business needs while maintaining stability and reliability.

**Next Steps**:
1. Review and approve this architecture
2. Set up development environment (Day 1)
3. Begin implementation following the 10-day plan
4. Iterate and refine based on testing feedback
5. Deploy to production and onboard first clients

**Key Questions for Review**:
- Are the three automation packs aligned with your business goals?
- Is the 10-day implementation timeline realistic for your team?
- Do you have any concerns about the technology stack (n8n, PostgreSQL)?
- Are there any critical features missing from v1?
- Do you agree with the prioritization in the roadmap?

This design is flexible and can be adapted based on your feedback. The modular architecture allows for incremental improvements and easy expansion as your business grows.
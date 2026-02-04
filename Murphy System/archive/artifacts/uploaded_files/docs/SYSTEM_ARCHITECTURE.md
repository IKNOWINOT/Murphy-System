# System Architecture Documentation

## Executive Summary

The Client-Facing Automation Platform is a B2B SaaS solution that delivers repeatable automation workflows to SMBs. The system is built on a configuration-only deployment model, where all client customizations are stored in PostgreSQL rather than requiring custom code deployments.

**Key Characteristics:**
- **Multi-tenant:** Single deployment serves multiple clients
- **Configuration-driven:** No custom code per client
- **Workflow-based:** n8n orchestrates all automation logic
- **Self-hosted:** Deployed on VPS/dedicated servers
- **Scalable:** Designed for 10-100 concurrent clients

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Webhooks │  │   APIs   │  │  Email   │  │  Forms   │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
└───────┼─────────────┼─────────────┼─────────────┼──────────────┘
        │             │             │             │
        └─────────────┴─────────────┴─────────────┘
                      │
┌─────────────────────▼─────────────────────────────────────────┐
│                   WORKFLOW LAYER (n8n)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  INTAKE_v1   │  │   DOCS_v1    │  │  TASKS_v1    │       │
│  │  (5 flows)   │  │  (6 flows)   │  │  (4 flows)   │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                  │                  │                │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐       │
│  │ SECURITY_v1  │  │  MONITOR_v1  │  │   DLQ        │       │
│  │  (2 flows)   │  │  (3 flows)   │  │ Processing   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────┬─────────────────────────────────────────┘
                      │
┌─────────────────────▼─────────────────────────────────────────┐
│                   DATA LAYER (PostgreSQL)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Clients    │  │   Workflows  │  │  Monitoring  │       │
│  │   Config     │  │   Data       │  │  Audit       │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└───────────────────────────────────────────────────────────────┘
                      │
┌─────────────────────▼─────────────────────────────────────────┐
│                   STORAGE LAYER                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Documents   │  │    Logs      │  │   Backups    │       │
│  │  /storage    │  │  /logs       │  │  /backups    │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└───────────────────────────────────────────────────────────────┘
                      │
┌─────────────────────▼─────────────────────────────────────────┐
│                MONITORING & DASHBOARDS                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Metrics    │  │    Alerts    │  │  Dashboards  │       │
│  │   API        │  │  Management  │  │   (HTML)     │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└───────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Workflow Layer (n8n)

**Technology:** n8n v2.4.7 (self-hosted)  
**Database:** SQLite (workflow definitions)  
**Port:** 5678  
**Purpose:** Orchestrates all automation workflows

#### Workflow Packs

**INTAKE_v1 Pack (5 workflows)**
- `INTAKE_v1_Capture_Leads` - Webhook-based lead capture
- `INTAKE_v1_Normalize_Data` - Data cleaning and scoring
- `INTAKE_v1_Enrich_Leads` - Email validation and company lookup
- `INTAKE_v1_Route_Leads` - Score-based routing
- `INTAKE_v1_DLQ_Processor` - Failed operation retry

**DOCS_v1 Pack (6 workflows)**
- `DOCS_v1_Intake_Docs` - Document ingestion
- `DOCS_v1_Classify_Docs` - Category classification
- `DOCS_v1_Extract_Data` - Field extraction
- `DOCS_v1_Validate_Data` - Data validation
- `DOCS_v1_Route_Docs` - Category-based routing
- `DOCS_v1_Human_Review_Queue` - Review queue management

**TASKS_v1 Pack (4 workflows)**
- `TASKS_v1_Create_Tasks` - Task creation
- `TASKS_v1_Assign_Tasks` - Intelligent assignment
- `TASKS_v1_Monitor_SLA` - SLA tracking
- `TASKS_v1_Generate_Reports` - Statistics reporting

**SECURITY_v1 Pack (2 workflows)**
- `SECURITY_v1_Manage_Credentials` - Credential management
- `SECURITY_v1_Validate_Configuration` - Config validation

**MONITOR_v1 Pack (3 workflows)**
- `MONITOR_v1_Collect_Metrics` - System metrics collection
- `MONITOR_v1_Process_Errors` - Error logging
- `MONITOR_v1_Generate_Alerts` - Alert generation

---

### 2. Data Layer (PostgreSQL)

**Technology:** PostgreSQL 15.15  
**Port:** 5432  
**Database:** automation_platform  
**Tables:** 30 total

#### Table Categories

**Core Configuration (5 tables)**
- `clients` - Client master records
- `client_packs` - Enabled automation packs
- `client_config` - Key-value configuration
- `client_integrations` - External service credentials
- `client_workflows` - Workflow instances

**INTAKE_v1 Pack (3 tables)**
- `leads` - Lead records
- `lead_enrichment` - Enrichment results
- `lead_routing` - Routing decisions

**DOCS_v1 Pack (3 tables)**
- `documents` - Document metadata
- `document_extractions` - Extracted data
- `document_routing` - Routing decisions

**TASKS_v1 Pack (5 tables)**
- `tasks` - Task records
- `team_members` - Team member profiles
- `task_assignments` - Assignment history
- `sla_events` - SLA monitoring
- `reports` - Generated reports

**Security (5 tables)**
- `encryption_keys` - Master encryption keys
- `roles` - Role definitions
- `user_roles` - User-role assignments
- `security_events` - Security event log
- `audit_logs_enhanced` - Enhanced audit trail

**Monitoring (5 tables)**
- `metrics` - System metrics
- `errors` - Error tracking
- `alerts` - Alert management
- `performance_aggregates` - Performance stats
- `dependency_health` - Dependency monitoring

**Audit & System (4 tables)**
- `workflow_executions` - Execution logs
- `config_audit_log` - Configuration changes
- `dead_letter_queue` - Failed operations
- `notifications` - Notification tracking

---

### 3. Storage Layer

**Base Directory:** `/workspace/storage`

**Structure:**
```
/workspace/
├── storage/
│   ├── documents/     # Document storage
│   ├── reports/       # Generated reports
│   └── logs/          # Application logs
├── backups/           # Database backups
└── outputs/           # Workflow outputs
```

**Storage Policies:**
- Documents: 90-day retention
- Logs: 30-day retention
- Backups: 30-day retention
- Reports: 180-day retention

---

### 4. Monitoring & Dashboards

**Monitoring API Server**
- **Port:** 8082
- **Technology:** Flask + CORS
- **Endpoints:** 6 REST endpoints
- **Purpose:** Provides data for dashboards

**Dashboards (3 total)**
1. **Task Dashboard** (port 8080)
   - Real-time task statistics
   - Team performance metrics
   - Filterable task list

2. **Security Dashboard** (port 8080)
   - Credential management
   - Security events
   - Role management

3. **Monitoring Dashboard** (port 8083)
   - System metrics
   - Active alerts
   - Recent errors
   - Dependency health

**Health Check Server**
- **Port:** 8081
- **Endpoints:** `/health`, `/ready`, `/live`
- **Purpose:** System health monitoring

---

## Data Flow

### Lead Processing Flow

```
1. Lead Capture
   ↓
2. Normalization (email, name, phone)
   ↓
3. Scoring (0-30 points)
   ↓
4. Enrichment (email validation, company lookup)
   ↓
5. Duplicate Detection
   ↓
6. Routing (webhook, email, Slack)
   ↓
7. Destination System
```

### Document Processing Flow

```
1. Document Intake
   ↓
2. Classification (8 categories)
   ↓
3. Data Extraction (OCR, parsing)
   ↓
4. Validation (score 0-100)
   ↓
5. Routing Decision
   ├─ High Score → Auto-route
   └─ Low Score → Human Review
   ↓
6. Destination System
```

### Task Management Flow

```
1. Task Creation
   ↓
2. Assignment Algorithm
   ├─ Workload Check
   ├─ Skills Matching
   └─ Priority Weighting
   ↓
3. SLA Monitoring
   ├─ On Track
   ├─ Warning (4 hours)
   ├─ Critical (1 hour)
   └─ Overdue
   ↓
4. Completion or Escalation
```

---

## Security Architecture

### Encryption

**At Rest:**
- Database credentials encrypted with pgcrypto (AES-256)
- Master encryption keys stored in `encryption_keys` table
- API keys encrypted before storage

**In Transit:**
- HTTPS for all external communications (production)
- Internal services use HTTP (localhost only)

### Authentication & Authorization

**Role-Based Access Control (RBAC):**
- 4 default roles: Super Admin, Admin, User, Viewer
- Permissions assigned at role level
- User-role assignments tracked in `user_roles`

**API Security:**
- Webhook endpoints require client validation
- Rate limiting: 100 requests/minute (configurable)
- Request validation and sanitization

### Audit Logging

**Comprehensive Tracking:**
- All configuration changes logged
- Workflow executions tracked
- Security events recorded
- User actions audited

---

## Scalability & Performance

### Current Capacity

**Designed For:**
- 10-100 concurrent clients
- 1,000 workflow executions/hour
- 10,000 records/day
- 100GB storage

### Scaling Strategies

**Vertical Scaling:**
- Increase server resources (CPU, RAM)
- Optimize database queries
- Add database indexes

**Horizontal Scaling (Future):**
- Multiple n8n instances
- Database read replicas
- Load balancing
- Distributed storage

### Performance Optimization

**Database:**
- Indexed columns for frequent queries
- Partitioning for large tables (future)
- Query optimization
- Connection pooling

**Workflows:**
- Batch processing where possible
- Asynchronous execution
- Retry strategies with exponential backoff
- Dead-letter queue for failed operations

---

## Disaster Recovery

### Backup Strategy

**Automated Backups:**
- Daily database backups
- 30-day retention
- Stored in `/workspace/backups`
- Backup script: `/workspace/scripts/backup.sh`

**Backup Contents:**
- Complete database dump
- Workflow definitions
- Configuration files
- Encryption keys

### Recovery Procedures

**Database Recovery:**
1. Stop all services
2. Restore from backup
3. Verify data integrity
4. Restart services
5. Validate workflows

**Workflow Recovery:**
1. Export workflows from n8n UI
2. Import into new instance
3. Activate workflows
4. Test execution

---

## Monitoring & Alerting

### Metrics Collection

**System Metrics (every 5 minutes):**
- Workflow execution counts
- Success/failure rates
- Execution timing
- Resource utilization

**Business Metrics:**
- Lead counts by status
- Document processing stats
- Task completion rates
- SLA compliance

### Alert Types

**Critical Alerts:**
- High error rate (>10%)
- System downtime
- Database connection failures
- Disk space critical (<10%)

**Warning Alerts:**
- SLA approaching deadline
- High DLQ count (>50 items)
- Degraded dependency health

### Alert Channels

**Configured Channels:**
- Email notifications
- Slack webhooks (placeholder)
- Dashboard notifications

---

## Technology Stack

### Core Technologies

| Component | Technology | Version |
|-----------|-----------|---------|
| Workflow Engine | n8n | 2.4.7 |
| Database | PostgreSQL | 15.15 |
| Runtime | Node.js | 20.x |
| Python | Python | 3.11 |
| OS | Debian Linux | slim |

### Supporting Tools

| Tool | Purpose |
|------|---------|
| Tesseract OCR | Document text extraction |
| wkhtmltopdf | PDF generation |
| Chromium | Web scraping |
| Flask | API server |
| SQLite | n8n workflow storage |

---

## Configuration Management

### Environment Variables

**Database:**
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`
- `POSTGRES_USER`, `POSTGRES_PASSWORD`

**n8n:**
- `N8N_HOST`, `N8N_PORT`, `N8N_PROTOCOL`
- `N8N_ENCRYPTION_KEY`
- `N8N_WEBHOOK_URL`

**Storage:**
- `LOCAL_STORAGE_PATH`

**Security:**
- `JWT_SECRET`
- `API_RATE_LIMIT`

### Configuration Files

**Location:** `/workspace/config/`
- `.env.example` - Environment template
- Database connection strings
- API credentials (encrypted)

---

## Known Limitations

### Current Limitations

1. **Schema Mismatches:** Workflow definitions need alignment with database schema
2. **No SSL:** HTTP only (HTTPS needed for production)
3. **Single Server:** No horizontal scaling yet
4. **Limited Integrations:** External API integrations are placeholders
5. **No User UI:** Admin operations via n8n UI only

### Future Enhancements

1. **v1.1:** SSL/TLS support, schema alignment
2. **v1.2:** Additional automation packs, UI improvements
3. **v2.0:** Multi-server deployment, advanced analytics

---

## Support & Maintenance

### Regular Maintenance

**Daily:**
- Monitor system health
- Review error logs
- Check disk space

**Weekly:**
- Review performance metrics
- Analyze workflow efficiency
- Update documentation

**Monthly:**
- Database optimization
- Security updates
- Backup verification

### Support Contacts

**Technical Support:**
- Email: support@automation-platform.com
- Documentation: /workspace/docs/
- Runbooks: /workspace/docs/OPERATIONS_MANUAL.md

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-29  
**Maintained By:** NinjaTech AI Team
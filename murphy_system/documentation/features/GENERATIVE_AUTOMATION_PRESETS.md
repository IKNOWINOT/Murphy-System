# Generative Automation Presets — Murphy System

**Design Label:** GAP-001  
**Owner:** Platform Engineering / Automation Team  
**Version:** 1.0.0  
**Last Updated:** 2026-03-22

---

## Overview

Murphy System provides a powerful "Describe → Execute" paradigm that converts natural language requests (via voice or typed commands) into fully-wired, governed automation workflows. This document defines how to utilize the system's subsystems for combination features that wire together based on voice activation or typed command, creating generative automations from natural language prompts.

### Key Principles

1. **No Code Required** — Users describe intent in natural language; the system generates executable DAGs
2. **Governance by Default** — Safety gates are automatically injected at critical junctures
3. **Role-Aware** — Automation capabilities respect RBAC permissions and tenant boundaries
4. **Human-in-the-Loop** — Critical operations require explicit human approval before execution

---

## System Architecture

### Core Subsystems for Generative Automation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER INPUT LAYER                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────────────┐ │
│  │ Voice Command   │  │  Typed Command  │  │  UI Terminal / Dashboard     │ │
│  │ Interface (VCI) │  │  (API / CLI)    │  │  Workflow Canvas             │ │
│  └────────┬────────┘  └────────┬────────┘  └──────────────┬───────────────┘ │
└───────────┼─────────────────────┼──────────────────────────┼────────────────┘
            │                     │                          │
            ▼                     ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        NATURAL LANGUAGE PROCESSING                           │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │            TextToAutomationEngine / AIWorkflowGenerator               │  │
│  │  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │  │
│  │  │ Template Match  │  │ Keyword Inference │  │ Dependency Resolution│  │  │
│  │  └─────────────────┘  └──────────────────┘  └──────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WORKFLOW GENERATION                                  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    WorkflowDAGEngine                                   │  │
│  │  ┌───────────────┐  ┌──────────────────┐  ┌─────────────────────────┐ │  │
│  │  │ DAG Creation  │  │ Step Handlers    │  │ Governance Gates        │ │  │
│  │  │ Topological   │  │ (24 built-in)    │  │ HITL Approval Points    │ │  │
│  │  │ Sort          │  │                  │  │                         │ │  │
│  │  └───────────────┘  └──────────────────┘  └─────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXECUTION & INTEGRATION                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │ Connectors      │  │ Rosetta State   │  │ Multi-Tenant Workspace      │  │
│  │ (40+ services)  │  │ Management      │  │ Isolation                   │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## User Roles & Permissions

### Role Hierarchy

| Role | Scope | Automation Capabilities |
|------|-------|------------------------|
| **Platform Admin/Founder** | Entire system | Full automation access, system-wide presets, user management |
| **Employee** | Entire system | Cross-tenant support, preset creation, tenant assistance |
| **Tenant Owner** | Own organization | Full tenant automation, preset management, user roles |
| **Tenant Admin** | Own organization | Automation execution, approval workflows, configuration |
| **Tenant Member** | Own organization | Basic automation execution within assigned scope |
| **Tenant Viewer** | Own organization | Read-only access to automation status and metrics |
| **Sub-Contractor** | Assigned tenants | Development access, preset creation per assignment |
| **HITL Operator** | Credential gates | Approval authority for credentialed operations |
| **Shadow Agent** | As configured | AI agent with bounded execution rights |

### Permission Matrix for Automations

```python
# From src/rbac_governance.py — Default permissions by role

AUTOMATION_PERMISSIONS = {
    "OWNER": {
        "create_preset", "delete_preset", "execute_any",
        "approve_gate", "manage_users", "view_all_metrics",
        "configure_integrations", "manage_budget"
    },
    "ADMIN": {
        "create_preset", "execute_any", "approve_gate",
        "view_all_metrics", "configure_integrations"
    },
    "AUTOMATOR_ADMIN": {
        "create_preset", "execute_scoped", "approve_gate",
        "view_automation_metrics", "manage_budget"
    },
    "OPERATOR": {
        "execute_scoped", "approve_gate",
        "view_automation_metrics"
    },
    "VIEWER": {
        "view_automation_metrics"
    },
    "SHADOW_AGENT": {
        "execute_scoped", "view_status"
    }
}
```

---

## Voice & Typed Command Activation

### Voice Command Interface (VCI)

The VCI provides end-to-end voice-to-automation processing:

**API Endpoint:** `POST /api/vci/process`

```json
{
  "text_input": "Monitor sales data and send a weekly summary to Slack",
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "stt": {
    "transcript": "Monitor sales data and send a weekly summary to Slack",
    "confidence": 0.95,
    "language": "en"
  },
  "command": {
    "action": "create_automation",
    "category": "workflow",
    "params": {
      "description": "Monitor sales data and send a weekly summary to Slack"
    }
  },
  "session_id": "vci-abc123"
}
```

### Typed Command Interface

**API Endpoints:**

| Endpoint | Description |
|----------|-------------|
| `POST /api/workflow-terminal/execute` | Execute natural language workflow request |
| `POST /api/workflows` | Create workflow from description |
| `POST /api/execute` | Execute a compiled state graph |

**Terminal Command Example:**
```bash
# Via murphy_terminal.py
murphy> describe "Build an ETL pipeline to extract sales from Salesforce, transform for analytics, and load into BigQuery"
```

---

## Generative Automation Templates

### Built-in Template Library

The system includes 12+ pre-configured workflow templates that match common automation patterns:

#### Core Templates

| Template ID | Pattern | Keywords | Steps |
|-------------|---------|----------|-------|
| `etl_pipeline` | Extract-Transform-Load | etl, pipeline, data, extract, transform, load | 4 |
| `ci_cd` | CI/CD Pipeline | ci, cd, build, test, deploy | 6 |
| `incident_response` | Incident Handling | incident, alert, outage, respond, escalate | 5 |
| `monitoring_alert` | Metric Monitoring | monitor, alert, watch, threshold | 3 |
| `report_generation` | Report & Distribute | report, summary, weekly, analytics | 4 |
| `data_sync` | Data Synchronization | sync, replicate, mirror, backup | 4 |

#### Business Domain Templates

| Template ID | Pattern | Keywords | Steps |
|-------------|---------|----------|-------|
| `order_fulfillment` | E-commerce Fulfillment | order, fulfill, ship, inventory | 7 |
| `invoice_processing` | AP Automation | invoice, payment, approve, ledger | 6 |
| `lead_nurture` | CRM Lead Management | lead, nurture, crm, email | 6 |
| `employee_onboarding` | HR Onboarding | onboard, employee, provision, access | 6 |
| `content_publishing` | Content Pipeline | publish, content, review, schedule | 5 |

### Natural Language to Workflow Translation

The `TextToAutomationEngine` processes natural language through three stages:

```python
# From strategic/gap_closure/text_to_automation/text_to_automation.py

def describe(self, text: str) -> AutomationWorkflow:
    """Convert a plain-English description into an AutomationWorkflow.
    
    Pipeline:
      1. Template matching — known patterns (ETL, CI/CD, monitoring, etc.)
      2. Keyword inference — extracts action verbs and maps to step types
      3. Dependency resolution — wires steps into a DAG
      4. Governance injection — inserts safety gates at critical junctures
    """
```

#### Keyword → Step Type Mapping

The system recognizes 100+ keywords that map to semantic step types:

```python
KEYWORD_MAP = {
    # Data Retrieval
    "fetch", "get", "pull", "download", "read", "collect", "extract", 
    "ingest", "monitor", "watch", "order", "receive", "import", "sync"
    → StepType.DATA_RETRIEVAL,
    
    # Data Transformation
    "transform", "convert", "parse", "format", "clean", "normalize", 
    "map", "enrich"
    → StepType.DATA_TRANSFORMATION,
    
    # Validation
    "validate", "check", "verify", "ensure", "test"
    → StepType.VALIDATION,
    
    # Notification
    "send", "notify", "alert", "email", "slack", "message"
    → StepType.NOTIFICATION,
    
    # Execution
    "run", "execute", "trigger", "invoke", "fulfill", "ship", "dispatch"
    → StepType.EXECUTION,
    
    # Approval
    "approve", "review", "sign-off", "sign", "reject"
    → StepType.APPROVAL,
    
    # Analysis
    "analyze", "report", "summarize", "aggregate", "score", "rank"
    → StepType.ANALYSIS,
    
    # ... and more
}
```

---

## Wired Preset Configurations

### Preset Structure

Presets wire together subsystems, connectors, and approval flows into reusable configurations:

```python
@dataclass
class AutomationPreset:
    """A pre-configured automation wiring."""
    preset_id: str
    name: str
    description: str
    trigger_phrases: List[str]        # Voice/typed activation phrases
    template_id: Optional[str]        # Base template (if any)
    required_connectors: List[str]    # Integration dependencies
    required_permissions: Set[str]    # RBAC requirements
    governance_gates: List[GateSpec]  # HITL approval points
    steps: List[StepSpec]             # Workflow steps
    role_scope: str                   # "platform", "tenant", "user"
    tenant_id: Optional[str]          # Null for platform-wide
```

### Example: Sales Report Preset

```yaml
preset_id: "sales-weekly-report"
name: "Weekly Sales Report"
description: "Generate and distribute weekly sales performance report"
trigger_phrases:
  - "run weekly sales report"
  - "generate sales summary"
  - "create this week's sales report"
  
template_id: "report_generation"
required_connectors:
  - "salesforce"
  - "slack"
  - "google_drive"
  
required_permissions:
  - "execute_scoped"
  - "view_automation_metrics"
  
governance_gates:
  - type: "approval"
    description: "Verify report before distribution"
    required_role: "OPERATOR"
    
steps:
  - name: "fetch_sales_data"
    type: "data_retrieval"
    connector: "salesforce"
    config:
      object: "Opportunity"
      filter: "CloseDate >= THIS_WEEK"
      
  - name: "aggregate_metrics"
    type: "analysis"
    depends_on: ["fetch_sales_data"]
    config:
      metrics: ["total_revenue", "deal_count", "avg_deal_size"]
      
  - name: "generate_report"
    type: "data_output"
    depends_on: ["aggregate_metrics"]
    config:
      format: "pdf"
      template: "sales_weekly_template"
      
  - name: "approval_gate"
    type: "governance_gate"
    depends_on: ["generate_report"]
    config:
      require_approval: true
      timeout_hours: 4
      
  - name: "upload_archive"
    type: "data_output"
    connector: "google_drive"
    depends_on: ["approval_gate"]
    config:
      folder: "/Reports/Sales/Weekly"
      
  - name: "notify_team"
    type: "notification"
    connector: "slack"
    depends_on: ["upload_archive"]
    config:
      channel: "#sales-team"
      message_template: "sales_report_notification"

role_scope: "tenant"
tenant_id: null  # Available to all tenants
```

---

## Industry Presets

The system includes industry-specific preset packages loaded from `src/org_build_plan/presets/`:

### Available Industry Presets

| Industry | Preset ID | Default Templates | Connectors |
|----------|-----------|-------------------|------------|
| **SaaS/Agency** | `saas_agency` | CI/CD, Customer Onboarding | GitHub, Stripe, Slack |
| **Retail/E-commerce** | `retail_ecommerce` | Order Fulfillment, Inventory | Shopify, WooCommerce |
| **Financial Services** | `financial_services` | Invoice Processing, Compliance | QuickBooks, PayPal |
| **Manufacturing** | `manufacturing` | Production Workflow, QA | Warehouse systems |
| **Logistics/Fleet** | `logistics_fleet` | Dispatch, Tracking | GPS, Routing APIs |
| **Energy/Utilities** | `energy_utilities` | Monitoring, Maintenance | SCADA connectors |
| **Nonprofit** | `nonprofit_advocacy` | Donor Management, Campaigns | CRM, Email |

### Loading Industry Presets

```python
# From src/org_build_plan/workflow_templates.py

from org_build_plan.presets import INDUSTRY_PRESETS

# Get templates for an industry
library = WorkflowTemplateLibrary()
finance_templates = library.get_templates_for_industry("financial_services")

# Compile a template to executable DAG
dag = library.compile_to_dag(finance_templates[0])
```

---

## Connector Wiring

### Available Connectors (40+)

The system provides pre-wired connectors organized by category:

#### Communication
- **Slack** — channels, DMs, notifications
- **Discord** — channels, bots
- **Telegram** — bot messaging
- **Twilio** — SMS, voice
- **SendGrid** — email campaigns

#### CRM & Sales
- **Salesforce** — opportunities, leads, contacts
- **HubSpot** — CRM, marketing
- **Pipedrive** — deals, contacts

#### E-commerce
- **Shopify** — products, orders, webhooks
- **WooCommerce** — products, orders
- **Stripe** — payments, subscriptions

#### Cloud & DevOps
- **GitHub** — repos, actions, issues
- **GitLab** — CI/CD, repos
- **CircleCI** — pipelines
- **Jenkins** — builds
- **AWS** — EC2, S3, Lambda
- **GCP** — Compute, Storage

#### Observability
- **Datadog** — metrics, alerts
- **PagerDuty** — incidents
- **Sentry** — errors
- **NewRelic** — APM

#### Storage & Documents
- **Google Drive** — files, folders
- **Dropbox** — files
- **DocuSign** — e-signatures

#### Databases
- **PostgreSQL** — queries
- **MySQL** — queries
- **Redis** — cache
- **MongoDB** — documents

### Wiring Connectors to Presets

```python
# From src/integrations/integration_framework.py

from integrations import IntegrationFramework

framework = IntegrationFramework()

# Configure connector
framework.configure_integration(
    integration_id="salesforce",
    config={
        "client_id": "${SALESFORCE_CLIENT_ID}",
        "client_secret": "${SALESFORCE_CLIENT_SECRET}",
        "instance_url": "${SALESFORCE_INSTANCE_URL}"
    }
)

# Wire to workflow step
step_config = {
    "connector": "salesforce",
    "action": "query",
    "params": {
        "object": "Opportunity",
        "fields": ["Id", "Name", "Amount", "CloseDate"]
    }
}
```

---

## Governance & Human-in-the-Loop

### Automatic Governance Gate Injection

The system automatically injects governance gates at critical points:

```python
# From strategic/gap_closure/text_to_automation/text_to_automation.py

GOVERNANCE_GATE_TRIGGERS = [
    StepType.DEPLOYMENT,      # Always gate before deploy
    StepType.DATA_OUTPUT,     # Gate before external writes
    StepType.APPROVAL,        # Explicit approval steps
    StepType.EXECUTION,       # Gate high-risk executions
]

def _inject_governance_gates(self, steps: List[StepSpec]) -> List[StepSpec]:
    """Insert governance gates before sensitive operations."""
    enhanced_steps = []
    for step in steps:
        if step.type in GOVERNANCE_GATE_TRIGGERS:
            gate = StepSpec(
                step_id=f"gate_before_{step.step_id}",
                name=f"Approval: {step.name}",
                type=StepType.GOVERNANCE_GATE,
                config={"require_approval": True}
            )
            enhanced_steps.append(gate)
        enhanced_steps.append(step)
    return enhanced_steps
```

### HITL Approval Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     HITL APPROVAL WORKFLOW                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Workflow reaches governance gate                                │
│     └─→ WorkflowDAGEngine pauses execution                         │
│                                                                     │
│  2. Approval request generated                                      │
│     └─→ TOSAcceptanceGate or CredentialGatedApproval               │
│         └─→ Request logged with document hash                       │
│                                                                     │
│  3. HITL notification sent                                          │
│     └─→ Dashboard: /ui/compliance                                   │
│     └─→ Slack/Email notification to authorized approvers            │
│                                                                     │
│  4. Human reviews and approves/rejects                              │
│     └─→ API: POST /api/approval/{request_id}/approve               │
│     └─→ Credential verification (if required)                       │
│                                                                     │
│  5. Workflow resumes or terminates                                  │
│     └─→ Approved: Continue to next step                            │
│     └─→ Rejected: Terminate with rejection reason                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Credential-Gated Approvals

For operations requiring verified credentials:

```python
# From src/murphy_credential_gate.py

class CredentialGatedApproval:
    """HITL approval with credential verification."""
    
    def request_approval(
        self,
        document_id: str,
        document_bytes: bytes,
        approver_credential_id: str,
        required_credential_types: List[CredentialType],
        jurisdiction: Optional[str] = None,
    ) -> ApprovalRecord:
        """Gate approval on credential verification."""
        # 1. Verify approver holds required credentials
        # 2. If valid: create e-stamp and approve
        # 3. If invalid: return REQUIRES_CREDENTIAL status
```

---

## API Reference for Generative Automation

### Create Automation from Natural Language

**Endpoint:** `POST /api/workflows`

```json
{
  "description": "Monitor AWS costs and alert when budget exceeds 80%",
  "tenant_id": "tenant-123",
  "user_id": "user-456"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "workflow_id": "wf-abc123",
    "strategy": "template_match",
    "template_used": "monitoring_alert",
    "steps": [
      {
        "step_id": "monitor_costs",
        "name": "Monitor AWS Costs",
        "type": "data_retrieval",
        "connector": "aws",
        "depends_on": []
      },
      {
        "step_id": "analyze_threshold",
        "name": "Check Budget Threshold",
        "type": "analysis",
        "depends_on": ["monitor_costs"]
      },
      {
        "step_id": "alert_team",
        "name": "Send Budget Alert",
        "type": "notification",
        "connector": "slack",
        "depends_on": ["analyze_threshold"]
      }
    ],
    "governance_gates": ["approval_before_alert"],
    "ready_to_execute": true
  }
}
```

### Execute Generated Workflow

**Endpoint:** `POST /api/execute`

```json
{
  "workflow_id": "wf-abc123",
  "context": {
    "budget_threshold": 0.8,
    "alert_channel": "#devops-alerts"
  }
}
```

### List Available Presets

**Endpoint:** `GET /api/presets`

```json
{
  "success": true,
  "data": {
    "presets": [
      {
        "preset_id": "sales-weekly-report",
        "name": "Weekly Sales Report",
        "trigger_phrases": ["run weekly sales report", "generate sales summary"],
        "required_permissions": ["execute_scoped"],
        "role_scope": "tenant"
      },
      ...
    ]
  }
}
```

### Activate Preset via Voice/Text

**Endpoint:** `POST /api/presets/activate`

```json
{
  "trigger_phrase": "run weekly sales report",
  "tenant_id": "tenant-123",
  "user_id": "user-456",
  "context": {
    "week_start": "2026-03-16"
  }
}
```

---

## UI Integration Points

### Dashboard Routes

| Route | Component | Purpose |
|-------|-----------|---------|
| `/ui/terminal-unified` | Unified Terminal | Voice/typed command interface |
| `/ui/workflow-canvas` | Visual Workflow Builder | Drag-drop workflow editing |
| `/ui/terminal-orchestrator` | Orchestrator View | Active workflow monitoring |
| `/ui/compliance` | Compliance Dashboard | HITL approval queue |
| `/ui/terminal-integrations` | Integration Manager | Connector configuration |

### Terminal Commands

```bash
# List available presets
murphy> presets list

# Activate a preset
murphy> preset activate "sales-weekly-report"

# Create from natural language
murphy> describe "Send Slack notification when GitHub PR is merged"

# View workflow status
murphy> workflow status wf-abc123

# Approve pending gate
murphy> approve gate-xyz789
```

---

## Best Practices

### 1. Use Specific Trigger Phrases

❌ Poor: "do the thing"  
✅ Good: "Generate weekly sales report and send to Slack #sales channel"

### 2. Leverage Template Matching

The system works best when requests align with known templates:
- ETL operations → Include "extract", "transform", "load"
- Monitoring → Include "monitor", "alert", "threshold"
- Reports → Include "report", "summary", "generate"

### 3. Specify Connectors Explicitly

❌ Vague: "Get data and send notification"  
✅ Specific: "Get sales data from Salesforce and send summary to Slack"

### 4. Trust the Governance Gates

Don't try to bypass governance gates — they protect against:
- Unintended data exposure
- Unauthorized deployments
- Budget overruns
- Compliance violations

### 5. Use Presets for Recurring Tasks

Create presets for frequently-used automations to ensure:
- Consistent execution
- Proper governance
- Audit trail
- Role-appropriate access

---

## Role-Specific Guidance

### Platform Admins / Founders

**Capabilities:**
- Create system-wide presets available to all tenants
- Configure global governance policies
- Manage connector credentials at platform level
- Override tenant restrictions when necessary

**Best Practices:**
- Create industry-specific preset packages
- Establish default governance gate policies
- Set up alerting for high-risk automation patterns

### Tenant Owners / Admins

**Capabilities:**
- Create tenant-specific presets
- Configure tenant connector integrations
- Assign automation permissions to team members
- Approve governance gates within tenant scope

**Best Practices:**
- Customize industry presets for your organization
- Set appropriate budget limits for automations
- Designate backup approvers for HITL gates

### Sub-Contractors

**Capabilities:**
- Create presets within assigned tenant scope
- Access development tools and APIs
- Test automations in sandbox environments

**Best Practices:**
- Follow tenant's coding standards and naming conventions
- Document custom presets thoroughly
- Test governance gate flows before deployment

### HITL Operators

**Capabilities:**
- Approve/reject credential-gated operations
- Review automation execution logs
- Escalate suspicious patterns

**Best Practices:**
- Verify document hashes before signing
- Maintain separation of duties
- Report anomalous approval patterns

---

## Optimization Strategies

### Maximize Template Match Rate

1. **Train the system** with organization-specific templates
2. **Use standard terminology** from the keyword map
3. **Structure requests** as: `[Action] [Object] from [Source] and [Action] to [Destination]`

### Minimize Execution Latency

1. **Pre-configure connectors** with valid credentials
2. **Use parallel step execution** where dependencies allow
3. **Cache frequently-accessed data** retrieval results

### Reduce Governance Friction

1. **Pre-approve trusted patterns** for low-risk operations
2. **Set appropriate timeout thresholds** for approval windows
3. **Configure notification channels** for immediate awareness

---

## Troubleshooting

### Common Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| "No matching template" | Request too vague | Include specific action keywords |
| "Permission denied" | Missing RBAC role | Request role assignment from admin |
| "Connector not configured" | Missing credentials | Configure via `/ui/terminal-integrations` |
| "Gate timeout" | Approver unavailable | Configure backup approvers |
| "Step handler not found" | Unknown step type | Use semantic step types from list |

### Debugging Commands

```bash
# Check workflow execution status
murphy> workflow debug wf-abc123

# View step handler mappings
murphy> handlers list

# Test connector health
murphy> connector test salesforce

# View governance gate queue
murphy> gates pending
```

---

## Appendix: Step Handlers

The WorkflowDAGEngine includes 24 built-in step handlers:

### Semantic Handlers (16)

| Handler | Description |
|---------|-------------|
| `data_retrieval` | Fetch data from sources |
| `data_transformation` | Transform data format/structure |
| `data_filtering` | Filter data by criteria |
| `validation` | Validate data integrity |
| `notification` | Send notifications |
| `deployment` | Deploy artifacts |
| `approval` | Request human approval |
| `scheduling` | Schedule future execution |
| `computation` | Perform calculations |
| `data_output` | Write data to destinations |
| `error_handling` | Handle errors and retries |
| `data_protection` | Backup/archive operations |
| `security` | Encryption/authentication |
| `delay` | Pause workflow execution |
| `execution` | Execute commands/actions |
| `analysis` | Analyze and report |

### Legacy Handlers (8)

| Handler | Maps To |
|---------|---------|
| `llm_execute` | LLM-powered execution |
| `llm_analyze` | LLM-powered analysis |
| `llm_generate` | LLM-powered generation |
| `llm_review` | LLM-powered review |
| `execute` | Generic execution |
| `generate` | Generic generation |
| `analyze` | Analysis (alias) |
| `review` | Review (alias) |

---

## Related Documentation

- [API Routes](../API_ROUTES.md) — Complete API reference
- [Architecture Overview](./architecture/ARCHITECTURE_OVERVIEW.md) — System architecture
- [Enterprise Features](./enterprise/ENTERPRISE_FEATURES.md) — RBAC and governance
- [Integration Framework](../src/integrations/README.md) — Connector development
- [Text to Automation Engine](../strategic/gap_closure/text_to_automation/) — Core NLP engine

---

*Copyright © 2020-2026 Inoni Limited Liability Company. All rights reserved.*  
*Created by: Corey Post*  
*License: BSL 1.1*

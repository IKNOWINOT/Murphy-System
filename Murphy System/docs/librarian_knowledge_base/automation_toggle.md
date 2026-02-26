# Toggleable Full Automation - Librarian Knowledge Base Entry

**Knowledge Base ID:** KB-AUTO-001  
**Category:** Automation & Control  
**Last Updated:** 2025-02-26  
**Access Level:** Admin/Owner Only

---

## Overview

The Murphy System supports **toggleable full automation** with comprehensive safety controls, HITL (Human-in-the-Loop) transition gap detection, and risk-based activation. This feature enables organizations and account owners to progressively enable autonomous operation based on demonstrated reliability and risk tolerance.

---

## Quick Reference

### Automation Modes

| Mode | Description | Auto-Approval | Use Case |
|------|-------------|---------------|----------|
| **MANUAL** | All actions require human approval | None | Initial deployment, high-risk environments |
| **SEMI_AUTONOMOUS** | Low-risk actions auto-approved | LOW, MINIMAL risk | Proven reliability, controlled automation |
| **FULL_AUTONOMOUS** | All actions auto-approved except critical | All except CRITICAL | High reliability, trusted environments |

### Authorization Requirements

| Context | Authorized Roles | Notes |
|---------|-----------------|-------|
| **Organization** | admin, owner | Only admin/owner can toggle full automation |
| **Individual Account** | owner | Only account owner can toggle for their agents |

### Key Thresholds

- **Success Rate Threshold:** 95% (required for mode upgrade)
- **HITL Gap Threshold:** 3 active gaps (triggers downgrade to MANUAL)
- **Minimum Observations:** 50 actions (before considering automation)

---

## Architecture

### Core Components

1. **FullAutomationController** (`src/full_automation_controller.py`)
   - Manages automation mode transitions
   - Detects HITL transition gaps
   - Evaluates action risk
   - Monitors success rates
   - Maintains audit logs

2. **RBACGovernance** (`src/rbac_governance.py`)
   - Enforces authorization for toggle operations
   - Provides `can_toggle_full_automation()` method
   - Integrates with existing permission system

3. **HumanOversightSystem** (`src/autonomous_systems/human_oversight_system.py`)
   - Manages approval workflows
   - Tracks interventions
   - Logs oversight events

### Data Flow

```
User Request
    │
    ▼
RBAC Permission Check
    │
    ▼
FullAutomationController
    │
    ├─► Mode Transition
    ├─► Risk Evaluation
    ├─► HITL Gap Detection
    └─► Success Rate Monitoring
    │
    ▼
Event Backbone (Publish Events)
    │
    ▼
Persistence Manager (Save State)
```

---

## Usage Patterns

### Pattern 1: Enabling Full Automation (Organization)

```python
from src.full_automation_controller import FullAutomationController, AutomationMode, AutomationToggleReason
from src.rbac_governance import RBACGovernance

# Initialize
controller = FullAutomationController()
rbac = RBACGovernance()

# Check permissions
allowed, reason = rbac.can_toggle_full_automation(
    user_id="admin-123",
    tenant_id="org-456",
    is_organization=True
)

if allowed:
    # Enable full automation
    success, message = controller.set_automation_mode(
        tenant_id="org-456",
        agent_id=None,
        mode=AutomationMode.FULL_AUTONOMOUS,
        user_id="admin-123",
        reason=AutomationToggleReason.ADMIN_OVERRIDE,
        user_role="admin",
        is_organization=True
    )
```

### Pattern 2: Monitoring Automation Performance

```python
# Record action outcome
controller.record_action_outcome(
    tenant_id="org-456",
    agent_id=None,
    action_type="deploy_to_staging",
    approved=True,
    auto_approved=True,
    success=True,
    response_time=45.2
)

# Get metrics
metrics = controller.get_metrics(tenant_id="org-456")
print(f"Success Rate: {metrics['success_rate']:.2%}")
print(f"Auto-Approved: {metrics['auto_approved']}/{metrics['total_actions']}")
```

### Pattern 3: Handling HITL Gaps

```python
# Detect a HITL gap
gap = controller.detect_hitl_gap(
    tenant_id="org-456",
    agent_id=None,
    gap_type="approval_timeout",
    severity=RiskLevel.HIGH,
    description="Production deployment approval timeout after 2 hours",
    metrics={
        "timeout_duration": 7200,
        "approver_id": "admin-123"
    }
)

# Resolve the gap
controller.resolve_hitl_gap(
    gap_id=gap.gap_id,
    resolved_by="admin-456"
)
```

---

## Risk Evaluation

### Risk Levels

| Risk Level | Description | Example Actions |
|------------|-------------|-----------------|
| **CRITICAL** | System-critical, irreversible | Deploy to production, delete data |
| **HIGH** | Significant impact, reversible | Deploy to staging, modify config |
| **MEDIUM** | Moderate impact, standard operations | Execute code, access data |
| **LOW** | Low impact, with rollback | Update documentation, run tests |
| **MINIMAL** | Negligible impact | Read operations, status checks |

### Auto-Approval Matrix

```
                    Risk Level
                    ┌─────────┬─────────┬─────────┬─────────┬─────────┐
                    │ CRITICAL│  HIGH   │ MEDIUM  │   LOW   │ MINIMAL │
        ┌───────────┼─────────┼─────────┼─────────┼─────────┼─────────┐
        │ MANUAL    │   NO    │   NO    │   NO    │   NO    │   NO    │
        │ SEMI-AUTO │   NO    │   NO    │   NO    │  YES    │  YES    │
        │ FULL-AUTO │   NO    │  YES    │  YES    │  YES    │  YES    │
        └───────────┴─────────┴─────────┴─────────┴─────────┴─────────┘
```

---

## HITL Gap Detection

### Gap Types

1. **approval_timeout** - Human approval not received within timeout
2. **escalation_failure** - Escalation to secondary approver failed
3. **intervention_rate** - High rate of human interventions

### Detection Workflow

```
Monitor Actions
    │
    ▼
Detect Anomalies
    │
    ▼
Assess Severity
    │
    ▼
Take Action
    ├─► Log gap
    ├─► Notify admins
    └─► Downgrade mode (if threshold exceeded)
```

### Automatic Downgrade

When HITL gap count ≥ 3:
- Automatic downgrade to MANUAL mode
- Audit log entry created
- Admin notification sent

---

## Success Rate Monitoring

### Metrics Tracked

- **total_actions** - Total actions processed
- **auto_approved** - Actions auto-approved
- **human_approved** - Actions approved by humans
- **rejected** - Actions rejected
- **escalated** - Actions escalated
- **success_rate** - Exponential moving average of success
- **avg_response_time** - Average action response time
- **hitl_gap_count** - Active HITL gaps

### Success Rate Calculation

```
success_rate = α × actual_success + (1 - α) × previous_success_rate

Where α = 0.1 (smoothing factor)
```

### Adaptive Mode Transitions

**Upgrade Conditions:**
- Success rate ≥ 95%
- Minimum 50 observations
- Zero active HITL gaps
- Current mode is MANUAL or SEMI_AUTONOMOUS

**Downgrade Conditions:**
- HITL gap count ≥ 3
- Success rate drops below threshold
- Critical risk events detected
- Manual override by admin

---

## Integration Points

### Event Backbone Events

- `AUTOMATION_MODE_CHANGED` - Mode transition event
- `HITL_GAP_DETECTED` - HITL gap detection event
- `HITL_GAP_RESOLVED` - HITL gap resolution event
- `AUTOMATION_ACTION_APPROVED` - Action approval event
- `AUTOMATION_ACTION_REJECTED` - Action rejection event

### Persistence Namespaces

- `automation_state/` - Automation mode and state
- `hitl_gaps/` - HITL gap records
- `automation_metrics/` - Performance metrics
- `automation_audit/` - Audit log entries

### API Endpoints

- `POST /api/automation/mode` - Set automation mode
- `GET /api/automation/mode` - Get current automation mode
- `GET /api/automation/metrics` - Get automation metrics
- `GET /api/automation/gaps` - Get active HITL gaps
- `POST /api/automation/gaps/{gap_id}/resolve` - Resolve HITL gap

---

## Safety & Security

### Safety Controls

1. **Permission-Based Activation** - Only authorized users can toggle automation
2. **Risk-Based Approval** - Critical actions always require human approval
3. **HITL Gap Detection** - Automatic downgrade on gap detection
4. **Success Rate Monitoring** - Adaptive mode transitions based on performance
5. **Audit Logging** - Complete audit trail of all mode changes
6. **Rollback Capability** - All changes can be rolled back

### Security Controls

1. **RBAC Integration** - Role-based access control for all operations
2. **Tenant Isolation** - Automation state isolated per tenant
3. **Audit Trail** - Immutable audit log for compliance
4. **Encryption** - Sensitive data encrypted at rest and in transit
5. **Rate Limiting** - Prevents abuse of automation features

### Compliance Support

- **SOC 2** - Audit logging, access controls, change management
- **ISO 27001** - Security controls, risk management, monitoring
- **GDPR** - Data protection, user consent, audit trails
- **HIPAA** - Access controls, audit logging, data encryption

---

## Troubleshooting

### Issue: Cannot Enable Full Automation

**Symptoms:** Permission denied when trying to enable full automation

**Possible Causes:**
1. User does not have admin/owner role
2. User is not in the correct tenant
3. Organization context mismatch

**Resolution:**
```python
# Check permissions
allowed, reason = rbac.can_toggle_full_automation(
    user_id=user_id,
    tenant_id=tenant_id,
    is_organization=True
)

if not allowed:
    print(f"Cannot enable: {reason}")
```

### Issue: Automatic Downgrade to MANUAL

**Symptoms:** Automation mode automatically downgrades to MANUAL

**Possible Causes:**
1. HITL gap count exceeded threshold (≥ 3)
2. Success rate dropped below threshold
3. Critical risk event detected

**Resolution:**
```python
# Check active HITL gaps
gaps = controller.get_active_hitl_gaps(tenant_id)

# Check metrics
metrics = controller.get_metrics(tenant_id)

# Resolve gaps before re-enabling
for gap in gaps:
    controller.resolve_hitl_gap(gap.gap_id, resolved_by="admin-123")
```

### Issue: Low Success Rate

**Symptoms:** Success rate below 95%, preventing mode upgrade

**Possible Causes:**
1. High failure rate for certain action types
2. Insufficient observations (< 50)
3. Recent performance degradation

**Resolution:**
```python
# Check metrics
metrics = controller.get_metrics(tenant_id)

# Analyze failure patterns
# Improve action reliability
# Wait for more observations
```

---

## Best Practices

### 1. Gradual Rollout

1. Start with **MANUAL** mode for all new deployments
2. Monitor performance for at least 50 actions
3. Progress to **SEMI_AUTONOMOUS** after 95%+ success rate
4. Enable **FULL_AUTONOMOUS** only for trusted environments

### 2. Continuous Monitoring

1. Monitor success rate trends
2. Track HITL gap activity
3. Review audit logs regularly
4. Set up alerts for threshold breaches

### 3. Maintain Human Oversight

1. Keep critical actions requiring approval
2. Regular review of automation decisions
3. Maintain escalation procedures
4. Document override decisions

### 4. Documentation

1. Document all mode changes with reasons
2. Maintain change history
3. Review and update policies regularly
4. Train staff on automation procedures

---

## Related Documentation

- [Self-Running Analysis](../self_running_analysis.md) - Comprehensive analysis of toggleable automation
- [RBAC Governance](../../src/rbac_governance.py) - Role-based access control
- [Human Oversight System](../../src/autonomous_systems/human_oversight_system.py) - HITL management
- [Event Backbone](../../src/event_backbone.py) - Event system integration

---

## API Reference

### FullAutomationController

```python
class FullAutomationController:
    def set_automation_mode(...) -> Tuple[bool, str]
    def get_automation_mode(...) -> Optional[AutomationMode]
    def get_automation_state(...) -> Optional[Dict[str, Any]]
    def detect_hitl_gap(...) -> HITLTransitionGap
    def resolve_hitl_gap(...) -> bool
    def get_active_hitl_gaps(...) -> List[HITLTransitionGap]
    def evaluate_action_risk(...) -> RiskLevel
    def should_auto_approve(...) -> Tuple[bool, str]
    def record_action_outcome(...) -> None
    def get_metrics(...) -> Optional[Dict[str, Any]]
    def get_audit_log(...) -> List[Dict[str, Any]]
    def get_status(...) -> Dict[str, Any]
```

### RBACGovernance

```python
class RBACGovernance:
    def can_toggle_full_automation(...) -> Tuple[bool, str]
```

---

**Knowledge Base Version:** 1.0  
**Last Reviewed:** 2025-02-26  
**Next Review:** 2025-05-26
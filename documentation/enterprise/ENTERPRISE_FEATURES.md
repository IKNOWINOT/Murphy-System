# Enterprise Features

Enterprise-grade capabilities built into the Murphy System — RBAC, multi-tenant isolation,
audit trails, SLA monitoring, and compliance reporting.

---

## Role-Based Access Control (RBAC)

Implemented in `src/rbac_governance.py`, the RBAC system provides hierarchical roles
with fine-grained permissions and multi-tenant policy isolation.

### Roles

| Role | Description |
|------|-------------|
| `OWNER` | Full system access including user management |
| `ADMIN` | All permissions except user management |
| `AUTOMATOR_ADMIN` | Task execution, gate approval, budget management |
| `OPERATOR` | Task execution, status viewing, gate approval |
| `VIEWER` | Read-only access to status and metrics |
| `SHADOW_AGENT` | AI agent role — task execution and status only |

### Permissions

Permissions are assigned per-role and enforced on every API call:

`EXECUTE_TASK` · `APPROVE_GATE` · `CONFIGURE_SYSTEM` · `VIEW_STATUS` ·
`MANAGE_USERS` · `MANAGE_SHADOWS` · `MANAGE_BUDGET` · `APPROVE_DELIVERY` ·
`MANAGE_COMPLIANCE` · `ESCALATE` · `TOGGLE_FULL_AUTOMATION` · `VIEW_AUTOMATION_METRICS`

Shadow Agent governance treats AI agents as org-chart peers with explicit boundaries,
preventing autonomous escalation beyond assigned permissions.

---

## Multi-Tenant Workspace Isolation

Implemented in `src/multi_tenant_workspace.py` (design label **MTW-001**).

Each tenant receives a dedicated namespace for data, configuration, and permissions.
No cross-tenant access is possible through the public API.

### Tenant Roles

`owner` · `admin` · `member` · `viewer` · `service_account`

### Workspace States

`active` · `suspended` · `archived` · `pending_deletion`

### Isolation Levels

| Level | Behaviour |
|-------|-----------|
| `strict` | Complete data and process isolation |
| `standard` | Data isolation with shared infrastructure |
| `shared` | Shared resources with logical separation |

### Resource Limits (per tenant)

| Limit | Default |
|-------|---------|
| Max storage | 1,024 MB |
| Max API calls | 100,000 |
| Max members | 50 |
| Audit log cap | 10,000 entries |

---

## Audit Trails

Both RBAC and multi-tenant modules maintain bounded, immutable audit logs:

- Every permission check, role change, and data access is recorded.
- Audit entries include timestamp, actor, action, and result.
- Logs are bounded via `capped_append` (CWE-770 mitigation) to prevent unbounded growth.
- Thread-safe: all mutable state is guarded by `threading.Lock`.

---

## SLA Monitoring

Tenant policies include configurable limits for:

- **Max concurrent tasks** (default: 10)
- **Budget limits** per tenant (default: $10,000)
- **Allowed domains** — restrict which external domains can be accessed.

---

## Compliance Reporting

Per-tenant `TenantPolicy` supports:

- **Compliance frameworks** — list of frameworks the tenant must adhere to (e.g., SOC 2, GDPR).
- **Compliance-as-code** engine for automated rule evaluation.
- **Region-specific validation** for data residency requirements.
- **Delivery gating** — compliance checks block deployment if rules are violated.

---

## See Also

- [Enterprise Overview](ENTERPRISE_OVERVIEW.md)
- [Performance](PERFORMANCE.md)
- [Enterprise Tests](../testing/ENTERPRISE_TESTS.md)

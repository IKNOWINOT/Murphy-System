# Enterprise Tests

Enterprise integration, compliance, and governance test suites for the Murphy System.

---

## Overview

The enterprise test suite validates multi-tenant isolation, RBAC enforcement, compliance
frameworks, and governance policies. All tests live under `Murphy System/tests/` and can
be run with pytest.

```bash
cd "Murphy System"
python -m pytest tests/ -k "enterprise or rbac or compliance or governance or multi_tenant" -v
```

---

## Test Categories

### Multi-Tenant Workspace Isolation

| Test File | Coverage |
|-----------|----------|
| `test_multi_tenant_workspace.py` | Tenant creation, data isolation, member management, cross-tenant access prevention |

### RBAC & Governance

| Test File | Coverage |
|-----------|----------|
| `test_rbac_governance.py` | Role hierarchy, permission checks, tenant policy enforcement |
| `test_automation_rbac_controller.py` | RBAC integration with the automation controller |
| `test_governance_framework.py` | Governance rule evaluation and policy application |
| `test_governance_kernel.py` | Core governance kernel operations |
| `test_governance_kernel_audit_completeness.py` | Audit trail completeness validation |
| `test_governance_kernel_budget_tracking.py` | Budget limit enforcement |
| `test_governance_dashboard_snapshot.py` | Governance dashboard snapshot accuracy |
| `test_base_governance_runtime.py` | Base governance runtime lifecycle |
| `test_bot_governance_policy_mapper.py` | Bot-level governance policy mapping |

### Compliance

| Test File | Coverage |
|-----------|----------|
| `test_compliance_engine.py` | Core compliance engine evaluation |
| `test_compliance_as_code_engine.py` | Compliance-as-code rule execution |
| `test_compliance_automation_bridge.py` | Bridge between compliance and automation |
| `test_compliance_delivery_gating.py` | Delivery gating based on compliance status |
| `test_compliance_monitoring_completeness.py` | Monitoring coverage validation |
| `test_compliance_orchestration_bridge.py` | Orchestration-compliance integration |
| `test_compliance_region_validator.py` | Region-specific compliance rules |
| `test_compliance_report_aggregator.py` | Compliance report aggregation |
| `test_compliance_toggle_manager.py` | Compliance feature toggles |
| `test_compliance_validation_snapshot.py` | Point-in-time compliance snapshots |
| `test_legal_compliance.py` | Legal compliance checks |

### Enterprise Integration & Scale

| Test File | Coverage |
|-----------|----------|
| `test_enterprise_integrations.py` | Third-party enterprise system integrations |
| `test_enterprise_scale.py` | Scale testing under enterprise workloads |

---

## Running Specific Suites

```bash
# RBAC tests only
python -m pytest tests/test_rbac_governance.py tests/test_automation_rbac_controller.py -v

# Compliance tests only
python -m pytest tests/ -k "compliance" -v

# Governance tests only
python -m pytest tests/ -k "governance" -v

# Multi-tenant tests only
python -m pytest tests/test_multi_tenant_workspace.py -v
```

---

## See Also

- [Testing Guide](TESTING_GUIDE.md)
- [Test Coverage](TEST_COVERAGE.md)
- [Enterprise Features](../enterprise/ENTERPRISE_FEATURES.md)

# `src/integration_engine` — Integration Engine

Unified system for safely adding new integrations with Human-in-the-Loop approval.
Implements the SwissKiss integration pattern: repository analysis → capability extraction →
module/agent generation → safety testing → HITL approval → sandbox quarantine → commitment.

## Public API

```python
from integration_engine import (
    UnifiedIntegrationEngine,
    HITLApprovalSystem,
    SafetyTester,
    SandboxQuarantine, QuarantineReport, ThreatFinding,
    CapabilityExtractor,
    ModuleGenerator, AgentGenerator,
)
```

## Integration Workflow

```
1. SwissKiss Scan      — analyse repository / API spec
2. Capability Extract  — identify capabilities from source
3. Module Generate     — generate Murphy module + tests
4. Safety Test         — automated test suite
5. HITL Approval       — human reviews generated module
5.5 Sandbox Quarantine — execute in isolation, scan for threats
6. Commit              — promote to live system
```

```python
from integration_engine import UnifiedIntegrationEngine

engine = UnifiedIntegrationEngine()
result = await engine.integrate(
    source_url="https://github.com/some/integration",
    auto_approve=False,   # Always requires human approval
)
# result.status  → "awaiting_approval" | "committed" | "rejected"
```

## Sandbox Quarantine Protocol (Step 5.5)

```python
from integration_engine import SandboxQuarantine

quarantine = SandboxQuarantine()
report: QuarantineReport = quarantine.run(module_code)
# report.threats → List[ThreatFinding]
# report.safe    → True | False
```

## Tests

`tests/test_integration_engine*.py`, `tests/test_sandbox_quarantine*.py`

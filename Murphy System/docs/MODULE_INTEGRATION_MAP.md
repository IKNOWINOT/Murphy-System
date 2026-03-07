# Murphy System — Module Integration Map

**Version:** 1.0.0  
**License:** BSL 1.1

---

## Overview

This document maps every cross-module dependency in Murphy System 1.0, identifies
integration test coverage per module pair, and documents known interaction patterns
and edge cases.

---

## Dependency Graph (Top-Level)

```
murphy_system_1.0_runtime.py
├── src/llm_controller.py
│   └── src/llm_integration_layer.py
│       └── src/safe_llm_wrapper.py
├── src/confidence_engine/
│   ├── src/domain_engine.py
│   └── src/inference_gate_engine.py
├── src/gate_execution_wiring.py
│   ├── src/governance_kernel.py
│   ├── src/compliance_engine.py
│   └── src/flask_security.py / fastapi_security.py
├── src/self_fix_loop.py
│   ├── src/persistence_manager.py
│   └── src/event_backbone.py
├── src/module_compiler/
│   └── src/capability_map.py
├── src/niche_business_generator.py
│   └── src/niche_viability_gate.py
│       ├── src/mss_controls.py
│       └── src/inference_gate_engine.py
└── src/aionmind/
    └── src/compute_plane/
```

---

## Module Dependency Table

| Module | Direct Dependencies | Integration Test File |
|---|---|---|
| `llm_controller` | `llm_integration_layer`, `safe_llm_wrapper`, `env_manager` | `test_llm_integration_with_fallback.py` |
| `llm_integration_layer` | `safe_llm_wrapper` | `test_llm_integration_with_fallback.py` |
| `safe_llm_wrapper` | `llm_output_validator` | `test_llm_integration_with_fallback.py` |
| `confidence_engine` | `domain_engine`, `inference_gate_engine` | `test_confidence_engine.py` |
| `domain_engine` | `inference_gate_engine` | `test_domain_engine.py` |
| `gate_execution_wiring` | `governance_kernel`, `compliance_engine` | `test_execution_wiring_integration.py` |
| `governance_kernel` | `flask_security`, `fastapi_security` | `test_governance_kernel.py` |
| `compliance_engine` | `governance_kernel` | `test_compliance_engine.py` |
| `self_fix_loop` | `persistence_manager`, `event_backbone` | `test_self_fix_loop.py` |
| `persistence_manager` | (none — leaf module) | `test_persistence_manager.py` |
| `event_backbone` | `persistence_manager` | `test_event_backbone.py` |
| `module_compiler` | `capability_map` | `test_module_compiler.py` |
| `niche_business_generator` | `niche_viability_gate`, `mss_controls`, `inference_gate_engine` | `test_niche_business_generator.py` |
| `niche_viability_gate` | `mss_controls`, `inference_gate_engine` | `test_niche_viability_gate.py` |
| `mss_controls` | `information_quality`, `concept_translation`, `simulation_engine` | `test_mss_controls.py` |
| `aionmind` | `compute_plane` | `test_aionmind*.py` |
| `flask_security` | (FastAPI/Flask framework) | `test_security_*.py` |
| `fastapi_security` | (FastAPI framework) | `test_security_*.py` |
| `state_schema` | (none — leaf module) | `test_state_schema.py` |
| `feedback_integrator` | `persistence_manager`, `confidence_engine` | `test_feedback_integrator.py` |
| `recovery_coordinator` | `persistence_manager`, `self_fix_loop` | `test_correction_loop.py` |

---

## Cross-Module Integration Pipelines

### Pipeline 1: Security → API → Confidence

```
HTTP Request
    → fastapi_security (auth, rate limit, CORS, PII detect)
    → gate_execution_wiring (gate evaluation)
    → confidence_engine (G/D/H scoring + 5D uncertainty)
    → llm_controller (if LLM enabled)
    → safe_llm_wrapper (output validation)
    → HTTP Response
```

**Integration test:** `tests/test_cross_module_integration.py::TestSecurityApiConfidencePipeline`  
**Known edge cases:**
- When rate limit is hit, gate evaluation is skipped (fast path)
- PII detection runs before gate evaluation; sanitised payload is forwarded
- If LLM is unavailable, confidence engine falls back to deterministic scoring

---

### Pipeline 2: State Schema → Feedback → LLM Validator

```
Task Execution
    → state_schema (formalise task state)
    → feedback_integrator (record result, compute signal)
    → llm_output_validator (validate quality)
    → confidence_engine (update calibration)
    → persistence_manager (persist updated state)
```

**Integration test:** `tests/test_cross_module_integration.py::TestStateFeedbackLLMPipeline`  
**Known edge cases:**
- Feedback with `score=None` is treated as `neutral` signal
- Calibration update is async; immediate confidence score may lag by one cycle

---

### Pipeline 3: MSS Controller → Sequence Optimizer → Niche Generator

```
Niche Discovery Request
    → mss_controls (MMSMM sequence orchestration)
    → sequence_optimizer (select optimal MSS sequence)
    → niche_business_generator (generate deployment spec)
    → niche_viability_gate (evaluate all 6 pipeline stages)
    → inoni_entity (create deployable entity on HITL approval)
```

**Integration test:** `tests/test_cross_module_integration.py::TestMSSNichePipeline`  
**Known edge cases:**
- Kill condition check (stage 3) uses running cost, not budget cap — ensure cost is accumulated before check
- HITL approval is asynchronous; `evaluate()` returns `PENDING_HITL_REVIEW` until `approve_hitl_request()` is called
- Hybrid niches require bid acquisition (stage 2); full-autonomy niches skip it

---

### Pipeline 4: Self-Fix Loop → Persistence → Recovery

```
Error Detected
    → self_fix_loop (diagnose, generate fix, verify)
    → persistence_manager (checkpoint fix attempt)
    → event_backbone (publish fix event)
    → recovery_coordinator (if fix failed, escalate)
    → persistence_manager (record final state)
```

**Integration test:** `tests/test_cross_module_integration.py::TestSelfFixRecoveryPipeline`  
**Known edge cases:**
- Self-fix loop has a 3-attempt limit before escalating to recovery coordinator
- Persistence manager uses file-locking; concurrent fix attempts may serialize
- Event backbone DLQ captures undeliverable fix events for manual review

---

### Pipeline 5: Gate System → Governance → RBAC

```
Action Request
    → gate_execution_wiring (evaluate configured gates)
    → governance_kernel (policy enforcement, budget check)
    → automation_rbac_controller (role + permission check)
    → audit_log (record decision)
    → response (allowed / denied + reasons)
```

**Integration test:** `tests/test_cross_module_integration.py::TestGateGovernanceRBACPipeline`  
**Known edge cases:**
- RBAC check is the last gate; governance budget check happens first
- If budget is exceeded, RBAC is not evaluated (short-circuit)
- Gate policies are hot-reloadable; a reload mid-request uses the pre-reload policy

---

## Integration Test Coverage Matrix

| Module Pair | Covered? | Test File |
|---|---|---|
| `security → api` | ✅ | `test_execution_wiring_integration.py` |
| `api → confidence_engine` | ✅ | `test_execution_wiring_integration.py` |
| `confidence_engine → llm_controller` | ✅ | `test_llm_integration_with_fallback.py` |
| `llm_controller → safe_llm_wrapper` | ✅ | `test_llm_integration_with_fallback.py` |
| `state_schema → feedback_integrator` | ✅ | `test_feedback_integrator.py` |
| `feedback_integrator → confidence_engine` | ✅ | `test_confidence_engine.py` |
| `mss_controls → niche_business_generator` | ✅ | `test_niche_business_generator.py` |
| `niche_business_generator → niche_viability_gate` | ✅ | `test_niche_viability_gate.py` |
| `self_fix_loop → persistence_manager` | ✅ | `test_self_fix_loop.py` |
| `persistence_manager → event_backbone` | ✅ | `test_event_backbone.py` |
| `gate_execution_wiring → governance_kernel` | ✅ | `test_governance_kernel.py` |
| `governance_kernel → rbac_controller` | ✅ | `test_automation_rbac_controller.py` |
| `security → confidence_engine → llm` (full pipeline) | ✅ | `test_cross_module_integration.py` |
| `state → feedback → llm_validator` (full pipeline) | ✅ | `test_cross_module_integration.py` |
| `mss → sequence → niche → gate` (full pipeline) | ✅ | `test_cross_module_integration.py` |
| `self_fix → persistence → recovery` (full pipeline) | ✅ | `test_cross_module_integration.py` |
| `gate → governance → rbac` (full pipeline) | ✅ | `test_cross_module_integration.py` |

---

## Known Interaction Patterns

### Hot-reload propagation

When an API key or LLM provider is reconfigured via `/api/llm/configure`, the
change propagates in this order:

1. `env_manager.write_env_key()` — persists to `.env`
2. `env_manager.reload_env()` — reloads process environment
3. `llm_controller.reconfigure()` — updates active provider
4. `confidence_engine` recalibrates on next evaluation (not immediate)

### Gate short-circuit ordering

Gates evaluate in the following order, stopping at the first failure:

1. `security` (auth + PII)
2. `compliance` (GDPR, SOC 2, HIPAA, PCI-DSS sensors)
3. `governance` (budget, policy)
4. `rbac` (role + permission)
5. `confidence` (quality threshold)

This ordering ensures expensive evaluations (confidence, RBAC) are skipped when
cheap ones (security, compliance) fail.

### Event backbone retry policy

The event backbone retries failed event deliveries with exponential back-off:
- Attempt 1: immediate
- Attempt 2: 1 second
- Attempt 3: 4 seconds
- Attempt 4: 16 seconds
- Attempt 5+: Dead Letter Queue (DLQ)

---

*Copyright © 2020 Inoni Limited Liability Company | Creator: Corey Post | License: BSL 1.1*

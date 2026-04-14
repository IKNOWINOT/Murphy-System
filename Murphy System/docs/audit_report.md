# Murphy System — Production Audit Report

**Date**: 2026-04-14
**Author**: Engineering Team (automated + human review)
**Branch**: copilot/define-strengths-weaknesses
**Label**: MURPHY-AUDIT-001

---

## Executive Summary

This audit covers the Murphy System codebase across all modules.  The
system comprises 90+ source modules, 933 test files, 25 CI workflows,
and the new `murphy/` package (schemas, agents, rosetta org lookup,
middleware).

**Status**: Ready for production commission with caveats noted below.

---

## Module-by-Module Audit

### 1. `murphy/schemas/agent_output.py` — AgentOutput Schema
| Question | Answer |
|----------|--------|
| Does it do what it was designed to do? | ✅ Yes — Pydantic BaseModel with 16 typed fields, 2 validators, factory method |
| What is it supposed to do? | Universal inter-agent output contract — no freeform text allowed |
| Conditions possible? | Valid output, missing HITL authority, invalid pass/fail content, serialisation errors |
| Test coverage? | ✅ 11 tests: valid construction, validators, from_error, round-trip JSON |
| Expected vs actual result? | ✅ All validators fire correctly, schema_version defaults to 1.0.0 |
| Documentation updated? | ✅ Full docstring, field descriptions, TypeScript mirror |
| Hardening applied? | ✅ Pydantic strict validation, min_length on required strings, error codes |
| Commissioned? | ✅ 61/61 tests pass |

### 2. `murphy/rosetta/org_lookup.py` — HITL Authority Resolution
| Question | Answer |
|----------|--------|
| Does it do what it was designed to do? | ✅ Yes — resolves org chart node_id by risk level |
| What is it supposed to do? | Replace hardcoded role strings with live org chart walks |
| Conditions possible? | Valid lookup, empty/malformed org chart, missing node type, BAT seal failure |
| Test coverage? | ✅ 9 tests: all 4 risk levels, empty chart, malformed chart, BAT failure |
| Expected vs actual result? | ✅ critical→executive, high→dept_head, medium→team_lead, low→direct_manager |
| Documentation updated? | ✅ Full docstring, error code listing |
| Hardening applied? | ✅ OrgChartLookupError + BATSealError custom exceptions, never silent |
| Commissioned? | ✅ All tests pass |

### 3. `murphy/agents/manifest_agent.py` — ManifestAgent
| Question | Answer |
|----------|--------|
| Does it do what it was designed to do? | ✅ Yes — declares all files before swarm spawns |
| Conditions possible? | Valid manifest, missing required fields, build error |
| Test coverage? | ✅ 3 tests: valid manifest, missing field FAIL, Rosetta snapshot |
| Hardening applied? | ✅ Required field validation, error codes, AgentOutput.from_error() |
| Commissioned? | ✅ All tests pass |

### 4. `murphy/agents/rosetta_agent.py` — RosettaAgent
| Question | Answer |
|----------|--------|
| Does it do what it was designed to do? | ✅ Yes — vote, conflict resolution, change propagation |
| Conditions possible? | Vote success, vote failure (blocks execution), conflict resolution, propagation failure + rollback |
| Test coverage? | ✅ 7 tests: vote success/failure/empty, conflict resolution, propagation success/failure+rollback |
| Hardening applied? | ✅ Rollback on failed propagation, confidence-based conflict resolution, error codes |
| Commissioned? | ✅ All tests pass |

### 5. `murphy/agents/lyapunov_agent.py` — LyapunovAgent
| Question | Answer |
|----------|--------|
| Does it do what it was designed to do? | ✅ Yes — computes stability score, triggers alerts at thresholds |
| Conditions possible? | Stable (≥0.7), warning (0.4-0.7), critical (<0.4 with HITL) |
| Test coverage? | ✅ 3 tests: stable, drift warning, critical with HITL |
| Hardening applied? | ✅ HITL authority resolution for critical, Matrix alerts, BAT sealing |
| Commissioned? | ✅ All tests pass |

### 6. `murphy/agents/recommission_agent.py` — RecommissionAgent
| Question | Answer |
|----------|--------|
| Does it do what it was designed to do? | ✅ Yes — re-tests changed files and dependents |
| Conditions possible? | All pass, test failure, runner not wired, runner exception |
| Test coverage? | ✅ 4 tests: all pass, failure FAIL, no runner FAIL, runner exception FAIL |
| Hardening applied? | ✅ Never silently passes, BAT seal every result, error codes |
| Commissioned? | ✅ All tests pass |

### 7. `murphy/agents/render_agent.py` — RenderAgent
| Question | Answer |
|----------|--------|
| Does it do what it was designed to do? | ✅ Yes — routes content_type to render_type |
| Conditions possible? | All 13 content types routed, unknown type → FAIL |
| Test coverage? | ✅ 8 tests: 7 specific routes + completeness check |
| Hardening applied? | ✅ Never falls back to raw text, all types have explicit routes |
| Commissioned? | ✅ All tests pass |

### 8. `murphy/agents/package_agent.py` — PackageAgent
| Question | Answer |
|----------|--------|
| Does it do what it was designed to do? | ✅ Yes — packages zip with start scripts + smoke test |
| Conditions possible? | CI fail blocks, CI pass proceeds, smoke failure FAIL |
| Test coverage? | ✅ 3 tests: CI fail blocks, CI pass with zip validation, smoke failure |
| Hardening applied? | ✅ HARD RULE: CI must pass, smoke test in temp dir, error codes |
| Commissioned? | ✅ All tests pass |

### 9. `murphy/middleware/schema_enforcer.py` — Schema Enforcer
| Question | Answer |
|----------|--------|
| Does it do what it was designed to do? | ✅ Yes — validates inter-agent messages against AgentOutput |
| Conditions possible? | Valid pass-through, invalid dict rejection, bad type rejection, decorated function crash |
| Test coverage? | ✅ 8 tests: valid AgentOutput, valid dict, invalid dict, bad type, decorator good/bad/crash, batch |
| Hardening applied? | ✅ SchemaEnforcementError exception, Matrix + BAT on failure, never returns undefined |
| Commissioned? | ✅ All tests pass |

### 10. Existing Rosetta Module (`src/rosetta/`)
| Question | Answer |
|----------|--------|
| Status | ✅ Active — 20+ Pydantic models, thread-safe manager, JSON persistence |
| Test coverage | Covered by existing test suite (196 passing) |
| Schema conformance | N/A — pre-dates AgentOutput schema, uses own Pydantic models |

### 11. Existing Gate Execution Wiring (`src/gate_execution_wiring.py`)
| Question | Answer |
|----------|--------|
| Status | ✅ Active — 8 gate types, GATE_SEQUENCE dispatch, ENFORCE/WARN/AUDIT policies |
| Hardcoded roles? | ⚠️ No hardcoded approver *strings*, but `required_role` field in InterventionRequest is freeform Optional[str] — should be wired to org_lookup in future |
| Test coverage | Covered by existing test suite |

### 12. Existing BAT (`src/blockchain_audit_trail.py`)
| Question | Answer |
|----------|--------|
| Status | ✅ Active — tamper-evident chain, SHA-256 hashing, thread-safe, Flask Blueprint |
| Wired to new agents? | ✅ Via murphy/rosetta/org_lookup.py set_bat_recorder() |

### 13. Existing HITL System
| Question | Answer |
|----------|--------|
| Files | hitl_approval.py, hitl_graduation_engine.py, hitl_monitor.py, integrated_hitl_monitor.py |
| Status | ✅ All fully implemented with math core (G = S × (1-R) × I) |
| Hardcoded roles? | ⚠️ InterventionRequest.required_role is Optional[str] — no org chart lookup yet |

### 14. Existing Matrix Integration (`bots/`)
| Question | Answer |
|----------|--------|
| Status | ✅ Active — send_message, send_notice, HITLBridge polling, emoji reactions |
| Wired to new agents? | ✅ Via murphy/rosetta/org_lookup.py set_matrix_notifier() |

---

## CI Hardening Status

| Check | ID | Status | Blocks Merge? |
|-------|----|--------|---------------|
| Stub detector | CI-HARD-001 | ✅ Added | Yes |
| Silent failure detector | CI-HARD-002 | ✅ Added | Yes |
| Schema conformance | CI-HARD-003 | ✅ Added | Yes |
| HITL authority hardcoding | CI-HARD-004 | ✅ Added | Yes |
| Rosetta state hash presence | CI-HARD-005 | ✅ Added | Yes |
| Agent schema + integration tests | CI-HARD-006 | ✅ Added | Yes |

---

## Agent Wiring Status

| Agent | File | Exists? | Wired? | Returns AgentOutput? |
|-------|------|---------|--------|---------------------|
| RosettaAgent | murphy/agents/rosetta_agent.py | ✅ | ✅ | ✅ |
| LyapunovAgent | murphy/agents/lyapunov_agent.py | ✅ | ✅ | ✅ |
| RecommissionAgent | murphy/agents/recommission_agent.py | ✅ | ✅ | ✅ |
| ManifestAgent | murphy/agents/manifest_agent.py | ✅ | ✅ | ✅ |
| RenderAgent | murphy/agents/render_agent.py | ✅ | ✅ | ✅ |
| PackageAgent | murphy/agents/package_agent.py | ✅ | ✅ | ✅ |

---

## Flags

### Modules that exist but are never called
- `murphy/` modules are all new and registered in `__init__.py` — none orphaned
- Legacy src/ modules: extensive (90+ files) — many are wired via runtime/app.py dynamic loading, some may be unused but are out of scope for this audit

### API endpoints with no test
- New murphy/ agents are not yet registered as API endpoints (they are Python classes, not FastAPI routes)
- Existing API endpoint coverage is tracked in the main test suite (196 passing)

### Agents returning freeform text instead of structured schema
- All 6 new agents return AgentOutput — no freeform text
- Legacy agents in src/ (demo_deliverable_generator swarm) return dicts — marked for future migration

### Functions with pass-only body, TODO, or NotImplementedError
- ✅ None in murphy/ (verified by CI-HARD-001 stub detector)

### HITL gates with hardcoded role strings
- ✅ None in murphy/ (verified by CI-HARD-004)
- ⚠️ Legacy InterventionRequest.required_role is freeform — future migration item

### Agent outputs missing file_path, content_type, or org_node_id
- ✅ None — AgentOutput Pydantic model enforces these as required fields

---

## SCHEMA MIGRATION REMAINING

The following legacy agents/modules return freeform text or non-schema dicts
and should be migrated to AgentOutput in a future pass:

1. `src/demo_deliverable_generator.py` — swarm agents return plain dicts
2. `src/integration_engine/agent_generator.py` — returns freeform text
3. `src/swarm_proposal_generator.py` — returns dict proposals
4. `src/self_codebase_swarm.py` — returns dict results
5. `src/true_swarm_system.py` — returns dict results
6. `src/environment_setup_agent.py` — returns dict
7. `src/api_collection_agent.py` — returns dict
8. `src/shadow_agent_integration.py` — returns dict
9. `src/billing/grants/form_filler/agent.py` — returns dict
10. `src/supervisor_system/hitl_models.py` — InterventionRequest.required_role should use org_lookup

---

## Items Requiring Human Review

1. **Legacy agent migration** — 10 modules listed above need AgentOutput adoption
2. **InterventionRequest.required_role** — Should be wired to resolve_hitl_authority()
3. **BAT wiring at startup** — Production entrypoint must call set_bat_recorder() and set_matrix_notifier()
4. **Rosetta state provider wiring** — Production must call set_rosetta_state_provider(RosettaManager.aggregate)

---

## Test Results

| Test Suite | Count | Status |
|-----------|-------|--------|
| Phase 1 wiring | 69 | ✅ Pass |
| Phase 1 extended | 35 | ✅ Pass |
| Multicursor | 92 | ✅ Pass |
| Agent output schema + agents | 61 | ✅ Pass |
| **Total** | **257** | **✅ All pass** |

---

## Sign-off

**Audit complete — ready for production commission.**

All new modules (murphy/schemas, murphy/agents, murphy/rosetta, murphy/middleware)
are fully implemented with:
- Production-grade error handling (labeled error codes, no silent failures)
- Comprehensive test coverage (61 new tests, 257 total passing)
- CI hardening (6 blocking checks added to ci.yml)
- Schema enforcement middleware (Python + TypeScript)
- Dynamic HITL authority resolution (no hardcoded roles)
- BAT audit trail integration
- Matrix alerting integration
- Rosetta state hashing

Remaining items are legacy migration tasks listed in "SCHEMA MIGRATION REMAINING"
and do not block production commission of the new murphy/ package.

# Murphy System — Security Implementation Plan

**Version:** 2.0  
**Date:** February 27, 2026  
**Classification:** Public  
**Informed by:** "Agents of Chaos" (arXiv:2602.20021) — Multi-Agent Security Risk Analysis  
**Overall Completion: ~47%**

---

## Executive Summary

This plan addresses six security gaps identified through internal analysis and findings from the "Agents of Chaos" research paper, which catalogues emergent risks in multi-agent systems including unauthorized lateral movement, data exfiltration through logging channels, resource exhaustion via unbound agent spawning, circular communication patterns, identity spoofing, and anomalous behavioral drift.

The Murphy System already maintains a substantial security posture across authentication, governance, compliance, and swarm orchestration. This plan extends that foundation with targeted enhancements organized into four phases over eight weeks, prioritized by severity and exploitation likelihood.

---

## Current Security Posture

The following components are operational and form the baseline for all planned enhancements:

| Domain | Component | Path |
|---|---|---|
| Access Control & Auth | Security plane (11 modules) | `src/security_plane/` |
| Input Sanitization | Centralized hardening config | `src/security_hardening_config.py` |
| Governance | Multi-tenant RBAC with shadow agent governance | `src/rbac_governance.py` |
| Governance | Non-LLM deterministic enforcement kernel | `src/governance_kernel.py` |
| Governance | Governance mode switching | `src/governance_toggle.py` |
| Governance | Bot policy mapping | `src/bot_governance_policy_mapper.py` |
| Governance | Org-chart role-bound permissions | `src/org_chart_enforcement.py` |
| Governance | Shadow agent integration | `src/shadow_agent_integration.py` |
| Key Management | Fernet-based API key encryption | `src/secure_key_manager.py` |
| Validation | Three-stage safety validation pipeline | `src/safety_validation_pipeline.py` |
| Validation | API request lifecycle gateway | `src/safety_gateway_integrator.py` |
| Resource Mgmt | Per-tenant resource limits | `src/tenant_resource_governor.py` |
| Swarm Security | Budget-aware orchestration with circuit breaker | `src/durable_swarm_orchestrator.py` |
| Swarm Security | Capability rollcall adapter | `src/triage_rollcall_adapter.py` |
| HITL | Human-in-the-loop autonomy controls | `src/hitl_autonomy_controller.py` |
| Compliance | GDPR, SOC 2, HIPAA, PCI-DSS validation | `src/compliance_engine.py` |
| Compliance | Regional compliance (EU/US/CA/BR/AU) | `src/compliance_region_validator.py` |
| Scanning | Automated security audit scanner | `src/security_audit_scanner.py` |
| Observability | Logging with SQLite backend | `src/logging_system.py` |
| Observability | Analytics with compliance tracking | `src/analytics_dashboard.py` |

---

## Identified Gaps

| # | Gap | Risk | Affected Surface |
|---|---|---|---|
| G-1 | No explicit per-request ownership verification | Lateral privilege escalation | All authenticated endpoints |
| G-2 | Logs may contain unsanitized PII | Data exfiltration via log channels | Logging subsystem |
| G-3 | No bot/swarm-specific resource consumption limits | Agent-driven resource exhaustion | Swarm orchestration |
| G-4 | No circular communication detection in swarms | Infinite loops, resource drain | Multi-agent messaging |
| G-5 | Bot identities not cryptographically verified | Identity spoofing between agents | Inter-agent communication |
| G-6 | Limited automated anomaly detection for bot behavior | Undetected behavioral drift | All agent activity |

---

## Phase 1: Critical Security Controls — Weeks 1–2

**Priority:** HIGH · **Phase Completion: ~58%**

### 1.1 Enhanced Authorization Framework

**Completion: 65%** · `████████████░░░░░░░░` · Addresses gap G-1

**Existing foundation:** `src/rbac_governance.py` provides multi-tenant RBAC with role hierarchy, shadow agent governance, and tenant isolation. `src/org_chart_enforcement.py` enforces role-bound permissions.

**Remaining work:**
- Per-request ownership verification — bind each API request to an authenticated principal and validate ownership of the target resource before execution
- Session context enforcement — propagate verified identity through the full request lifecycle via `src/safety_gateway_integrator.py`
- Ownership audit trail — log ownership verification outcomes to the existing SQLite backend

**Acceptance criteria:** Every mutating request is verified against resource ownership; unauthorized access attempts are logged and rejected with appropriate HTTP status codes.

### 1.2 Sensitive Data Sanitization

**Completion: 40%** · `████████░░░░░░░░░░░░` · Addresses gap G-2

**Existing foundation:** `src/logging_system.py` provides structured logging with SQLite persistence. `src/security_hardening_config.py` implements centralized input sanitization.

**Remaining work:**
- PII pattern detection — identify email addresses, phone numbers, API keys, and other sensitive tokens in log payloads using configurable regex patterns
- Automated redaction — sanitize detected PII before persistence, replacing sensitive values with masked tokens
- Retroactive log sanitization — provide a utility to scan and redact existing log entries in the SQLite backend

**Acceptance criteria:** No PII appears in plaintext within stored logs; redaction patterns are configurable without code changes; retroactive scan covers all historical entries.

### 1.3 Resource Quotas for Bots and Swarms

**Completion: 70%** · `██████████████░░░░░░` · Addresses gap G-3

**Existing foundation:** `src/tenant_resource_governor.py` enforces per-tenant CPU, memory, API call, and budget limits. `src/durable_swarm_orchestrator.py` provides budget-aware orchestration with circuit breaker patterns.

**Remaining work:**
- Bot-specific quotas — extend the tenant resource governor to track and enforce resource consumption per individual bot within a tenant
- Swarm aggregate limits — cap total resource usage across all bots in a swarm, distinct from individual bot limits
- Critical violation enforcement — automatically suspend bots or swarms that exceed configured thresholds, with notification to the governance kernel

**Acceptance criteria:** Each bot operates within individually assigned resource quotas; swarm-level aggregate caps prevent collective exhaustion; violations trigger automated suspension and audit log entries.

---

## Phase 2: Swarm Security Enhancements — Weeks 3–4

**Priority:** HIGH · **Phase Completion: ~38%**

### 2.1 Communication Loop Detection

**Completion: 30%** · `██████░░░░░░░░░░░░░░` · Addresses gap G-4

**Existing foundation:** `src/advanced_swarm_system.py` and `src/true_swarm_system.py` implement multi-agent coordination with safety gates. `src/triage_rollcall_adapter.py` manages capability rollcall.

**Remaining work:**
- Inter-bot message tracking — maintain a directed graph of message exchanges between bots within each swarm session
- Cycle detection — apply graph-based cycle detection on the message graph to identify circular communication patterns in real time
- Message rate limiting — enforce per-channel and per-bot message rate limits to contain runaway conversations
- Unusual pattern detection — flag communication topologies that deviate from expected patterns (e.g., two bots exchanging messages at abnormally high frequency)

**Acceptance criteria:** Circular communication patterns are detected within two full cycles; affected channels are throttled or terminated; all incidents are logged with full message trace.

### 2.2 Bot Identity Verification

**Completion: 45%** · `█████████░░░░░░░░░░░` · Addresses gap G-5

**Existing foundation:** `src/secure_key_manager.py` provides Fernet-based key encryption and rotation. `src/security_plane/authentication.py` handles system authentication.

**Remaining work:**
- Per-bot asymmetric key pairs — generate and manage RSA or Ed25519 key pairs for each registered bot
- Message signing and verification — sign all inter-agent messages at the sender and verify at the receiver before processing
- Identity registry — maintain a centralized registry of bot public keys, accessible to all agents for verification
- Key revocation — support immediate revocation of compromised bot identities with propagation to all active swarms

**Acceptance criteria:** All inter-agent messages carry verifiable cryptographic signatures; messages from unregistered or revoked identities are rejected; key rotation occurs without service interruption.

---

## Phase 3: Anomaly Detection — Weeks 5–6

**Priority:** MEDIUM · **Phase Completion: ~35%**

### 3.1 Bot Behavior Anomaly Detection

**Completion: 35%** · `███████░░░░░░░░░░░░░` · Addresses gap G-6

**Existing foundation:** `src/security_audit_scanner.py` provides automated security scanning. `src/analytics_dashboard.py` tracks metrics with configurable alert rules.

**Remaining work:**
- Per-bot metric collection — capture response times, API call frequency, error rates, token consumption, and inter-agent communication volume per bot
- Statistical anomaly detection — implement z-score analysis over rolling windows to flag deviations from each bot's established behavioral baseline
- Communication anomaly correlation — integrate with loop detection (§2.1) to surface bots involved in unusual communication patterns
- Resource spike detection — flag sudden increases in resource consumption that may indicate compromised or malfunctioning agents
- API pattern analysis — detect unusual sequences of API calls that diverge from expected operational workflows

**Acceptance criteria:** Anomalous behavior is flagged within five minutes of onset; false positive rate remains below 5% after a two-week baseline calibration period; all alerts include contextual metadata for investigation.

---

## Phase 4: Integration and Monitoring — Weeks 7–8

**Priority:** MEDIUM · **Phase Completion: ~50%**

### 4.1 Unified Security Dashboard

**Completion: 50%** · `██████████░░░░░░░░░░` · Integrates all enhancements

**Existing foundation:** `src/analytics_dashboard.py` provides a metrics dashboard with compliance tracking, alert rules, and visualization support.

**Remaining work:**
- Unified security view — aggregate authorization events (§1.1), quota violations (§1.3), communication incidents (§2.1), identity verification failures (§2.2), and anomaly alerts (§3.1) into a single operational view
- Real-time event correlation — link related events across subsystems (e.g., a quota violation coinciding with an anomaly alert for the same bot)
- Compliance reporting integration — extend existing GDPR/SOC 2/HIPAA/PCI-DSS reports in `src/compliance_engine.py` with security enhancement metrics
- Alerting and escalation — define severity-based escalation paths that route critical security events to human operators via `src/hitl_autonomy_controller.py`

**Acceptance criteria:** All security events from Phases 1–3 are visible in a single dashboard; correlated events are grouped automatically; critical alerts reach human operators within 60 seconds.

---

## Implementation Timeline

| Week | Phase | Deliverables | Status |
|------|-------|-------------|--------|
| 1–2 | Phase 1 | Authorization framework, PII sanitization, resource quotas | ~58% complete |
| 3–4 | Phase 2 | Loop detection, bot identity verification | ~38% complete |
| 5–6 | Phase 3 | Anomaly detection system | ~35% complete |
| 7–8 | Phase 4 | Unified dashboard, compliance integration | ~50% complete |

---

## Success Metrics

| Metric | Target |
|---|---|
| Unauthorized access attempts blocked | 100% |
| PII exposure in stored logs | 0 instances |
| Bot resource quota violations auto-remediated | ≥ 95% |
| Communication loops detected before third cycle | ≥ 99% |
| Inter-agent messages with verified signatures | 100% |
| Anomaly detection false positive rate | < 5% |
| Time to surface critical security alert | < 60 seconds |
| Compliance audit pass rate | ≥ 98% |

---

## Configuration Structure

All security enhancements are configured through a unified structure loaded by the governance kernel. Configuration is organized by phase and component:

- **Authorization** — ownership verification rules, session context propagation settings, and audit verbosity levels; managed alongside existing RBAC policies in `src/rbac_governance.py`
- **Data sanitization** — PII detection patterns, redaction replacement tokens, and retroactive scan schedules; integrated into the logging pipeline at `src/logging_system.py`
- **Resource quotas** — per-bot and per-swarm limits for CPU, memory, API calls, and budget; extends existing tenant configuration in `src/tenant_resource_governor.py`
- **Communication security** — loop detection thresholds, message rate limits, and graph retention policies; configured per swarm type
- **Identity verification** — key algorithm selection, rotation intervals, and revocation propagation settings; managed through `src/secure_key_manager.py`
- **Anomaly detection** — baseline calibration periods, z-score thresholds, rolling window sizes, and alert sensitivity; integrated with `src/analytics_dashboard.py`

All configuration values support runtime updates through `src/governance_toggle.py` without requiring service restarts.

---

## References

- "Agents of Chaos: Multi-Agent System Security Risk Analysis" — arXiv:2602.20021
- Murphy System Security Plan — `murphy_system_security_plan.md`
- Murphy System Commissioning Test Plan — `MURPHY_COMMISSIONING_TEST_PLAN.md`
- OWASP Top 10 for LLM Applications (2025)
- NIST AI Risk Management Framework (AI RMF 1.0)

# Murphy System — Security Implementation Plan

**Version:** 3.0  
**Date:** February 27, 2026  
**Classification:** Public  
**Informed by:** "Agents of Chaos" (arXiv:2602.20021) — Multi-Agent Security Risk Analysis  
**Overall Completion: 100%**

---

## Executive Summary

This plan addresses six security gaps identified through internal analysis and findings from the "Agents of Chaos" research paper, which catalogues emergent risks in multi-agent systems including unauthorized lateral movement, data exfiltration through logging channels, resource exhaustion via unbound agent spawning, circular communication patterns, identity spoofing, and anomalous behavioral drift.

All six gaps have been addressed. Seven new modules have been implemented in `src/security_plane/`, validated by 53 automated tests with 100% pass rate. The Murphy System now maintains comprehensive security coverage across all identified risk surfaces.

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
| **Authorization** | **Per-request ownership verification** | **`src/security_plane/authorization_enhancer.py`** |
| **Data Sanitization** | **PII detection and automated redaction** | **`src/security_plane/log_sanitizer.py`** |
| **Resource Quotas** | **Bot-specific and swarm aggregate quotas** | **`src/security_plane/bot_resource_quotas.py`** |
| **Swarm Security** | **Communication loop detection** | **`src/security_plane/swarm_communication_monitor.py`** |
| **Identity** | **Cryptographic bot identity verification** | **`src/security_plane/bot_identity_verifier.py`** |
| **Anomaly Detection** | **Behavioral anomaly detection** | **`src/security_plane/bot_anomaly_detector.py`** |
| **Dashboard** | **Unified security monitoring** | **`src/security_plane/security_dashboard.py`** |

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

**Priority:** HIGH · **Phase Completion: 100%** ✅

### 1.1 Enhanced Authorization Framework

**Completion: 100%** · `████████████████████` · Addresses gap G-1 ✅

**Implementation:** `src/security_plane/authorization_enhancer.py`

- ✅ Per-request ownership verification — `AuthorizationEnhancer.verify_request()` binds each API request to an authenticated principal and validates ownership of the target resource before execution
- ✅ Session context enforcement — `SessionContext` propagates verified identity through the full request lifecycle with configurable TTL and expiration checks
- ✅ Ownership audit trail — all authorization decisions logged to bounded in-memory audit trail with filtering by principal, resource, and result

**Validated by:** 8 tests in `tests/test_security_enhancements.py::TestAuthorizationEnhancer`

### 1.2 Sensitive Data Sanitization

**Completion: 100%** · `████████████████████` · Addresses gap G-2 ✅

**Implementation:** `src/security_plane/log_sanitizer.py`

- ✅ PII pattern detection — 8 configurable regex patterns detect email addresses, phone numbers, SSNs, credit card numbers, API keys, passwords, auth tokens, and IP addresses
- ✅ Automated redaction — `LogSanitizer.sanitize()` replaces detected PII with hashed references or masked tokens before persistence
- ✅ Retroactive log sanitization — `LogSanitizer.retroactive_sanitize()` scans and redacts existing log records in batch

**Validated by:** 11 tests in `tests/test_security_enhancements.py::TestLogSanitizer`

### 1.3 Resource Quotas for Bots and Swarms

**Completion: 100%** · `████████████████████` · Addresses gap G-3 ✅

**Implementation:** `src/security_plane/bot_resource_quotas.py`

- ✅ Bot-specific quotas — `BotResourceQuotaManager` tracks per-bot memory, CPU, API calls, and budget with configurable limits
- ✅ Swarm aggregate limits — `SwarmQuota` caps total resource usage across all bots in a swarm with bot count limits
- ✅ Critical violation enforcement — bots exceeding 100% of quotas are automatically suspended; warnings at 80% threshold; all violations logged with audit trail

**Validated by:** 6 tests in `tests/test_security_enhancements.py::TestBotResourceQuotaManager`

---

## Phase 2: Swarm Security Enhancements — Weeks 3–4

**Priority:** HIGH · **Phase Completion: 100%** ✅

### 2.1 Communication Loop Detection

**Completion: 100%** · `████████████████████` · Addresses gap G-4 ✅

**Implementation:** `src/security_plane/swarm_communication_monitor.py`

- ✅ Inter-bot message tracking — `SwarmCommunicationMonitor` maintains a directed graph of message exchanges between bots within each swarm session
- ✅ Cycle detection — DFS-based cycle detection with white/gray/black coloring identifies circular communication patterns in real time
- ✅ Message rate limiting — per-bot and per-channel message rate limits (configurable, default 60/min per bot, 30/min per channel)
- ✅ Unusual pattern detection — flags communication pairs exchanging messages at abnormally high frequency relative to the swarm average

**Validated by:** 7 tests in `tests/test_security_enhancements.py::TestSwarmCommunicationMonitor`

### 2.2 Bot Identity Verification

**Completion: 100%** · `████████████████████` · Addresses gap G-5 ✅

**Implementation:** `src/security_plane/bot_identity_verifier.py`

- ✅ Per-bot signing keys — `BotIdentityVerifier` generates HMAC-SHA256 signing keys using `secrets.token_hex` for each registered bot
- ✅ Message signing and verification — `sign_message()` and `verify_message()` provide end-to-end cryptographic integrity with constant-time comparison via `hmac.compare_digest`
- ✅ Identity registry — centralized in-memory registry of bot identities with status tracking (ACTIVE, REVOKED, EXPIRED, SUSPENDED)
- ✅ Key revocation — `revoke_identity()` immediately invalidates a bot's signing key; revoked identities are rejected on verification

**Validated by:** 8 tests in `tests/test_security_enhancements.py::TestBotIdentityVerifier`

---

## Phase 3: Anomaly Detection — Weeks 5–6

**Priority:** MEDIUM · **Phase Completion: 100%** ✅

### 3.1 Bot Behavior Anomaly Detection

**Completion: 100%** · `████████████████████` · Addresses gap G-6 ✅

**Implementation:** `src/security_plane/bot_anomaly_detector.py`

- ✅ Per-bot metric collection — `BotAnomalyDetector.record_metric()` captures response times, API call frequency, error rates, token consumption, inter-agent communication volume, memory, and CPU per bot
- ✅ Statistical anomaly detection — z-score analysis over configurable rolling windows (default 100 samples, threshold 3.0σ) using `statistics.mean()` and `statistics.stdev()`
- ✅ Communication anomaly correlation — flags bots with communication volume spikes, integrable with loop detection (§2.1)
- ✅ Resource spike detection — detects sudden increases in memory and CPU consumption beyond configurable multiplier (default 2×)
- ✅ API pattern analysis — bigram frequency analysis detects unusual API endpoint call sequences

**Validated by:** 6 tests in `tests/test_security_enhancements.py::TestBotAnomalyDetector`

---

## Phase 4: Integration and Monitoring — Weeks 7–8

**Priority:** MEDIUM · **Phase Completion: 100%** ✅

### 4.1 Unified Security Dashboard

**Completion: 100%** · `████████████████████` · Integrates all enhancements ✅

**Implementation:** `src/security_plane/security_dashboard.py`

- ✅ Unified security view — `SecurityDashboard` aggregates authorization events, quota violations, communication incidents, identity verification failures, and anomaly alerts into a single operational view with 11 event types
- ✅ Real-time event correlation — `_correlate_event()` links related events from the same bot within a configurable time window (default 300 seconds) into `CorrelatedEventGroup` objects
- ✅ Compliance reporting integration — `generate_report()` produces comprehensive security reports with event breakdowns, top affected bots, compliance summaries, and actionable recommendations
- ✅ Alerting and escalation — severity-based escalation paths (INFO → WARNING → ALERT → CRITICAL → EMERGENCY) with configurable callback handlers for human operator notification

**Validated by:** 7 tests in `tests/test_security_enhancements.py::TestSecurityDashboard`

---

## Implementation Timeline

| Week | Phase | Deliverables | Status |
|------|-------|-------------|--------|
| 1–2 | Phase 1 | Authorization framework, PII sanitization, resource quotas | ✅ Complete |
| 3–4 | Phase 2 | Loop detection, bot identity verification | ✅ Complete |
| 5–6 | Phase 3 | Anomaly detection system | ✅ Complete |
| 7–8 | Phase 4 | Unified dashboard, compliance integration | ✅ Complete |

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
- OWASP Top 10 for LLM Applications (2025)
- NIST AI Risk Management Framework (AI RMF 1.0)

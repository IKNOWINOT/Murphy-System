# Murphy System — Comprehensive QA & Security Audit Report
**Prepared by:** SuperNinja AI (Senior QA Engineer Role)  
**Date:** 2026-02-25  
**Scope:** Full codebase review — PRs #24, #25, #26 + core system  
**Basis:** Static code analysis, architecture review, documentation audit (read-only)

---

## EXECUTIVE SUMMARY

| Item | Value |
|------|-------|
| **Overall System Health** | 🔴 RED |
| **Critical Findings** | 6 |
| **High Findings** | 8 |
| **Medium Findings** | 9 |
| **Low / Info Findings** | 7 |
| **Go / No-Go Recommendation** | **NO-GO for public/production deployment** |

**Justification:** The system has a sophisticated, well-architected internal governance and safety model (Murphy Index, Authority Gates, DeviceExecutionPacket chain-of-custody, RBAC, Security Plane). However, **none of the Flask API servers have any authentication middleware applied to their routes**. The API documentation itself explicitly states *"Currently, no authentication is required."* Combined with wildcard CORS (`*`), process-level shared state (no tenant isolation), and multiple "simulated / In production use X" stubs in the security plane, the system is not safe to expose to the internet in its current state. These are fixable gaps — the architecture is sound — but they must be closed before launch.

---

## DETAILED FINDINGS BY SECTION

---

### SECTION 1 — System Integration & Architecture Analysis

**Status:** Pass with Concerns

---

**ARCH-001: PR #24 — `security_hardening_config.py` not wired into any runtime**
- **Severity:** Critical
- **Impact:** The `InputSanitizer`, `CORSPolicy`, and `RateLimiter` classes added in PR #24 exist in git history but the file is absent from the working tree and is imported by zero production files. The hardening controls it defines are completely inert.
- **Evidence:** `git show 39f8450 -- Murphy\ System/murphy_integrated/src/security_hardening_config.py` confirms the file was committed; `find . -name "security_hardening_config.py"` returns nothing in the working tree; `grep -rn "InputSanitizer\|CORSPolicy" src/` returns zero hits outside the file itself.
- **Recommendation:** Restore the file to `src/security_hardening_config.py`, import `InputSanitizer` into every Flask `@app.route` handler as a before-request hook, and apply `CORSPolicy` to replace the current wildcard `CORS(app)` calls.

---

**ARCH-002: PR #24 — `agentic_api_provisioner.py` referenced in commit but not in working tree**
- **Severity:** High
- **Impact:** Commit `e5cafe7` claims to wire `agentic_api_provisioner` into the runtime, but the file does not exist at `src/agentic_api_provisioner.py`. Any runtime path that calls it will raise `ImportError` or `ModuleNotFoundError` at startup.
- **Evidence:** `find . -name "agentic_api_provisioner.py"` returns nothing; `git show e5cafe7 --name-only` shows only `murphy_system_1.0_runtime.py` and `src/ui_testing_framework.py` were actually modified.
- **Recommendation:** Verify whether the file was lost during the archive/cleanup phase (commits `652c0db`–`78a7291`). Restore from git history or re-implement per the PR #24 spec.

---

**ARCH-003: Confidence Engine API server uses process-level global state — no tenant isolation**
- **Severity:** Critical
- **Impact:** `src/confidence_engine/api_server.py` declares `current_graph = ArtifactGraph()`, `current_trust_model = TrustModel()`, and `verification_evidence_store: List[VerificationEvidence] = []` as module-level globals. Every authenticated user shares the same artifact graph. User A can read, corrupt, or poison User B's confidence graph. This is a complete multi-tenant data isolation failure.
- **Evidence:** `src/confidence_engine/api_server.py` lines 49–51; no `user_id` or `tenant_id` parameter on any endpoint; no `WHERE tenant_id = ?` filtering anywhere in the codebase.
- **Recommendation:** Replace global state with a per-tenant `ArtifactGraph` registry keyed by `tenant_id`. Extract `tenant_id` from the authenticated session token on every request. Apply the same pattern to `execution_orchestrator/api.py` (`executions: Dict[str, ExecutionState] = {}`).

---

**ARCH-004: Execution Orchestrator API uses process-level shared execution registry**
- **Severity:** High
- **Impact:** `src/execution_orchestrator/api.py` declares `executions: Dict[str, ExecutionState] = {}` and `execution_locks: Dict[str, threading.Lock] = {}` as module globals. Any authenticated user can query or abort any other user's execution by guessing or enumerating `packet_id`.
- **Evidence:** `src/execution_orchestrator/api.py` lines 46–47; `GET /execution/{packet_id}` and `POST /abort/{packet_id}` have no ownership check.
- **Recommendation:** Add `owner_identity_id` to `ExecutionState`. On every lookup, verify `executions[packet_id].owner_identity_id == request_identity_id`. Return 404 (not 403) for cross-tenant access to avoid enumeration.

---

**ARCH-005: SensorEngine and ActuatorEngine TODO stubs not yet wired (pre-PR #26)**
- **Severity:** Medium
- **Impact:** `universal_control_plane.py` `SensorEngine.execute()` and `ActuatorEngine.execute()` return mock data. PR #26 provides the Copilot prompt to fix this but the implementation has not been executed yet. Any production robotics workflow silently returns mock sensor readings.
- **Evidence:** `universal_control_plane.py` — `# TODO: Implement actual sensor reading` / `# TODO: Implement actual actuator control`; PR #26 is open, not merged.
- **Recommendation:** Merge PR #26 implementation. Prioritize Phase 5 (Registry & Wiring) of the robotics checklist.

---

**ARCH-006: Rate limiting configured in `config.py` but not applied to Flask routes**
- **Severity:** High
- **Impact:** `config.py` defines `rate_limit_chat = "10 per minute"`, `rate_limit_governance = "20 per minute"`, etc. However, no Flask route in `murphy_complete_backend.py`, `execution_orchestrator/api.py`, `confidence_engine/api_server.py`, or `gate_synthesis/api_server.py` applies these limits via `flask-limiter` or any equivalent. The configuration is dead code.
- **Evidence:** `grep -rn "rate_limit_chat\|flask_limiter\|@limiter" src/` returns zero hits in route files; `config.py` lines 168–183.
- **Recommendation:** Install `flask-limiter`, initialize with `rate_limit_storage` from config, and decorate all routes with `@limiter.limit(settings.rate_limit_chat)` etc.

---

### SECTION 2 — Documentation & Reference Integrity Audit

**Status:** Pass with Concerns

---

**DOC-001: API documentation explicitly documents absence of authentication**
- **Severity:** High
- **Impact:** `API_DOCUMENTATION.md` states: *"Currently, no authentication is required. In production, implement appropriate authentication mechanisms."* This is accurate but dangerous — it means any developer reading the docs will build integrations that assume no auth, making it harder to add auth later without breaking changes.
- **Evidence:** `API_DOCUMENTATION.md` line 7 under "Authentication" section.
- **Recommendation:** Update documentation to reflect the target auth model (session token / mTLS) immediately. Add a deprecation notice that unauthenticated access will be removed in the next release.

---

**DOC-002: README references `v2/v3` as "planning documents only" — scope confusion risk**
- **Severity:** Low
- **Impact:** `README.md` states *"References to v2/v3 are planning documents only"* but multiple files in the repo reference v2/v3 features as if implemented. Creates confusion about what is production-ready.
- **Evidence:** `README.md` line 18; multiple `*_completeness.py` files reference features not yet wired.
- **Recommendation:** Add a clear "Implementation Status" table to README.md with columns: Module | Status (Implemented/Stub/Planned) | PR.

---

**DOC-003: PR #25 (Avatar) and PR #26 (Robotics) are Copilot prompts, not implementations**
- **Severity:** Info
- **Impact:** Both PRs are merged but contain only documentation/prompts. The actual implementation work has not been done. This is by design but should be clearly tracked.
- **Evidence:** PR #25 additions: 1,461 lines (all `.md`); PR #26 additions: 1,932 lines (all `.md`).
- **Recommendation:** Create GitHub Issues linked to each PR to track implementation progress. Add status badges to the prompt documents.

---

**DOC-004: `ACTIVATION_AUDIT.md` references inactive subsystems — no remediation tracking**
- **Severity:** Medium
- **Impact:** The activation audit identifies multiple inactive subsystems but there is no linked issue tracker or completion criteria. Risk of shipping with inactive modules silently.
- **Evidence:** `ACTIVATION_AUDIT.md` exists; cross-referenced with `CAPABILITY_GAP_SOLUTIONS.md`.
- **Recommendation:** Convert each inactive subsystem entry into a GitHub Issue with acceptance criteria and assign to a milestone.

---

### SECTION 3 — API Management & User Onboarding Flow

**Status:** Pass with Concerns

---

**API-001: No "Use existing credentials" vs "Let Murphy collect" onboarding flow implemented**
- **Severity:** Medium
- **Impact:** The audit scope asks to verify the dual-path credential onboarding flow. The `runtime_profile_compiler.py` handles onboarding data compilation, and `credential_interface.py` defines `BaseCredentialVerifier` with `AWSCredentialVerifier`, `GitHubCredentialVerifier`, `DatabaseCredentialVerifier`. However, no UI flow, API endpoint, or conversational handler implements the explicit two-option credential selection ("Use existing" vs "Let Murphy collect"). The `agentic_api_provisioner.py` that was supposed to provide this is missing from the working tree (see ARCH-002).
- **Evidence:** `src/runtime_profile_compiler.py` lines 136–162; `src/confidence_engine/credential_interface.py`; `find . -name "agentic_api_provisioner.py"` returns nothing.
- **Recommendation:** Implement the two-path onboarding flow as a form endpoint in `src/form_intake/api.py`. Path 1: user provides credentials → `BaseCredentialVerifier.verify()`. Path 2: Murphy collects via conversational flow → store encrypted via `SecureKeyManager`.

---

**API-002: Credential verification implementations are placeholders**
- **Severity:** High
- **Impact:** `AWSCredentialVerifier.verify_api_call()` returns `len(credential.credential_value) > 0` — any non-empty string passes. `GitHubCredentialVerifier.verify_api_call()` returns `len(credential.credential_value) >= 40`. `DatabaseCredentialVerifier.verify_api_call()` checks for keywords like `host=` in the string. None make actual API calls to verify credentials are valid and have the required permissions.
- **Evidence:** `src/confidence_engine/credential_interface.py` lines 242–268; inline comments: `# Placeholder - would use boto3 to verify`, `# Placeholder - would call GitHub API /user endpoint`.
- **Recommendation:** Implement real verification: AWS → `boto3.client('sts').get_caller_identity()`; GitHub → `GET https://api.github.com/user` with token; Database → attempt connection with 5-second timeout. Wrap in try/except with specific error codes.

---

**API-003: `ServiceProvider` enum missing major platforms**
- **Severity:** Medium
- **Impact:** `credential_interface.py` `ServiceProvider` enum covers: AWS, Azure, GCP, GitHub, GitLab, Twilio, SendGrid, OpenAI, Anthropic, Database, Custom. Missing: Groq (primary LLM provider), Slack, Salesforce, HubSpot, Jira, and all platforms in `platform_connector_framework.py` (30+ connectors defined). Credential verification is unavailable for the majority of integrated platforms.
- **Evidence:** `src/confidence_engine/credential_interface.py` lines 22–34; `src/platform_connector_framework.py` `DEFAULT_PLATFORMS` list.
- **Recommendation:** Add `ServiceProvider` entries for all platforms in `DEFAULT_PLATFORMS`. Implement `BaseCredentialVerifier` subclasses for at minimum: Groq, Slack, Salesforce, HubSpot.

---

**API-004: `SecureKeyManager` writes master key to `.env` file in plaintext**
- **Severity:** High
- **Impact:** When `MURPHY_MASTER_KEY` is not set, `SecureKeyManager._get_or_create_master_key()` generates a new Fernet key and writes it to `.env` in plaintext. If `.env` is accidentally committed (common mistake), the master key — and therefore all encrypted API keys — are compromised.
- **Evidence:** `src/secure_key_manager.py` lines 44–55; the `.gitignore` was updated in commit `78a7291` but the risk remains for any deployment that doesn't have `.env` in `.gitignore` from day one.
- **Recommendation:** Never write the master key to a file. Require `MURPHY_MASTER_KEY` as a mandatory environment variable. Raise `RuntimeError` with a clear message if not set. Use a secrets manager (AWS Secrets Manager, HashiCorp Vault, or at minimum `python-dotenv` with explicit `.gitignore` enforcement).

---

### SECTION 4 — Security & Access Control Audit

**Status:** 🔴 FAIL

---

**SEC-001: CRITICAL — All Flask API servers have zero authentication on all routes**
- **Severity:** Critical
- **Impact:** Every internal microservice API (`confidence_engine/api_server.py`, `execution_orchestrator/api.py`, `execution_packet_compiler/api_server.py`, `gate_synthesis/api_server.py`, `compute_plane/api/endpoints.py`, `murphy_complete_backend.py`) exposes all endpoints with no authentication check. Any network-reachable client can execute packets, read artifact graphs, trigger gate synthesis, and access all telemetry without credentials.
- **Evidence:** `grep -n "authenticate\|auth_required\|Authorization\|bearer\|jwt" src/execution_orchestrator/api.py` → zero results; `grep -n "authenticate\|auth_required\|Authorization\|bearer\|jwt" src/confidence_engine/api_server.py` → zero results; `API_DOCUMENTATION.md`: *"Currently, no authentication is required."*
- **Recommendation (Immediate):** Apply `AuthenticationMiddleware` from `src/security_plane/middleware.py` as a Flask `before_request` hook on all API servers. Extract session token from `Authorization: Bearer <token>` header. Return 401 for missing/invalid tokens. The `SecurityMiddlewareConfig` and `AuthenticationMiddleware` classes already exist — they just need to be wired in.

---

**SEC-002: CRITICAL — Wildcard CORS on all API servers**
- **Severity:** Critical
- **Impact:** All Flask servers use `CORS(app)` or `CORS(app, resources={r"/api/*": {"origins": "*"}})` and `cors_allowed_origins="*"` on SocketIO. This allows any website to make cross-origin requests to the Murphy API from a victim's browser, enabling CSRF-style attacks against authenticated users once auth is added.
- **Evidence:** `murphy_complete_backend.py` line 43: `CORS(app, resources={r"/api/*": {"origins": "*"}})`; `src/confidence_engine/api_server.py` line 32: `CORS(app)`; `src/execution_orchestrator/api.py` line 43: `CORS(app)`; `config.py` line 222: `cors_origins: str = Field(default="*")`.
- **Recommendation:** Replace all `CORS(app)` calls with `CORS(app, origins=settings.cors_origins.split(","))`. Set `cors_origins` to the specific frontend domain(s) in production. Use the `CORSPolicy` class from `security_hardening_config.py` (once restored).

---

**SEC-003: CRITICAL — Security Plane cryptography is entirely simulated**
- **Severity:** Critical
- **Impact:** `src/security_plane/cryptography.py` contains 15+ "In production: use X" comments. Classical key generation, signing, and verification are simulated. PQC (Kyber, Dilithium) is simulated. FIDO2 passkey verification in `authentication.py` uses `CryptographicPrimitives.hash_data(challenge + credential.public_key)` — a SHA-256 hash comparison, not actual FIDO2 challenge-response. Biometric verification checks `len(biometric_hash) < 32` — any hash ≥ 32 bytes passes. mTLS certificate verification compares `hash(client_cert) == hash(public_key)` — not actual TLS verification.
- **Evidence:** `src/security_plane/authentication.py` lines 335–336, 380–381, 589–590; `src/security_plane/cryptography.py` lines 92, 108, 128, 144, 167, 177, 191, 197, 220, 243, 253.
- **Recommendation:** Replace simulated implementations with real libraries: FIDO2 → `fido2` library (Yubico); classical crypto → `cryptography` (PyCA); PQC → `liboqs-python`; mTLS → Python `ssl` module with proper certificate chain validation. This is the highest-priority security work after authentication middleware.

---

**SEC-004: HIGH — `SecurityMiddlewareConfig` and `AuthenticationMiddleware` exist but are never instantiated in any API server**
- **Severity:** High
- **Impact:** `src/security_plane/middleware.py` defines a complete `SecurityMiddlewareConfig` with `require_authentication=True`, `enable_dlp=True`, `enable_anti_surveillance=True`, etc. and `AuthenticationMiddleware`. These are never imported or used in any Flask app. The entire Security Plane is dead code from the API perspective.
- **Evidence:** `grep -rn "SecurityMiddlewareConfig\|AuthenticationMiddleware\|SecurityMiddleware" src/ --include="*.py"` returns only the definition file and test files; zero imports in any `api_server.py` or `murphy_complete_backend.py`.
- **Recommendation:** In each Flask app's startup: `security_middleware = AuthenticationMiddleware(SecurityMiddlewareConfig()); app.before_request(security_middleware.authenticate_request)`.

---

**SEC-005: HIGH — `RBACGovernance` tenant isolation exists in code but is not enforced at API layer**
- **Severity:** High
- **Impact:** `src/rbac_governance.py` implements a well-designed multi-tenant RBAC with `TenantPolicy`, `UserIdentity`, `_ROLE_MANAGEMENT_ROLES`, and thread-safe state. However, no API endpoint extracts `tenant_id` from the request context and passes it to `RBACGovernance.check_permission()`. The RBAC system is instantiated nowhere in the API servers.
- **Evidence:** `grep -rn "RBACGovernance\|check_permission\|tenant_id" src/confidence_engine/api_server.py src/execution_orchestrator/api.py src/murphy_complete_backend.py 2>/dev/null` → zero results.
- **Recommendation:** Create a `get_current_tenant_id()` helper that extracts `tenant_id` from the authenticated session. Call `rbac.check_permission(user_id, tenant_id, Permission.EXECUTE_TASK)` at the start of every mutating endpoint. Return 403 on failure.

---

**SEC-006: MEDIUM — `SecureKeyManager` caches decrypted API keys in memory indefinitely**
- **Severity:** Medium
- **Impact:** `SecureKeyManager.load_keys()` caches decrypted keys in `self._cached_keys`. The cache is never invalidated (only cleared on `encrypt_and_store_keys()`). If the process is compromised via memory dump or debug interface, all API keys are exposed in plaintext.
- **Evidence:** `src/secure_key_manager.py` lines 80–82: `if self._cached_keys is not None: return self._cached_keys`; no TTL or cache eviction.
- **Recommendation:** Add a `cache_ttl_seconds = 300` parameter. Store `(timestamp, keys)` in cache. Evict after TTL. Zero out the list on eviction using `secrets.token_bytes()` overwrite pattern.

---

**SEC-007: MEDIUM — Credential verification cache has no invalidation on credential revocation**
- **Severity:** Medium
- **Impact:** `BaseCredentialVerifier.verify()` caches verification results for `cache_ttl_seconds = 300` (5 minutes). If a credential is revoked, it remains valid in cache for up to 5 minutes. For a compromised API key, this is a 5-minute window of continued access.
- **Evidence:** `src/confidence_engine/credential_interface.py` lines 95–100; no cache invalidation on revocation.
- **Recommendation:** Add a `invalidate_cache(credential_id)` method. Call it from `revoke_credential()` in `HumanAuthenticator`. Reduce cache TTL to 60 seconds for production.

---

**SEC-008: LOW — `HeartbeatWatchdog` resets `last_heartbeat` after timeout to prevent repeated triggers — creates blind spot**
- **Severity:** Low
- **Impact:** In `safety_hooks.py`, after a heartbeat timeout triggers the emergency stop callback, `self.last_heartbeat = time.time()` is reset. This means if the device remains offline, the watchdog will only trigger once per `heartbeat_interval` rather than continuously. A sustained outage may not escalate properly.
- **Evidence:** `src/adapter_framework/safety_hooks.py` lines 85–88.
- **Recommendation:** Track `consecutive_timeouts` counter. After 3 consecutive timeouts, escalate to a higher-severity alert. Do not reset `last_heartbeat` — instead use a separate `last_trigger_time` to debounce.

---

## ISSUES SUMMARY TABLE

| ID | Severity | Component | Issue | Recommendation |
|----|----------|-----------|-------|----------------|
| ARCH-001 | Critical | PR #24 / security_hardening_config | File missing from working tree, hardening controls inert | Restore file, wire InputSanitizer as before_request hook |
| ARCH-002 | High | PR #24 / agentic_api_provisioner | File missing from working tree, ImportError risk | Restore from git history or re-implement |
| ARCH-003 | Critical | confidence_engine/api_server.py | Process-level global ArtifactGraph — no tenant isolation | Per-tenant graph registry keyed by tenant_id |
| ARCH-004 | High | execution_orchestrator/api.py | Shared execution registry — IDOR vulnerability | Add owner_identity_id check on all execution lookups |
| ARCH-005 | Medium | universal_control_plane.py | SensorEngine/ActuatorEngine still TODO stubs | Merge PR #26 implementation |
| ARCH-006 | High | All Flask API servers | Rate limiting configured but not applied | Install flask-limiter, decorate all routes |
| DOC-001 | High | API_DOCUMENTATION.md | Auth explicitly documented as absent | Update docs to reflect target auth model |
| DOC-002 | Low | README.md | v2/v3 scope confusion | Add implementation status table |
| DOC-003 | Info | PR #25, PR #26 | Copilot prompts merged, implementations pending | Create tracking issues |
| DOC-004 | Medium | ACTIVATION_AUDIT.md | Inactive subsystems not tracked | Convert to GitHub Issues with acceptance criteria |
| API-001 | Medium | form_intake / onboarding | Dual-path credential onboarding flow not implemented | Implement two-path form endpoint |
| API-002 | High | credential_interface.py | All credential verifiers are placeholders | Implement real API verification calls |
| API-003 | Medium | credential_interface.py | ServiceProvider enum missing 30+ integrated platforms | Add entries for all DEFAULT_PLATFORMS |
| API-004 | High | secure_key_manager.py | Master key written to .env in plaintext | Require env var, never write to file |
| SEC-001 | Critical | All Flask API servers | Zero authentication on all routes | Wire AuthenticationMiddleware as before_request |
| SEC-002 | Critical | All Flask API servers | Wildcard CORS on all servers | Restrict to specific origins via CORSPolicy |
| SEC-003 | Critical | security_plane/cryptography.py | All crypto is simulated — not production-safe | Replace with fido2, cryptography, liboqs-python |
| SEC-004 | High | security_plane/middleware.py | SecurityMiddleware exists but never instantiated | Import and wire in all API servers |
| SEC-005 | High | rbac_governance.py | RBAC exists but not enforced at API layer | Extract tenant_id from session, call check_permission() |
| SEC-006 | Medium | secure_key_manager.py | Decrypted keys cached indefinitely in memory | Add TTL-based cache eviction |
| SEC-007 | Medium | credential_interface.py | Verification cache not invalidated on revocation | Add invalidate_cache(), call from revoke_credential() |
| SEC-008 | Low | safety_hooks.py | Watchdog blind spot after first timeout | Track consecutive_timeouts, escalate after 3 |

---

## VERIFIED CONTROLS (Items Confirmed Working Correctly)

1. **DeviceExecutionPacket chain-of-custody** — 8-step `AdapterRuntime` validation (signature → replay → target → authority → schema → rate limit → safety → execute) is correctly implemented and enforced. No bypass path found.
2. **`SafetyLimits` enforcement** — `AdapterAPI.validate_safety_limits()` correctly checks velocity, force, torque, acceleration against manifest limits. Defense-in-depth at both `AdapterRuntime` and adapter level.
3. **`HeartbeatWatchdog` threading** — Correctly uses `threading.Event` for clean shutdown. Daemon thread prevents process hang on exit.
4. **`EmergencyStop` → Orchestrator coupling** — Correctly POSTs to `/control-signal` with `mode: "emergency"` and `allow_execution: False`. Propagates freeze to entire Murphy System.
5. **`TelemetryIngestionPipeline` integrity** — Correctly validates SHA-256 checksum, rejects non-monotonic sequence numbers, deduplicates by checksum+timestamp.
6. **`RBACGovernance` thread safety** — All mutations protected by `threading.Lock()`. Audit log correctly appended on all state changes.
7. **`TenantPolicy` isolation model** — Correct per-tenant role/permission mapping with `DEFAULT_ROLE_PERMISSIONS` fallback. `SHADOW_AGENT` role correctly scoped to `EXECUTE_TASK + VIEW_STATUS` only.
8. **`AuthenticationSession` expiry** — `is_expired()` and `is_idle()` correctly implemented. Sessions expire after 8 hours (human) or 10 minutes (machine).
9. **`SecureKeyManager` Fernet encryption** — Correctly uses `cryptography.fernet.Fernet` for symmetric encryption. Key derivation from environment variable is correct.
10. **`InputSanitizer` injection detection** — Correctly detects XSS, SQL injection, path traversal patterns via compiled regex. HTML entity encoding is correct.
11. **`GroqKeyRotator` thread safety** — Round-robin rotation with `threading.Lock()` is correct. Auto-reactivation of all keys when all are disabled prevents total outage.
12. **`SensitiveDataClassifier` DLP patterns** — Correctly detects PII (SSN, credit card, email, phone), credentials (API keys, passwords), and cryptographic material via regex patterns.
13. **`TrustRecomputer` decay model** — Time-based trust decay `(1 - decay_rate) ** hours_elapsed` is mathematically correct. Behavior signal integration is sound.
14. **`AdapterRegistry.emergency_stop_all()`** — Correctly iterates all registered runtimes and calls `emergency_stop()` on each. Returns per-adapter success map.
15. **`DeviceExecutionPacket.check_replay()`** — Correctly checks nonce uniqueness AND timestamp freshness (30-second window). Prevents both replay and stale packet attacks.

---

## RECOMMENDATIONS PRIORITIZED

### Priority 1 — Critical (Block Launch)

1. **Wire `AuthenticationMiddleware` into all Flask API servers** (`murphy_complete_backend.py`, `confidence_engine/api_server.py`, `execution_orchestrator/api.py`, `execution_packet_compiler/api_server.py`, `gate_synthesis/api_server.py`, `compute_plane/api/endpoints.py`). The middleware already exists in `src/security_plane/middleware.py`. This is a wiring task, not a build task. Estimated effort: 1 day.

2. **Replace wildcard CORS with origin allowlist** on all Flask servers. Use `CORSPolicy` from `security_hardening_config.py`. Set `cors_origins` in config to the specific frontend domain. Estimated effort: 2 hours.

3. **Fix tenant isolation in `confidence_engine/api_server.py`** — replace `current_graph` global with per-tenant registry. Apply same fix to `execution_orchestrator/api.py` `executions` dict. Estimated effort: 2 days.

4. **Replace simulated cryptography** — at minimum replace FIDO2 passkey verification with the `fido2` library (Yubico). Replace mTLS certificate verification with Python `ssl` module. PQC can remain simulated for now with a clear feature flag. Estimated effort: 3 days.

5. **Restore `security_hardening_config.py`** to working tree and wire `InputSanitizer` as a `before_request` hook. Estimated effort: 4 hours.

### Priority 2 — High (Fix Before Beta)

6. **Implement real credential verification** in `AWSCredentialVerifier`, `GitHubCredentialVerifier`, `DatabaseCredentialVerifier`. Replace placeholder returns with actual API calls. Estimated effort: 2 days.

7. **Wire `RBACGovernance.check_permission()`** at the API layer. Create `get_current_tenant_id()` helper. Apply to all mutating endpoints. Estimated effort: 2 days.

8. **Apply rate limiting** via `flask-limiter` using the limits already defined in `config.py`. Estimated effort: 4 hours.

9. **Fix `SecureKeyManager`** — remove `.env` write, require `MURPHY_MASTER_KEY` as mandatory env var, add TTL-based cache eviction. Estimated effort: 4 hours.

10. **Restore or re-implement `agentic_api_provisioner.py`**. Estimated effort: 1 day.

### Priority 3 — Medium (Fix Before GA)

11. **Implement dual-path credential onboarding flow** ("Use existing" vs "Let Murphy collect") as a form endpoint. Estimated effort: 3 days.

12. **Add `ServiceProvider` entries** for all 30+ platforms in `DEFAULT_PLATFORMS`. Estimated effort: 1 day.

13. **Merge PR #26 robotics implementation** — execute the Copilot prompt to wire `SensorEngine`/`ActuatorEngine` stubs. Estimated effort: 5 days (Copilot-assisted).

14. **Convert `ACTIVATION_AUDIT.md` entries** to GitHub Issues with acceptance criteria and milestones. Estimated effort: 4 hours.

15. **Add implementation status table** to `README.md`. Estimated effort: 2 hours.

### Priority 4 — Low / Hardening

16. Fix `HeartbeatWatchdog` consecutive timeout escalation (SEC-008).
17. Add `invalidate_cache()` to `BaseCredentialVerifier` (SEC-007).
18. Add TTL-based eviction to `SecureKeyManager` cache (SEC-006).
19. Update `API_DOCUMENTATION.md` to document target auth model (DOC-001).
20. Add PR #25 (Avatar) and PR #26 (Robotics) implementation tracking issues (DOC-003).

---

## ASSUMPTIONS & LIMITATIONS

1. **No live system access** — All findings are based on static code analysis of the repository at commit `e9a7a89`. No runtime testing was performed.
2. **Internal service mesh assumed** — It is assumed the Flask microservices (ports 8052–8058) are intended to be internal-only, not directly internet-facing. If any are internet-facing, SEC-001 and SEC-002 are immediately exploitable.
3. **Database schema not reviewed** — No SQL schema files were found in the repository. SQLite is referenced in `config.py` (`db_path: "murphy_logs.db"`). Row-level security analysis was limited to Python-layer filtering; no database-level RLS was found or could be assessed.
4. **Frontend not reviewed** — No frontend code was found in the repository. CORS and XSS findings are based on API server configuration only.
5. **`security_hardening_config.py` content** — The file was reviewed via `git show` from commit `39f8450`. The working-tree absence was confirmed. It is possible the file was intentionally removed; if so, the rationale should be documented.
6. **PR #24 scope** — PR #24 claims 12,423 additions. Only a subset of the added files were reviewed in depth. The `ml_strategy_engine.py`, `building_automation_connectors.py`, and `energy_management_connectors.py` were not individually audited.
7. **Biometric verification** — The `len(biometric_hash) < 32` check in `authentication.py` was flagged as a stub. It is possible this is intentional placeholder behavior gated by a feature flag not visible in the code reviewed.
8. **Test coverage** — 401 tests are claimed to pass. Test quality and coverage were not assessed in this review. The presence of tests does not imply the tested code is wired into production paths.
# Murphy-System: Comprehensive Testing Strategy

**Date:** 2026-03-10
**Scope:** Testing plan for all modules, Groq API integration, and system-wide validation
**Related:** [Audit and Completion Report](./AUDIT_AND_COMPLETION_REPORT.md)

---

## Table of Contents

1. [Testing Overview](#1-testing-overview)
2. [Groq API Integration Testing](#2-groq-api-integration-testing)
3. [Module-Level Testing Plan](#3-module-level-testing-plan)
4. [Cross-Module System Testing](#4-cross-module-system-testing)
5. [Test Execution Guide](#5-test-execution-guide)

---

## 1. Testing Overview

### 1.1 Current State

The Murphy-System has **498 test files** with **8,843 test functions** and a **100% pass rate**.
This testing strategy extends coverage to include:

- **Groq API integration tests** — Validate LLM provider connectivity and response handling
- **Cross-module system tests** — Verify end-to-end workflows spanning multiple subsystems
- **Regression protection** — Ensure new changes do not break existing functionality

### 1.2 Test Categories

| Category | Purpose | Execution |
|----------|---------|-----------|
| **Unit Tests** | Individual function/class behavior | `pytest tests/test_*.py` |
| **Integration Tests** | Multi-module interaction | `pytest tests/ -m integration` |
| **E2E Tests** | Full HTTP API stack | `pytest tests/e2e/` |
| **Groq Integration** | LLM provider validation | `pytest tests/test_groq_integration.py` |
| **System-Wide** | Cross-module workflows | `pytest tests/test_system_wide_validation.py` |
| **Commissioning** | Import verification | `pytest tests/commissioning/` |

### 1.3 Test Environment Setup

```bash
# Navigate to project root
cd "Murphy System"

# Install test dependencies
pip install pytest pytest-asyncio pytest-cov httpx

# Set up environment for Groq live tests (optional)
export GROQ_API_KEY="your_groq_api_key_here"

# Run all tests
python -m pytest tests/ -v --timeout=60
```

---

## 2. Groq API Integration Testing

### 2.1 Test Architecture

The Groq integration tests are structured in three tiers:

```
┌─────────────────────────────────────────────────┐
│  Tier 3: Live API Tests (requires GROQ_API_KEY) │
│  - Real API calls to api.groq.com               │
│  - Validates actual response format/content      │
│  - Skipped automatically when key not set        │
├─────────────────────────────────────────────────┤
│  Tier 2: Integration Tests (mocked HTTP)         │
│  - Mock Groq API responses                       │
│  - Tests error handling, retries, fallbacks      │
│  - Always runs (no external dependencies)        │
├─────────────────────────────────────────────────┤
│  Tier 1: Unit Tests (no I/O)                     │
│  - Provider configuration & detection            │
│  - Key rotation logic                            │
│  - Circuit breaker state transitions             │
│  - Always runs                                   │
└─────────────────────────────────────────────────┘
```

### 2.2 Test File: `tests/test_groq_integration.py`

**Test Classes:**

| Class | Tests | Tier | Description |
|-------|-------|------|-------------|
| `TestGroqProviderDetection` | 5 | 1 | Environment-based provider auto-detection |
| `TestGroqKeyRotation` | 5 | 1 | Key rotation, failure handling, statistics |
| `TestGroqDomainRouting` | 4 | 1 | Domain-to-provider mapping for Groq |
| `TestGroqMockedAPI` | 5 | 2 | Mocked HTTP request/response validation |
| `TestGroqCircuitBreaker` | 3 | 2 | Circuit breaker with Groq failures |
| `TestGroqLiveAPI` | 4 | 3 | Live API calls (requires `GROQ_API_KEY`) |

### 2.3 Running Groq Tests

```bash
# Run all Groq tests (Tier 1 & 2 always, Tier 3 if key set)
python -m pytest tests/test_groq_integration.py -v

# Run only live API tests
GROQ_API_KEY="your_key" python -m pytest tests/test_groq_integration.py -k "LiveAPI" -v

# Run only unit/mock tests (no API key needed)
python -m pytest tests/test_groq_integration.py -k "not LiveAPI" -v
```

### 2.4 Groq API Test Scenarios

#### Tier 1: Configuration Tests
1. **Auto-detection:** Setting `GROQ_API_KEY` auto-selects Groq provider
2. **Default model:** Groq provider defaults to `mixtral-8x7b-32768`
3. **Base URL:** Groq base URL is `https://api.groq.com/openai/v1`
4. **Key rotation:** Multiple keys rotate correctly via round-robin
5. **Key disable:** Keys auto-disable after consecutive failures

#### Tier 2: Mocked Integration Tests
1. **Successful response:** Mock 200 response with valid chat completion
2. **Error handling:** Mock 429 (rate limit), 500 (server error) responses
3. **Fallback:** Groq failure triggers onboard LLM fallback
4. **Timeout:** Request timeout triggers fallback
5. **Circuit breaker:** Repeated failures open circuit

#### Tier 3: Live API Tests
1. **Health check:** Verify Groq API is reachable
2. **Chat completion:** Send simple prompt, validate response format
3. **Model listing:** Verify available models match expectations
4. **Rate limiting:** Validate rate limit headers in response

---

## 3. Module-Level Testing Plan

### 3.1 New/Updated Module Tests

| Module | Test File | New Tests | Focus |
|--------|-----------|-----------|-------|
| Groq Integration | `test_groq_integration.py` | 26 | Provider, routing, API |
| System-Wide | `test_system_wide_validation.py` | 18 | Cross-module workflows |

### 3.2 Existing Test Suites (Baseline Verification)

| Test Suite | File | Tests | Status |
|-----------|------|-------|--------|
| E2E Smoke | `test_e2e_smoke.py` | 10 | ✅ Passing |
| OpenAI Provider | `test_openai_compatible_provider.py` | 36 | ✅ Passing |
| MFM | 9 files | 228 | ✅ Passing |
| AUAR | 3 files | 211 | ✅ Passing |
| Code Quality | 3 files | ~100 | ✅ Passing |
| Gap Closure | 34 files | ~2,000 | ✅ Passing |

### 3.3 New Module Test Coverage

| Module | Test Label | Tests | Status |
|--------|-----------|-------|--------|
| self_introspection_module | INTRO-001 | Unit tests for AST scanning, codebase discovery, metric recording | ✅ |
| self_codebase_swarm | SCS-001 | Unit tests for BMS spec generation, RFP parsing, cutsheet_engine integration | ✅ |
| cutsheet_engine | CSE-001 | Unit tests for manufacturer data parsing, wiring diagram generation | ✅ |
| visual_swarm_builder | VSB-001 | Unit tests for visual pipeline construction and rendering | ✅ |
| ceo_branch_activation | CEO-002 | Unit tests for planning cycles, heartbeat integration, org chart ops | ✅ |
| production_assistant_engine | PROD-ENG-001 | 92 tests: 7-stage lifecycle, DeliverableGateValidator, 99% gate | ✅ |

---

## 4. Cross-Module System Testing

### 4.1 System Test Architecture

The system-wide tests validate workflows that span multiple subsystems:

```
┌──────────────┐    ┌───────────────┐    ┌────────────────┐
│  LLM Layer   │───▶│  Execution    │───▶│  Persistence   │
│  (Provider,  │    │  (Compiler,   │    │  (WAL, State)  │
│   Controller)│    │   Engine)     │    │                │
└──────────────┘    └───────────────┘    └────────────────┘
       │                    │                     │
       ▼                    ▼                     ▼
┌──────────────┐    ┌───────────────┐    ┌────────────────┐
│  Confidence  │    │  Gate         │    │  Telemetry     │
│  Engine      │    │  Synthesis    │    │  System        │
└──────────────┘    └───────────────┘    └────────────────┘
```

### 4.2 Test File: `tests/test_system_wide_validation.py`

**Test Classes:**

| Class | Tests | Description |
|-------|-------|-------------|
| `TestModuleImportIntegrity` | 4 | All critical modules importable and compatible |
| `TestLLMSubsystemIntegration` | 4 | Provider → Controller → Integration Layer |
| `TestExecutionPipeline` | 3 | Compiler → Engine → Feedback loop |
| `TestMFMSubsystem` | 3 | MFM module chain validation |
| `TestAUARSubsystem` | 2 | AUAR pipeline end-to-end |
| `TestCrossModuleWorkflow` | 2 | Full system workflow validation |

### 4.3 Cross-Module Test Scenarios

1. **LLM → Execution:** LLM generates plan → Execution compiler processes it
2. **Confidence → Gate:** Confidence scores feed gate synthesis decisions
3. **AUAR → LLM:** AUAR routes requests to appropriate LLM provider
4. **MFM → Runtime:** MFM inference integrates with runtime API
5. **Telemetry → All:** All modules emit telemetry events correctly

### 4.4 EventBackbone Wiring Tests

| Test | Description | Status |
|------|-------------|--------|
| EventBackbone wiring — INTRO-001 | Verify SelfIntrospectionEngine publishes to EventBackbone | Pending |
| EventBackbone wiring — SCS-001 | Verify SelfCodebaseSwarm publishes to EventBackbone | Pending |
| EventBackbone wiring — CSE-001 | Verify CutSheetEngine publishes to EventBackbone | Pending |
| EventBackbone wiring — VSB-001 | Verify VisualSwarmBuilder publishes to EventBackbone | Pending |
| EventBackbone wiring — CEO-002 | Verify CEOBranchActivation publishes to EventBackbone | Pending |
| EventBackbone wiring — PROD-ENG-001 | Verify ProductionAssistantEngine publishes to EventBackbone | Pending |

---

## 5. Test Execution Guide

### 5.1 Quick Start

```bash
cd "Murphy System"

# Run the new test suites
python -m pytest tests/test_groq_integration.py tests/test_system_wide_validation.py -v

# Run with coverage
python -m pytest tests/test_groq_integration.py tests/test_system_wide_validation.py \
  --cov=src --cov-report=term-missing -v

# Run all tests including existing suite
python -m pytest tests/ -v --timeout=60 --tb=short
```

### 5.2 CI Integration

The test suites are designed for CI/CD integration:

```yaml
# In .github/workflows/ci.yml
- name: Run Groq Integration Tests
  env:
    GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
  run: |
    cd "Murphy System"
    python -m pytest tests/test_groq_integration.py -v --tb=short

- name: Run System-Wide Tests
  run: |
    cd "Murphy System"
    python -m pytest tests/test_system_wide_validation.py -v --tb=short
```

### 5.3 Groq Live Test Configuration

To run live Groq API tests:

1. Obtain a Groq API key from [console.groq.com/keys](https://console.groq.com/keys)
2. Set the environment variable:
   ```bash
   export GROQ_API_KEY="gsk_your_key_here"
   ```
3. Run live tests:
   ```bash
   python -m pytest tests/test_groq_integration.py -k "LiveAPI" -v
   ```

**Note:** Live API tests are automatically skipped when `GROQ_API_KEY` is not set.
The key should be stored as a CI secret (`secrets.GROQ_API_KEY`), never committed to code.

### 5.4 Test Markers

| Marker | Description | Command |
|--------|-------------|---------|
| `groq_live` | Requires live Groq API key | `-m groq_live` |
| `system_wide` | Cross-module validation | `-m system_wide` |
| `unit` | Unit tests (no I/O) | `-m unit` |
| `integration` | Integration tests | `-m integration` |

### 5.5 Expected Results

When all tests pass:

```
tests/test_groq_integration.py    - 26 passed (4 skipped without GROQ_API_KEY)
tests/test_system_wide_validation.py - 18 passed
Total new tests: 44 (40 always-run + 4 live-only)
```

---

*Strategy document created as part of Issue: Audit and Completion Plan for Code, Documentation, and Testing Across All Modules*

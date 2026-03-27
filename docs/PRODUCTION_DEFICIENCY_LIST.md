# Murphy System — Production Deficiency List

> **Generated:** 2026-03-27  
> **PR:** #441 (copilot/coordinate-migration-to-deepinfra-together-ai)  
> **Overall Readiness:** ~86% Production Ready

---

## 1. Critical Deficiencies (Require Immediate Attention)

### 1.1 Structural Issues (Category A)

| ID | Deficiency | Impact | Recommendation |
|----|-----------|--------|----------------|
| A-001 | Directory `Murphy System/` contains a space | Breaks scripting, CI paths | Rename to `murphy_system/` in coordinated PR |
| A-010 | `murphy_terminal.py` 96 KB monolithic | Maintenance burden | Decompose into `src/terminal/` package |

### 1.2 Wiring Issues (Category B)

| ID | Deficiency | Impact | Recommendation |
|----|-----------|--------|----------------|
| B-003 | ~17% module wiring incomplete | Reduced functionality | Complete stub implementations |
| B-004 | Persistence at 70% — DB backends | Data integrity risk | Validate PostgreSQL live-mode |
| B-006 | E2E Hero Flow at 85% | User experience gaps | Live-environment tracing needed |
| B-010 | No production load testing | Performance unknown | Implement k6/locust tests |

### 1.3 Security Issues (Category C)

| ID | Deficiency | Impact | Recommendation |
|----|-----------|--------|----------------|
| C-001 | E2EE stub gated | Communication not encrypted | Integrate matrix-nio |
| C-003 | No secret scanning in CI | Credential leak risk | Add gitleaks action |
| C-006 | No SBOM generation | Supply chain visibility | Add syft/cyclonedx |
| C-007 | No container scanning | Vulnerability exposure | Add Trivy scan |

---

## 2. API Keys & SDKs Required

### 2.1 LLM Providers (Primary)

| Service | Environment Variable | Status | Priority |
|---------|---------------------|--------|----------|
| DeepInfra | `DEEPINFRA_API_KEY` | ⬜ Required | 🔴 HIGH |
| Together AI | `TOGETHER_API_KEY` | ⬜ Required | 🔴 HIGH |
| OpenAI (fallback) | `OPENAI_API_KEY` | ⬜ Optional | 🟡 MED |
| Anthropic (fallback) | `ANTHROPIC_API_KEY` | ⬜ Optional | 🟡 MED |

**Actions:**
- Sign up at https://deepinfra.com for primary LLM
- Sign up at https://together.ai for overflow capacity
- Configure in GitHub Secrets: `DEEPINFRA_API_KEY`, `TOGETHER_API_KEY`

### 2.2 Communication Services

| Service | Environment Variable | Status | Priority |
|---------|---------------------|--------|----------|
| SendGrid | `SENDGRID_API_KEY` | ⬜ Required for email | 🔴 HIGH |
| Slack | `SLACK_BOT_TOKEN` | ⬜ Required for notifications | 🟡 MED |
| Twilio | `TWILIO_AUTH_TOKEN`, `TWILIO_ACCOUNT_SID` | ⬜ Required for SMS | 🟡 MED |
| Zoom | `ZOOM_API_KEY` | ⬜ Optional for meetings | 🟢 LOW |

**Actions:**
- SendGrid: https://sendgrid.com → API Keys → Create
- Slack: https://api.slack.com/apps → Create App → Bot Token
- Twilio: https://console.twilio.com → API Keys

### 2.3 CRM Integrations

| Service | Environment Variable | Status | Priority |
|---------|---------------------|--------|----------|
| HubSpot | `HUBSPOT_API_KEY` | ⬜ Optional | 🟡 MED |
| Pipedrive | `PIPEDRIVE_API_TOKEN` | ⬜ Optional | 🟢 LOW |
| Salesforce | `SALESFORCE_CONSUMER_KEY` | ⬜ Optional | 🟢 LOW |

### 2.4 Project Management

| Service | Environment Variable | Status | Priority |
|---------|---------------------|--------|----------|
| Notion | `NOTION_API_KEY` | ⬜ Optional | 🟡 MED |
| Jira | `JIRA_API_TOKEN` | ⬜ Optional | 🟢 LOW |
| Asana | `ASANA_ACCESS_TOKEN` | ⬜ Optional | 🟢 LOW |
| Monday | `MONDAY_API_KEY` | ⬜ Optional | 🟢 LOW |
| Airtable | `AIRTABLE_API_KEY` | ⬜ Optional | 🟢 LOW |

### 2.5 Infrastructure & Monitoring

| Service | Environment Variable | Status | Priority |
|---------|---------------------|--------|----------|
| GitHub | `GITHUB_TOKEN` | ✅ Available (Secrets) | 🔴 HIGH |
| Datadog | `DATADOG_API_KEY` | ⬜ Optional | 🟡 MED |
| PagerDuty | `PAGERDUTY_API_KEY` | ⬜ Optional | 🟡 MED |
| AWS | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | ⬜ Optional | 🟡 MED |

### 2.6 Payment Processing

| Service | Environment Variable | Status | Priority |
|---------|---------------------|--------|----------|
| Stripe | `STRIPE_SECRET_KEY` | ⬜ Required for payments | 🔴 HIGH |
| Coinbase | `COINBASE_*` | ⬜ Optional for crypto | 🟢 LOW |

---

## 3. Platform-Side Requirements

### 3.1 Database Configuration

| Component | Requirement | Status |
|-----------|-------------|--------|
| PostgreSQL | Production database | ⬜ Configure `POSTGRES_PASSWORD` |
| Redis | Session/cache store | ⬜ Deploy with docker-compose |
| SQLite | Development fallback | ✅ Built-in |

### 3.2 Infrastructure

| Component | Requirement | Status |
|-----------|-------------|--------|
| Docker | Container runtime | ✅ Dockerfile ready |
| Kubernetes | Production orchestration | ⬜ k8s/ manifests need audit |
| Nginx | Reverse proxy | ✅ Config templates ready |
| Prometheus | Metrics collection | ✅ prometheus.yml ready |
| Grafana | Visualization | ✅ Dashboards in grafana/ |

### 3.3 Mail System

| Component | Environment Variable | Status |
|-----------|---------------------|--------|
| IMAP Server | `IMAP_HOST`, `IMAP_PORT` | ⬜ Configure for murphy.systems |
| Mail Admin | `MAIL_ADMIN_EMAIL`, `MAIL_ADMIN_PASSWORD` | ⬜ Set secure credentials |

---

## 4. Test Coverage Gaps

### 4.1 Module-Specific Gaps

| Module | Current Coverage | Target | Gap |
|--------|-----------------|--------|-----|
| Dynamic chains | ~85% | 95% | 10% |
| Platform connectors | ~70% | 90% | 20% |
| UI→API wiring | ~75% | 95% | 20% |
| E2E flows | ~85% | 95% | 10% |

### 4.2 Test Types Needed

| Test Type | Status | Tool Recommendation |
|-----------|--------|---------------------|
| Unit tests | ✅ 24,341 functions | pytest |
| Integration tests | 🔄 In progress | pytest + docker |
| Load tests | ⬜ Not implemented | k6 or locust |
| Security tests | ✅ bandit, pip-audit | Add SAST/DAST |
| E2E browser tests | ✅ MultiCursor | Use MCB test suite |

---

## 5. Documentation Gaps

| Document | Issue | Action |
|----------|-------|--------|
| ARCHITECTURE_MAP.md | 113 KB — too large | Split into sections |
| API_ROUTES.md | 60 KB — needs modularisation | Generate from OpenAPI |
| CHANGELOG.md | 115 KB — needs archival | Archive pre-v1.0 entries |
| Test count claims | Unverified 24,341 | Add CI verification step |

---

## 6. Recommended Priority Actions

### Phase 1: Immediate (Week 1)
1. ✅ Configure `DEEPINFRA_API_KEY` in GitHub Secrets
2. ✅ Configure `TOGETHER_API_KEY` in GitHub Secrets
3. ⬜ Set `POSTGRES_PASSWORD` for production
4. ⬜ Configure `SENDGRID_API_KEY` for email
5. ⬜ Complete B-003 module wiring

### Phase 2: Short-term (Week 2-3)
1. ⬜ Add gitleaks secret scanning (C-003)
2. ⬜ Add Trivy container scanning (C-007)
3. ⬜ Complete E2E Hero Flow validation (B-006)
4. ⬜ Set up Slack/Twilio notifications

### Phase 3: Medium-term (Month 1)
1. ⬜ Implement k6 load testing (E-004)
2. ⬜ Add SBOM generation (C-006)
3. ⬜ Complete PostgreSQL live-mode testing (B-004)
4. ⬜ Audit K8s manifests (G-002)

### Phase 4: Long-term (Quarter 1)
1. ⬜ Decompose murphy_terminal.py (A-010)
2. ⬜ Rename `Murphy System/` directory (A-001)
3. ⬜ Implement matrix-nio for E2EE (C-001)
4. ⬜ Complete platform connector OAuth (B-011)

---

## 7. Summary Statistics

| Metric | Value |
|--------|-------|
| Total Deficiencies | 131 |
| Fixed | 24 (18%) |
| In Progress | 9 (7%) |
| Deferred | 98 (75%) |
| Critical Items | 8 |
| API Keys Required | 15+ |
| Test Coverage Target | 95% |

---

*This deficiency list is maintained alongside `PRODUCTION_READINESS_AUDIT.md`. Update as items are resolved.*

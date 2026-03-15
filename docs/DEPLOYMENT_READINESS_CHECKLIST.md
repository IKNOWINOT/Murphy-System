# Murphy System — Deployment Readiness Checklist

**Version:** 1.0.0  
**Owner:** Platform Engineering  
**License:** BSL 1.1  
**Copyright:** © 2020 Inoni Limited Liability Company

Use this checklist before going live with Murphy System in any production
environment. Each item links to the responsible module or document.

---

## 1. Infrastructure

- [ ] Python 3.10+ installed (3.12 recommended)
- [ ] `.env` file populated from `.env.example` — all required keys set
- [ ] `GROQ_API_KEY` (or alternative LLM provider key) confirmed working
- [ ] Database / Redis connection verified (if persistence enabled)
- [ ] Disk space ≥ 10 GB available for logs and state files
- [ ] `pip install -r requirements_murphy_1.0.txt` completed without errors
- [ ] `python murphy_system_1.0_runtime.py` starts cleanly
- [ ] `GET /api/health` returns `200 OK`

---

## 2. Security

- [ ] `MURPHY_ENV=production` set in environment
- [ ] All API keys stored via `SecureKeyManager` (not in plain `.env` for prod)
- [ ] CORS `allowed_origins` list does **not** contain `*` in production
- [ ] HTTPS enforced for all external endpoints (reverse proxy or Cloudflare)
- [ ] RBAC roles configured — no wildcard permissions in production
- [ ] SSRF protection active: `WebhookDispatcher.validate_webhook_url()` rejects private IPs
- [ ] Brute-force protection active: 5 failed auth attempts → 15-min lockout
- [ ] PII never written to log files (raw email addresses not logged)
- [ ] All input validation in place (CWE-20 guards on all public APIs)
- [ ] Audit trail persistence configured and writable

---

## 3. Compliance

- [ ] `OutreachComplianceGovernor` instantiated with correct daily limits
  - Default: 50 email / 20 SMS / 30 LinkedIn per day
  - Adjust for your launch volume
- [ ] `ContactComplianceGovernor` (COMPL-001) DNC list loaded from persistence
- [ ] Suppression list populated with any known opt-outs before first cycle
- [ ] CAN-SPAM: unsubscribe link and physical address present in all outreach templates
- [ ] TCPA: SMS outreach disabled until express consent mechanism is live
- [ ] GDPR: right-to-erasure workflow documented and tested
- [ ] CASL: Canadian prospects require express consent before contact
- [ ] 30-day cooldown configured and verified in staging
- [ ] Opt-out detection regex tested with sample replies

---

## 4. Selling Engine

- [ ] `MurphySelfSellingEngine` initialised with `OutreachComplianceGovernor`
- [ ] `run_selling_cycle()` tested end-to-end in staging
- [ ] `SalesAutomationEngine.generate_leads()` returns valid leads
- [ ] `ProspectOnboarder.onboard()` creates valid `ProspectProfile` objects
- [ ] `SelfSellingOutreach.send()` connected to real email/SMS/LinkedIn provider
- [ ] Live system stats (`get_live_system_stats()`) returning real counters
- [ ] At least one selling cycle completed successfully in staging without errors

---

## 5. Onboarding

- [ ] `OnboardingOrchestrator` tested with all 13 `BUSINESS_DEMOGRAPHICS` types
- [ ] `AgenticOnboardingEngine` wired to `SecureKeyManager` and `TelemetryAdapter`
- [ ] Regulatory zone resolution tested for target countries
- [ ] Integration provisioning (`provisioning` → `building` → `deploying`) verified
- [ ] Deployment targets tested: Cloudflare Worker, AWS Lambda, or self-hosted
- [ ] `GET /api/onboarding/status/{profile_id}` returns correct lifecycle state

---

## 6. Production Assistant

- [ ] `ProductionAssistantEngine` (PROD-001) running
- [ ] `SafetyGate` (COMPLIANCE type, threshold=0.99) configured and active
- [ ] `validate_proposal()` tested: ≥ 0.99 confidence passes, < 0.99 blocks
- [ ] `validate_work_order()` tested: mismatched regulatory zone fails
- [ ] HITL gate requirements tested: certifications, licensing, experience criteria
- [ ] Audit log persistence configured for work order history
- [ ] `submit_work_order()` end-to-end tested with sample proposal

---

## 7. Billing

- [ ] PayPal API credentials configured (primary payment provider)
- [ ] Coinbase Commerce API configured (crypto payment provider)
- [ ] Webhook endpoints verified: `/api/billing/webhook/paypal` and `/api/billing/webhook/coinbase`
- [ ] HMAC webhook signature verification active for both providers
- [ ] `SubscriptionManager` tested: create, pause, cancel flows
- [ ] Currency converter tested with target currencies
- [ ] Japan 10% discount active if targeting JP market (`JPY` or `locale=ja`)
- [ ] Webhook body size limit (256 KB) confirmed

---

## 8. Monitoring and Alerting

- [ ] `DeploymentReadinessChecker` (`/api/readiness`) returns all green
- [ ] `SelfAutomationBootstrap` (`/api/bootstrap`) completes all 3 stages
- [ ] `AlertRulesEngine` connected and rules registered for active prospects
- [ ] `TelemetryAdapter` sending metrics to configured backend
- [ ] Error rate alerts configured (target: < 1% cycle error rate)
- [ ] Memory usage monitoring active (bounded collections prevent unbounded growth)

---

## 9. Trial Pipeline

- [ ] `TrialOrchestrator` tested: positive reply → trial started
- [ ] `TrialShadowDeployer` tested: shadow agent deployed during trial
- [ ] Trial duration configured (default: 3 days)
- [ ] Metrics report generated at trial completion
- [ ] Conversion flow from trial → paid subscription tested
- [ ] Customer status propagated to `OutreachComplianceGovernor` after conversion

---

## 10. Confidence and Gates

- [ ] `SafetyGate` (6 gate types) tested for all production flows
- [ ] `MurphyGate` phase thresholds reviewed for your use case
- [ ] HITL escalation path tested: human approver queue functional
- [ ] Gate audit log persisted and queryable
- [ ] `GateCompiler` dynamic gate generation tested for domain-specific pipelines

---

## 11. Load and Resilience

- [ ] 20-minute selling cycle load-tested (no memory leaks after 24 hours)
- [ ] `RateLimiter` TTL-based cleanup verified (buckets evicted after 1 hour)
- [ ] Chaos resilience tested: service restarts without data loss
- [ ] `AutonomousRepairEngine` active for self-healing on transient failures
- [ ] Rate limiter `_MAX_BUCKETS=100,000` cap confirmed sufficient for launch volume

---

## 12. Go-Live Sign-Off

| Item | Status | Sign-Off |
|------|--------|----------|
| Infrastructure ready | ☐ | |
| Security reviewed | ☐ | |
| Compliance verified | ☐ | |
| Selling engine tested | ☐ | |
| Onboarding tested | ☐ | |
| Production assistant tested | ☐ | |
| Billing tested | ☐ | |
| Monitoring active | ☐ | |
| Trial pipeline tested | ☐ | |
| Gates and confidence verified | ☐ | |
| Load testing passed | ☐ | |
| **APPROVED FOR PRODUCTION** | ☐ | |

---

## Quick Start (Minimum Viable Launch)

For the fastest path to a live selling cycle:

```bash
# 1. Set environment
export MURPHY_ENV=production
export GROQ_API_KEY=<your_key>

# 2. Install
pip install -r requirements_murphy_1.0.txt

# 3. Start runtime
python murphy_system_1.0_runtime.py

# 4. Verify health
curl http://localhost:8000/api/health

# 5. Trigger first readiness check
curl http://localhost:8000/api/readiness

# 6. Bootstrap automation
curl -X POST http://localhost:8000/api/bootstrap
```

See `docs/DEPLOYMENT_GUIDE.md` for full deployment options (Docker, K8s,
Cloudflare Workers).

---

## Related Documents

- [`docs/DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md) — full deployment instructions
- [`docs/CEO_AUTONOMOUS_OPERATIONS.md`](CEO_AUTONOMOUS_OPERATIONS.md) — org chart and autonomous operations plan
- [`docs/API_REFERENCE.md`](API_REFERENCE.md) — API endpoint reference

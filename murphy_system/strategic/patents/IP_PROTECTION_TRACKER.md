# IP Protection Tracker — Murphy System

**Maintained by:** Corey Post, Inoni LLC  
**Last Updated:** 2026-03-05

---

## Patent Status Table

| # | Invention Title | Status | Filing Date | Application # | Assignee |
|---|----------------|--------|-------------|---------------|----------|
| 1 | Method and System for Multi-Factor Generative-Deterministic Confidence Scoring in Autonomous AI Systems | PROVISIONAL FILED | 2026-03-05 | TBD — awaiting USPTO confirmation | Inoni LLC |
| 2 | System and Method for Dynamic Synthesis of Safety Gates in AI Execution Pipelines | PROVISIONAL FILED | 2026-03-05 | TBD — awaiting USPTO confirmation | Inoni LLC |
| 3 | Cryptographic Integrity Verification System for AI Execution Packets with Time-Bounded Validity and Replay Prevention | PROVISIONAL FILED | 2026-03-05 | TBD — awaiting USPTO confirmation | Inoni LLC |

---

## Prior Art Notes

### Invention 1 — MFGC Confidence Scoring

| Reference | Relevance | Distinguishing Factor |
|-----------|-----------|----------------------|
| OpenAI RLHF (2017–present) | Uses reward models for output scoring | No phase-locked weight schedules; no hazard penalty; no seven-phase pipeline |
| Anthropic Constitutional AI (2022) | Rule-based AI safety filtering | Binary allow/deny; no scalar confidence score; no action tier classification |
| Google SAFE (2023) | Safety evaluation framework | Post-hoc evaluation; not integrated into execution pipeline; no phase gates |
| LangChain guardrails (2023) | Chain-level safety hooks | No MFGC formula; no domain × generative × hazard decomposition |
| LlamaIndex (2023) | LLM query routing with confidence | Confidence scores not phase-adaptive; no dynamic gate synthesis |

**Conclusion:** No prior art found that combines (1) three-factor confidence decomposition with (2) phase-locked weight schedules and (3) adaptive thresholds in a single unified formula.

### Invention 2 — Dynamic Gate Synthesis

| Reference | Relevance | Distinguishing Factor |
|-----------|-----------|----------------------|
| Traditional rule engines (Drools, etc.) | Rule-based decision systems | Not confidence-driven; not AI-pipeline-specific |
| AWS Step Functions | Workflow orchestration with gates | No confidence scoring integration; no HITL/COMPLIANCE gate taxonomy |
| Apache Airflow | DAG-based workflow with safety checks | Static gate configuration; not dynamically compiled from runtime confidence |

**Conclusion:** Dynamic synthesis of typed safety gates from a confidence result at runtime is novel.

### Invention 3 — Cryptographic AI Execution Packets

| Reference | Relevance | Distinguishing Factor |
|-----------|-----------|----------------------|
| JWT (RFC 7519) | Time-bounded cryptographic tokens | Not specific to AI execution; no confidence score field; no phase encoding |
| Macaroons | Contextual caveats on tokens | No HMAC-SHA256 over AI confidence scores; no replay prevention for AI actions |
| W3C Verifiable Credentials | Cryptographic credential format | Not designed for AI execution flow; no TTL-based replay prevention |

**Conclusion:** Application of HMAC-SHA256 with time-bounded validity and replay prevention specifically to AI execution packets is novel.

---

## Next Steps Timeline

| Action | Owner | Target Date | Status |
|--------|-------|-------------|--------|
| Receive USPTO provisional filing confirmation | Patent agent | 2026-04-01 | PENDING |
| Convert provisional → non-provisional (Invention 1) | Patent counsel | 2027-03-04 | PLANNED |
| Convert provisional → non-provisional (Invention 2) | Patent counsel | 2027-03-04 | PLANNED |
| Convert provisional → non-provisional (Invention 3) | Patent counsel | 2027-03-04 | PLANNED |
| File PCT international application (Inventions 1 & 2) | Patent counsel | 2027-03-04 | PLANNED |
| European Patent Office (EPO) national phase entry | Patent counsel | 2028-Q1 | PLANNED |
| Conduct formal prior art search (all 3 inventions) | Patent agent | 2026-05-01 | PLANNED |
| Register copyright for murphy_confidence source code | Inoni LLC | 2026-04-15 | PLANNED |
| File trademark application "murphy_system" | Inoni LLC | 2026-05-01 | PLANNED |

---

## Trade Secret Inventory

The following remain as trade secrets (not in patent applications):

| Item | Protection Method |
|------|------------------|
| Trained healthcare domain model weights | Source code access controls + NDA |
| Financial regulatory mapping database | Source code access controls + NDA |
| Phase weight tuning methodology | Internal documentation only |
| Customer-specific gate configurations | Per-customer NDA |

---

## VERIFIED BY: Corey Post — Inoni LLC

© 2020-2026 Inoni Limited Liability Company. All rights reserved.

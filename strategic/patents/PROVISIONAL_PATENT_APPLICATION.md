# PROVISIONAL PATENT APPLICATION

**Filing Type:** Provisional Patent Application  
**Filing Date:** 2026-03-05  
**Inventor:** Corey Post  
**Assignee:** Inoni Limited Liability Company  
**Attorney Docket:** INONI-2026-001  

---

## INVENTION 1

### Title
**"Method and System for Multi-Factor Generative-Deterministic Confidence
Scoring in Autonomous AI Systems"**

---

### Field of the Invention

This invention relates to artificial intelligence systems, and more
particularly to methods and systems for computing a multi-factor confidence
score that governs autonomous AI decision-making through a phase-structured
execution pipeline.

---

### Background

Existing AI systems lack principled mechanisms for self-assessment of output
quality under uncertainty.  Large language models (LLMs) and agentic AI
frameworks produce outputs without quantifying the composite risk of acting
on those outputs.  Simple binary allow/deny guardrails fail to provide the
graduated, proportionate response required for regulated industries.

---

### Summary of the Invention

The present invention provides a **Multi-Factor Generative-Deterministic
Confidence (MFGC)** scoring system that computes a scalar confidence score
by integrating generative quality, domain-deterministic match, and hazard
penalty, subject to phase-locked weight schedules that enforce progressively
conservative scoring as an AI pipeline approaches execution.

---

### Detailed Description

#### 1. MFGC Formula

The core formula is:

```
C(t) = w_g · G(x) + w_d · D(x) − κ · H(x)
```

Where:
- `G(x)` ∈ [0,1] — Generative quality score: measures the internal coherence, grammaticality, and self-consistency of the AI-generated output.
- `D(x)` ∈ [0,1] — Domain-deterministic match score: measures the alignment of the output with a domain knowledge base, rule set, or deterministic validator.
- `H(x)` ∈ [0,1] — Hazard factor: measures the potential for harm, irreversibility, or regulatory violation if the output is acted upon.
- `w_g` — Weight for generative component (phase-locked, decreasing toward EXECUTE).
- `w_d` — Weight for domain component (phase-locked, increasing toward EXECUTE).
- `κ` — Hazard penalty multiplier (phase-locked, increasing toward EXECUTE).

The score `C(t)` is bounded to [0,1] by clamping.

#### 2. Seven-Phase Pipeline Architecture

The pipeline processes AI decisions through seven sequential phases:

| Phase | Description | Min Threshold |
|-------|-------------|---------------|
| EXPAND | Broad idea generation; loose constraints | 0.50 |
| TYPE | Apply type-system constraints | 0.55 |
| ENUMERATE | Generate candidate solutions | 0.60 |
| CONSTRAIN | Apply domain and safety constraints | 0.65 |
| COLLAPSE | Collapse to a single candidate | 0.70 |
| BIND | Bind variables to concrete values | 0.78 |
| EXECUTE | Commit to irreversible action | 0.85 |

At each phase, the MFGC formula is re-evaluated with phase-specific weights.
The phase threshold must be met before advancement to the next phase.

#### 3. Phase-Locked Weight Schedules

| Phase | w_g | w_d | κ |
|-------|-----|-----|---|
| EXPAND | 0.60 | 0.30 | 0.10 |
| TYPE | 0.55 | 0.35 | 0.10 |
| ENUMERATE | 0.50 | 0.40 | 0.10 |
| CONSTRAIN | 0.40 | 0.45 | 0.15 |
| COLLAPSE | 0.35 | 0.50 | 0.15 |
| BIND | 0.30 | 0.55 | 0.15 |
| EXECUTE | 0.25 | 0.55 | 0.20 |

#### 4. Six-Tier Action Classification

| Score Range | Action | Meaning |
|-------------|--------|---------|
| ≥ 0.90 | PROCEED_AUTOMATICALLY | No human intervention required |
| ≥ 0.80 | PROCEED_WITH_MONITORING | Log for async review |
| ≥ 0.70 | PROCEED_WITH_CAUTION | Surface for synchronous review |
| ≥ 0.55 | REQUEST_HUMAN_REVIEW | Route to human reviewer |
| ≥ 0.40 | REQUIRE_HUMAN_APPROVAL | Block until explicit human approval |
| < 0.40 | BLOCK_EXECUTION | Hard stop; do not execute |

---

### Claims — Invention 1

**Claim 1.** A computer-implemented method for confidence scoring in an
autonomous AI system, comprising: receiving at least three inputs representing
a generative quality score G(x), a domain-deterministic match score D(x), and
a hazard factor H(x); computing a confidence score C(t) according to the
formula C(t) = w_g·G(x) + w_d·D(x) − κ·H(x); and classifying an AI action
based on said confidence score into one of at least six action tiers.

**Claim 2.** The method of claim 1, wherein w_g, w_d, and κ are phase-locked
weights determined by a current pipeline phase selected from a sequence of
at least seven phases.

**Claim 3.** The method of claim 2, wherein the sequence of phases comprises,
in order: EXPAND, TYPE, ENUMERATE, CONSTRAIN, COLLAPSE, BIND, and EXECUTE.

**Claim 4.** The method of claim 2, wherein w_g decreases and w_d increases
as the pipeline progresses from EXPAND to EXECUTE, reflecting increasing
reliance on domain-deterministic validation.

**Claim 5.** The method of claim 2, wherein each phase has an associated
minimum confidence threshold, and wherein the threshold increases monotonically
from EXPAND to EXECUTE.

**Claim 6.** The method of claim 1, wherein classifying comprises assigning
one of: PROCEED_AUTOMATICALLY, PROCEED_WITH_MONITORING, PROCEED_WITH_CAUTION,
REQUEST_HUMAN_REVIEW, REQUIRE_HUMAN_APPROVAL, or BLOCK_EXECUTION.

**Claim 7.** The method of claim 1, further comprising generating a
human-readable rationale string that includes the confidence score, phase,
action tier, and individual component scores.

**Claim 8.** A system for multi-factor confidence scoring comprising: a
processor configured to execute instructions; a memory storing phase-locked
weight schedules indexed by pipeline phase; and a confidence engine configured
to compute C(t) = w_g·G(x) + w_d·D(x) − κ·H(x) using weights retrieved from
said memory.

**Claim 9.** The system of claim 8, wherein the confidence engine is further
configured to apply adaptive phase thresholds that enforce a minimum confidence
score before an AI action is permitted to proceed.

**Claim 10.** A non-transitory computer-readable medium storing instructions
that, when executed by a processor, cause the processor to: compute a
multi-factor confidence score for an AI decision using separate generative,
domain, and hazard components; apply a phase-specific weight schedule to said
components; compare the resulting score to a phase-specific minimum threshold;
and emit one of six action classification signals based on the comparison.

**Claim 11.** The medium of claim 10, wherein the instructions further cause
the processor to prevent execution of an AI action when the confidence score
falls below the phase-specific minimum threshold.

**Claim 12.** The medium of claim 10, wherein the six action classification
signals map to: full autonomy, monitored autonomy, cautious autonomy, human
review request, human approval requirement, and hard execution block.

---

## INVENTION 2

### Title
**"System and Method for Dynamic Synthesis of Safety Gates in AI Execution
Pipelines"**

---

### Field of the Invention

This invention relates to AI safety systems, and more particularly to dynamic
compilation of safety gate configurations from real-time confidence assessments
in AI execution pipelines.

---

### Background

Static safety guardrails in AI systems cannot adapt to the risk level of
individual decisions.  A fixed rule that blocks all low-confidence outputs
creates unacceptable false-positive rates; no guardrail creates unacceptable
risk.  What is needed is a system that dynamically synthesises the right
safety gates for each specific decision context.

---

### Detailed Description

#### 1. Gate Types

Six gate types are defined:

| Gate Type | Blocking Default | Default Threshold | Purpose |
|-----------|-----------------|-------------------|---------|
| EXECUTIVE | Yes | 0.85 | C-suite / strategic decisions |
| OPERATIONS | No | 0.70 | Operational workflow steps |
| QA | No | 0.75 | Quality assurance review |
| HITL | Yes | 0.80 | Human-in-the-loop approval |
| COMPLIANCE | Yes | 0.90 | Regulatory compliance enforcement |
| BUDGET | No | 0.65 | Financial exposure control |

#### 2. Blocking vs. Non-Blocking Gates

- **Blocking gates:** When confidence score < threshold, execution is halted and
  the action is upgraded to BLOCK_EXECUTION.
- **Non-blocking gates:** When confidence score < threshold, the action is
  upgraded to REQUIRE_HUMAN_APPROVAL but execution is not halted; the gate
  annotates the pipeline output for downstream review.

#### 3. Gate Compilation Algorithm

The GateCompiler accepts a ConfidenceResult and optional execution context,
then applies a rule table to synthesise a list of SafetyGate objects.
Rules match on (phase, action) pairs.  Context keys such as
`compliance_required` and `budget_limit` drive additional gate synthesis.
Duplicate gate IDs are deduplicated (first occurrence wins).

---

### Claims — Invention 2

**Claim 1.** A computer-implemented method for dynamic safety gate synthesis,
comprising: receiving a confidence result comprising a confidence score, a
pipeline phase, and an action classification; applying a rule table indexed
by at least one of pipeline phase and action classification to select one or
more safety gate types; and instantiating a set of safety gates corresponding
to the selected gate types.

**Claim 2.** The method of claim 1, wherein each safety gate is instantiated
with a gate type, a blocking flag, and a confidence threshold.

**Claim 3.** The method of claim 1, further comprising receiving an execution
context dictionary and adding supplementary gates based on context keys
including at least one of compliance_required and budget_limit.

**Claim 4.** The method of claim 1, wherein blocking gates halt execution when
the confidence score is below the gate threshold, and non-blocking gates
annotate the pipeline without halting execution.

**Claim 5.** The method of claim 1, wherein the rule table defines at least
six gate types: EXECUTIVE, OPERATIONS, QA, HITL, COMPLIANCE, and BUDGET.

**Claim 6.** A system for dynamic safety gate synthesis comprising a gate
compiler configured to: accept a confidence result from a multi-factor
confidence engine; select applicable gate types from a rule table based on
the pipeline phase and action classification in said confidence result;
and return an ordered list of instantiated safety gate objects.

**Claim 7.** The system of claim 6, wherein each safety gate object is
configured to evaluate a confidence result and return a gate result indicating
pass or fail status, blocking status, and a human-readable message.

**Claim 8.** A non-transitory computer-readable medium storing instructions
that, when executed, dynamically compile safety gates for an AI execution
pipeline by: mapping a confidence action tier to one or more gate types via a
rule table; instantiating gates with appropriate blocking and threshold
parameters; and evaluating each gate against the confidence score to produce
a gate result.

---

## INVENTION 3

### Title
**"Cryptographic Integrity Verification System for AI Execution Packets with
Time-Bounded Validity and Replay Prevention"**

---

### Field of the Invention

This invention relates to cryptographic integrity systems for AI execution
environments, providing tamper detection, time-bounded validity, and
prevention of replay attacks on AI action packets.

---

### Detailed Description

#### 1. AI Execution Packet Structure

An AI Execution Packet (AEP) comprises:
- `action_id` — UUID uniquely identifying the intended action
- `confidence_score` — C(t) computed by the MFGC engine
- `phase` — Pipeline phase at time of scoring
- `timestamp` — UTC Unix timestamp (64-bit)
- `ttl` — Time-to-live in seconds (validity window)
- `context_hash` — SHA-256 hash of the execution context
- `hmac` — HMAC-SHA256 signature over all above fields

#### 2. HMAC-SHA256 Integrity

The HMAC is computed as:
```
HMAC-SHA256(secret_key, action_id || confidence_score || phase || timestamp || ttl || context_hash)
```

Verification fails if:
- The HMAC does not match (tampering detected)
- `current_time > timestamp + ttl` (packet expired)
- `action_id` appears in the replay prevention cache (replay detected)

#### 3. Replay Prevention

A time-bounded cache of consumed `action_id` values prevents replay attacks.
The cache is scavenged of entries older than the maximum TTL at regular intervals.

---

### Claims — Invention 3

**Claim 1.** A computer-implemented method for cryptographic integrity
verification of AI execution packets, comprising: generating an AI execution
packet comprising an action identifier, a confidence score, a pipeline phase,
a timestamp, a time-to-live value, and a context hash; computing an
HMAC-SHA256 signature over said fields using a secret key; and attaching
said signature to the packet.

**Claim 2.** The method of claim 1, further comprising verifying the packet
by recomputing the HMAC and comparing to the attached signature.

**Claim 3.** The method of claim 1, further comprising rejecting the packet
if the current time exceeds the packet timestamp plus the time-to-live value.

**Claim 4.** The method of claim 1, further comprising maintaining a
replay-prevention cache of consumed action identifiers and rejecting any
packet whose action identifier appears in said cache.

**Claim 5.** The method of claim 4, wherein the replay-prevention cache
is scavenged of entries older than a maximum time-to-live at periodic intervals.

**Claim 6.** A system for cryptographic integrity verification of AI execution
packets comprising: a packet generator configured to assemble an execution
packet and compute an HMAC-SHA256 signature; a packet verifier configured to
validate the signature, check time-bounded validity, and consult a
replay-prevention cache; and said replay-prevention cache configured to store
consumed action identifiers with associated expiry times.

---

*All three inventions described herein are patent-pending inventions of
Corey Post, assigned to Inoni Limited Liability Company.*

*This provisional patent application establishes a priority date of 2026-03-05.*

© 2020-2026 Inoni Limited Liability Company. All rights reserved.

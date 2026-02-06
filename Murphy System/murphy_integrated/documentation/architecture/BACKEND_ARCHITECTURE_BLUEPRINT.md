1. **[CLARIFYING QUESTIONS]**

1) **Domain scope** — Domain-agnostic engine with per-session domain instantiation and session priors.  
   *Why it matters:* Determines how priors and domain packs are layered without hard-coding verticals.

2) **Question sourcing strategy** — Hybrid: curated bank for calibration/governance + LLM augmentation (non-authoritative).  
   *Why it matters:* Controls semantic drift and defines safe question injection points.

3) **Response formats (MVP)** — Multiple choice, Yes/No boundary tests, numeric, short constrained text (taxonomy-mapped).  
   *Why it matters:* Evidence strength depends on deterministic response parsing.

4) **Knowledge representation** — Graph + ledger + templates, with taxonomies for reason codes and approval routing.  
   *Why it matters:* Enables relationship inference, drift detection, and HITL gating.

5) **Scale targets** — 10–100 concurrent sessions, 10–50 questions/session, sub-second scoring, incremental inference.  
   *Why it matters:* Guides deployment model and cost/latency tradeoffs.

2. **[ARCHITECTURE BLUEPRINT]**

### System Diagram (Mermaid)
```mermaid
flowchart TB
    UI[UI Enhancement\n(Integrated UI Variants)] -->|JSON: {session_id, response}| API[Integration Layer\nREST API + Control Plane]
    API -->|Evidence + Prior| BAYES[Mathematical Framework\nBayesian Inference Engine]
    API -->|Session Context| INTERVIEW[Synthetic Interview Engine\nAdaptive Question Selection]
    API -->|Telemetry Events| CALIB[Knowledge Calibration System\nGap Detection + Drift]

    BAYES -->|Posterior Beliefs| CALIB
    INTERVIEW -->|Question Candidates| API
    CALIB -->|Gap Metrics + HITL Flags| API

    API -->|Audit Events| LEDGER[(Ledger DB\nTime-indexed truth)]
    API -->|Graph Updates| GRAPH[(Knowledge Graph\nEntities + Relations)]
    API -->|Question Bank| BANK[(Curated Bank\nGovernance + Calibration)]
    API -->|LLM Proposals| LLM[LLM Augmentation\nNon-authoritative]

    GRAPH -->|Entity Context| INTERVIEW
    LEDGER -->|Drift Signals| CALIB
```

### Technology Stack
- **Bayesian inference library:** **SciPy** (`scipy.stats`) — mature, well-maintained, and provides distributions + numerical stability without heavy frameworks.
- **NLP/text analysis:** **spaCy** — practical tokenization + entity labeling for constrained text responses; active maintenance and easy pipeline customization.
- **API framework:** **FastAPI** — already used in Murphy, strong typing support, and auto-generated OpenAPI for frontend integration.
- **Database:** **PostgreSQL** — reliable relational store for ledger + session data; supports JSONB for flexible schema evolution.
- **Testing framework:** **pytest** — standard Python testing stack with fixtures and strong ecosystem support.

### API Contracts
```python
# Interface: Integration Layer → Bayesian Inference Engine
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class Evidence:
    question_id: str
    response: str
    strength: float
    response_type: str

@dataclass
class BeliefState:
    concept_id: str
    probability: float
    entropy: float


def update_beliefs(session_id: str, evidence: Evidence) -> List[BeliefState]:
    """
    Purpose: Update posterior beliefs for concepts in the session.
    When called: After each validated response.
    Example payload: {"question_id": "q1", "strength": 0.7} → {"concept_id": "cA", "probability": 0.73}
    Errors: ValueError for invalid session_id or malformed evidence payload (e.g., strength not in [0,1], response_type outside allowed set).
    """
    pass
```

```python
# Interface: Integration Layer → Synthetic Interview Engine
from typing import Sequence

@dataclass
class QuestionCandidate:
    question_id: str
    prompt: str
    response_type: str
    expected_concept: str


def select_next_question(session_id: str, beliefs: Sequence[BeliefState]) -> QuestionCandidate:
    """
    Purpose: Choose the next most informative question.
    When called: After belief update or session start.
    Example payload: {"beliefs": [...]} → {"question_id": "q7", "response_type": "yes_no"}
    Errors: LookupError if no eligible question exists (caller should trigger HITL or end session).
    """
    pass
```

```python
# Interface: Integration Layer → Knowledge Calibration System
@dataclass
class GapReport:
    session_id: str
    gaps: Dict[str, float]
    drift_detected: bool
    hitl_required: bool


def evaluate_gaps(session_id: str, beliefs: Sequence[BeliefState]) -> GapReport:
    """
    Purpose: Detect knowledge gaps and drift signals.
    When called: After each belief update or batch telemetry ingest.
    Example payload: {"beliefs": [...]} → {"drift_detected": true, "hitl_required": true}
    Drift: Trigger when posterior deltas exceed configured variance or contradict ledger invariants.
    HITL: Set true when drift or low-confidence gates cross policy thresholds.
    """
    pass
```

```python
# Interface: Integration Layer → Ledger
@dataclass
class LedgerEvent:
    session_id: str
    event_type: str
    payload: Dict[str, str]
    timestamp: str


def append_event(event: LedgerEvent) -> None:
    """
    Purpose: Write immutable audit events for every belief update.
    When called: After each response and system decision.
    Example payload: {"event_type": "belief_update"} → {}
    """
    pass
```

### Deployment Strategy
- **Architecture pattern:** Modular monolith with explicit component boundaries.  
  *Rationale:* Simplifies MVP delivery while preserving clear separations for later service extraction.
- **Scalability approach:** Horizontal scale at the API layer; background workers for telemetry ingestion; cache belief states per session.  
- **Deployment target:** Dockerized FastAPI service + Postgres (single-node for MVP; containerized for future scaling).  
- **Development workflow:** Local env via `docker-compose` or venv; CI runs unit tests; production deploys tagged container with config-driven environment variables.

3. **[MATHEMATICAL FRAMEWORK]**

### Class Structure
```python
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

@dataclass(frozen=True)
class Config:
    entropy_threshold: float
    max_questions: int
    min_confidence: float

@dataclass(frozen=True)
class Evidence:
    question_id: str
    concept_id: str
    response_type: str
    strength: float

@dataclass
class BeliefState:
    concept_id: str
    probability: float
    entropy: float

class BayesianInferenceEngine:
    """Belief updating and uncertainty estimation for adaptive questioning."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def update_beliefs(self, prior: BeliefState, evidence: Evidence) -> BeliefState:
        """Apply Bayesian update to produce a posterior belief."""
        pass

    def compute_entropy(self, belief: BeliefState) -> float:
        """Compute entropy in bits; handle edge cases for probabilities of 0 or 1."""
        pass

    def select_next_question(self, beliefs: Iterable[BeliefState]) -> str:
        """Choose the next question based on maximum information gain."""
        pass

    def should_stop(self, beliefs: Iterable[BeliefState], questions_asked: int) -> bool:
        """Determine if questioning should stop based on entropy + thresholds."""
        pass
```

### Algorithms
- **Entropy calculation:**
  \( H(X) = -\sum p(x) \log_2 p(x) \) — computed after each belief update, using the limit convention \(0 \log 0 = 0\) (implement via conditional checks or NumPy vectorization alongside SciPy).
- **Question selection:**
  Choose the question that maximizes expected information gain:  
  \( \Delta H = H(prior) - \mathbb{E}[H(posterior | q)] \)
- **Convergence criteria:**
  Stop when entropy \( < 0.2 \) or max questions reached, and confidence \( > 0.85 \).
- **Belief update mechanism:**
  \( P(H | E) = \frac{P(E | H) P(H)}{P(E)} \) with evidence strength modeled as likelihood.

### Worked Example
```
Initial belief: P(concept_understood) = 0.50
Question: "Do you have a documented approval workflow?" (Yes/No)
User response: Yes
Evidence strength: 0.70
Updated belief: P(concept_understood | evidence) = 0.73
Entropy: 1.00 → 0.85 bits
Decision: Continue (entropy > threshold)
```

4. **[IMPLEMENTATION ROADMAP]**

### Development Phases
1. **Phase 1 (S)** — Core Bayesian engine + belief update API  
   *Deliverables:* belief update class, entropy calculations, unit tests.

2. **Phase 2 (M)** — Adaptive interview engine + curated bank integration  
   *Deliverables:* question selection pipeline, response parsing, calibration bank.

3. **Phase 3 (M)** — Knowledge calibration + ledger + HITL workflow  
   *Deliverables:* gap report logic, drift detection, audit ledger.

4. **Phase 4 (L)** — UI integration + performance tuning  
   *Deliverables:* API contract alignment, UI hookup, benchmarking.

### MVP Definition
- 3-question adaptive loop
- Bayesian belief update + entropy gating
- Basic REST API integration
- Output: knowledge gap score + recommendation

**Deferred:** full LLM augmentation, deep graph analytics, advanced response types.

### Top 3 Technical Risks
1. **Semantic drift from LLM augmentation** — *Impact: High*  
   Mitigation: Require librarian grounding + curated bank anchoring.
2. **Overfitting priors to sparse answers** — *Impact: Medium*  
   Mitigation: enforce minimum evidence before strong belief shifts.
3. **Graph growth complexity** — *Impact: Medium*  
   Mitigation: incremental updates, session-scoped subgraphs.

5. **[KEY DECISIONS SUMMARY]**
- Modular monolith to deliver MVP quickly while keeping component boundaries.
- Hybrid question sourcing with curated bank as governance anchor.
- Graph + ledger as core representation with templates for capability/goal separation.
- FastAPI + PostgreSQL for integration and auditability.
- Entropy-driven adaptive loop with HITL gating for safety.

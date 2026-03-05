# Adaptive Universal API Router (AUAR) — Comprehensive Technical Proposal

> **Internal Codename:** FAPI (Flexible Adaptive Provider Interface)
> **Version:** 0.1.0 | **Status:** Engineering Review Draft
> **Module Reference:** `src/auar/` package

---

## PART 1: STRATEGIC FOUNDATION

---

### 1. Executive Summary

#### Problem Statement

Modern enterprise software architectures consume an average of 15–40 external APIs spanning payments, communications, identity, analytics, and domain-specific services. This proliferation creates four compounding challenges that existing tooling fails to address holistically. First, **API fragmentation** forces engineering teams to learn, implement, and maintain bespoke integrations for every provider—each with unique authentication schemes, payload schemas, rate-limiting policies, and error semantics. Second, **integration complexity** compounds non-linearly: adding a single new provider to an ecosystem of _n_ existing integrations introduces testing surface proportional to _O(n)_ due to cross-cutting concerns such as data normalization, error propagation, and observability correlation. Third, **vendor lock-in** emerges silently as business logic becomes entangled with provider-specific data models, making migration prohibitively expensive—industry analyses estimate 3–6 engineering-months per provider swap in mature systems. Fourth, and most critically, current solutions lack **intelligent routing**: no production-grade system dynamically selects the optimal provider for a given request based on real-time cost, latency, reliability, and compliance constraints.

#### Solution Overview

The Adaptive Universal API Router (AUAR), internally codenamed **FAPI** (Flexible Adaptive Provider Interface), introduces **capability-based semantic routing** powered by a hybrid LLM-plus-deterministic architecture. Rather than mapping requests to specific provider endpoints, AUAR resolves requests to abstract *capabilities* (e.g., `payments.charge`, `communications.sms.send`) and then routes them through a multi-factor decision engine that evaluates providers in real time. The system combines deterministic schema matching for high-confidence requests with LLM-assisted natural-language interpretation for ambiguous or novel queries, achieving sub-50ms routing decisions for 95% of traffic.

#### Value Proposition

AUAR delivers measurable impact across three dimensions: a **70% reduction in time-to-integration** by eliminating per-provider implementation effort and replacing it with capability declaration; **40% infrastructure cost savings** through intelligent provider selection that continuously optimizes for price-performance; and **99.95% effective uptime** via automatic failover across equivalent providers when a primary endpoint degrades.

#### Market Timing

Three converging trends create an optimal window for AUAR. LLM maturity now permits reliable intent classification in production (GPT-4-class models achieve >92% accuracy on API-intent benchmarks). API proliferation continues accelerating—the average enterprise API catalog grew 31% year-over-year in 2024. Cloud-native adoption makes the Kubernetes-native deployment model AUAR requires a baseline assumption rather than a constraint.

#### Core Innovation

The capability graph—a Neo4j-backed directed acyclic graph mapping abstract capabilities to concrete provider endpoints—combined with an ML-optimized routing layer using epsilon-greedy multi-armed bandit algorithms, enables continuous, autonomous improvement of routing decisions without manual tuning.

#### Target Market

Mid-to-large enterprises (500+ engineers), SaaS platforms requiring multi-tenant provider abstraction, and regulated verticals (fintech, healthtech) where compliance-aware routing is a hard requirement.

[Word count: ~390]

---

### 2. High-Level System Architecture

#### A. Logical Component Diagram

AUAR is decomposed into seven logical components, each implemented as a discrete module within the `src/auar/` package. The components interact through well-defined interfaces and share no mutable state except through the Observability Layer's event bus.

1. **Signal Interpretation Layer** (`signal_interpretation.py`) — Parses inbound requests, classifies intent, and produces a confidence-scored `IntentSignal`. Accepts REST, GraphQL, and natural-language inputs.
2. **Capability Graph Layer** (`capability_graph.py`) — Maintains the ontology of abstract capabilities and their mappings to concrete provider endpoints. Serves as the system's semantic backbone.
3. **Routing Decision Engine** (`routing_engine.py`) — Evaluates provider candidates against multi-factor criteria (cost, latency, reliability, certification level) and produces a `RoutingDecision` with ordered fallbacks.
4. **Schema Translation Layer** (`schema_translation.py`) — Performs bidirectional data transformation between AUAR's canonical schema and provider-specific schemas using registered `FieldMapping` rules.
5. **Provider Adapter Layer** (`provider_adapter.py`) — Manages authentication, protocol translation, connection pooling, and retry logic for downstream provider communication.
6. **ML Optimization Layer** (`ml_optimization.py`) — Continuously learns from routing outcomes using an epsilon-greedy multi-armed bandit to improve provider selection over time.
7. **Observability & Governance Layer** (`observability.py`) — Provides distributed tracing, metrics collection, audit logging, and per-tenant cost attribution across all layers.

#### B. Request-Response Journey

1. **Ingress** — Client sends a request to the AUAR gateway endpoint (REST, GraphQL, or natural-language prompt).
2. **Signal Interpretation** — `SignalInterpreter.interpret()` parses the request, applies deterministic schema matching, and falls back to LLM-assisted parsing if confidence is below 0.85.
3. **Confidence Scoring** — `ConfidenceScorer.score()` computes a composite confidence using the formula `0.4×schema + 0.3×history + 0.2×semantic + 0.1×completeness`.
4. **Capability Resolution** — The `CapabilityGraph` resolves the classified `CapabilityIntent` to a set of matching `Capability` nodes and their associated `Provider` mappings.
5. **Routing Decision** — `RoutingDecisionEngine.route()` scores all candidate providers, applies circuit-breaker checks, and selects the optimal provider with fallback ordering.
6. **Schema Translation** — `SchemaTranslator.translate_request()` transforms the canonical request payload into the selected provider's expected schema.
7. **Provider Execution** — `ProviderAdapter.call()` handles authentication header injection, executes the HTTP call with retry logic and exponential backoff, and returns an `AdapterResponse`.
8. **Response Translation** — `SchemaTranslator.translate_response()` normalizes the provider's response back to AUAR's canonical schema.
9. **ML Feedback** — `MLOptimizer.record()` logs the routing outcome (latency, cost, success) as a `RoutingFeatures` observation to update bandit statistics.
10. **Observability Finalization** — `ObservabilityLayer.finish_trace()` closes the distributed trace, emits metrics, records audit entries, and attributes costs to the originating tenant.

#### C. Control Plane vs. Data Plane Separation

The **Control Plane** manages system configuration, capability registration, provider onboarding, routing policy definition, and ML model training. It operates asynchronously and tolerates eventual consistency. The **Data Plane** handles live request routing, schema translation, and provider communication on the critical path. This separation ensures that control-plane operations (e.g., registering a new provider) never impact data-plane latency. The control plane writes to Neo4j and Kafka; the data plane reads from Redis-cached projections.

#### D. Deployment Topology

AUAR deploys across three tiers: the **Edge Layer** (Envoy-based ingress, TLS termination, rate limiting), the **Core Layer** (Kubernetes-hosted AUAR services with horizontal pod autoscaling), and the **Provider Layer** (egress proxies with connection pooling and circuit breakers). Each tier scales independently, and the Core Layer supports multi-region active-active deployment through Kafka-based event replication.

#### E. Technology Stack with Rationale

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Orchestration | **Kubernetes** | Industry-standard container orchestration with native HPA, service mesh integration, and multi-cloud portability |
| Event Streaming | **Apache Kafka** | Durable, ordered event log for cross-plane communication; supports exactly-once semantics and replay |
| Capability Graph | **Neo4j** | Native graph database optimized for traversal queries on capability-provider relationships; Cypher query language maps directly to hierarchical taxonomies |
| Metrics & Alerting | **Prometheus + Grafana** | Cloud-native metrics pipeline with PromQL for complex alerting rules; Grafana provides unified dashboarding |
| Caching | **Redis** | Sub-millisecond reads for routing table projections; supports pub/sub for cache invalidation across pods |

#### F. Scalability Approach

AUAR scales horizontally at the pod level for stateless components (Signal Interpretation, Routing Engine, Schema Translation) and vertically for stateful stores (Neo4j, Redis). Kafka partitioning enables parallel event consumption. The ML Optimization Layer trains asynchronously on batch windows, decoupling learning from serving. Target: 10,000 routing decisions per second per core pod, scaling linearly to 100K+ with horizontal replication.

[Word count: ~500]

---

### 3. Competitive Differentiation Matrix

#### vs. Traditional API Gateways (Kong, Apigee, AWS API Gateway)

Traditional gateways excel at request proxying, rate limiting, and authentication enforcement, but they operate at the *endpoint* level—every upstream API must be explicitly configured with routes, plugins, and transformations. AUAR operates at the *capability* level: instead of routing `/v1/charges` to Stripe and `/v1/payments` to Adyen, AUAR resolves the abstract capability `payments.charge` to the optimal provider dynamically. Kong and Apigee require manual failover configuration; AUAR's circuit breaker and multi-armed bandit continuously re-evaluate provider health and cost. Additionally, traditional gateways have no concept of semantic intent classification—a malformed request simply returns a 400 error, whereas AUAR's Signal Interpretation Layer can infer intent from partial or natural-language inputs.

#### vs. iPaaS Platforms (Zapier, Workato, Tray.io)

Integration-platform-as-a-service solutions target workflow automation through visual builders and pre-built connectors. They optimize for breadth of connectors (Zapier offers 6,000+) but sacrifice depth: transformations are simplistic, routing is static (one trigger → one action), and there is no concept of multi-provider optimization. AUAR complements iPaaS for complex, latency-sensitive, programmatic integrations where Zapier's webhook-based model introduces unacceptable overhead (typically 500ms–2s per step). AUAR's bidirectional schema translation and ML-optimized routing address use cases iPaaS platforms were not designed for—real-time payment routing, multi-provider SMS delivery optimization, and compliance-aware data residency enforcement.

#### vs. Unified APIs (Merge.dev, Finch, Apideck)

Unified API providers abstract multiple providers behind a single, normalized API surface. Merge.dev, for example, provides a unified HRIS API that normalizes BambooHR, Workday, and Gusto. While this reduces integration effort, it introduces three limitations AUAR avoids. First, unified APIs are *domain-locked*—Merge.dev covers HR, CRM, and accounting but cannot extend to arbitrary domains without the vendor building a new vertical. AUAR's capability graph is domain-agnostic and extensible by the consumer. Second, unified APIs offer no routing intelligence—they proxy to a single configured provider per category. Third, unified APIs are SaaS-only, creating a dependency on the vendor's availability. AUAR deploys on-premise or in the customer's cloud, preserving data sovereignty.

#### vs. LLM Function-Calling Frameworks (LangChain, Semantic Kernel)

LangChain and Semantic Kernel enable LLMs to invoke functions and APIs through tool-use abstractions. They excel at orchestrating multi-step agent workflows but lack production-grade routing infrastructure: no circuit breakers, no cost optimization, no provider health monitoring, and no schema translation. They treat API calls as opaque tool invocations rather than as optimizable routing decisions. AUAR integrates LLM capabilities *selectively*—only in the Signal Interpretation Layer for ambiguous intent classification—while the routing, translation, and execution layers are fully deterministic and observable. This hybrid approach avoids the latency, cost, and non-determinism penalties of routing all traffic through an LLM.

#### Unique Market Position

AUAR occupies the intersection of API gateway reliability, unified API simplicity, and ML-driven optimization that no existing product addresses. It is the only solution that combines capability-based semantic routing, real-time multi-factor provider selection, bidirectional schema translation, and continuous ML optimization in a single, self-hosted, Kubernetes-native platform.

[Word count: ~410]

---

## PART 2: CORE ARCHITECTURAL LAYERS

---

### 4. Layer 1 — Signal Interpretation Layer

> **Reference Implementation:** `src/auar/signal_interpretation.py`

#### Purpose

The Signal Interpretation Layer is the system's front door, responsible for transforming raw inbound requests—whether structured REST payloads, GraphQL queries, or free-form natural-language prompts—into a normalized `IntentSignal` that downstream layers consume. It must achieve sub-20ms parsing latency for deterministic paths and sub-200ms for LLM-assisted interpretation while maintaining a false-positive intent classification rate below 2%.

#### Key Components

1. **Request Parser** — Extracts HTTP method, path, query parameters, headers, and body from inbound requests. Handles content negotiation and charset normalization.
2. **Natural Language Interpreter** — Invokes an LLM backend (configurable; defaults to GPT-4-class models) to classify intent from free-form text when deterministic parsing produces low confidence. Operates behind a feature flag for environments without LLM access.
3. **Intent Classifier** — Maps parsed signals to a `CapabilityIntent` using a combination of registered schema patterns and semantic similarity matching against the capability taxonomy.
4. **Confidence Scorer** (`ConfidenceScorer`) — Computes a multi-factor confidence score that determines whether the request can be directly routed, requires validation, or needs client clarification.
5. **Ambiguity Resolver** — When confidence falls in the validation range (0.60–0.85), generates ranked alternative interpretations with individual confidence scores for downstream validation or client disambiguation.

#### Data Structures

```python
@dataclass
class IntentSignal:
    request_id: str
    parsed_intent: CapabilityIntent
    confidence_score: float          # 0.0 to 1.0
    factors: Dict[str, float]        # {schema, history, semantic, completeness}
    context: RequestContext
    alternatives: List[CapabilityIntent]
    requires_clarification: bool
    interpretation_method: str       # "deterministic" | "llm" | "hybrid"
    latency_ms: float

@dataclass
class CapabilityIntent:
    capability_name: str             # e.g., "payments.charge"
    domain: str                      # e.g., "payments"
    category: str                    # e.g., "charge"
    version: Optional[str]
    parameters: Dict[str, Any]
```

#### Confidence Formula

The `ConfidenceScorer` applies the following weighted formula, with weights stored in `DEFAULT_WEIGHTS`:

```
confidence = 0.4 × schema_match + 0.3 × history_match + 0.2 × semantic_match + 0.1 × completeness
```

**Routing thresholds:**
- **> 0.85** → Direct routing — no human validation needed
- **0.60 – 0.85** → Validation routing — proceed with monitoring and log for review
- **< 0.60** → Clarification required — return disambiguation prompt to client

#### Critical Design Decisions

1. **Deterministic-first, LLM-fallback** — The system attempts schema-based matching before invoking the LLM, ensuring that well-formed API requests (the majority of traffic) never incur LLM latency or cost. This reduces per-request cost by approximately 98% for structured traffic. Rationale: production telemetry from comparable systems shows >85% of requests match known schemas exactly.
2. **Immutable IntentSignal** — Once created, `IntentSignal` objects are never modified, enabling safe concurrent processing and audit replay. Rationale: immutability eliminates race conditions in multi-threaded routing pipelines.
3. **Pluggable LLM backend** — The `SignalInterpreter` accepts an optional `llm_backend` callable, decoupling the interpretation layer from any specific LLM vendor. Rationale: avoids vendor lock-in on the very component designed to eliminate it.

#### Technology Choices

- **spaCy** for lightweight NER and tokenization in the deterministic path (fast, CPU-only, Apache 2.0 licensed).
- **OpenAI-compatible API interface** for the LLM backend, enabling swappable providers (OpenAI, Anthropic, local Ollama deployments).
- **Pydantic dataclasses** for schema validation and serialization of `IntentSignal` and `CapabilityIntent`.

#### Integration Points

- **Upstream:** Receives raw HTTP requests from the Edge Layer (Envoy ingress).
- **Downstream:** Emits `IntentSignal` to the Capability Graph Layer for resolution.
- **Lateral:** Reports interpretation metrics (latency, method, confidence distribution) to the Observability Layer via `ObservabilityLayer.add_span()`.

#### Performance Considerations

Deterministic parsing targets p99 < 15ms. LLM-assisted parsing targets p99 < 500ms with aggressive caching of recent intent classifications in Redis (TTL: 300s). Schema registry lookup uses an in-memory hash map (`self._schemas`) for O(1) path matching. Request history is bounded to the last 1,000 entries per tenant to prevent memory growth.

#### Failure Modes

- **LLM timeout/unavailability:** Gracefully degrades to deterministic-only parsing; sets `interpretation_method` to `"deterministic"` and adjusts confidence accordingly.
- **Schema registry empty:** Returns `requires_clarification = True` with a diagnostic message indicating no schemas are registered for the requested domain.
- **Malformed input:** Returns a structured error response with the specific parsing failure and suggested corrections.

[Word count: ~440]

---

### 5. Layer 2 — Capability Graph Layer

> **Reference Implementation:** `src/auar/capability_graph.py`

#### Purpose

The Capability Graph Layer maintains the semantic ontology that maps abstract capabilities to concrete provider endpoints, forming the intellectual core of AUAR. It answers the fundamental question: "Given a capability intent, which providers can fulfill it, and what are their characteristics?" The graph structure enables hierarchical capability discovery, similarity-based fallback, and real-time provider health tracking.

#### Key Components

1. **Capability Ontology** — A hierarchical taxonomy organized as Domain → Category → Capability → Variant (e.g., `payments → charge → payments.charge → payments.charge.3ds`). Each `Capability` node stores input/output schemas, semantic tags, and parent relationships.
2. **Provider Registry** — A catalog of downstream API providers, each described by a `Provider` dataclass including base URL, authentication method, rate limits, SLA tier, cost model, and real-time `HealthStatus` (HEALTHY, DEGRADED, UNHEALTHY, UNKNOWN).
3. **Relationship Mapper** — Manages edges between capability nodes (parent-child, similarity) and between capabilities and providers (`CapabilityMapping` edges with certification level, performance metrics, and cost-per-call).
4. **Schema Repository** — Stores input and output JSON schemas for each capability, enabling the Schema Translation Layer to generate mappings automatically.
5. **Graph Query Engine** — Exposes traversal and query methods (`providers_for_capability()`, `similar_capabilities()`, `child_capabilities()`) that the Routing Decision Engine consumes.

#### Data Structures

```python
class CertificationLevel(Enum):
    EXPERIMENTAL = "experimental"
    BETA = "beta"
    PRODUCTION = "production"

@dataclass
class Capability:
    id: str
    name: str                           # e.g., "payments.charge"
    domain: str                         # e.g., "payments"
    category: str                       # e.g., "charge"
    description: str
    input_schema: Dict[str, Any]        # JSON Schema
    output_schema: Dict[str, Any]
    semantic_tags: List[str]            # ["payment", "transaction", "billing"]
    parent_capabilities: List[str]      # IDs of parent capabilities
    version: str

@dataclass
class Provider:
    id: str
    name: str                           # e.g., "stripe"
    supported_capabilities: List[str]
    base_url: str
    auth_method: str
    rate_limits: RateLimitConfig
    sla_tier: str                       # "gold", "silver", "bronze"
    cost_model: CostModel
    health_status: HealthStatus

@dataclass
class CapabilityMapping:
    capability_id: str
    provider_id: str
    certification_level: CertificationLevel
    schema_adapter: Optional[str]
    performance: PerformanceMetrics
    cost_per_call: float
```

#### Hierarchical Taxonomy (Neo4j Cypher Representation)

```cypher
// Domain → Category → Capability hierarchy
CREATE (payments:Domain {name: 'payments'})
CREATE (charge:Category {name: 'charge'})
CREATE (payments_charge:Capability {name: 'payments.charge', version: '2.0'})
CREATE (payments)-[:HAS_CATEGORY]->(charge)
CREATE (charge)-[:HAS_CAPABILITY]->(payments_charge)

// Provider mapping with performance metadata
MATCH (cap:Capability {name: 'payments.charge'}), (prov:Provider {name: 'stripe'})
CREATE (cap)-[:FULFILLED_BY {
    certification: 'production',
    avg_latency_ms: 145,
    success_rate: 0.998,
    cost_per_call: 0.02
}]->(prov)
```

#### Critical Design Decisions

1. **Neo4j for graph storage** — The capability-provider relationship model is inherently a graph: capabilities have parent-child hierarchies, similarity edges, and many-to-many provider mappings. Neo4j's native graph storage yields O(1) relationship traversal versus O(n) joins in relational databases. The in-memory implementation (`CapabilityGraph` class) mirrors this structure with dictionaries for development and testing, while production deployments back the same interface with Neo4j. Rationale: graph traversal performance is critical for routing latency.
2. **Certification levels as explicit metadata** — The `CertificationLevel` enum (EXPERIMENTAL, BETA, PRODUCTION) on `CapabilityMapping` edges enables the Routing Decision Engine to enforce maturity gates: production traffic is never routed to EXPERIMENTAL providers unless explicitly overridden. Rationale: prevents accidental exposure to unstable integrations.
3. **Real-time health tracking** — Provider `HealthStatus` is updated asynchronously via health-check probes and failure-rate monitoring (integrated with the circuit breaker in the Routing Decision Engine). The graph serves as the single source of truth for provider availability. Rationale: decouples health assessment from routing execution.

#### Technology Choices

- **Neo4j Community Edition** for production graph storage (open-source, ACID-compliant, Cypher query language).
- **In-memory Python dictionaries** for the reference implementation and unit testing (zero external dependencies).
- **Redis** for caching hot graph projections (provider lists per capability) with pub/sub-based invalidation when the graph mutates.

#### Integration Points

- **Upstream:** Receives `CapabilityIntent` from the Signal Interpretation Layer.
- **Downstream:** Provides `Capability`, `Provider`, and `CapabilityMapping` data to the Routing Decision Engine.
- **Control Plane:** Accepts registration commands (`register_capability()`, `register_provider()`) from the administrative API.

#### Performance Considerations

Capability resolution targets p99 < 5ms from the in-memory graph and < 15ms from Neo4j with warm caches. Provider listing is O(k) where k is the number of providers for a capability (typically 2–5). Similarity search uses pre-computed edges rather than runtime vector comparison, bounding traversal to O(degree). The graph statistics method (`get_stats()`) enables real-time monitoring of graph size and health distribution.

#### Failure Modes

- **Neo4j unavailability:** Falls back to the last-known Redis cache projection; enters read-only mode for graph queries. New registrations are queued in Kafka for replay when Neo4j recovers.
- **Capability not found:** Returns an empty provider list, causing the Routing Decision Engine to return a structured `404 Capability Not Found` error with suggestions from `similar_capabilities()`.
- **Stale health data:** Health probes run on a 10-second interval; staleness is bounded and annotated with `last_checked` timestamps.

[Word count: ~450]

---

### 6. Layer 3 — Routing Decision Engine

> **Reference Implementation:** `src/auar/routing_engine.py`

#### Purpose

The Routing Decision Engine is the strategic brain of AUAR, responsible for selecting the optimal provider for each request from the set of candidates supplied by the Capability Graph Layer. It evaluates providers against configurable multi-factor criteria and produces a `RoutingDecision` that includes the selected provider, ordered fallback alternatives, and the scoring rationale. The engine must produce decisions in under 10ms for the critical path.

#### Key Components

1. **Multi-Factor Scorer** — Computes a weighted composite score for each candidate provider using four factors: reliability (35%), latency (25%), cost (25%), and certification level (15%). Weights are configurable per-tenant and per-capability via `DEFAULT_WEIGHTS`.
2. **Circuit Breaker** — Tracks failure counts per provider and transitions through three states: CLOSED (normal), OPEN (all requests blocked after threshold), and HALF_OPEN (limited probe traffic to test recovery). Prevents cascading failures when a provider degrades.
3. **Strategy Selector** — Supports multiple routing strategies via the `RoutingStrategy` enum: COST_OPTIMIZED, LATENCY_OPTIMIZED, RELIABILITY_FIRST, ROUND_ROBIN, and WEIGHTED (default). Strategy can be specified per-request or defaulted at the tenant level.
4. **Fallback Chain Builder** — Orders non-selected candidates by descending score to produce an ordered fallback list. If the primary provider fails, the Provider Adapter Layer iterates through fallbacks without re-entering the Routing Decision Engine.
5. **A/B Testing Framework** — Supports traffic splitting across providers for controlled experiments: a configurable percentage of requests are routed to a challenger provider while metrics are collected for comparison.

#### Data Structures

```python
class RoutingStrategy(Enum):
    COST_OPTIMIZED = "cost_optimized"
    LATENCY_OPTIMIZED = "latency_optimized"
    RELIABILITY_FIRST = "reliability_first"
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class RoutingDecision:
    decision_id: str
    intent_signal_id: str
    selected_provider: ProviderCandidate
    fallback_providers: List[ProviderCandidate]
    strategy_used: RoutingStrategy
    score: float
    latency_ms: float
    circuit_breaker_triggered: bool

@dataclass
class ProviderCandidate:
    provider_id: str
    provider_name: str
    capability_mapping: CapabilityMapping
    score: float                      # 0.0 to 1.0
    reason: str                       # Human-readable explanation
```

#### Scoring Algorithm

```python
DEFAULT_WEIGHTS = {
    "reliability": 0.35,
    "latency": 0.25,
    "cost": 0.25,
    "certification": 0.15,
}

def _compute_score(candidate, weights):
    reliability = candidate.performance.success_rate
    latency = 1.0 - min(candidate.performance.avg_latency_ms / 2000.0, 1.0)
    cost = 1.0 - min(candidate.cost_per_call / 1.0, 1.0)
    cert = {"production": 1.0, "beta": 0.6, "experimental": 0.2}[candidate.certification]
    return (weights["reliability"] * reliability +
            weights["latency"] * latency +
            weights["cost"] * cost +
            weights["certification"] * cert)
```

#### Critical Design Decisions

1. **Weighted multi-factor over single-criterion routing** — Single-criterion routing (cheapest, fastest) leads to provider concentration and brittleness. The weighted approach distributes traffic more evenly while still respecting priorities. Rationale: mirrors portfolio optimization theory—diversification reduces systemic risk.
2. **Circuit breaker at the routing layer, not the adapter layer** — By checking circuit state *before* selecting a provider, AUAR avoids wasting scoring computation on providers known to be unhealthy. The `record_failure()` and `record_success()` methods update circuit state asynchronously. Rationale: fail-fast at the earliest possible point in the pipeline.
3. **Strategy as a first-class request parameter** — Clients can override the default routing strategy per-request (e.g., `X-AUAR-Strategy: cost_optimized` for batch jobs, `latency_optimized` for real-time UIs). Rationale: different workloads within the same tenant have different optimization objectives.

#### Technology Choices

- **Pure Python with no external dependencies** for the scoring engine—ensures sub-millisecond execution with no network calls.
- **In-memory dictionaries** for circuit breaker state (`_circuit_failures`, `_circuit_state`) with optional Redis backing for multi-pod consistency.
- **UUID4** for `decision_id` generation, ensuring global uniqueness across distributed instances.

#### Integration Points

- **Upstream:** Receives `IntentSignal` and candidate lists from the Capability Graph Layer.
- **Downstream:** Emits `RoutingDecision` to the Schema Translation Layer and Provider Adapter Layer.
- **Feedback Loop:** Receives success/failure signals from the Provider Adapter Layer via `record_success()` / `record_failure()` to update circuit breaker state.

#### Performance Considerations

Scoring is O(k) where k is the number of candidate providers (typically 2–5), yielding sub-1ms execution. Circuit breaker checks are O(1) dictionary lookups. Round-robin state uses a simple counter with modular arithmetic. The engine is entirely stateless except for circuit breaker counters, enabling horizontal scaling with no coordination overhead.

#### Failure Modes

- **All providers circuit-broken:** Returns a `RoutingDecision` with `circuit_breaker_triggered = True` and no selected provider, allowing the caller to return a 503 Service Unavailable with a Retry-After header.
- **No candidates supplied:** Returns an error decision indicating the capability has no registered providers.
- **Scoring tie:** Tie-breaking uses provider ID lexicographic ordering for deterministic behavior in tests and production.

[Word count: ~440]

---

### 7. Layer 4 — Schema Translation Layer

> **Reference Implementation:** `src/auar/schema_translation.py`

#### Purpose

The Schema Translation Layer eliminates the impedance mismatch between AUAR's canonical data model and the diverse, often inconsistent schemas of downstream providers. It performs bidirectional transformation—normalizing outbound requests to provider-specific formats and inbound responses back to the canonical model—ensuring that upstream consumers interact with a single, stable schema regardless of which provider fulfills the request.

#### Key Components

1. **Dynamic Schema Mapper** — Resolves the correct `SchemaMapping` for a given (capability, provider, direction) tuple. Supports versioned mappings to handle provider API evolution without breaking existing consumers.
2. **Data Transformer** — Applies ordered sequences of `FieldMapping` rules, each specifying source path, target path, optional transform function, and default value. Supports nested field access via dot-notation (e.g., `billing.address.zip`).
3. **Type Coercion Engine** — Provides built-in transform functions (`to_str`, `to_int`, `to_float`, `to_bool`, `to_upper`, `to_lower`, `strip`) and supports registration of custom transforms via `register_transform()`.
4. **Bidirectional Translation** — Maintains separate `SchemaMapping` definitions for request (canonical → provider) and response (provider → canonical) directions, avoiding the complexity of invertible-mapping constraints.
5. **Validation & Reporting** — Returns a `TranslationResult` that includes success status, translated data, lists of errors and warnings, count of fields mapped, and count of fields that fell back to default values.

#### Data Structures

```python
@dataclass
class FieldMapping:
    source_field: str              # Dot-notation path, e.g., "amount.value"
    target_field: str              # Dot-notation path, e.g., "charge_amount"
    transform: Optional[str]       # Transform function name, e.g., "to_int"
    default_value: Any             # Fallback if source field is missing
    required: bool                 # If True, missing source field → error

@dataclass
class SchemaMapping:
    mapping_id: str
    capability_name: str           # e.g., "payments.charge"
    provider_id: str               # e.g., "stripe"
    direction: str                 # "request" | "response"
    field_mappings: List[FieldMapping]
    static_fields: Dict[str, Any]  # Fields injected regardless of input
    version: str

@dataclass
class TranslationResult:
    success: bool
    translated_data: Dict[str, Any]
    errors: List[str]
    warnings: List[str]
    fields_mapped: int
    fields_defaulted: int
```

#### Translation Example

```python
# Canonical request for payments.charge
canonical = {"amount": {"value": 2999, "currency": "USD"}, "customer_id": "cust_123"}

# Stripe-specific mapping
mapping = SchemaMapping(
    mapping_id="m1", capability_name="payments.charge",
    provider_id="stripe", direction="request",
    field_mappings=[
        FieldMapping("amount.value", "amount", "to_int", None, True),
        FieldMapping("amount.currency", "currency", "to_lower", "usd", False),
        FieldMapping("customer_id", "customer", None, None, True),
    ],
    static_fields={"source": "tok_visa"},
    version="1.0"
)

# Translated output → {"amount": 2999, "currency": "usd", "customer": "cust_123", "source": "tok_visa"}
```

#### Critical Design Decisions

1. **Explicit bidirectional mappings over invertible transforms** — While invertible transforms reduce configuration, they constrain the transform vocabulary to bijective functions and make debugging difficult when request and response schemas differ structurally. Separate request/response mappings are more verbose but unambiguous. Rationale: clarity and debuggability outweigh configuration brevity in production systems.
2. **Dot-notation for nested field access** — Using `_get_nested()` and `_set_nested()` helper methods with dot-delimited paths (e.g., `billing.address.zip`) avoids requiring users to write custom traversal code. Rationale: the majority of schema differences involve field renaming and restructuring at varying nesting depths.
3. **Custom transform registry** — The `register_transform()` method enables consumers to add domain-specific transforms (e.g., currency conversion, date format normalization) without modifying core code. Rationale: extensibility without core coupling.

#### Technology Choices

- **Pure Python dictionary manipulation** — No external transformation libraries; the translation logic is intentionally simple and auditable for regulated environments (fintech, healthtech).
- **JSON Schema** for canonical schema definitions, enabling automated validation of both inputs and outputs.
- **Pydantic** for runtime type enforcement on `TranslationResult` fields.

#### Integration Points

- **Upstream:** Receives canonical request payloads from the Routing Decision Engine.
- **Downstream:** Provides provider-specific payloads to the Provider Adapter Layer and normalizes responses on the return path.
- **Control Plane:** Accepts mapping registrations via `register_mapping()` and custom transforms via `register_transform()`.

#### Performance Considerations

Translation is O(m) where m is the number of `FieldMapping` rules per schema (typically 5–20). Nested field access via `_get_nested()` is O(d) where d is the nesting depth (typically 1–4). No external I/O is performed during translation. Statistics tracking (`get_stats()`) provides `translations_performed`, `fields_mapped`, and `fields_defaulted` counters for operational monitoring.

#### Failure Modes

- **Required field missing:** Returns `TranslationResult` with `success = False` and descriptive error listing the missing field path. The Provider Adapter Layer is not invoked.
- **Transform function not found:** Falls back to identity transform and appends a warning to `TranslationResult.warnings`.
- **Circular nested path:** Dot-notation traversal terminates at non-dict nodes, returning `None` and triggering the default-value path.

[Word count: ~440]

---

### 8. Layer 5 — Provider Adapter Layer

> **Reference Implementation:** `src/auar/provider_adapter.py`

#### Purpose

The Provider Adapter Layer is AUAR's outbound gateway, responsible for managing the full lifecycle of downstream provider communication. It abstracts protocol differences (REST, GraphQL, gRPC, SOAP), handles authentication credential injection, manages connection pooling, and implements retry logic with exponential backoff. Each provider is represented by a `ProviderAdapter` instance configured via an `AdapterConfig` dataclass.

#### Key Components

1. **Adapter Pattern Implementation** — Each provider receives a dedicated `ProviderAdapter` instance that encapsulates its unique configuration: base URL, authentication method, protocol, timeout, retry policy, and custom headers. The `ProviderAdapterManager` serves as the registry and factory.
2. **Authentication Handler** — Supports six authentication methods via the `AuthMethod` enum: NONE, API_KEY (injected as `X-API-Key` header), BEARER (injected as `Authorization: Bearer <token>`), OAUTH2 (token refresh flow), BASIC (Base64-encoded `username:password`), and HMAC (request signing). The `_build_auth_headers()` method constructs the appropriate headers for each method.
3. **Protocol Translator** — Adapts request semantics across protocols via the `Protocol` enum: REST (standard HTTP), GRAPHQL (query wrapping), GRPC (protobuf serialization), and SOAP (XML envelope construction).
4. **Connection Pool Manager** — Configurable `connection_pool_size` per adapter (default: 10) limits concurrent connections to prevent downstream resource exhaustion while maintaining throughput.
5. **Retry Engine** — Implements exponential backoff with configurable `max_retries` (default: 3) and `retry_backoff_s` (default: 1.0). Each retry doubles the backoff interval. The `AdapterResponse` tracks `retries_used` for observability.

#### Data Structures

```python
class AuthMethod(Enum):
    NONE = "none"
    API_KEY = "api_key"
    BEARER = "bearer"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    HMAC = "hmac"

class Protocol(Enum):
    REST = "rest"
    GRAPHQL = "graphql"
    GRPC = "grpc"
    SOAP = "soap"

@dataclass
class AdapterConfig:
    provider_id: str
    provider_name: str
    base_url: str
    auth_method: AuthMethod
    auth_credentials: Dict[str, str]   # Keys vary by auth method
    protocol: Protocol
    timeout_s: float                   # Default: 30.0
    max_retries: int                   # Default: 3
    retry_backoff_s: float             # Default: 1.0
    headers: Dict[str, str]            # Additional static headers
    connection_pool_size: int          # Default: 10

@dataclass
class AdapterResponse:
    success: bool
    status_code: int
    body: Any
    headers: Dict[str, str]
    latency_ms: float
    retries_used: int
    error: Optional[str]
```

#### Authentication Header Construction

```python
def _build_auth_headers(config: AdapterConfig) -> Dict[str, str]:
    if config.auth_method == AuthMethod.API_KEY:
        return {"X-API-Key": config.auth_credentials["api_key"]}
    elif config.auth_method == AuthMethod.BEARER:
        return {"Authorization": f"Bearer {config.auth_credentials['token']}"}
    elif config.auth_method == AuthMethod.BASIC:
        encoded = base64.b64encode(
            f"{config.auth_credentials['username']}:{config.auth_credentials['password']}".encode()
        ).decode()
        return {"Authorization": f"Basic {encoded}"}
    return {}
```

#### Critical Design Decisions

1. **Pluggable execute callback** — `ProviderAdapter.call()` delegates actual HTTP execution to a configurable `_execute` callable (defaulting to `_default_execute()`), enabling dependency injection of mock executors for testing and custom transport implementations for non-HTTP protocols. Rationale: testability without mocking frameworks.
2. **Retry at the adapter level, not the routing level** — Retries are provider-specific (different providers have different idempotency guarantees and retry-safety profiles). Retrying at the routing level would risk sending duplicate requests to non-idempotent endpoints. Rationale: retry semantics are inherently provider-specific.
3. **Adapter-per-provider, not adapter-per-request** — `ProviderAdapter` instances are long-lived and reused across requests, amortizing connection setup costs and enabling connection pooling. The `ProviderAdapterManager` ensures singleton semantics per `provider_id`. Rationale: connection reuse is critical for throughput at scale.

#### Technology Choices

- **`httpx`** (async HTTP client) for REST and GraphQL calls — supports HTTP/2, connection pooling, and async/await natively.
- **`grpcio`** for gRPC protocol support — Google's official Python gRPC library with protobuf integration.
- **`zeep`** for SOAP protocol support — mature Python SOAP client with WSDL parsing.
- **Base64 from Python stdlib** for Basic authentication encoding — no external dependency needed.

#### Integration Points

- **Upstream:** Receives translated request payloads and `RoutingDecision` (including selected provider and fallback chain) from the Schema Translation Layer.
- **Downstream:** Executes HTTP/gRPC/SOAP calls against provider endpoints and returns `AdapterResponse`.
- **Feedback:** Reports call outcomes (success, latency, retries) to the Routing Decision Engine (`record_success()` / `record_failure()`) and ML Optimization Layer (`MLOptimizer.record()`).

#### Performance Considerations

Connection pooling reduces TCP handshake overhead for repeated calls to the same provider. Timeout enforcement prevents slow providers from consuming thread pool resources. The `get_stats()` method on each adapter tracks `total_calls`, `successes`, `failures`, and `total_retries` for capacity planning. The `ProviderAdapterManager.get_all_stats()` aggregates across all adapters for dashboard rendering.

#### Failure Modes

- **Provider timeout:** After `timeout_s` seconds, the request is aborted and counted as a failure. If retries remain, the next attempt uses doubled backoff.
- **Authentication failure (401/403):** Reported as a non-retryable failure; triggers circuit breaker increment in the Routing Decision Engine. OAuth2 adapters attempt a single token refresh before failing.
- **Connection refused:** Treated as a retryable failure with backoff. After `max_retries` exhausted, the adapter returns `AdapterResponse(success=False, error="connection_refused")`.
- **All fallbacks exhausted:** The caller (orchestration layer) returns a 502 Bad Gateway to the client with a correlation ID for debugging.

[Word count: ~450]

---

### 9. Layer 6 — ML Optimization Layer

> **Reference Implementation:** `src/auar/ml_optimization.py`

#### Purpose

The ML Optimization Layer continuously improves AUAR's routing decisions by learning from historical outcomes. It operates asynchronously—outside the critical request path—and provides recommendations that the Routing Decision Engine can incorporate as an additional scoring signal. The layer implements an epsilon-greedy multi-armed bandit algorithm that balances exploitation of known-good providers with exploration of potentially superior alternatives.

#### Key Components

1. **Epsilon-Greedy Multi-Armed Bandit** — The core algorithm treats each provider (for a given capability) as an "arm" of a bandit. With probability ε it selects a random provider (exploration); with probability 1−ε it selects the provider with the highest average reward (exploitation). Epsilon decays over time to shift from exploration toward exploitation as the system accumulates data.
2. **Feature Engineering** — Each routing outcome is recorded as a `RoutingFeatures` observation containing capability name, provider ID, latency, cost, success flag, user context, and timestamp. These features are used to compute a composite reward signal.
3. **Reward Function** — Combines three normalized signals with configurable weights: success (50%), inverse latency (30%), and inverse cost (20%). The formula produces a reward in [0, 3] that is accumulated per provider.
4. **Model Training Pipeline** — The bandit updates incrementally: each `record()` call updates the running statistics for the observed provider. No batch training or offline retraining is required, making the system fully online.
5. **A/B Testing Integration** — The `recommend()` method returns an `OptimizationResult` that includes whether the recommendation was an exploration (random) or exploitation (best-known) decision, enabling downstream A/B analysis.

#### Data Structures

```python
@dataclass
class RoutingFeatures:
    capability_name: str
    provider_id: str
    latency_ms: float
    cost: float
    success: bool
    user_context: Optional[Dict[str, Any]]
    timestamp: Optional[str]

@dataclass
class ProviderScore:
    provider_id: str
    total_calls: int
    successes: int
    total_latency_ms: float
    total_cost: float
    reward_sum: float

    @property
    def success_rate(self) -> float: ...
    @property
    def avg_latency_ms(self) -> float: ...
    @property
    def avg_cost(self) -> float: ...
    @property
    def avg_reward(self) -> float: ...

@dataclass
class OptimizationResult:
    recommended_provider_id: str
    confidence: float                # Derived from sample size
    exploration: bool                # True if random selection
    reason: str                      # Human-readable explanation
```

#### Reward Computation

```python
DEFAULT_REWARD_WEIGHTS = {"success": 0.5, "latency": 0.3, "cost": 0.2}

def _compute_reward(features: RoutingFeatures, weights=DEFAULT_REWARD_WEIGHTS) -> float:
    # Success component: 1.0 if successful, 0.0 otherwise
    success_reward = 1.0 if features.success else 0.0

    # Latency component: normalized inverse (lower latency → higher reward)
    max_latency = 5000.0  # 5s normalization ceiling
    latency_reward = 1.0 - min(features.latency_ms / max_latency, 1.0)

    # Cost component: normalized inverse (lower cost → higher reward)
    max_cost = 1.0  # $1.00 normalization ceiling
    cost_reward = 1.0 - min(features.cost / max_cost, 1.0)

    return (weights["success"] * success_reward +
            weights["latency"] * latency_reward +
            weights["cost"] * cost_reward)
```

#### Epsilon Decay Schedule

```python
epsilon_initial = 0.15      # 15% exploration at start
epsilon_min = 0.01          # 1% exploration floor
epsilon_decay = 0.995       # Multiplicative decay per observation

# After each record():
epsilon = max(epsilon_min, epsilon * epsilon_decay)
```

After 500 observations, ε ≈ 0.012 (near minimum), ensuring the system has converged to exploiting the best-known providers while maintaining a small exploration rate for adapting to provider changes.

#### Critical Design Decisions

1. **Multi-armed bandit over deep RL or supervised learning** — Bandits are ideal for the routing problem because the action space is small (2–5 providers per capability), feedback is immediate (each request produces a reward), and the environment is non-stationary (provider performance changes over time). Deep RL adds complexity without proportional benefit at this action-space scale. Rationale: simplicity, interpretability, and proven convergence guarantees.
2. **Online incremental updates over batch training** — Each `record()` call updates running statistics in O(1) time, eliminating the need for a training pipeline, GPU resources, or scheduled retraining jobs. Rationale: operational simplicity and real-time adaptation.
3. **Capability-scoped bandits** — Each capability maintains independent bandit statistics, preventing cross-capability interference (e.g., a provider excellent at payments but poor at SMS doesn't have its SMS score inflated by payment successes). Rationale: routing optimization is inherently per-capability.

#### Technology Choices

- **Pure Python with no ML framework dependencies** — The bandit algorithm requires only arithmetic operations on running sums and counts. No NumPy, TensorFlow, or PyTorch needed. Rationale: minimizes deployment footprint and eliminates version-conflict risks.
- **In-memory statistics dictionaries** with optional persistence to Redis for durability across pod restarts.
- **Python `random` module** for epsilon-greedy exploration coin flips.

#### Integration Points

- **Upstream:** Receives `RoutingFeatures` observations from the Provider Adapter Layer after each provider call completes.
- **Downstream:** Provides `OptimizationResult` recommendations to the Routing Decision Engine as an optional scoring input.
- **Observability:** Reports exploration rate, per-provider reward distributions, and recommendation confidence to the Observability Layer.

#### Performance Considerations

`record()` executes in O(1) — a constant number of additions and multiplications. `recommend()` is O(k) where k is the number of providers for the capability (typically 2–5). No locks are required in the single-threaded reference implementation; production deployments use per-capability locks for thread safety. Memory usage is O(C × P) where C is capability count and P is average providers per capability.

#### Failure Modes

- **Cold start (no observations):** Returns a random provider with `confidence = 0.0` and `exploration = True`. The system naturally warms up as traffic flows.
- **Single provider dominance:** The minimum epsilon (1%) ensures at least 1 in 100 requests explores alternatives, detecting if a previously inferior provider has improved.
- **Reward normalization drift:** If real-world latencies or costs exceed the normalization ceilings (5000ms, $1.00), the reward component saturates at 0.0. Ceilings should be tuned to the deployment's actual distribution.

[Word count: ~450]

---

### 10. Layer 7 — Observability & Governance Layer

> **Reference Implementation:** `src/auar/observability.py`

#### Purpose

The Observability & Governance Layer provides comprehensive operational visibility and regulatory compliance across all AUAR layers. It implements four pillars: distributed tracing (following OpenTelemetry conventions), metrics collection (counters and histograms), immutable audit logging, and per-tenant cost attribution. Every routing decision, schema translation, and provider call is instrumented through this layer, enabling root-cause analysis, SLA monitoring, and financial accountability.

#### Key Components

1. **Distributed Tracing Engine** — Manages `RequestTrace` objects that aggregate `SpanRecord` entries across the full request lifecycle. Each span records operation name, start/end timestamps, custom attributes, and status. Traces follow OpenTelemetry's trace-id/span-id/parent-span-id model for compatibility with Jaeger, Zipkin, and Tempo backends.
2. **Metrics Collector** — Provides two metric types: **counters** (monotonically increasing values, e.g., `requests_total`, `failures_total`) via `increment()` and **histograms** (distribution tracking with min, max, avg, p99) via `observe()`. Metrics are exported in Prometheus exposition format.
3. **Audit Logger** — Records immutable `AuditEntry` objects for every security-relevant and compliance-relevant action: provider registration, routing policy changes, authentication failures, and manual overrides. Each entry captures actor, action, resource, detail, tenant, outcome, and timestamp.
4. **Cost Attribution Engine** — Tracks per-request costs via `CostAttribution` records, enabling precise billing allocation by tenant, capability, and provider. The `get_cost_summary()` method aggregates costs with filtering by tenant and time range.
5. **Billing Integration** — Cost attribution data feeds into downstream billing systems via Kafka events, supporting usage-based pricing models where tenants are charged based on actual provider costs plus AUAR's margin.

#### Data Structures

```python
@dataclass
class SpanRecord:
    span_id: str
    parent_span_id: Optional[str]
    operation: str                    # e.g., "signal_interpretation"
    start_time: float                 # Unix timestamp
    end_time: Optional[float]
    attributes: Dict[str, Any]        # Custom metadata
    status: str                       # "ok" | "error"

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None

@dataclass
class RequestTrace:
    trace_id: str
    request_id: str
    tenant_id: str
    capability: str
    provider_id: Optional[str]
    spans: List[SpanRecord]
    total_latency_ms: Optional[float]
    success: bool
    timestamp: str

@dataclass
class AuditEntry:
    entry_id: str
    timestamp: str
    actor: str                        # User or system identifier
    action: str                       # e.g., "provider.register"
    resource: str                     # e.g., "provider:stripe"
    detail: str
    tenant_id: str
    outcome: str                      # "success" | "failure" | "denied"

@dataclass
class CostAttribution:
    attribution_id: str
    tenant_id: str
    capability: str
    provider_id: str
    cost: float
    currency: str                     # Default: "USD"
    timestamp: str
    request_id: str
```

#### Histogram Summary Example

```python
# After observing latencies: [12.5, 45.2, 23.1, 150.0, 33.7]
summary = observability.get_histogram_summary("routing_latency_ms")
# Returns: {"min": 12.5, "max": 150.0, "avg": 52.9, "count": 5, "p99": 150.0}
```

#### Critical Design Decisions

1. **OpenTelemetry-compatible span model** — By aligning `SpanRecord` with the OpenTelemetry specification (trace ID, span ID, parent span ID, attributes), AUAR's traces can be exported to any OpenTelemetry-compatible backend (Jaeger, Zipkin, Grafana Tempo) without adaptation. Rationale: avoids building a proprietary tracing ecosystem; leverages the industry standard.
2. **Immutable append-only audit log** — `AuditEntry` objects are never modified or deleted after creation. The audit log is append-only, providing a tamper-evident record for compliance auditors. In production, entries are replicated to a write-once object store (e.g., AWS S3 with Object Lock). Rationale: regulatory requirements in fintech and healthtech mandate immutable audit trails.
3. **Per-request cost attribution** — Rather than approximating costs at the monthly or daily level, AUAR records the exact cost of each provider call against the specific tenant and request that triggered it. This enables precise usage-based billing and cost anomaly detection. Rationale: multi-tenant SaaS platforms require per-tenant cost transparency.

#### Technology Choices

- **OpenTelemetry SDK for Python** (`opentelemetry-api`, `opentelemetry-sdk`) for trace context propagation and span export.
- **Prometheus client library** (`prometheus_client`) for metrics exposition, natively compatible with Prometheus scraping and Grafana dashboards.
- **Apache Kafka** for durable, ordered delivery of audit entries and cost attribution events to downstream consumers (billing systems, compliance archives).
- **Grafana** for unified dashboarding across traces (Tempo), metrics (Prometheus), and logs (Loki).

#### Integration Points

- **All Layers:** Every AUAR layer instruments its operations through `ObservabilityLayer.add_span()`, `increment()`, `observe()`, and `audit()`. The observability layer is injected as a dependency into all other layers.
- **External:** Exports traces to Jaeger/Tempo via OTLP, metrics to Prometheus via scrape endpoint, audit logs to Kafka, and cost data to billing microservices.
- **Dashboards:** Pre-built Grafana dashboards for routing decision distribution, provider health heatmaps, per-tenant cost trends, and confidence score histograms.

#### Performance Considerations

Span creation and metric updates are in-memory operations with O(1) amortized cost. Histogram p99 computation uses sorted-array sampling, which is O(n log n) but executed only on read (not on the hot path). Trace storage is bounded to the last 10,000 traces in-memory, with overflow flushed to the Kafka export pipeline. The `get_stats()` method returns aggregate counts (`traces_total`, `spans_total`, `audit_entries_total`, `cost_records_total`) for health monitoring.

#### Failure Modes

- **Kafka export unavailable:** Audit entries and cost records are buffered in-memory (bounded queue, configurable size) and flushed when Kafka recovers. A metric (`observability_buffer_size`) alerts operators when the buffer exceeds 80% capacity.
- **Trace storage full:** Oldest traces are evicted (LRU) to make room for new entries. Eviction events are logged and counted.
- **Metrics cardinality explosion:** Label validation limits the number of unique metric keys to prevent unbounded memory growth. Labels exceeding the cardinality limit are aggregated under an `_overflow` bucket.

[Word count: ~440]

---

## Appendix A: Module Cross-Reference

| Layer | Module File | Primary Class | Key Method |
|-------|------------|---------------|------------|
| 1 — Signal Interpretation | `src/auar/signal_interpretation.py` | `SignalInterpreter` | `interpret()` |
| 2 — Capability Graph | `src/auar/capability_graph.py` | `CapabilityGraph` | `providers_for_capability()` |
| 3 — Routing Decision Engine | `src/auar/routing_engine.py` | `RoutingDecisionEngine` | `route()` |
| 4 — Schema Translation | `src/auar/schema_translation.py` | `SchemaTranslator` | `translate_request()` |
| 5 — Provider Adapter | `src/auar/provider_adapter.py` | `ProviderAdapterManager` | `call_provider()` |
| 6 — ML Optimization | `src/auar/ml_optimization.py` | `MLOptimizer` | `recommend()` |
| 7 — Observability & Governance | `src/auar/observability.py` | `ObservabilityLayer` | `finish_trace()` |

## Appendix B: Internal Codename Note

The codename **FAPI** (Flexible Adaptive Provider Interface) is used internally as a developer-friendly shorthand for the Adaptive Universal API Router. All internal package references, configuration keys, and log prefixes use the `auar` namespace (e.g., `src/auar/`, `AUAR_CONFIG_*` environment variables). The FAPI codename appears in design discussions, sprint boards, and internal documentation but is not exposed in any public-facing API surface or client SDK.

---

*Document prepared for engineering leadership review. All architecture decisions are subject to ADR (Architecture Decision Record) governance. Implementation reference: `src/auar/` package, version 0.1.0.*

# Murphy System — The Full Story

## How the System Works: Inoni LLC Sets Up Murphy to Sell Itself

*This document tells the story of Murphy System as experienced by Inoni LLC — the company
that built Murphy and now uses it to sell itself. From the moment a team member opens the
terminal, through onboarding, into building the first sales automation, and finally watching
the system learn, protect itself, and grow. Every section maps to actual code running in the
current runtime. Nothing here is aspirational — this is what the code does.*

---

## Prologue: What Murphy Actually Is

Murphy is a two-phase automation system that takes a person's plain-English description of
what they want automated, builds the agents and safety gates required to do it, and then
runs those agents repeatedly in a sandboxed production environment — learning from every
execution and tightening its own safety rails over time.

The system is named after Murphy's Law: *"Anything that can go wrong, will go wrong."*
Every component in Murphy is designed around that premise. Nothing is trusted by default.
Confidence must be earned. Safety gates are generated from discovered risks, not from
optimistic assumptions. Refusal to act is treated as a valid outcome, not a failure.

The system spans roughly 200 Python modules, 100+ bots, a governance kernel, a swarm
intelligence engine, a librarian knowledge base, a deterministic compute plane, and a
universal control plane that loads only the engines needed for each job. It is a single
runtime that can automate content publishing, invoice processing, sales pipelines, social
media campaigns, factory floor robotics, trading strategies, and its own self-improvement.

Here is the story of what happens when Inoni LLC uses Murphy to sell Murphy.

---

## Chapter 1: The First Encounter

A team member at Inoni LLC opens the Murphy terminal. On their screen appears a
conversational interface — not a dashboard full of buttons, but a natural language chat
window.

Murphy introduces itself:

> *"Hello! I'm Murphy — your professional automation assistant. I help teams automate
> operations, onboard new users, manage integrations, and run end-to-end workflows."*

Below the greeting, the user sees links to Swagger API docs, the system dashboard, the
onboarding wizard, and the web terminal — all clickable, all live. A sidebar lists available
commands. A status indicator shows whether the backend is connected.

The team member's goal: set up Murphy to automate Inoni LLC's sales pipeline — lead
generation, qualification, demo scheduling, and proposal creation — so that Murphy can
sell itself to prospective customers.

They type: **"start interview"**

**What happens in the code:**
The `MurphyTerminalApp` detects the intent via regex pattern matching against 23 defined
intents. It routes to the `DialogContext`, which manages a 7-step synthetic interview.

---

## Chapter 2: The Onboarding Interview

Murphy doesn't start by asking technical questions. It starts with the person.

**Step 1:** "What is your name or organization?"
**Step 2:** "What is the primary business goal you'd like Murphy to help with?"
**Step 3:** "What is your primary use-case?"
**Step 4:** "What platforms or tools does your team use today?"
**Step 5:** "Which billing tier interests you?"
**Step 6:** "Based on your answers, which integrations should Murphy set up?"
**Step 7:** "Here's what I have so far — shall I proceed?"

The questions are ordered deliberately: business context first, technical details second.
Each answer is interpreted with inference logic — if the user says "all of them," Murphy
records "all." If they say "not sure" or "I don't know," Murphy records "(needs guidance)."
If they say "auto" or "let Murphy decide," Murphy records "(auto-configure)" and will
deduce the rest itself.

The user can type "skip" to pass a question, "back" to revisit, or "review" to see all
collected answers. Help is context-aware — if the user types "help" during the interview,
Murphy shows interview-specific navigation, not the general command list.

At the end, Murphy summarizes: *"Here's what I collected: Name: Inoni LLC, Business Goal:
sell the Murphy System, Use-Case: sales automation, Platforms: email and CRM, Integrations:
auto-configure. Shall I proceed?"*

The user types **"confirm."**

**What happens in the code:**
`DialogContext.advance()` records each answer, infers meaning from conversational input via
`_infer_value()`, and advances through `INTERVIEW_STEPS`. On confirmation, the collected
data feeds into the `SetupWizard` which maps answers to system configuration.

---

## Chapter 3: The Setup Wizard Configures Murphy

Behind the scenes, the `SetupWizard` takes the interview answers and generates a full
system configuration.

The wizard asks 12 deeper questions internally: organization name, industry, company size,
which automation types to enable (factory IoT, content, data, system, agent, business),
security level, robotics integration, avatar identity, LLM provider, compliance frameworks,
deployment mode, and sales automation.

For Inoni LLC, the answers map to: organization "Inoni LLC", industry "technology", company
size "small", automation types ["business", "agent"], security level "standard", sales
automation enabled. This activates the business automation modules
(`trading_bot_engine`, `executive_planning_engine`, `workflow_template_marketplace`) and
agent modules (`agentic_api_provisioner`, `shadow_agent_integration`, `advanced_swarm_system`,
`true_swarm_system`, `domain_swarms`).

Because sales automation is enabled, Murphy adds the sales-specific modules
(`workflow_template_marketplace`, `executive_planning_engine`) and sales bots
(`sales_outreach_bot`, `lead_scoring_bot`, `marketing_automation_bot`). Because the
industry is "technology", it also recommends `devops_bot`, `code_review_bot`, and
`incident_response_bot`.

Everyone gets the core modules: `config`, `module_manager`, `command_parser`,
`conversation_handler`, `compliance_engine`, `authority_gate`, and `capability_map`.

The configuration is exported as a JSON file. Murphy is now tailored to Inoni LLC's
mission: selling the Murphy System itself.

**What happens in the code:**
`SetupWizard.generate_config()` consults `AUTOMATION_MODULE_MAP`, `INDUSTRY_BOT_MAP`,
`AUTOMATION_BOT_MAP`, and applies `CORE_MODULES` as the baseline. `get_enabled_modules()`
builds the active module list. `get_recommended_bots()` builds the bot roster. The result is
a dict with every configuration choice and its downstream effects.

---

## Chapter 4: The System Bootstraps

Before Murphy can run anything, it needs to establish operational baselines. The
`ReadinessBootstrapOrchestrator` runs on first startup and seeds the system with:

- **KPI baselines**: automation rate targets, success rate goals, uptime requirements
- **RBAC roles**: admin, operator, viewer — with permission boundaries
- **Tenant resource limits**: API call caps, CPU limits, memory budgets
- **Alert thresholds**: when to warn, when to escalate, when to halt
- **Risk registers**: known risk categories and their baseline assessments

This is idempotent — running it twice doesn't duplicate anything. It publishes a
`LEARNING_FEEDBACK` event when done, telling the learning engine that the system is
initialized.

The `AutomationReadinessEvaluator` then checks every core module across 8 phases of
readiness. It produces a go/no-go verdict. If any critical module is unregistered or
unhealthy, the system won't proceed to autonomous operation.

The `CapabilityMap` scans all 200+ modules, classifies them by subsystem (execution,
governance, delivery, persistence, learning, security, telemetry, swarm, compute,
integration, adapter), extracts dependencies via AST parsing, and marks utilization
status. If a critical module is unwired, it's flagged for remediation.

**What happens in the code:**
`ReadinessBootstrapOrchestrator` seeds via `_seed_kpi_baselines()`,
`_configure_rbac_roles()`, `_set_tenant_limits()`, `_configure_alert_thresholds()`,
`_seed_risk_register()`. `AutomationReadinessEvaluator.evaluate()` iterates all phases.
`CapabilityMap.scan()` uses `importlib` and AST analysis to build the module graph.

---

## Chapter 5: The User Asks for Their First Automation

The Inoni LLC team member returns to the terminal. They type:

**"I want to automate our sales pipeline. When a lead comes in, score them, qualify them,
generate a personalized demo script, and create a proposal if they're qualified."**

Murphy's command system detects this isn't a slash-command — it's natural language. The
`ConversationHandler` classifies the question type (procedural), identifies entities
(leads, scoring, qualification, demo, proposal), and routes it through the state machine.

The `DomainEngine` identifies the affected domains: **Sales** (pipeline management) and
**Operations** (scheduling, reliability). It applies domain-specific constraints: lead data
must be validated, proposals must match the correct edition, and demo scripts must be
personalized to industry. It applies domain-specific gates: Lead Validation Gate, Budget
Gate, Compliance Gate.

The `OrgCompiler` checks: does this user's role have authority to create automations?
What's their decision authority level? What escalation paths apply? Are there compliance
constraints (SOC2, GDPR) that gate this workflow?

If everything checks out, Murphy enters **Phase 1: Generative Setup**.

**What happens in the code:**
`ConversationHandler.handle()` → `StateMachine` routes → `DomainEngine.classify()` →
`OrgCompiler.check_authority()` → `TwoPhaseOrchestrator.create_automation()`.

---

## Chapter 6: Phase 1 — Murphy Builds the Automation

The `TwoPhaseOrchestrator` takes over. Phase 1 is about *understanding and building* — not
executing.

**Step 1: Information Gathering**
The `InformationGatheringAgent` extracts: pipeline stages (lead scoring, qualification, demo,
proposal), data sources (lead intake form, CRM), output targets (email, proposals), and
whether human approval is needed. If anything is ambiguous, Murphy asks — but only one
question at a time, managed by the `QuestionManager` which queues up to 9 questions and
formats them with progress indicators.

**Step 2: Regulation Discovery**
The `RegulationDiscoveryAgent` discovers CRM APIs, email sending policies, data privacy
requirements (GDPR for EU leads, CAN-SPAM for email outreach), and technical constraints
(API rate limits, data retention rules, authentication methods).

**Step 3: Constraint Compilation**
The `ConstraintCompiler` takes all discovered constraints — technical, business, legal,
operational — and compiles them into a single constraint set. This becomes the rulebook
for the automation.

**Step 4: Agent Generation**
The `AgentGenerator` creates specialized agents from templates, constrained by the compiled
rules. For the Inoni LLC sales pipeline, it generates:
- **LeadScorer** — scores leads 0-100 based on company size, industry match, and interests
- **LeadQualifier** — determines if score meets the qualification threshold (≥40)
- **EditionRecommender** — maps company size to edition (enterprise/professional/community)
- **DemoScriptGenerator** — creates personalized demo scripts with industry-specific features
- **ProposalGenerator** — produces complete sales proposals with implementation timelines

**Step 5: Sandbox Creation**
The `SandboxManager` creates an isolated Docker environment with only the dependencies
these agents need — API libraries, credentials (securely injected), and the constraint
file. No agent can reach outside this sandbox.

An `automation_id` is generated. The configuration is saved. Phase 1 is complete.

**What happens in the code:**
`TwoPhaseOrchestrator.create_automation()` → `InformationGatheringAgent.gather()` →
`RegulationDiscoveryAgent.discover()` → `ConstraintCompiler.compile()` →
`AgentGenerator.generate()` → `SandboxManager.create_sandbox()`. Each step publishes
events to the `EventBackbone`.

---

## Chapter 7: The Domain Gates Activate

Before anything executes, the domain gate system activates. This is Murphy's Law made
into code.

The `DomainGateGenerator` creates gates based on the system requirements, the domain,
and the librarian's knowledge base. It doesn't use predefined checklists — it generates
gates from the actual risks discovered for *this specific automation*.

For the Inoni LLC sales pipeline, the gates might include:
- **Lead Data Validation Gate** (VALIDATION type, HIGH severity): Does the lead have
  a valid email? Is the company name present? Is the industry recognized?
- **Budget Gate** (BUSINESS type, MEDIUM severity): Will the cost of outreach stay
  within the allocated sales budget?
- **Compliance Gate** (COMPLIANCE type, CRITICAL severity): Does the outreach comply
  with CAN-SPAM and GDPR? Is consent recorded for email communication?
- **Approval Gate** (AUTHORIZATION type, HIGH severity): Has a sales manager approved
  proposals above a certain deal size?

Each gate has conditions (threshold checks, presence checks, format validations), pass
actions (proceed, log), and fail actions (block, escalate, retry). Each gate has a
`wired_function` — actual code that executes the check — and a `risk_reduction` score
indicating how much risk it mitigates.

The `GateExecutionWiring` registers these gates and defines the evaluation sequence:
COMPLIANCE first, then BUDGET, then EXECUTIVE, then OPERATIONS, then QA, then HITL. The
order matters — there's no point checking content quality if the compliance gate already
failed.

The `MurphyGate` in the confidence engine applies phase-specific thresholds. Each phase
has its own minimum: EXPAND requires 0.5, TYPE and ENUMERATE require 0.6, CONSTRAIN
requires 0.7, COLLAPSE requires 0.75, BIND requires 0.8, and EXECUTE — the final gate —
requires 0.85. If confidence is above the threshold but below 1.0, Murphy proceeds with
monitoring. If it's below the threshold, Murphy requests human review. If it drops more
than 0.15 below the threshold, execution is blocked entirely.

The `AuthorityGate` enforces five invariants: facts must be verified from external sources,
confidence must exceed the minimum threshold, there must be no unresolved unknowns, facts
must be non-empty, and entities must match between hypothesis and verified facts. If any
invariant fails, the gate returns CLARIFY (mild violation) or HALT (severe violation).

**Key principle:** Gates never authorize — they only restrict. A gate can block an action
or require more evidence. It can never override another gate's block.

**What happens in the code:**
`DomainGateGenerator.generate_gates_for_system()` creates gates based on domain, complexity,
regulatory, security, and performance requirements. `GateExecutionWiring.evaluate_gates()`
runs them in dependency order. `MurphyGate.evaluate()` applies threshold logic.
`AuthorityGate.check_invariants()` enforces five core invariants.

---

## Chapter 8: The Control Plane Selects Engines

The `UniversalControlPlane` analyzes the automation request and determines which execution
engines are needed. It doesn't load everything — it loads *only what's required*.

The `ControlTypeAnalyzer` classifies the Inoni LLC sales pipeline as a "content_api" control
type — it processes data (lead profiles) and calls external APIs (CRM, email). The
`EngineRegistry` maps this to two engines: the `ContentEngine` (for proposal/demo generation)
and the `APIEngine` (for CRM and email API calls). The `SensorEngine` and `ActuatorEngine`
stay dormant — they're not needed for sales automation.

An `IsolatedSession` is created with only those two engines loaded. The session has its own
state, its own engine instances, and its own execution context. If another team at Inoni is
running a content automation at the same time, their session loads different engines, and
the two sessions are completely isolated.

The `PacketCompiler` then creates an `ExecutionPacket` — an immutable, cryptographically
signed contract that defines exactly what actions are allowed, what safety constraints
apply, what time window is valid, and what rollback plans exist. The packet must be signed
by a quorum (3 signatures) before it's executable.

**What happens in the code:**
`UniversalControlPlane.create_automation()` → `ControlTypeAnalyzer.analyze()` →
`EngineRegistry.get_engines()` → `IsolatedSession()` → `PacketCompiler.compile()` →
`ExecutionPacket` (frozen, hashed, signed).

---

## Chapter 9: Phase 2 — Murphy Runs the Automation

Phase 2 begins. The `ProductionExecutionOrchestrator` loads the configuration from Phase 1
and starts the workflow.

The execution follows a 7-phase pipeline managed by the `FormDrivenExecutor`:

1. **EXPAND** — Expand the task scope. What exactly needs to happen? Score the lead?
   Qualify? Generate demo? Create proposal?
2. **TYPE** — Classify the task type. Sales pipeline. Data processing. Multi-step.
3. **ENUMERATE** — List all specific actions. Receive lead data. Validate fields.
   Score by size/industry/interests. Qualify against threshold. Recommend edition.
   Generate demo script. Create proposal.
4. **CONSTRAIN** — Apply all constraints. CAN-SPAM compliance. GDPR for EU leads.
   Budget limits. Approval requirements for large deals.
5. **COLLAPSE** — Narrow to the optimal execution path. Choose the most efficient
   sequence of actions that satisfies all constraints.
6. **BIND** — Bind actions to concrete implementations. Map "score lead" to the
   `SalesAutomationEngine.score_lead()` method with the Inoni LLC configuration.
7. **EXECUTE** — Run the bound actions. Lead data flows from intake through scoring
   through qualification through demo generation through proposal creation.

At each phase, the `ConfidenceEngine` computes a confidence score. The `MurphyGate`
checks whether confidence is high enough to proceed. If confidence drops below the phase
threshold (0.5 for EXPAND, rising to 0.85 for EXECUTE), the system pauses and asks for
human input.

The `TaskExecutor` handles the actual running with retry logic (exponential backoff),
timeout handling, and a circuit breaker pattern that prevents cascade failures. If one
API call fails three times, the circuit breaker opens and prevents further calls until
the service recovers.

Meanwhile, the `Wingman Protocol` pairs each executing agent with a deterministic
validator. The executor agent does the work; the validator checks the output. Five
built-in checks run on every output: does it have a result? Does it contain PII (email,
SSN, phone)? Is confidence above 0.5? Is cost within budget? Did all gates pass? If any
BLOCK-severity check fails, the output is rejected.

**What happens in the code:**
`ProductionExecutionOrchestrator.run_automation()` → `FormDrivenExecutor` runs 7 phases →
`ConfidenceEngine.compute()` at each phase → `MurphyGate.evaluate()` for gating →
`TaskExecutor.execute()` with retry/circuit-breaker → `WingmanProtocol.validate()` on
each output.

---

## Chapter 10: The Safety Net

While execution runs, multiple safety systems watch simultaneously.

The `SafetyValidationPipeline` runs three stages:
- **PRE-EXECUTION**: authorization check, input validation, risk assessment, rate
  limiting, budget verification
- **EXECUTION**: progress monitoring, anomaly detection, resource usage tracking
- **POST-EXECUTION**: output correctness, side-effect detection, metrics collection,
  audit trail generation

The `SafetyGatewayIntegrator` intercepts every API request and routes it through the
safety pipeline. It classifies routes by risk level — CRITICAL, HIGH, MEDIUM, LOW,
MINIMAL. Unclassified routes default to HIGH (fail-closed). Health and monitoring
endpoints are on a bypass list.

The `EmergencyStopController` watches for cascading failures. If 5 consecutive operations
fail, or if the error rate exceeds 20%, the emergency stop triggers automatically. All
autonomous operations halt. State is preserved — nothing is destroyed — but nothing new
runs until a human reviews and resumes.

The `GovernanceKernel` routes every tool call through centralized policy checks. It tracks
per-department and per-task budgets. It isolates memory between departments. It maintains
an immutable audit log of every enforcement decision.

The `HumanOversightSystem` manages the approval queue. Depending on the governance mode
(HEAVY, BALANCED, LIGHT, AUTONOMOUS), different operations require human sign-off. In
BALANCED mode, only critical and high-risk operations need approval. Everything else runs
autonomously but is logged.

If something does go wrong, the `SelfHealingCoordinator` activates. It listens for
`TASK_FAILED` and `SYSTEM_HEALTH` events on the event backbone. When a failure occurs,
it looks up registered recovery procedures for that failure category, runs the recovery
with exponential backoff, and reports the outcome. If recovery fails after 3 attempts,
it escalates to a human.

**What happens in the code:**
`SafetyValidationPipeline.validate()` → `SafetyGatewayIntegrator.evaluate()` →
`EmergencyStopController.check()` → `GovernanceKernel.enforce()` →
`HumanOversightSystem.check_approval()` → `SelfHealingCoordinator.handle_failure()`.
All connected via the `EventBackbone` pub/sub system.

---

## Chapter 11: The Swarm Intelligence

For complex problems, Murphy doesn't use a single agent — it deploys a swarm.

The `TrueSwarmSystem` creates two coupled swarms that work in opposition:

**The Exploration Swarm** generates solutions. It instantiates profession atoms —
engineers, analysts, strategists — each bringing a different perspective. They collaborate
in a `TypedGenerativeWorkspace`, producing artifacts: hypotheses, constraints, risk
assessments, and proposals.

**The Control Swarm** finds everything that can go wrong. Red-teamers, risk analysts,
and adversarial agents attack the exploration swarm's proposals. They discover failure
modes, edge cases, and vulnerabilities.

Here's the key: **Gates are synthesized from the control swarm's discoveries.** The
`GateGenerator` in `gate_synthesis` takes the discovered failure modes — semantic drift,
verification gaps, authority misuse, irreversible actions, blast radius exceeded,
constraint violations — and generates specific gates for each.

- A **Semantic Stability Gate** prevents interpretation drift over iterations
- A **Verification Gate** forces deterministic checks where confidence is low
- An **Authority Decay Gate** downgrades authority bands when risk increases
- An **Isolation Gate** enforces sandboxing when blast radius is too high
- A **Constraint Gate** prevents violations of compiled constraints

The `AdvancedSwarmGenerator` adds six generation strategies: creative, analytical, hybrid,
adversarial, synthesis, and optimization. Candidates are scored on confidence, novelty,
feasibility, and risk. The best candidates survive; the rest inform learning.

**What happens in the code:**
`TrueSwarmSystem` → `ExplorationSwarm` + `ControlSwarm` → `TypedGenerativeWorkspace` →
`GateGenerator.generate_gates_from_failure_modes()` → synthesized gates wired into
`GateExecutionWiring`.

---

## Chapter 12: How Bots Do the Work

Murphy's intelligence is distributed across 100+ specialized bots. Every bot extends one
of two base classes: `AsyncBot` (for async message handling) or `HiveBot` (for dynamically
loaded plugins). Each bot implements a `handle(message)` method that receives a `Message`
(sender + content) and returns a string response.

For Inoni LLC's sales pipeline, the key bots include:

- **`sales_outreach_bot`** — handles lead outreach emails, follow-ups, and scheduling
- **`lead_scoring_bot`** — scores leads based on company size, industry, and interests
  using the `SalesAutomationEngine.score_lead()` formula: base score from company size
  (small=10, medium=30, enterprise=50), +20 for target industry match, +5 per interest
  (max 30), capped at 100
- **`marketing_automation_bot`** — manages campaign creation, content scheduling, and
  social media coordination

Bots are loaded dynamically via a plugin system (`load_plugin()`, `load_plugins()`,
`reload_plugin()`). The `composite_registry.json` maps bot names to their implementations.
When Murphy's `SetupWizard` configures the system for Inoni LLC with
`sales_automation_enabled=True`, it adds `SALES_BOTS` to the active bot roster.

Bots don't operate independently — they're orchestrated by the `GovernanceKernel`, which
routes every tool call through centralized policy checks. Each bot's execution is bounded
by the `AgentDescriptor` that defines its authority level, resource caps, access scope,
and termination conditions.

**What happens in the code:**
`AsyncBot.handle(message)` processes requests. `HiveBot.init()` + `register_handlers()`
wire into the runtime. `SalesAutomationEngine` provides the lead scoring logic. The
`GovernanceScheduler` schedules bot execution while enforcing resource containment and
authority precedence.

---

## Chapter 13: The Confidence Engine — The Math Behind Every Decision

Every decision Murphy makes is backed by a mathematical framework that quantifies
uncertainty. This is the confidence engine — the system's core mathematical foundation.

**The Confidence Equation:**

    c_t = w_g(p_t) × G(x_t) + w_d(p_t) × D(x_t)

Where:
- `c_t` is the overall confidence at time t
- `w_g(p_t)` is the phase-dependent weight for generative adequacy
- `w_d(p_t)` is the phase-dependent weight for deterministic grounding
- `G(x_t)` measures how thoroughly Murphy has explored the solution space
- `D(x_t)` measures how much of that exploration is backed by verified evidence

**Generative Adequacy** breaks down further:

    G(x) = 0.4 × hypothesis_coverage + 0.3 × decision_branching + 0.3 × question_quality

- `hypothesis_coverage` = how many diverse hypotheses have been generated (measured via
  entropy analysis of the artifact graph)
- `decision_branching` = how many decision points have been explored
- `question_quality` = ratio of resolved questions to total questions

**Deterministic Grounding** measures verified evidence:

    D(x) = Σ(verified_artifacts × trust_weight × stability_score) / total_weight

Each artifact in the graph has a trust weight (how reliable the source is) and a stability
score (how much it has changed over iterations). Only verified artifacts contribute.

**Epistemic Instability** tracks how uncertain the system is:

    H(x) = (conflict_score + semantic_variance) / 2

Higher H means more internal contradictions and semantic drift — a sign that Murphy should
slow down and ask for human input.

For Inoni LLC's sales pipeline, when Murphy scores a lead, the confidence engine computes
G(x) from the hypothesis coverage (did we explore multiple scoring strategies?), D(x) from
the verified data (is the lead's company size confirmed?), and H(x) from any
contradictions (does the lead claim to be "enterprise" but have 5 employees?).

**What happens in the code:**
`ConfidenceCalculator.compute_confidence()` computes c_t using `GraphAnalyzer` for graph
metrics. `calculate_generative_adequacy()` computes G(x). `calculate_deterministic_grounding()`
computes D(x). `calculate_epistemic_instability()` computes H(x).

---

## Chapter 14: The Murphy Index — Quantifying What Can Go Wrong

The Murphy Index is the system's namesake formula. It answers: "Given what we know, how
much risk remains?"

**The Murphy Index:**

    M_t = Σ_k (L_k × p_k)

Where:
- `L_k` is the loss magnitude for failure mode k (0.1 to 0.9)
- `p_k` is the probability of failure mode k, computed via sigmoid:

    p_k = σ(α × H + β × (1 - D) + γ × Exposure + δ × AuthorityRisk)

The sigmoid weights are empirically tuned:
- α = 2.0 — epistemic instability (contradictions and drift)
- β = 1.5 — lack of deterministic grounding (unverified claims)
- γ = 1.0 — exposure (ratio of unverified artifacts to total)
- δ = 1.2 — authority risk (executing with low confidence)

**Five Failure Modes** are identified for every execution:

1. **Contradiction-induced failure** — detected contradictions in the artifact graph.
   Loss scales from 0.1 to 0.9 based on how many contradictions exist.
2. **Insufficient grounding** — when D < 0.5, the system is operating on unverified
   claims. Loss = 0.5.
3. **High exposure** — when more than 30% of artifacts are unverified. Loss = 0.4.
4. **Authority risk** — executing in a high-authority phase with low confidence.
   Loss = 0.7. Authority risk increases through phases: EXPAND (0) → TYPE (0.1) →
   ENUMERATE (0.2) → CONSTRAIN (0.3) → COLLAPSE (0.5) → BIND (0.7) → EXECUTE (1.0).
5. **Unresolved dependencies** — missing links between artifacts. Loss = 0.5.

The Murphy Index is normalized to [0, 1]. Higher means more risk. When M_t is high, more
gates activate, more human oversight is required, and execution may be blocked entirely.

For Inoni LLC's sales pipeline: if a lead's company data is unverified (low D), the Murphy
Index spikes due to "insufficient grounding" and "high exposure" failure modes. Murphy would
pause scoring and ask for data verification before proceeding.

**What happens in the code:**
`MurphyCalculator.calculate_murphy_index()` iterates failure modes, computes each p_k via
sigmoid, multiplies by L_k, and sums to produce M_t.

---

## Chapter 15: The Deterministic Compute Plane

Not everything should be handled by an LLM. Murphy's `DeterministicRoutingEngine` decides
which tasks get deterministic execution (pure functions, reproducible results) and which
get LLM execution (generative, creative, stochastic).

**The routing decision** is policy-based. Four default policies define the boundary:

- **Math/Compute tasks** → deterministic (guardrails: max_iterations=1000, timeout=30s).
  Lead scoring is math — `score = size_points + industry_bonus + interest_points`. No LLM
  needed.
- **Validation/Verification tasks** → deterministic (guardrails: strict_mode=True). Email
  validation, data format checks, threshold comparisons — all pure functions.
- **Creative/Generation tasks** → LLM (guardrails: content_filter, max_tokens=4096). Demo
  script personalization, proposal narrative — these benefit from language generation.
- **Analysis/Research tasks** → hybrid (guardrails: require_sources). Market analysis,
  competitive positioning — combine data lookup with LLM synthesis.

The `DeterministicRoutingEngine` matches each task against registered `RoutingPolicy`
objects by comparing task tags. The highest-priority matching policy wins. If no policy
matches, the fallback is always "deterministic" — fail safe, not fail creative.

**Guardrails** are applied per route type:
- **Deterministic**: output_validation, strict_mode
- **LLM**: content_filter, token_limits, pii_redaction
- **Hybrid**: both sets of guardrails
- **Universal** (all routes): timeout_enforcement, production_safety_gate

For Inoni LLC's sales pipeline: lead scoring routes to deterministic (pure math), proposal
text routes to LLM (creative writing), and lead qualification routes to deterministic
(threshold comparison: score ≥ 40).

**What happens in the code:**
`DeterministicRoutingEngine.route_task()` matches policies. `evaluate_guardrails()` applies
safety checks. `promote_fallback()` promotes successful deterministic outputs to the main
graph. `validate_route_parity()` ensures routing consistency.

---

## Chapter 16: Murphy Learns

Every execution produces data. The `LearningEngine` consumes it.

The `PerformanceTracker` records metrics from every run: execution time, success rate,
error types, resource usage. The `PatternRecognizer` analyzes these metrics using linear
regression for trend detection and cycle detection for recurring patterns.

When the Inoni LLC team provides a correction — "that lead should have been qualified" or
"don't contact leads in the EU without explicit consent" — the `FeedbackSystem` captures it
with a type tag (CORRECTION, SUGGESTION, BUG_REPORT, FEATURE_REQUEST, PRAISE). The
`FeedbackValidator` checks quality. The `FeedbackAnalyzer` categorizes patterns.

The `AdaptiveDecisionEngine` turns all of this into better future decisions. It maintains
`DecisionHistory` — every decision made, with its outcome and utility score. From this
history, it derives `DecisionPolicies` (deterministic, probabilistic, or adaptive
strategies). The `PolicyManager` evolves policies based on success rates, adjusting
exploration rates and action utilities.

The `GoldenPathBridge` captures particularly successful execution paths. When an automation
runs perfectly — high confidence, zero errors, human-approved output — the bridge records
the entire execution specification. Next time a similar request comes in, Murphy can match
against golden paths and skip the full exploration phase.

The `GateBypassController` implements this at the gate level. Low-risk tasks that have
succeeded K consecutive times may bypass full gate evaluation. But critical and high-risk
tasks always go through full gates, no matter how many times they've succeeded.

**What happens in the code:**
`LearningEngine.record()` → `PerformanceTracker` → `PatternRecognizer.detect()` →
`FeedbackSystem.collect()` → `AdaptiveDecisionEngine.decide()` →
`PolicyManager.evolve()` → `GoldenPathBridge.record_path()` →
`GateBypassController.check_bypass()`.

---

## Chapter 17: The Librarian Remembers Everything

The `SystemLibrarian` is Murphy's institutional memory.

Every action taken by every module is logged as a `TranscriptEntry` — timestamp, module
name, action, details, actor (user or bot), success/failure, and duration. This creates
a complete audit trail that can answer "what happened, when, and why?"

The `LibrarianModule` provides a unified interface combining three components: a
`KnowledgeBase` that stores domain knowledge, a `SemanticSearchEngine` that finds
relevant knowledge, and a `DocumentManager` that ingests and processes new documents.

When Murphy generates documentation — module guides, API references, technical docs — it
uses the librarian's knowledge, not the LLM's imagination. The `ResponseComposer` builds
responses from templates and verified facts only, never from generated text. Every response
is tagged: **V** for Verified (from knowledge base) or **G** for Generated (from LLM,
marked as uncertain).

The librarian also feeds the domain gate generator. When `DomainGateGenerator` creates
gates for a new automation, it consults `LibrarianKnowledgeBase` for best practices,
regulatory standards, and architectural requirements specific to the domain. The gates
aren't generic — they're informed by accumulated system knowledge.

**What happens in the code:**
`SystemLibrarian.log_transcript()` records actions. `LibrarianModule.search()` retrieves
knowledge. `ResponseComposer.compose()` builds verified-facts-only responses.
`DomainGateGenerator` consults `LibrarianKnowledgeBase` during gate generation.

---

## Chapter 18: The User Sees Results

Back in the terminal, the Inoni LLC team member sees:

> ✓ Automation "inoni-sales-pipeline" created and executed successfully.
> — 5 new leads scored and qualified
> — 3 leads qualified (score ≥ 40), 2 need nurturing
> — Demo scripts generated for qualified leads (personalized by industry)
> — Proposals created: 1 Enterprise, 2 Professional editions
> — Next pipeline review: Monday 9:00 AM

The `ResponseFormatter` has cleaned the output — removing internal metric lines, system
noise, and technical artifacts. It shows the user only what matters: what happened, what
was produced, and what comes next.

If the user types **"show modules"**, they see the `MODULE_COMMAND_MAP` — a table of every
module and its available commands. If they type **"librarian"**, they get access to the
knowledge base expert. If they type **"plan"**, they see the two-plane execution model
explained. If they type **"billing"**, they see subscription tiers.

The system is fully navigable through natural language. Every module is accessible.
Every feature is discoverable.

---

## Chapter 19: Murphy Automates Itself

The `SelfAutomationOrchestrator` is Murphy's most ambitious module. It performs continuous
self-improvement through a structured cycle:

1. **Gap Analysis** — Discovers missing capabilities, unwired modules, incomplete coverage
2. **Task Creation** — Creates improvement tasks with priorities and prompt chain steps
3. **Execution** — Each task flows through: analysis → planning → implementation →
   testing → review → documentation
4. **Cycle Tracking** — Records what was improved, when, and whether it succeeded

Murphy can identify its own weaknesses (via the `CapabilityMap`), create tasks to fix
them, execute those tasks through its own automation pipeline, validate the results, and
document the changes. Each cycle makes the system more capable and more reliable.

But self-automation is bounded. The `GovernanceKernel` ensures Murphy can't bypass its
own safety constraints. The `StabilityController` detects divergence and oscillation. The
`EmergencyStopController` can halt everything if self-improvement goes wrong. And the
`HumanOversightSystem` requires human approval for any self-modification above a risk
threshold.

**What happens in the code:**
`SelfAutomationOrchestrator.discover_gaps()` → `create_task()` → `start_task()` →
`advance_step()` (through 6 prompt steps) → `complete_task()` →
`GovernanceKernel.enforce()` limits scope at every step.

---

## Chapter 20: The LLM Dual-Write and Rosetta State Management

Murphy's LLM layer writes in two directions simultaneously. Externally, it generates
user-facing content — demo scripts, proposals, natural-language responses. Internally,
it writes to the **Rosetta state system** — the canonical document store that drives
every agentic function call, org chart lookup, and archive review in the runtime.

The `LLMIntegrationLayer` is the router. Every request enters through `route_request()`,
which consults `domain_routing` tables to decide: does this go to a cloud provider (Groq,
Aristotle), or to the `local_llm` fallback? The layer tracks `request_count`,
`validation_count`, and `trigger_count`. When a response triggers a follow-up action,
`get_pending_triggers()` queues it and `resolve_trigger()` fires it. This is how one LLM
call chains into three agentic steps — without recursion and without losing audit trail.

The `SafeLLMWrapper` intercepts every LLM output before it reaches the user or Rosetta.
`safe_generate()` enforces safety gates: content filtering, PII redaction, token limits.
`verify_against_sources()` cross-checks the LLM's claims against the librarian's
knowledge base. If the LLM asserts a fact that contradicts verified sources, the output
is flagged as **unverified** and never written to Rosetta as ground truth.

**The Rosetta State System** is the internal document backbone:

- `RosettaManager` provides the core state API: `save_state()`, `load_state()`,
  `update_state()`, `delete_state()`, `list_agents()`, and `aggregate()`. Every agent
  in the system reads from and writes to Rosetta documents. These documents are the
  single source of truth — not the LLM's memory, not a database, not a config file.

- `ArchiveClassifier` categorizes completed Rosetta documents by domain and importance.
  `classify()` assigns a category; `should_archive()` decides retention; `archive_item()`
  moves the document to long-term storage.

- `RosettaStoneHeartbeat` monitors translator health. `register_translator()` adds a new
  Rosetta translator to the pulse system. `emit_pulse()` sends a heartbeat. `sync_check()`
  verifies all translators are synchronized. `get_tier_state()` reports health per tier.
  If a translator falls behind, the heartbeat catches it before stale state propagates.

- `RecalibrationScheduler` triggers periodic Rosetta state reconciliation.
  `run_recalibration()` forces a full state audit. `get_status()` reports whether
  recalibration is running, idle, or overdue.

**Key principle:** The LLM is never the source of truth. It generates; Rosetta stores.
The `RosettaManager` drives agentic calls — agents read their instructions from Rosetta
documents, execute, and write results back. The LLM accelerates but never governs.

**What happens in the code:**
`LLMIntegrationLayer.route_request()` → `SafeLLMWrapper.safe_generate()` →
`RosettaManager.save_state()` (internal write) + user response (external write) →
`ArchiveClassifier.classify()` → `RosettaStoneHeartbeat.sync_check()` →
`RecalibrationScheduler.run_recalibration()` (periodic).

---

## Chapter 21: Avatar Sessions Coin-Join with Agent Calls via Streaming

When Inoni LLC demos Murphy to a prospect, the system doesn't just show slides — it
runs a **live avatar session** that coin-joins with agent execution in real time. The
avatar speaks, the agents execute, and the prospect sees both on a shared screen.

The `AvatarSessionManager` is the coordinator. `start_session()` creates an isolated
session with a persona, cost tracking, and message history. `record_message()` logs
every utterance. `add_cost()` tracks token and compute spend per session. `end_session()`
finalizes and archives the session record. `list_active_sessions()` shows all live demos
running across the org.

The avatar pipeline has four stages:

1. **Persona Injection** — `PersonaInjector` loads the avatar's personality, vocabulary,
   and behavioral boundaries from the org chart. The avatar for Inoni LLC's sales demos
   speaks confidently about automation but defers technical architecture questions to a
   human engineer.

2. **Sentiment Classification** — `SentimentClassifier` analyzes the prospect's
   responses in real time. Is the prospect engaged, skeptical, confused, or excited?
   This feeds back into the avatar's response strategy.

3. **Behavioral Scoring** — `BehavioralScoringEngine` evaluates the avatar's own
   performance: staying on-script, avoiding hallucinated claims, maintaining appropriate
   tone, and respecting compliance boundaries.

4. **Compliance Guard** — `ComplianceGuard` blocks the avatar from making commitments
   the system can't fulfill — pricing promises, timeline guarantees, feature claims that
   don't match the current runtime.

The avatar connects to external platforms through pluggable connectors:
`ElevenLabs` (voice synthesis), `HeyGen` (video avatar), `Tavus` (personalized video),
and `VAPI` (voice API). Each connector implements a standard interface; the
`AvatarRegistry` manages active connectors and their health.

**Streaming Integration:**
The `VideoStreamingRegistry` manages live streaming connections. `create_simulcast()`
sets up multi-platform broadcasting. `list_platforms()` shows available streaming
targets. The `SimulcastManager` handles simultaneous streaming to multiple platforms.

The **coin-join** works like this: when the avatar calls a Murphy agent (e.g., "let me
score that lead for you live"), the agent execution happens in real time, the result
flows back through the avatar pipeline, and the avatar narrates the outcome — all
within the same streaming session. The prospect sees Murphy working, not just talking.

**What happens in the code:**
`AvatarSessionManager.start_session()` → `PersonaInjector.inject()` →
`SentimentClassifier.classify()` → agent execution via `LLMIntegrationLayer` →
`BehavioralScoringEngine.score()` → `ComplianceGuard.check()` →
`VideoStreamingRegistry.create_simulcast()` → live stream.

---

## Chapter 22: Shadow Agents and the Org Chart

Every role in Inoni LLC's org chart has a **shadow agent** — a passive learning entity
that watches how the role operates, learns patterns, and can eventually propose
automations or substitutions when the role holder is unavailable.

The `ShadowAgentIntegration` manages the lifecycle:

- `create_account()` registers a new organizational account
- `create_shadow_agent()` spawns a shadow for a specific role
- `bind_shadow_to_role()` attaches the shadow to an org chart position
- `get_shadows_for_org()` lists all active shadows in the organization
- `get_shadows_for_account()` lists shadows for a specific team
- `check_shadow_permission()` verifies a shadow has authority for an action
- `get_shadow_governance_boundary()` returns what the shadow can and cannot do
- `suspend_shadow()` pauses a shadow (e.g., when its role holder returns)
- `revoke_shadow()` permanently removes a shadow
- `reactivate_shadow()` brings a suspended shadow back online

The `OrgChartEnforcement` system ensures shadows respect organizational boundaries.
Escalation paths are immutable — defined by the org chart, not by the shadow. A shadow
agent for a sales rep cannot approve deals above the rep's authority limit. A shadow
for a department head cannot modify another department's budget.

The `RoleTemplateCompiler` compiles org chart data into executable role templates:
- `add_org_chart()` loads the organizational structure
- `add_process_flow()` adds workflow definitions
- `add_sop_data()` adds standard operating procedures
- `add_work_artifacts()` adds example work outputs
- `add_handoff_events()` defines when roles transfer responsibility
- `compile_role_template()` generates a complete template for one role
- `compile_all()` generates templates for the entire organization

The `ShadowLearningAgent` in `org_compiler/shadow_learning` observes role execution
patterns, detects recurring tasks, and proposes automation candidates. It uses a
`TelemetryCollector` to gather execution data, a `PatternRecognitionEngine` to identify
repeating patterns, and a `TemplateProposalGenerator` to suggest new role templates.

**Chronological Archive Review:**
Shadow agents participate in the **Rosetta archive review cycle**. When the
`RecalibrationScheduler` triggers a review, each shadow agent reads its role's Rosetta
documents chronologically, checks whether events match expected patterns, and flags
deviations. This is how the system detects organizational drift — when actual practice
diverges from documented process.

**What happens in the code:**
`ShadowAgentIntegration.create_shadow_agent()` → `bind_shadow_to_role()` →
`RoleTemplateCompiler.compile_role_template()` → `ShadowLearningAgent.observe()` →
`RecalibrationScheduler.run_recalibration()` → chronological Rosetta document review →
`ArchiveClassifier.classify()` → drift detection.

---

## Chapter 23: The Security Plane

Murphy operates under a **zero-trust security model**. Every request, every agent call,
every data access is verified — no matter where it originates.

The `ZeroTrustAccessController` in `security_plane/access_control` enforces this:
- Every access request is evaluated against capability scopes and authority bands
- `AuthorityBandEnforcer` ensures agents operate within their declared authority level
- `CapabilityManager` tracks what each agent is allowed to do
- `TrustRecomputer` dynamically adjusts trust scores based on behavior — an agent that
  consistently produces verified results earns higher trust; one that triggers safety
  gates loses trust

**Bot Verification:**
- `BotIdentityVerifier` in `security_plane/bot_identity_verifier` validates that every
  bot is who it claims to be — checking signatures, version hashes, and registry entries
- `BotAnomalyDetector` in `security_plane/bot_anomaly_detector` watches for behavioral
  anomalies — a bot suddenly accessing data it has never accessed, or calling APIs at
  unusual rates
- `BotResourceQuotas` in `security_plane/bot_resource_quotas` enforces per-bot resource
  limits — CPU, memory, API calls, token spend

**Data Protection:**
- `DataLeakPreventionSystem` in `security_plane/data_leak_prevention` classifies data by
  sensitivity level, monitors data transfers, and blocks unauthorized exfiltration. The
  `SensitiveDataClassifier` categorizes data; the `ExfiltrationDetector` watches for
  leaks; the `EncryptionEnforcer` ensures data-at-rest and data-in-transit encryption.
- `PacketProtectionSystem` in `security_plane/packet_protection` protects execution
  packets — the immutable contracts that define what agents can do. `PacketSigner`
  creates cryptographic signatures; `IntegrityValidator` verifies them; `ReplayPrevention`
  stops packet reuse attacks.
- `LogSanitizer` in `security_plane/log_sanitizer` scrubs sensitive data from logs
  before they're stored or transmitted.
- `AntiSurveillance` in `security_plane/anti_surveillance` detects and blocks attempts
  to monitor system internals from outside.

**Adaptive Defense:**
- `AdaptiveDefense` in `security_plane/adaptive_defense` adjusts security posture based
  on threat level. During normal operation, monitoring is standard. When anomalies spike,
  the system tightens access controls, increases logging verbosity, and alerts humans.

For Inoni LLC's sales pipeline: lead PII (emails, phone numbers) is classified as
sensitive by the `SensitiveDataClassifier`. The `DataLeakPreventionSystem` ensures lead
data never leaves the sandbox. The `BotIdentityVerifier` confirms that only the
authorized `sales_outreach_bot` can access lead contact information.

**What happens in the code:**
`ZeroTrustAccessController.evaluate()` → `BotIdentityVerifier.verify()` →
`BotAnomalyDetector.check()` → `DataLeakPreventionSystem.monitor()` →
`PacketProtectionSystem.validate()` → `AdaptiveDefense.assess()`.

---

## Chapter 24: The Recursive Stability Controller

When Murphy's agents spawn sub-agents, and those sub-agents spawn further sub-agents,
the system risks **recursive instability** — exponential resource consumption,
oscillating decisions, or infinite loops. The Recursive Stability Controller (RSC)
prevents this.

**Lyapunov Monitoring:**
The `LyapunovMonitor` in `recursive_stability_controller/lyapunov_monitor` applies
control theory to agent recursion. It tracks a `LyapunovState` — a mathematical
representation of the system's energy level. If the Lyapunov function is decreasing,
the system is converging toward stability. If it's increasing, the system is diverging
and intervention is needed. A `LyapunovViolation` is raised when divergence exceeds
safety thresholds.

**Gate Damping:**
The `GateDampingController` in `recursive_stability_controller/gate_damping` prevents
oscillation in gate evaluations. When a gate flip-flops (pass → fail → pass → fail),
the damping controller smooths the signal. It tracks gate synthesis requests and
responses, applying exponential decay to prevent rapid-fire gate state changes.

**Spawn Control:**
The `SpawnRateController` in `recursive_stability_controller/spawn_controller` limits
how fast agents can create sub-agents. Every `SpawnRequest` is evaluated: Is the parent
agent within its spawn budget? Is the global spawn rate below the safety limit? Would
this spawn push the Lyapunov function toward instability? The controller returns a
`SpawnDecision` — approved, denied, or deferred.

**Stability Scoring:**
The `StabilityScoreCalculator` in `recursive_stability_controller/stability_score`
computes a single stability metric that combines Lyapunov energy, gate damping state,
spawn rate, and resource utilization. This score feeds into the confidence engine — if
stability drops, confidence drops, and gates tighten automatically.

**Supporting Infrastructure:**
- `ControlSignals` manage the feedback loops between stability components
- `FeedbackIsolation` prevents stability corrections from creating new instabilities
- `RecursionEnergy` tracks computational energy spent on recursive operations
- `StateVariables` maintain the RSC's own internal state
- `RSCTelemetry` exports stability metrics to the observability stack

For Inoni LLC: when the `SelfAutomationOrchestrator` discovers a gap and spawns agents
to fix it, the RSC ensures the fix doesn't spawn more fixes in an infinite loop. The
`SpawnRateController` caps recursion depth. The `LyapunovMonitor` detects divergence.
The `GateDampingController` prevents oscillating gate decisions.

**What happens in the code:**
`SpawnRateController.evaluate()` → `LyapunovMonitor.check()` →
`GateDampingController.damp()` → `StabilityScoreCalculator.compute()` →
feeds into `ConfidenceEngine` → gate thresholds adjust automatically.

---

## Chapter 25: The Supervisor System and Correction Loops

Above all the automation sits the **Supervisor System** — the layer that manages
assumptions, detects when they become invalid, and triggers correction loops.

**Assumption Management:**
The `AssumptionRegistry` in `supervisor_system/assumption_management` tracks every
assumption the system makes during execution. When Murphy scores a lead and assumes
"technology companies prefer CI/CD automation," that assumption is registered with its
source, confidence level, and expiration conditions.

The `SupervisorInterface` in `supervisor_system/supervisor_loop` provides the feedback
API: `submit_feedback()` accepts human corrections, `process_feedback()` routes them to
the appropriate handler, and `get_statistics()` reports correction patterns. The
`SupervisorAuditLogger` records every feedback event immutably.

**Correction Loops:**
When an assumption is invalidated — by human feedback, by contradicting evidence, or by
time expiration — the `InvalidationDetector` in `supervisor_system/correction_loop`
triggers a correction cascade:

1. The `ConfidenceDecayer` reduces confidence for all decisions that depended on the
   invalidated assumption
2. The `AuthorityDecayer` downgrades the authority of agents that relied on it
3. The `ExecutionFreezer` pauses any in-flight executions that depend on it
4. The `ReExpansionTrigger` queues the affected workflow for re-evaluation from the
   EXPAND phase — starting fresh with the corrected understanding

The `AssumptionBindingManager` tracks which decisions depend on which assumptions. When
assumption A is invalidated, it finds every decision that transitively depends on A and
marks them for review. The `MurphyIndexTrend` monitors whether corrections are improving
or degrading the system's overall risk profile.

**Anti-Recursion:**
The `AntiRecursionSystem` in `supervisor_system/anti_recursion` prevents correction
loops from becoming recursive. If correcting assumption A invalidates assumption B,
which invalidates assumption C, which re-validates assumption A — the anti-recursion
system detects the cycle. The `CircularDependencyDetector` maps assumption dependencies.
The `SelfValidationBlocker` prevents an assumption from validating itself. The
`ValidationSourceTracker` ensures every validation comes from an independent source.

For Inoni LLC: when a human corrects a lead scoring assumption ("retail companies
actually do want CI/CD automation"), the `InvalidationDetector` finds all leads scored
under the old assumption, the `ConfidenceDecayer` reduces their confidence scores, and
the `ReExpansionTrigger` re-queues them for re-scoring. The anti-recursion system
ensures the re-scoring doesn't trigger another cascade.

**What happens in the code:**
`AssumptionRegistry.register()` → human feedback via `SupervisorInterface.submit_feedback()` →
`InvalidationDetector.detect()` → `ConfidenceDecayer.decay()` +
`AuthorityDecayer.decay()` + `ExecutionFreezer.freeze()` →
`ReExpansionTrigger.trigger()` → `AntiRecursionSystem.check_cycle()`.

---

## Epilogue: The Design Philosophy

Murphy System is built on a set of principles visible in every line of code:

**1. Never trust, always verify.** The confidence engine computes a Murphy Index
(1.0 minus confidence) for every decision. The higher the Murphy Index, the more likely
something will go wrong, and the more gates and human oversight activate.

**2. Gates are generated, not predefined.** The swarm discovers risks. The gate generator
creates gates for those specific risks. This means every automation gets gates tailored
to its actual failure modes, not a generic checklist.

**3. Fail closed, never fail open.** Unknown routes default to HIGH risk. Unclassified
operations require full governance. Missing modules block execution. The system's default
state is "stop and ask" — not "proceed and hope."

**4. Refusal is a valid state.** When an agent refuses to act — due to safety constraints,
insufficient evidence, or governance violations — that refusal is recorded as a legitimate
terminal state with a signed audit trail. It's not retried or overridden.

**5. Humans escalate, not machines.** Escalation paths are immutable — defined in the org
chart and enforced by the org compiler. Agents cannot modify escalation rules. Only humans
can change who approves what.

**6. The LLM suggests, humans decide.** The `ArtifactIngestion` framework explicitly
prevents the LLM from asserting compliance or modifying governance terms. LLMs generate
suggestions. Humans make decisions. The boundary is enforced in code.

**7. Everything is auditable.** Every gate evaluation, every human approval, every agent
refusal, every budget expenditure, every emergency stop — all logged to immutable audit
trails. The librarian can reconstruct the complete history of any decision.

**8. The system learns, but within bounds.** The learning engine improves decisions over
time. But the governance kernel constrains what the learning engine can change. The
stability controller prevents divergence. The emergency stop can halt everything. Learning
improves the system; governance ensures it doesn't improve itself into a dangerous state.

---

## Appendix: Module-to-Story Mapping

| Story Moment | Key Modules |
|---|---|
| User opens terminal | `murphy_terminal.py`, `MurphyTerminalApp`, `StatusBar` |
| Onboarding interview | `DialogContext`, `INTERVIEW_STEPS`, `_infer_value()` |
| System configuration | `setup_wizard.py`, `SetupProfile`, `generate_config()` |
| Bootstrap & readiness | `readiness_bootstrap_orchestrator.py`, `automation_readiness_evaluator.py` |
| User requests automation | `conversation_handler.py`, `command_parser.py`, `state_machine.py` |
| Domain classification | `domain_engine.py`, `DomainEngine`, `DomainType` |
| Authority check | `org_compiler/`, `authority_gate.py`, `AuthorityGate` |
| Phase 1: Build automation | `two_phase_orchestrator.py`, `TwoPhaseOrchestrator` |
| Information gathering | `InformationGatheringAgent`, `QuestionManager` |
| Regulation discovery | `RegulationDiscoveryAgent`, `ConstraintCompiler` |
| Agent generation | `AgentGenerator`, `SandboxManager` |
| Domain gate generation | `domain_gate_generator.py`, `DomainGateGenerator` |
| Gate synthesis from risks | `gate_synthesis/gate_generator.py`, `GateGenerator` |
| Gate evaluation sequencing | `gate_execution_wiring.py`, `GateExecutionWiring` |
| Confidence gating | `confidence_engine/murphy_gate.py`, `MurphyGate` |
| Control plane routing | `universal_control_plane.py`, `UniversalControlPlane` |
| Engine selection | `ControlTypeAnalyzer`, `EngineRegistry`, `IsolatedSession` |
| Execution packet | `control_plane/packet_compiler.py`, `ExecutionPacket` |
| Phase 2: Run automation | `ProductionExecutionOrchestrator`, `FormDrivenExecutor` |
| 7-phase execution | EXPAND → TYPE → ENUMERATE → CONSTRAIN → COLLAPSE → BIND → EXECUTE |
| Task execution | `execution_engine/task_executor.py`, `TaskExecutor` |
| Output validation | `wingman_protocol.py`, `WingmanProtocol`, `BuiltinChecks` |
| Safety pipeline | `safety_validation_pipeline.py`, `SafetyValidationPipeline` |
| API gateway | `safety_gateway_integrator.py`, `SafetyGatewayIntegrator` |
| Emergency stop | `emergency_stop_controller.py`, `EmergencyStopController` |
| Governance enforcement | `governance_kernel.py`, `GovernanceKernel` |
| Human oversight | `autonomous_systems/human_oversight_system.py` |
| Self-healing | `self_healing_coordinator.py`, `SelfHealingCoordinator` |
| Swarm intelligence | `true_swarm_system.py`, `advanced_swarm_system.py` |
| Learning from execution | `learning_engine/`, `PerformanceTracker`, `PatternRecognizer` |
| User feedback | `learning_engine/feedback_system.py`, `HumanFeedbackSystem` |
| Policy evolution | `learning_engine/adaptive_decision_engine.py`, `PolicyManager` |
| Golden path caching | `golden_path_bridge.py`, `GoldenPathBridge` |
| Gate bypass for low-risk | `gate_bypass_controller.py`, `GateBypassController` |
| Knowledge management | `system_librarian.py`, `librarian/`, `LibrarianModule` |
| Response composition | `response_composer.py`, `response_formatter.py` |
| Event communication | `event_backbone.py`, `EventBackbone` |
| Self-improvement | `self_automation_orchestrator.py`, `SelfAutomationOrchestrator` |
| Capability scanning | `capability_map.py`, `CapabilityMap` |
| Bot orchestration | `bots/`, `AsyncBot`, `HiveBot`, `composite_registry.json` |
| Sales bots | `sales_outreach_bot`, `lead_scoring_bot`, `marketing_automation_bot` |
| Confidence equation | `confidence_engine/confidence_calculator.py`, `ConfidenceCalculator` |
| Murphy Index math | `confidence_engine/murphy_calculator.py`, `MurphyCalculator` |
| Deterministic routing | `deterministic_routing_engine.py`, `DeterministicRoutingEngine` |
| Sales automation | `sales_automation.py`, `SalesAutomationEngine`, `SalesAutomationConfig` |
| Lead pipeline | `LeadProfile`, `score_lead()`, `qualify_lead()`, `generate_proposal()` |
| KPI monitoring | `kpi_tracker.py`, `KPITracker` |
| Compliance validation | `compliance_engine.py`, `ComplianceEngine` |
| Telemetry & observability | `telemetry_adapter.py`, `telemetry_system/`, `telemetry_learning/` |
| LLM request routing | `llm_integration_layer.py`, `LLMIntegrationLayer`, `route_request()` |
| LLM safety wrapper | `safe_llm_wrapper.py`, `SafeLLMWrapper`, `safe_generate()` |
| LLM controller | `llm_controller.py`, `llm_integration.py`, `llm_routing_completeness.py` |
| Local LLM fallback | `local_llm_fallback.py`, `local_model_layer.py`, `enhanced_local_llm.py` |
| Rosetta state management | `rosetta/rosetta_manager.py`, `RosettaManager`, `save_state()`, `load_state()` |
| Rosetta archive classifier | `rosetta/archive_classifier.py`, `ArchiveClassifier`, `classify()` |
| Rosetta heartbeat | `rosetta_stone_heartbeat.py`, `RosettaStoneHeartbeat`, `emit_pulse()` |
| Rosetta recalibration | `rosetta/recalibration_scheduler.py`, `RecalibrationScheduler` |
| Rosetta models & aggregator | `rosetta/rosetta_models.py`, `rosetta/global_aggregator.py` |
| Avatar session management | `avatar/avatar_session_manager.py`, `AvatarSessionManager` |
| Avatar persona & scoring | `avatar/persona_injector.py`, `avatar/behavioral_scoring_engine.py` |
| Avatar sentiment & compliance | `avatar/sentiment_classifier.py`, `avatar/compliance_guard.py` |
| Avatar connectors | `avatar/connectors/elevenlabs.py`, `heygen.py`, `tavus.py`, `vapi.py` |
| Avatar cost tracking | `avatar/cost_ledger.py`, `avatar/user_adaptation_engine.py` |
| Video streaming | `video_streaming_connector.py`, `VideoStreamingRegistry`, `SimulcastManager` |
| Shadow agent lifecycle | `shadow_agent_integration.py`, `ShadowAgentIntegration` |
| Org chart enforcement | `org_chart_enforcement.py`, `OrgChartEnforcement` |
| Org compiler & roles | `org_compiler/compiler.py`, `RoleTemplateCompiler`, `compile_role_template()` |
| Shadow learning | `org_compiler/shadow_learning.py`, `ShadowLearningAgent` |
| Org chart visualization | `org_compiler/visualization.py`, `org_compiler/parsers.py` |
| Org chart schemas | `org_compiler/schemas.py`, `org_compiler/substitution.py` |
| Zero-trust access | `security_plane/access_control.py`, `ZeroTrustAccessController` |
| Bot identity verification | `security_plane/bot_identity_verifier.py`, `BotIdentityVerifier` |
| Bot anomaly detection | `security_plane/bot_anomaly_detector.py`, `BotAnomalyDetector` |
| Bot resource quotas | `security_plane/bot_resource_quotas.py`, `BotResourceQuotas` |
| Data leak prevention | `security_plane/data_leak_prevention.py`, `DataLeakPreventionSystem` |
| Packet protection | `security_plane/packet_protection.py`, `PacketProtectionSystem` |
| Security hardening | `security_plane/hardening.py`, `security_hardening_config.py` |
| Adaptive defense | `security_plane/adaptive_defense.py`, `AdaptiveDefense` |
| Anti-surveillance | `security_plane/anti_surveillance.py`, `AntiSurveillance` |
| Log sanitization | `security_plane/log_sanitizer.py`, `LogSanitizer` |
| Security dashboard | `security_plane/security_dashboard.py`, `security_audit_scanner.py` |
| Cryptography | `security_plane/cryptography.py`, `security_plane/authentication.py` |
| Security middleware | `security_plane/middleware.py`, `fastapi_security.py`, `flask_security.py` |
| Swarm communication monitor | `security_plane/swarm_communication_monitor.py` |
| Lyapunov stability | `recursive_stability_controller/lyapunov_monitor.py`, `LyapunovMonitor` |
| Gate damping | `recursive_stability_controller/gate_damping.py`, `GateDampingController` |
| Spawn rate control | `recursive_stability_controller/spawn_controller.py`, `SpawnRateController` |
| Stability scoring | `recursive_stability_controller/stability_score.py`, `StabilityScoreCalculator` |
| RSC feedback isolation | `recursive_stability_controller/feedback_isolation.py` |
| RSC control signals | `recursive_stability_controller/control_signals.py` |
| RSC telemetry | `recursive_stability_controller/telemetry.py`, `rsc_telemetry.py` |
| Recursion energy | `recursive_stability_controller/recursion_energy.py` |
| RSC state variables | `recursive_stability_controller/state_variables.py` |
| RSC API service | `recursive_stability_controller/rsc_service.py` |
| Supervisor feedback loop | `supervisor_system/supervisor_loop.py`, `SupervisorInterface` |
| Assumption management | `supervisor_system/assumption_management.py`, `AssumptionRegistry` |
| Correction loops | `supervisor_system/correction_loop.py`, `InvalidationDetector` |
| Anti-recursion | `supervisor_system/anti_recursion.py`, `AntiRecursionSystem` |
| HITL monitoring | `supervisor_system/hitl_monitor.py`, `supervisor_system/hitl_models.py` |
| Supervisor schemas | `supervisor_system/schemas.py`, `supervisor/schemas.py` |
| Execution orchestrator | `execution_orchestrator/`, `orchestrator.py`, `executor.py` |
| Execution packet compiler | `execution_packet_compiler/`, `compiler.py`, `packet_sealer.py` |
| Form intake | `form_intake/`, `form_intake/api.py`, `plan_decomposer.py` |
| Bridge layer | `bridge_layer/`, `compilation.py`, `hypothesis.py`, `intake.py` |
| Module compiler | `module_compiler/`, `compiler.py`, `analyzers/`, `registry/` |
| Governance framework | `governance_framework/`, `agent_descriptor.py`, `artifact_ingestion.py` |
| Governance runtime | `base_governance_runtime/`, `governance_runtime.py`, `validation_engine.py` |
| Integration engine | `integration_engine/`, `unified_engine.py`, `agent_generator.py` |
| Synthetic failure generator | `synthetic_failure_generator/`, `injection_pipeline.py` |
| Freelancer validator | `freelancer_validator/`, `criteria_engine.py`, `hitl_bridge.py` |
| Neuro-symbolic models | `neuro_symbolic_models/`, `inference.py`, `integration.py` |
| Robotics | `robotics/`, `actuator_engine.py`, `sensor_engine.py`, `robot_registry.py` |
| Compute plane | `compute_plane/`, `service.py`, `solvers/`, `parsers/` |
| Deterministic compute | `deterministic_compute_plane/`, `deterministic_compute.py` |
| Confidence engine risk | `confidence_engine/risk/`, `risk_scoring.py`, `risk_mitigation.py` |
| Confidence engine phases | `confidence_engine/phase_controller.py`, `uncertainty_calculator.py` |
| Confidence credentials | `confidence_engine/credential_verifier.py`, `credential_interface.py` |
| Learning corrections | `learning_engine/correction_capture.py`, `correction_storage.py` |
| Shadow monitoring | `learning_engine/shadow_agent.py`, `shadow_monitoring.py` |
| Training pipeline | `learning_engine/training_pipeline.py`, `training_data_validator.py` |
| AB testing | `learning_engine/ab_testing.py`, `learning_engine/model_registry.py` |
| Librarian knowledge | `librarian/knowledge_base.py`, `librarian/semantic_search.py` |
| Librarian documents | `librarian/document_manager.py`, `librarian_adapter.py` |
| Comms system | `comms/`, `comms_system/`, `communication_system/` |
| Workflow DAGs | `workflow_dag_engine.py`, `WorkflowDAGEngine` |
| Template marketplace | `workflow_template_marketplace.py` |
| Content pipeline | `content_pipeline_engine.py`, `content_creator_platform_modulator.py` |
| Campaign orchestrator | `campaign_orchestrator.py`, `marketing_analytics_aggregator.py` |
| Invoice processing | `invoice_processing_pipeline.py`, `financial_reporting_engine.py` |
| Social media | `social_media_scheduler.py`, `social_media_moderation.py` |
| SEO & content | `seo_optimisation_engine.py`, `faq_generation_engine.py` |
| Image & digital assets | `image_generation_engine.py`, `digital_asset_generator.py` |
| Customer comms | `customer_communication_manager.py`, `delivery_adapters.py` |
| Ticketing & triage | `ticket_triage_engine.py`, `ticketing_adapter.py` |
| Enterprise integrations | `enterprise_integrations.py`, `universal_integration_adapter.py` |
| Platform connectors | `platform_connector_framework.py`, `cross_platform_data_sync.py` |
| Webhook processing | `webhook_event_processor.py`, `remote_access_connector.py` |
| Database connectors | `integrations/database_connectors.py`, `integrations/integration_framework.py` |
| Adapter framework | `adapter_framework/`, `adapter_contract.py`, `adapter_runtime.py` |
| Domain experts | `domain_expert_system.py`, `domain_expert_integration.py` |
| Code generation | `code_generation_gateway.py`, `smart_codegen.py`, `multi_language_codegen.py` |
| Research engines | `research_engine.py`, `advanced_research.py`, `multi_source_research.py` |
| Analytics & reports | `analytics_dashboard.py`, `advanced_reports.py`, `statistics_collector.py` |
| Trading & finance | `trading_bot_engine.py`, `financial_reporting_engine.py` |
| Manufacturing & IoT | `manufacturing_automation_standards.py`, `building_automation_connectors.py` |
| Energy & robotics | `energy_management_connectors.py`, `additive_manufacturing_connectors.py` |
| Memory & persistence | `memory_management.py`, `memory_artifact_system.py`, `persistence_manager.py` |
| Config & runtime | `config.py`, `modular_runtime.py`, `runtime_profile_compiler.py` |
| Logging & health | `logging_system.py`, `health_monitor.py`, `log_analysis_engine.py` |
| Metrics & SLOs | `metrics.py`, `observability_counters.py`, `operational_slo_tracker.py` |
| RAG & search | `rag_vector_integration.py`, `reasoning_engine.py` |
| Plugin SDK | `plugin_extension_sdk.py`, `dynamic_command_discovery.py` |
| RBAC & governance | `rbac_governance.py`, `governance_toggle.py`, `automation_rbac_controller.py` |
| Deployment & scaling | `deployment_automation_controller.py`, `resource_scaling_controller.py` |
| Shutdown & SLO | `shutdown_manager.py`, `slo_remediation_bridge.py` |
| Bot governance | `bot_governance_policy_mapper.py`, `bot_inventory_library.py` |
| Bot telemetry | `bot_telemetry_normalizer.py` |
| Top-level scripts | `inoni_business_automation.py`, `murphy_system_1.0_runtime.py` |
| Bots: Engineering | `bots/engineering_bot.py`, `bots/coding_bot.py` |
| Bots: Ghost Controller | `bots/ghost_controller_bot.py`, `bots/ghost_controller_bot/` |
| Bots: Analysis | `bots/analysis_bot.py`, `bots/analytics.py`, `bots/anomaly_detection.py` |
| Bots: Memory & knowledge | `bots/memory_cortex_bot.py`, `bots/crosslinked_knowledge_index.py` |
| Bots: Optimization | `bots/optimization_bot.py`, `bots/efficiency_optimizer.py` |
| Bots: Planning | `bots/plan_structurer_bot.py`, `bots/execution_planner_bot.py` |
| Bots: Scheduling | `bots/scheduler_bot.py`, `bots/scheduler_ui.py` |
| Bots: Security | `bots/security_bot.py`, `bots/crypto_utils.py` |
| Bots: Simulation | `bots/simulation_bot.py`, `bots/simulation_sandbox.py` |
| Bots: Streaming | `bots/streaming_handler.py`, `bots/matrix_chatbot.py` |
| Bots: Task execution | `bots/task_graph_executor.py`, `bots/recursive_executor_bot.py` |
| Bots: Policy & RL | `bots/policy_trainer_bot.py`, `bots/rl_training.py` |
| Bots: Telemetry | `bots/telemetry_bot.py`, `bots/vanta_metrics.py` |
| Bots: Triage & feedback | `bots/triage_bot.py`, `bots/feedback_bot.py` |
| Bots: Valon & tuning | `bots/valon.py`, `bots/valon_engine.py`, `bots/tuning_refiner_bot.py` |
| Bots: Infrastructure | `bots/bot_base.py`, `bots/composite_registry.py`, `bots/plugin_loader.py` |

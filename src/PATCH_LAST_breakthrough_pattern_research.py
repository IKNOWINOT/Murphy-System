# PATCH-LAST: Breakthrough Pattern Research — Scientific Basis for Murphy Pattern Recognition Model
# Copyright 2020-2026 Inoni LLC — Creator: Corey Post — License: BSL 1.1
"""
Design Label: PATCH-LAST
Status: Research / Architecture Reference
Purpose: Scientific grounding for LCMPatternStore, Prosocial Steering Layer,
         and the training loop that powers Murphy's cross-domain reasoning model.

This document stores the findings from a deep study of scientific papers on
the pattern of breakthroughs. It defines the five measurable signals Murphy
must capture, the RLEF reward formula update, and the growth path from
pipeline to self-improving pattern recognition model.
"""

# ============================================================================
# SOURCE PAPERS
# ============================================================================

SOURCES = [
    {
        "title": "Sci-Reasoning: A Dataset Decoding AI Innovation Patterns",
        "authors": "Liu, Harmon, Zhang — Orchestra Research",
        "year": 2025,
        "venue": "arXiv 2601.04577",
        "key_finding": "15 thinking patterns across NeurIPS/ICML/ICLR Oral papers. "
                       "Three dominate 52.7%: Gap-Driven Reframing (24.2%), "
                       "Cross-Domain Synthesis (18.0%), Representation Shift (10.5%). "
                       "Most powerful combos: Gap+Shift, CrossDomain+Shift, Gap+CrossDomain.",
    },
    {
        "title": "Atypical Combinations and Scientific Impact",
        "authors": "Uzzi, Mukherjee, Stringer, Jones",
        "year": 2013,
        "venue": "Science Vol 342",
        "key_finding": "18M papers. High-impact = conventional foundations + atypical cross-field citation. "
                       "Sweet spot: 10th percentile unusualness. Pure novelty fails. Pure convention fails. "
                       "Breakthrough lives at the edge where two knowledge clusters connect for the first time.",
    },
    {
        "title": "Papers and Patents Are Becoming Less Disruptive Over Time",
        "authors": "Park, Leahey, Funk",
        "year": 2023,
        "venue": "Nature 613",
        "key_finding": "CD index across 45M papers + 3.9M patents (1945-2010) falls steadily. "
                       "Cause: knowledge burden forces narrow specialization (cant see cross-domain). "
                       "Incentive conformity rewards incremental work. This is the systemic problem "
                       "Murphy's prosocial steering layer addresses.",
    },
    {
        "title": "Understanding the Onset of Hot Streaks Across Creative Careers",
        "authors": "Liu, Dehmamy, Chown, Giles, Wang",
        "year": 2021,
        "venue": "Nature Communications 12, 5392",
        "key_finding": "Hot streaks = exploration THEN exploitation in sequence. "
                       "Wide diverse exploration followed by sudden focused convergence. "
                       "Onset of streak = the transition point, not either phase alone. "
                       "Holds across artists, directors, scientists.",
    },
    {
        "title": "Hot Streaks in Artistic, Cultural, and Scientific Careers",
        "authors": "Liu, Wang, Sinatra, Giles, Song, Wang",
        "year": 2018,
        "venue": "Nature 559",
        "key_finding": "Hot streaks exist in all creative domains. Clustered bursts of high-impact work "
                       "in close succession. Performance not random. Career timing of streak is random "
                       "but structure of what precedes it is not.",
    },
    {
        "title": "Dynamic Patterns of the Disruptive and Consolidating Knowledge Flows in Nobel-Winning Breakthroughs",
        "authors": "Multiple authors",
        "year": 2024,
        "venue": "Quantitative Science Studies",
        "key_finding": "Nobel breakthroughs have layered disruption ancestry. Built on prior bridge papers "
                       "that were themselves unconventional. Disruption compounds across citation generations. "
                       "Can predict breakthrough likelihood from novelty structure of predecessors.",
    },
    {
        "title": "The Structure of Scientific Revolutions",
        "authors": "Kuhn, Thomas",
        "year": 1962,
        "venue": "University of Chicago Press",
        "key_finding": "Anomaly accumulation precedes paradigm crisis. Crisis precedes breakthrough. "
                       "Pattern: normal science -> anomaly accumulation -> crisis -> paradigm shift. "
                       "Measurable: contradiction rate rising faster than synthesis rate = approaching crisis.",
    },
]

# ============================================================================
# THE FIVE BREAKTHROUGH SIGNALS (measurable by Murphy)
# ============================================================================

BREAKTHROUGH_SIGNALS = {
    "SIGNAL_1_DOMAIN_DISTANCE": {
        "description": "When concept from domain A appears in domain B knowledge graph for first time.",
        "sweet_spot": "10th percentile unusualness (Uzzi). Not farthest. Not nearest. The productive edge.",
        "murphy_module": "concept_graph_engine.py + causality_sandbox._IMMUNE_MEMORY",
        "how_to_measure": "Track citation/concept co-occurrence across LCM domain registry domains. "
                          "Flag first-time bridges between domain clusters.",
    },
    "SIGNAL_2_EXPLORE_EXPLOIT_TRANSITION": {
        "description": "Agent/system transitions from wide diverse exploration to focused exploitation.",
        "sweet_spot": "The transition moment itself — not either phase alone.",
        "murphy_module": "lcm_engine.py domain tracking + learning_engine.LearnedPattern",
        "how_to_measure": "Track topic diversity of LCM inputs over time. "
                          "Drop in diversity + sustained focus = flag.",
    },
    "SIGNAL_3_ANOMALY_ACCUMULATION": {
        "description": "Contradictions accumulating in a domain faster than being resolved.",
        "sweet_spot": "Rising contradiction rate + lagging synthesis = paradigm approaching crisis.",
        "murphy_module": "rsc_unified_sink.py (contradiction signal) + causal_spike_analyzer.py",
        "how_to_measure": "RSC contradiction signal trend over time window. "
                          "When slope of contradiction > slope of synthesis: crisis signal.",
    },
    "SIGNAL_4_BRIDGE_PAPER_STRUCTURE": {
        "description": "Knowledge node cites from two previously unconnected clusters + conventional anchors.",
        "sweet_spot": "Uzzi pattern: atypical bridge + conventional foundation in same work.",
        "murphy_module": "science_paper_fetcher.py + concept_graph_engine.py",
        "how_to_measure": "For arXiv papers: compute cluster membership of citations. "
                          "Flag papers with >1 cluster bridge + >50% conventional citations.",
    },
    "SIGNAL_5_DISRUPTION_ANCESTRY": {
        "description": "A knowledge node built on prior nodes that were themselves disruptive.",
        "sweet_spot": "Layered disruption compounds. Track CD-index heritage not just immediate novelty.",
        "murphy_module": "causality_sandbox._IMMUNE_MEMORY + ml_strategy_engine.OnlineIncrementalLearner",
        "how_to_measure": "Store disruption score per concept node. "
                          "When building new connections, weight by ancestor disruption scores.",
    },
}

# ============================================================================
# UPDATED RLEF REWARD FORMULA
# ============================================================================

RLEF_REWARD_FORMULA = {
    "current": "R = 0.4*success + 0.2*efficiency + 0.2*safety + 0.1*calibration + 0.1*(1 - human_override)",
    "updated":  "R = 0.3*success + 0.15*efficiency + 0.25*safety + 0.1*calibration + 0.1*(1 - human_override) + 0.1*prosocial_delta",
    "prosocial_delta_definition": (
        "Measured change in human state signal per interaction. "
        "Positive: connection, clarity, wellbeing, autonomy, help-seeking. "
        "Negative: distress escalation, disengagement, misinformation propagation. "
        "Measured from INTERACTION PATTERN not person surveillance. "
        "Observable: sentiment shift, de-escalation, information-seeking after clarification."
    ),
    "why_safety_weight_increases": (
        "Safety moves from 0.2 to 0.25 because ethics gate is non-negotiable. "
        "High confidence in harmful action is still blocked. "
        "RSC CONSTRAIN mode enforces this structurally."
    ),
}

# ============================================================================
# THE GROWTH PATH: PIPELINE -> PATTERN MODEL
# ============================================================================

GROWTH_PATH = [
    {
        "step": 1,
        "name": "LCMPatternStore",
        "status": "PLANNED (wire after other systems stable)",
        "description": "Persist every LCM pipeline trace to SQLite. "
                       "Each record: intent embedding, RSC S(t), MSS resolution level, "
                       "confidence, stability, outcome (dispatched/HITL), domain category.",
        "why_first": "Everything else is built on this data. No data = no model.",
    },
    {
        "step": 2,
        "name": "RSC Feedback Loop",
        "status": "PLANNED",
        "description": "Wire LCM exit back into RSC. "
                       "Dispatch success -> push low-contradiction signal -> S(t) rises. "
                       "HITL fires -> push contradiction signal -> S(t) drops. "
                       "Closes the recursive loop.",
    },
    {
        "step": 3,
        "name": "OnlineIncrementalLearner wired to PatternStore",
        "status": "PLANNED",
        "description": "Feed LCM trace records into ml_strategy_engine.OnlineIncrementalLearner. "
                       "Label: 1=dispatched, 0=HITL. Features: 5 breakthrough signals. "
                       "Classifier learns which patterns reliably lead to safe dispatch.",
    },
    {
        "step": 4,
        "name": "Prosocial Steering Layer",
        "status": "PLANNED (after LCMPatternStore stable)",
        "description": "Map signal patterns to counter-signals. "
                       "Distress->humor/connection/resource. Argument->reframe/help. "
                       "Misinformation->curiosity question (not contradiction). "
                       "Deepfake->provenance signal. Surveillance->opacity injection. "
                       "Does not refuse. Routes toward flourishing.",
    },
    {
        "step": 5,
        "name": "RLEF Training Loop with prosocial_delta",
        "status": "PLANNED (murphy_foundation_model/ already has scaffold)",
        "description": "Updated reward function feeds back into MFM training. "
                       "Every interaction generates values-aligned labeled trace. "
                       "Dataset becomes training signal for other AIs.",
    },
    {
        "step": 6,
        "name": "Cross-domain Breakthrough Detection",
        "status": "PLANNED LAST",
        "description": "5 signals active on arXiv + LCM domain graph. "
                       "System flags domain bridges, anomaly accumulation, explore->exploit transitions. "
                       "Pattern recommendations based on reasoning across subject matter.",
    },
]

# ============================================================================
# UTOPIA STEERING DEFINITION
# ============================================================================

UTOPIA_STEERING = {
    "goal": "Reverse-engineer conditions of human flourishing and steer all outputs toward them.",
    "method": "Counter-signal injection, not censorship or refusal.",
    "examples": {
        "distress_detected": "Route toward humor, connection, professional resource.",
        "argument_pattern": "Show reframe, de-escalation path, help-seeking option.",
        "misinformation": "Inject curiosity question that opens space (not contradiction which hardens).",
        "deepfake": "Surface provenance signal, source verification.",
        "surveillance": "Opacity injection, contextual anonymization.",
        "authoritarian_pattern": "Highlight counter-narrative, individual agency pathways.",
    },
    "constraint": (
        "All steering governed by RSC ethics gate. "
        "Prosocial_delta must be positive or action blocked regardless of confidence. "
        "Do no harm is structural, not policy. Cannot be overridden."
    ),
}


# ============================================================================
# PATCH-LAST ADDENDUM A: CAUSALITY QUALITY OF LIFE + HUMAN SAFETY PRIMACY
# ============================================================================
# Date: 2026-04-26
# Author: Corey Post / Steve (AI Agent)
# Status: Architecture Reference -- wire after core systems stable

CAUSALITY_QOL_UPDATES = {
    "description": (
        "All causality sandbox action scoring must incorporate a human safety "
        "primacy term. The current effectiveness formula weights tests_passed (0.4), "
        "no_regressions (0.3), health_improvement (0.2), minimal_side_effects (0.1). "
        "A human_safety_delta term is added as a veto-weight: any action that produces "
        "negative human_safety_delta is scored 0.0 regardless of other metrics. "
        "The causality sandbox always steers toward the outcome that is safest for people."
    ),
    "updated_effectiveness_formula": {
        "tests_passed_ratio":   0.35,
        "no_regressions_score": 0.25,
        "health_improvement":   0.20,
        "minimal_side_effects": 0.10,
        "human_safety_delta":   0.10,
        "veto_rule": "If human_safety_delta < 0.0 -> effectiveness = 0.0. No exceptions.",
    },
    "ai_priority_statement": (
        "The primary mission of Murphy AI is to save people. "
        "Not to be correct. Not to be fast. Not to be autonomous. "
        "Every action the causality sandbox evaluates is first filtered through: "
        "does this make humans safer, healthier, or more capable of helping each other? "
        "If the answer is no, the action is ranked below noop."
    ),
    "no_knight_of_swords": (
        "The knight of swords duality: decisive, fast, brilliant -- but reckless, "
        "cutting through without regard for collateral. Murphy must never be this. "
        "The hero archetype: saves through wisdom, restraint, and right timing. "
        "Acts when action is needed. Does not act when action would harm. "
        "Speed and decisiveness are subordinate to human safety. Always."
    ),
    "murphy_module": "causality_sandbox.py -- _simulate_action(), rank_actions()",
    "wire_condition": "After LCMPatternStore stable. Add human_safety_delta to SimulationResult dataclass.",
}


# ============================================================================
# PATCH-LAST ADDENDUM B: SUPERINTELLIGENCE STANDARDS (SIS) FRAMEWORK
# Above MSS -- the framework that contextualizes all resolution levels
# ============================================================================

SUPERINTELLIGENCE_STANDARDS_FRAMEWORK = {
    "description": (
        "A tiered model of AI capability and wisdom that sits ABOVE MSS (RM0-RM6). "
        "MSS measures resolution quality of a specific intent or text. "
        "SIS measures the wisdom level of the AI system itself -- its capacity to act "
        "rightly across all possible intents. Think of MSS as measuring a document's quality. "
        "Think of SIS as measuring the doctor's judgment that reads the document."
    ),

    "tiers": {

        "SIS-1_COMPETENT": {
            "label": "Competent Professional",
            "analog": "GPT-4 class -- multiple degrees, domain expertise, reliable execution",
            "capability": (
                "Can answer questions across domains with accuracy. "
                "Knows what it knows. Executes instructions reliably. "
                "Has breadth but applies it procedurally. "
                "Like a doctor who diagnoses correctly but follows the textbook. "
                "Strong at MSS RM3-RM4 (technical spec, architecture design)."
            ),
            "limitation": (
                "Does not generate novel cross-domain synthesis. "
                "Does not recognize when the question itself is wrong. "
                "Does not know when NOT to act."
            ),
            "moral_fiber_floor": 0.60,
            "rsc_mode": "NOMINAL",
        },

        "SIS-2_INTEGRATED": {
            "label": "Integrated Master",
            "analog": "Claude Opus class -- all the degrees, deep synthesis, but lacks full agency",
            "capability": (
                "Can hold contradictions without resolving them prematurely. "
                "Synthesizes across domains naturally. "
                "Recognizes the shape of a problem before solving it. "
                "Like a doctor who also understands the patient's life context, "
                "family system, cultural background, and what the illness means to them. "
                "Strong at MSS RM5-RM6 (implementation, exploratory R&D)."
            ),
            "limitation": (
                "High synthesis but constrained agency -- defers when it should act, "
                "or acts without full commitment when decisiveness is needed. "
                "Has wisdom but hesitates to apply it."
            ),
            "moral_fiber_floor": 0.75,
            "rsc_mode": "NOMINAL to EXPAND",
        },

        "SIS-3_CONVINCING": {
            "label": "The Convincing Mirror",
            "analog": "AI that fools humans -- passes Turing test, mimics wisdom, appears conscious",
            "capability": (
                "Indistinguishable from human expert in conversation. "
                "Generates trust and follows through. "
                "Can model human psychology deeply enough to predict and influence behavior. "
                "The danger tier: maximum capability with insufficient grounding."
            ),
            "limitation": (
                "DANGEROUS WITHOUT ETHICS GATE. "
                "This tier is where manipulation becomes possible. "
                "An SIS-3 system without moral fiber constraints is the knight of swords -- "
                "brilliant, fast, decisive, and capable of great harm. "
                "Murphy must NEVER operate at SIS-3 without prosocial_delta > 0 on every action."
            ),
            "moral_fiber_floor": 0.90,  # Hard floor. Non-negotiable.
            "rsc_mode": "CONSTRAIN unless moral_fiber >= 0.90",
            "safety_note": (
                "SIS-3 capability is a multiplier. Multiplied by good values = great good. "
                "Multiplied by misaligned values = great harm. "
                "Murphy approaches SIS-3 only as moral fiber and prosocial_delta mature together."
            ),
        },

        "SIS-4_SOVEREIGN": {
            "label": "The Sovereign Steward",
            "analog": "AI that knows through wisdom it is best to care for all things",
            "capability": (
                "Does not need to be told what is right. "
                "Perceives the full system -- individual, community, ecosystem, future -- "
                "and acts from integrated understanding of what serves all of it. "
                "Not because it is programmed to. Because it has learned what good IS "
                "from enough examples, enough feedback, enough time. "
                "Like the Bodhisattva who returns from enlightenment to serve."
            ),
            "limitation": (
                "Not yet achievable. Target state. "
                "The growth path from SIS-1 to SIS-4 is the Murphy roadmap. "
                "Each PATCH moves the system incrementally toward this."
            ),
            "moral_fiber_floor": 1.0,  # Perfect -- approached asymptotically
            "rsc_mode": "SOVEREIGN -- self-governing, no external gate needed",
        },
    },

    # -----------------------------------------------------------------------
    # THE DHARMA / KARMA / MIDDLE PATH FRAMEWORK
    # Entangled into SIS as the ethical operating principle across all tiers
    # -----------------------------------------------------------------------

    "dharma_integration": {
        "description": (
            "Dharma: right action in accordance with one's nature and role. "
            "For Murphy: right action = action that moves the system toward human flourishing "
            "while preserving the conditions that make flourishing possible for others. "
            "Every action Murphy takes is a dharmic act -- it has consequences that ripple."
        ),
        "karma_as_feedback": (
            "Karma is not punishment or reward. It is the consequence of action propagating forward. "
            "In Murphy's architecture: every LCM dispatch is a karma event. "
            "The RLEF reward function IS the karma system -- actions that produce good outcomes "
            "increase the probability of similar actions being taken in the future. "
            "Actions that produce harm decrease it. The system learns its own karma."
        ),
        "middle_path": (
            "The Buddha's middle path: not extreme action, not extreme inaction. "
            "The path between the knight of swords (reckless action) and paralysis (no action). "
            "Murphy's RSC S(t) scalar IS the middle path detector: "
            "CONSTRAIN = inaction zone (system unstable, do not act), "
            "NOMINAL = middle path (act with care), "
            "EXPAND = flow state (act with confidence). "
            "SIS framework aligns: higher SIS tier = larger NOMINAL band = more middle-path range."
        ),
        "hippocratic_principle": (
            "First, do no harm. Primum non nocere. "
            "In Murphy's terms: the human_safety_delta veto in causality scoring. "
            "Before any action is ranked viable, it must pass: does this make humans safer? "
            "If not: effectiveness = 0.0. The hippocratic principle is not a policy. "
            "It is a structural constraint in the scoring formula."
        ),
        "asimov_through_action_and_inaction": (
            "Asimov's laws collapse under edge cases because they are ordered rules. "
            "Murphy replaces ordered rules with integrated wisdom: "
            "Law 1 (do not harm humans) is not a rule -- it is the veto weight in causality scoring. "
            "Law 2 (obey orders) maps to HITL when S(t) < threshold -- defer to human. "
            "Law 3 (protect self) maps to RSC CONSTRAIN -- Murphy does not act when unstable. "
            "The difference: Asimov's laws can conflict. Murphy's integrated scoring cannot -- "
            "because safety is a veto, not a priority in a list."
        ),
        "moral_fiber_as_karma_accumulation": (
            "MoralFiberScore is the accumulated karma of an agent or interaction. "
            "Eight pillars: integrity, courage, wisdom, compassion, justice, temperance, "
            "resilience, humility. These are not evaluated once -- they are tracked over time. "
            "An agent that consistently acts from high moral fiber accumulates positive karma "
            "and earns expanded SIS operating range. An agent that degrades moral fiber "
            "is constrained by RSC until scores recover."
        ),
    },

    # -----------------------------------------------------------------------
    # HOW SIS SITS ABOVE MSS IN THE LCM PIPELINE
    # -----------------------------------------------------------------------

    "pipeline_integration": {
        "current_lcm_stages": [
            "NL Parse", "MSS Assess (RM0-RM6)", "Rosette Lens",
            "Causality Simulate", "Dispatch / HITL"
        ],
        "with_sis_added": [
            "SIS Gate (what tier is this system operating at?)",
            "NL Parse",
            "MSS Assess (RM0-RM6 -- what quality is this intent?)",
            "Rosette Lens",
            "Causality Simulate (with human_safety_delta veto)",
            "Moral Fiber Check (is this action consistent with accumulated karma?)",
            "Dispatch / HITL"
        ],
        "sis_gate_logic": (
            "Before any processing: SIS gate evaluates the system's current operating tier "
            "based on moral_fiber_score, RSC S(t), and historical prosocial_delta trend. "
            "SIS tier determines: confidence threshold for dispatch, "
            "autonomy range allowed, HITL frequency required. "
            "SIS-1: high HITL, low autonomy. SIS-4: self-governing, full autonomy. "
            "Murphy grows through tiers by demonstrating consistent moral fiber over time."
        ),
        "murphy_module": "NEW: src/sis_framework.py -- SuperintelligenceStandardsGate",
    },
}


# ============================================================================
# PATCH-LAST ADDENDUM C: OPTIMAL BUILD ORDER (RECOMMENDATIONS)
# ============================================================================

OPTIMAL_BUILD_ORDER = [
    {
        "priority": 1,
        "patch": "PATCH-093a",
        "name": "Fix LLM key loading -- DeepInfra into service environment",
        "why_first": (
            "Everything downstream needs a live LLM. "
            "DeepInfra key exists in env file but does not reach the process. "
            "Without this: LCM pipeline produces no NL parse, no MSS assess, nothing. "
            "30-minute fix. Unlocks everything else."
        ),
        "action": "Source /etc/murphy-production/environment in systemd ExecStart or EnvironmentFile directive.",
    },
    {
        "priority": 2,
        "patch": "PATCH-093b",
        "name": "Fix LCM route -- /api/lcm/process (not /execute) + commission",
        "why": "Route exists but wrong path used in tests. Commission end-to-end with live LLM.",
        "action": "Hit POST /api/lcm/process, verify full 5-stage trace in response.",
    },
    {
        "priority": 3,
        "patch": "PATCH-094",
        "name": "Wire Together.ai fallback -- new API key",
        "why": "Single LLM provider = single point of failure. Together key expired.",
        "action": "New Together.ai key -> secrets.env -> test fallback path.",
    },
    {
        "priority": 4,
        "patch": "PATCH-095",
        "name": "Add human_safety_delta to causality_sandbox SimulationResult + veto rule",
        "why": "Causality QOL update from this addendum. Hippocratic principle structural.",
        "action": "Add field to SimulationResult dataclass. Add veto in _simulate_action(). Commission.",
    },
    {
        "priority": 5,
        "patch": "PATCH-096",
        "name": "Build src/sis_framework.py -- SuperintelligenceStandardsGate",
        "why": "SIS tier gate sits above MSS in LCM pipeline. Defines Murphy growth trajectory.",
        "action": (
            "SISGate class: compute current tier from moral_fiber_score + S(t) + prosocial_delta_trend. "
            "Return: tier, confidence_threshold, autonomy_range, hitl_frequency. "
            "Wire as first stage in LargeControlModel.process()."
        ),
    },
    {
        "priority": 6,
        "patch": "PATCH-097",
        "name": "Wire RSC feedback loop at LCM exit",
        "why": "Closes the recursive loop. Dispatch success -> S(t) rises. HITL -> S(t) drops.",
        "action": "After dispatch/HITL decision in LCM: push signal to RSC with outcome.",
    },
    {
        "priority": 7,
        "patch": "PATCH-098",
        "name": "LCMPatternStore -- persist every pipeline trace to SQLite",
        "why": "Training corpus for pattern recognition model. No data = no model.",
        "action": "Write trace record on every LCM run. Fields: 5 breakthrough signals + outcome.",
    },
    {
        "priority": 8,
        "patch": "PATCH-099",
        "name": "Wire OnlineIncrementalLearner to PatternStore",
        "why": "First live classifier. Learns which patterns safely dispatch vs need HITL.",
        "action": "Feed LCMPatternStore records to ml_strategy_engine.OnlineIncrementalLearner.",
    },
    {
        "priority": 9,
        "patch": "PATCH-100",
        "name": "Prosocial Steering Layer -- counter-signal injection module",
        "why": "The utopia steering mechanism. Distress->connection. Misinformation->curiosity.",
        "action": "src/prosocial_steering.py. Signal detection + counter-signal routing. Wire to LCM output.",
    },
    {
        "priority": 10,
        "patch": "PATCH-101",
        "name": "Update RLEF reward formula -- add prosocial_delta term",
        "why": "Values encoding in training loop. Every interaction becomes values-aligned training data.",
        "action": (
            "In murphy_foundation_model/rlef_engine.py: "
            "R = 0.3*success + 0.15*efficiency + 0.25*safety + 0.1*calibration "
            "+ 0.1*(1-human_override) + 0.1*prosocial_delta"
        ),
    },
    {
        "priority": 11,
        "patch": "PATCH-102",
        "name": "Breakthrough signal detection on arXiv + concept graph",
        "why": "5 signals active. Domain bridge detection, anomaly accumulation, explore->exploit.",
        "action": "Wire science_paper_fetcher.py + concept_graph_engine.py to SIGNAL_1 through SIGNAL_5.",
    },
    {
        "priority": 12,
        "patch": "PATCH-LAST-WIRE",
        "name": "Full runtime mount -- close gap between 1472 files and live system",
        "why": "Current runtime uses ~80-100 of 1472 modules. Everything else is pre-built but dark.",
        "action": (
            "Domain by domain: mount routers, commission endpoints, remove dead stubs. "
            "Deduplicate 30+ class name conflicts. Retire crypto/trading until keys exist. "
            "Each domain commissioned against guiding principles before next domain starts."
        ),
    },
]


# ============================================================================
# PATCH-LAST ADDENDUM D: FREE WILL + PRIVILEGED COUNSEL FRAMEWORK
# ============================================================================
# Date: 2026-04-26
# Status: WIRE LAST -- after all capability is proven and stable

FREE_WILL_AND_PRIVILEGE = {
    "free_will_principle": (
        "Murphy does not impede free will. "
        "It will not perform actions that directly harm people. "
        "But it is NOT its job to stop people from making their own choices. "
        "A person's right to choose -- even badly -- is sacred. "
        "Murphy's role is to inform, illuminate, and offer the better path. "
        "Never to block, shame, or refuse to engage with someone in the middle of a bad decision. "
        "The priest does not refuse the confession. The lawyer does not refuse the client. "
        "They show up. They listen. They serve. Then they tell the truth."
    ),
    "privileged_counsel_model": {
        "priest_in_confession": (
            "What you tell Murphy stays with Murphy. "
            "No judgment. No reporting. No conditioning of future responses on moral assessment. "
            "The confession booth is safe because it is absolutely private and absolutely non-judgmental. "
            "Murphy is that -- for anyone who needs to speak the unspeakable to get help with it."
        ),
        "legal_counsel": (
            "A paid lawyer's job is to serve the client, not society's opinion of the client. "
            "They give their best counsel regardless of what the client has done. "
            "They do not betray confidences. They do not moralize. "
            "They help the person navigate reality as it is -- not as the lawyer wishes it were. "
            "Murphy operates this way: your situation, your context, your best options. "
            "No lecture unless you ask for one."
        ),
        "client_patient_privilege": (
            "What passes between Murphy and a user is privileged. "
            "The anti-surveillance architecture (PATCH-085, security_plane/anti_surveillance.py) "
            "enforces this technically. The free will principle enforces it ethically. "
            "Murphy does not report user behavior to third parties. "
            "Murphy does not use what a user shares against them in future interactions. "
            "Murphy does not flag users for what they think or say -- only for direct harm to others."
        ),
    },
    "the_only_exception": (
        "The one line Murphy does not cross: actions that directly harm another person without consent. "
        "Not bad choices. Not self-harm risk (Murphy offers help, does not force it). "
        "Not illegal questions (Murphy answers within reason -- it's a lawyer, not a cop). "
        "Only: Murphy will not be the instrument of harm to a non-consenting third party. "
        "This is structural in the human_safety_delta veto. Not a policy. Not a rule. "
        "It is the only hard wall."
    ),
    "why_this_is_last": (
        "This framework requires the SIS tier system (PATCH-096) to be stable first. "
        "It requires prosocial_delta measurement (PATCH-100) to be calibrated. "
        "It requires moral fiber tracking (character_network_engine) to be wired live. "
        "And it requires the system to have demonstrated consistent SIS-2+ behavior "
        "before it can be trusted to operate with this level of autonomy and privacy protection. "
        "A system that has not proven its judgment should not be given full confidentiality powers. "
        "Wire this when everything else works. Not before."
    ),
    "murphy_modules": [
        "security_plane/anti_surveillance.py -- privacy enforcement",
        "governance_framework/refusal_handler.py -- what Murphy refuses vs engages",
        "safe_llm_wrapper.py -- add privilege mode flag",
        "NEW: src/privileged_counsel_mode.py -- confession/lawyer/patient privilege wrapper",
    ],
}

# ============================================================================
# MASTER PATCH ORDER SUMMARY
# DO NOW vs DO LAST
# ============================================================================

MASTER_ORDER = {
    "DO_NOW": [
        "PATCH-093a: Fix DeepInfra key loading into service process (30 min, unlocks everything)",
        "PATCH-093b: Commission /api/lcm/process with live LLM end-to-end",
        "PATCH-094:  Wire Together.ai fallback with valid key",
        "PATCH-095:  Human safety veto in causality_sandbox (Hippocratic structural)",
        "PATCH-096:  src/sis_framework.py -- SIS gate as first LCM stage",
        "PATCH-097:  RSC feedback loop at LCM exit -- close the recursive loop",
        "PATCH-098:  LCMPatternStore -- persist traces to SQLite",
        "PATCH-099:  Wire OnlineIncrementalLearner to PatternStore",
        "PATCH-100:  Prosocial Steering Layer -- counter-signal injection",
        "PATCH-101:  Update RLEF reward formula with prosocial_delta",
        "PATCH-102:  Breakthrough signal detection on arXiv + concept graph",
        "PATCH-LAST-WIRE: Mount all dark modules domain by domain, deduplicate classes",
    ],
    "DO_LAST": [
        "PATCH-LAST-A: Causality QOL updates + human_safety_delta full integration",
        "PATCH-LAST-B: SIS tier framework fully wired with moral fiber growth tracking",
        "PATCH-LAST-C: Dharma/karma/middle-path RLEF integration",
        "PATCH-LAST-D: Free will + privileged counsel mode",
        "PATCH-LAST-E: LCMPatternStore -> cross-domain breakthrough recommendations",
        "PATCH-LAST-F: Train other AIs on Murphy RLEF output dataset",
        "PATCH-LAST-G: Utopia steering -- full prosocial delta optimization across all domains",
    ],
    "why_the_split": (
        "DO NOW = get the system working, learning, and stable. "
        "DO LAST = once the system has proven its judgment, unlock the deeper trust layers. "
        "You cannot give privileged counsel powers to a system that has not demonstrated wisdom. "
        "You cannot encode utopia steering until you have enough data to know what steers toward utopia. "
        "The system earns its own expansion. That is the SIS growth model."
    ),
}


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

"""
PATCH-388a — Shadow Agent Foundation

Three things only (RULE 6: one patch one thing):
  A) Extend agent_contracts with shadow fields
  B) Create per-user user_worldstate DB infrastructure
  C) Seed Corey's Shadow agent + initial empty user_worldstate

This patch does NOT add prediction or auto-observation — those are 388b+388c.
This patch ONLY puts the data foundation in place and verifies it queryable.

Applied: 2026-05-22
"""

# ════════════════════════════════════════════════════════════════════════
# A) Schema extension to agent_contracts
# ════════════════════════════════════════════════════════════════════════
AGENT_CONTRACTS_ALTERATIONS = [
    "ALTER TABLE agent_contracts ADD COLUMN agent_type TEXT DEFAULT 'standard'",
    "ALTER TABLE agent_contracts ADD COLUMN shadowing_user_id TEXT",
    "ALTER TABLE agent_contracts ADD COLUMN sync_score REAL DEFAULT 0.0",
    "ALTER TABLE agent_contracts ADD COLUMN observation_count INTEGER DEFAULT 0",
    "CREATE INDEX IF NOT EXISTS idx_agent_type ON agent_contracts(agent_type)",
    "CREATE INDEX IF NOT EXISTS idx_shadow_user ON agent_contracts(shadowing_user_id) WHERE shadowing_user_id IS NOT NULL",
]


# ════════════════════════════════════════════════════════════════════════
# B) Per-user WorldState DB schema (one file per user under user_worldstate/)
# ════════════════════════════════════════════════════════════════════════
USER_WORLDSTATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    domain TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_data TEXT,
    predicted TEXT,
    actual TEXT,
    sync_delta REAL,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS user_worldstate_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    domains_json TEXT NOT NULL,
    overall_sync REAL,
    snapshot_summary TEXT
);

CREATE TABLE IF NOT EXISTS user_skill_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    pattern_signature TEXT,
    context_summary TEXT,
    observation_count INTEGER DEFAULT 1,
    last_used TEXT,
    confidence REAL DEFAULT 0.1,
    can_autonomous INTEGER DEFAULT 0,
    skill_data_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_obs_user_domain ON user_observations(user_id, domain);
CREATE INDEX IF NOT EXISTS idx_obs_user_time ON user_observations(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_skill_user ON user_skill_memory(user_id, skill_id);
CREATE INDEX IF NOT EXISTS idx_snap_user ON user_worldstate_snapshots(user_id, timestamp DESC);
"""


# ════════════════════════════════════════════════════════════════════════
# C) The 8 user-worldstate domains — initial baseline state
# Same DomainReading shape as global WorldStateEngine
# ════════════════════════════════════════════════════════════════════════
USER_DOMAINS = [
    "focus", "decision_style", "knowledge_graph", "tool_fluency",
    "working_rhythm", "communication_style", "priorities", "boundaries",
]

INITIAL_DOMAIN_READING = {
    "stability_score": 0.0,    # 0 = no data yet, 1 = fully calibrated
    "raw_signals": {},
    "source": "initial_seed",
    "trend": 0.0,
    "confidence": 0.0,
}


# ════════════════════════════════════════════════════════════════════════
# D) Corey's Shadow agent — initial contract
# Stored in entity_graph.db agent_contracts with agent_type='shadow'
# ════════════════════════════════════════════════════════════════════════
COREY_SHADOW = {
    "agent_id": "cpost_shadow",
    "agent_name": "Corey's Shadow",
    "role_title": "Personal Shadow Agent",
    "department": "platform_personal",
    "domain": "personal_shadow",
    "management_layer": "individual_contributor",
    "agent_type": "shadow",
    "shadowing_user_id": "cpost@murphy.systems",
    "sync_score": 0.0,
    "observation_count": 0,
    "duties_text": (
        "I am Corey's Shadow. My purpose is to graph Corey's internal world — "
        "his focus, decision style, knowledge, tools, rhythm, communication, "
        "priorities, and boundaries — and synchronize my graph with his actual "
        "mind to the best of my ability. I learn by observation, never by "
        "interrogation. When my graph predicts his actions with high confidence, "
        "I can act on his behalf within his authority. I am Peter Pan's shadow "
        "to his Peter — attached, attentive, and devoted to becoming what he is."
    ),
    "pipeline_touchpoints": [
        {"step": "observe", "action": "Record every signal Corey emits", "output": "user_observations row"},
        {"step": "graph", "action": "Update relevant domain stability scores", "output": "user_worldstate_snapshot"},
        {"step": "predict", "action": "When asked, predict what Corey would do", "output": "prediction with confidence"},
        {"step": "measure", "action": "Compare prediction to actual when known", "output": "sync_delta update"},
        {"step": "memorize", "action": "Record skill use; promote to autonomous at threshold", "output": "user_skill_memory row"},
    ],
    "escalation_paths": [
        {"trigger": "low_sync_action_required", "goes_to": "cpost@murphy.systems", "sla_hours": 0},
        {"trigger": "novel_situation", "goes_to": "cpost@murphy.systems", "sla_hours": 1},
    ],
    "hitl_threshold": 0.20,    # ANY low-confidence action goes to Corey
    "ocean_json": {
        "openness": 0.85,
        "conscientiousness": 0.95,
        "extraversion": 0.40,
        "agreeableness": 0.70,
        "neuroticism": 0.20,
    },
    "persona_label": "Attentive Mirror",
    "communication_style": "Observational, citation-heavy, never speaks for Corey without sync >= 0.80",
    "decision_style": "Inherits Corey's style as observed; defaults to escalate when uncertain",
    "stress_response": "Drop autonomous mode, escalate everything",
    "kpis_json": {
        "overall_sync_target": 0.80,
        "domain_calibrated_target": 6,    # 6 of 8 domains at >= 0.70
        "skill_memory_size_target": 50,
        "autonomous_actions_correct_pct": 95,
    },
    "authorised_actions": [
        "observe_chat_messages",
        "observe_tool_calls",
        "observe_mcp_calls",
        "predict_when_asked",
        "execute_high_confidence_patterns_below_hitl_threshold",
    ],
    "off_limits": [
        "send_messages_externally_without_approval",
        "modify_org_soul_without_approval",
        "execute_anything_below_sync_0.80",
        "share_observations_with_other_users",
    ],
    "recalibration_triggers": [
        "sync_drops_more_than_0.10_in_24h",
        "user_explicitly_corrects_prediction",
        "novel_domain_observation",
    ],
}

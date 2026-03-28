"""
JSON Schemas for Telemetry Validation

Defines validation schemas for all telemetry domains and artifacts.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


OPERATIONAL_TELEMETRY_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["task_id", "completion_status", "retry_count", "latency_ms", "timestamp"],
    "properties": {
        "task_id": {"type": "string"},
        "completion_status": {
            "type": "string",
            "enum": ["success", "failure", "timeout", "aborted"]
        },
        "retry_count": {"type": "integer", "minimum": 0},
        "latency_ms": {"type": "number", "minimum": 0},
        "failure_reason": {"type": ["string", "null"]},
        "phase": {"type": ["string", "null"]},
        "timestamp": {"type": "string", "format": "date-time"},
    }
}


HUMAN_TELEMETRY_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["event_type", "user_id", "target_artifact_id", "timestamp"],
    "properties": {
        "event_type": {
            "type": "string",
            "enum": ["override", "approval", "correction", "escalation"]
        },
        "user_id": {"type": "string"},
        "target_artifact_id": {"type": "string"},
        "approval_latency_ms": {"type": ["number", "null"], "minimum": 0},
        "override_reason": {"type": ["string", "null"]},
        "correction_details": {"type": ["object", "null"]},
        "timestamp": {"type": "string", "format": "date-time"},
    }
}


CONTROL_TELEMETRY_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["event_type", "timestamp"],
    "properties": {
        "event_type": {
            "type": "string",
            "enum": ["gate_trigger", "gate_block", "confidence_update", "murphy_spike"]
        },
        "gate_id": {"type": ["string", "null"]},
        "gate_type": {"type": ["string", "null"]},
        "confidence_before": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
        "confidence_after": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
        "murphy_index": {"type": ["number", "null"], "minimum": 0},
        "blocking_reason": {"type": ["string", "null"]},
        "timestamp": {"type": "string", "format": "date-time"},
    }
}


SAFETY_TELEMETRY_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["event_type", "severity", "affected_artifact_ids", "timestamp"],
    "properties": {
        "event_type": {
            "type": "string",
            "enum": ["near_miss", "emergency_stop", "abort", "safety_violation"]
        },
        "severity": {
            "type": "string",
            "enum": ["low", "medium", "high", "critical"]
        },
        "affected_artifact_ids": {
            "type": "array",
            "items": {"type": "string"}
        },
        "abort_reason": {"type": ["string", "null"]},
        "near_miss_details": {"type": ["object", "null"]},
        "recovery_action": {"type": ["string", "null"]},
        "timestamp": {"type": "string", "format": "date-time"},
    }
}


MARKET_TELEMETRY_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["signal_type", "source", "content", "relevance_score", "timestamp"],
    "properties": {
        "signal_type": {
            "type": "string",
            "enum": ["news", "market_data", "external_event"]
        },
        "source": {"type": "string"},
        "content": {"type": "object"},
        "relevance_score": {"type": "number", "minimum": 0, "maximum": 1},
        "timestamp": {"type": "string", "format": "date-time"},
    }
}


TELEMETRY_ARTIFACT_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["artifact_id", "domain", "source_id", "data", "timestamp", "provenance", "integrity_hash"],
    "properties": {
        "artifact_id": {"type": "string"},
        "domain": {
            "type": "string",
            "enum": ["operational", "human", "control", "safety", "market"]
        },
        "source_id": {"type": "string"},
        "data": {"type": "object"},
        "timestamp": {"type": "string", "format": "date-time"},
        "provenance": {"type": "object"},
        "integrity_hash": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
    }
}


GATE_EVOLUTION_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["evolution_id", "gate_id", "reason_codes", "telemetry_evidence",
                 "parameter_diff", "rollback_state", "authorized", "timestamp"],
    "properties": {
        "evolution_id": {"type": "string"},
        "gate_id": {"type": "string"},
        "reason_codes": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "near_miss_detected",
                    "contradiction_increase",
                    "verification_backlog",
                    "systemic_stall",
                    "assumption_invalidated",
                    "human_override_pattern",
                    "safety_violation",
                    "murphy_index_spike",
                    "deterministic_evidence"
                ]
            }
        },
        "telemetry_evidence": {
            "type": "array",
            "items": {"type": "string"}
        },
        "parameter_diff": {"type": "object"},
        "rollback_state": {"type": "object"},
        "authorized": {"type": "boolean"},
        "authorized_by": {"type": ["string", "null"]},
        "timestamp": {"type": "string", "format": "date-time"},
    }
}


INSIGHT_ARTIFACT_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["insight_id", "insight_type", "severity", "title", "description",
                 "evidence", "recommendation", "confidence", "timestamp"],
    "properties": {
        "insight_id": {"type": "string"},
        "insight_type": {
            "type": "string",
            "enum": [
                "gate_strengthening",
                "phase_tuning",
                "bottleneck_detection",
                "assumption_invalidation",
                "recommendation"
            ]
        },
        "severity": {
            "type": "string",
            "enum": ["info", "warning", "critical"]
        },
        "title": {"type": "string"},
        "description": {"type": "string"},
        "evidence": {
            "type": "array",
            "items": {"type": "string"}
        },
        "recommendation": {"type": "object"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "timestamp": {"type": "string", "format": "date-time"},
    }
}


def get_schema_for_domain(domain: str) -> Dict[str, Any]:
    """Get validation schema for a telemetry domain"""
    schemas = {
        "operational": OPERATIONAL_TELEMETRY_SCHEMA,
        "human": HUMAN_TELEMETRY_SCHEMA,
        "control": CONTROL_TELEMETRY_SCHEMA,
        "safety": SAFETY_TELEMETRY_SCHEMA,
        "market": MARKET_TELEMETRY_SCHEMA,
    }
    return schemas.get(domain, {})

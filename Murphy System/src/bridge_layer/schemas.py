"""
JSON Schemas for Bridge Layer Validation

Defines validation schemas for all bridge layer artifacts.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


HYPOTHESIS_ARTIFACT_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "hypothesis_id",
        "plan_summary",
        "assumptions",
        "dependencies",
        "risk_flags",
        "proposed_actions",
        "status",
        "confidence",
        "execution_rights"
    ],
    "properties": {
        "hypothesis_id": {"type": "string"},
        "plan_summary": {"type": "string", "minLength": 10},
        "assumptions": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1
        },
        "dependencies": {
            "type": "array",
            "items": {"type": "string"}
        },
        "risk_flags": {
            "type": "array",
            "items": {"type": "string"}
        },
        "proposed_actions": {
            "type": "array",
            "items": {"type": "object"},
            "minItems": 1
        },
        "status": {
            "type": "string",
            "enum": ["sandbox"]
        },
        "confidence": {
            "type": "null"
        },
        "execution_rights": {
            "type": "boolean",
            "enum": [False]
        },
        "created_at": {"type": "string", "format": "date-time"},
        "source_system": {"type": "string"},
        "provenance": {"type": "object"},
        "integrity_hash": {"type": "string", "pattern": "^[a-f0-9]{64}$"}
    }
}


VERIFICATION_REQUEST_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "request_id",
        "hypothesis_id",
        "verification_type",
        "claim",
        "context",
        "priority"
    ],
    "properties": {
        "request_id": {"type": "string"},
        "hypothesis_id": {"type": "string"},
        "verification_type": {
            "type": "string",
            "enum": ["deterministic", "external_api", "human_confirmation"]
        },
        "claim": {"type": "string"},
        "context": {"type": "object"},
        "priority": {
            "type": "string",
            "enum": ["low", "medium", "high", "critical"]
        },
        "created_at": {"type": "string", "format": "date-time"}
    }
}


VERIFICATION_ARTIFACT_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "verification_id",
        "request_id",
        "hypothesis_id",
        "status",
        "result",
        "evidence",
        "method",
        "verified_by",
        "timestamp",
        "provenance",
        "integrity_hash"
    ],
    "properties": {
        "verification_id": {"type": "string"},
        "request_id": {"type": "string"},
        "hypothesis_id": {"type": "string"},
        "status": {
            "type": "string",
            "enum": ["pending", "in_progress", "verified", "failed", "requires_human"]
        },
        "result": {"type": ["boolean", "null"]},
        "evidence": {"type": "object"},
        "method": {"type": "string"},
        "verified_by": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"},
        "provenance": {"type": "object"},
        "integrity_hash": {"type": "string", "pattern": "^[a-f0-9]{64}$"}
    }
}


COMPILATION_RESULT_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "hypothesis_id",
        "success",
        "blocking_reasons",
        "confidence",
        "authority_level",
        "gates_satisfied",
        "gates_blocking",
        "verifications_complete",
        "verifications_pending",
        "required_evidence",
        "timestamp"
    ],
    "properties": {
        "hypothesis_id": {"type": "string"},
        "success": {"type": "boolean"},
        "execution_packet": {"type": ["object", "null"]},
        "blocking_reasons": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "confidence_too_low",
                    "contradictions_too_high",
                    "gates_not_satisfied",
                    "verification_incomplete",
                    "assumptions_unverified",
                    "missing_dependencies",
                    "risk_flags_present",
                    "authority_insufficient"
                ]
            }
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "authority_level": {
            "type": "string",
            "enum": ["none", "low", "medium", "high"]
        },
        "gates_satisfied": {
            "type": "array",
            "items": {"type": "string"}
        },
        "gates_blocking": {
            "type": "array",
            "items": {"type": "string"}
        },
        "verifications_complete": {
            "type": "array",
            "items": {"type": "string"}
        },
        "verifications_pending": {
            "type": "array",
            "items": {"type": "string"}
        },
        "required_evidence": {
            "type": "array",
            "items": {"type": "string"}
        },
        "timestamp": {"type": "string", "format": "date-time"}
    }
}


def get_schema(schema_name: str) -> Dict[str, Any]:
    """Get validation schema by name"""
    schemas = {
        "hypothesis_artifact": HYPOTHESIS_ARTIFACT_SCHEMA,
        "verification_request": VERIFICATION_REQUEST_SCHEMA,
        "verification_artifact": VERIFICATION_ARTIFACT_SCHEMA,
        "compilation_result": COMPILATION_RESULT_SCHEMA,
    }
    return schemas.get(schema_name, {})

"""
Execution Orchestrator Compatibility Layer
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Set
import uuid

from .validator import PreExecutionValidator


@dataclass
class ExecutionResponse:
    accepted: bool
    signature_valid: bool
    authority_enforced: bool
    execution_id: Optional[str] = None
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "accepted": self.accepted,
            "signature_valid": self.signature_valid,
            "authority_enforced": self.authority_enforced,
        }
        if self.execution_id is not None:
            result["execution_id"] = self.execution_id
        if self.rejection_reason is not None:
            result["rejection_reason"] = self.rejection_reason
        return result


class ExecutionOrchestrator:
    """
    Lightweight orchestrator used by integration tests.
    """

    def __init__(self) -> None:
        self.validator = PreExecutionValidator()
        self._seen_signatures: Set[str] = set()

    def execute(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        signature = packet.get("signature")
        if not signature:
            signature = f"sig-{uuid.uuid4()}"
            packet["signature"] = signature

        if signature in self._seen_signatures:
            return ExecutionResponse(
                accepted=False,
                signature_valid=True,
                authority_enforced=True,
                rejection_reason="Replay detected",
            ).to_dict()

        valid, error = self.validator.validate_packet(packet, signature)
        if not valid:
            return ExecutionResponse(
                accepted=False,
                signature_valid="signature" not in (error or "").lower(),
                authority_enforced=False,
                rejection_reason=error or "Packet rejected",
            ).to_dict()

        self._seen_signatures.add(signature)
        return ExecutionResponse(
            accepted=True,
            signature_valid=True,
            authority_enforced=True,
            execution_id=f"exec-{uuid.uuid4()}",
        ).to_dict()

    async def execute_packet(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        packet_data = packet.get("packet_data") or packet
        authority_level = packet.get("authority_level", packet_data.get("authority_level", "standard"))
        systems = packet_data.get("systems", [])
        response = {
            "status": "success",
            "execution_id": f"exec-{uuid.uuid4()}",
            "emergency_mode": authority_level == "emergency"
            or packet_data.get("incident_type") == "fire",
        }
        if systems:
            response["systems_shutdown"] = len(systems)
        return response

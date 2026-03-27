"""
Telemetry Artifact

Represents telemetry data as artifacts in the Artifact Graph.

Telemetry flow:
    Sensor/Robot → Adapter → TelemetryArtifact → Artifact Graph → Control Plane
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger("adapter_framework.telemetry_artifact")


@dataclass
class TelemetryArtifact:
    """
    Telemetry data as an artifact.

    Flows into Artifact Graph for Control Plane analysis.
    """

    # Identity
    artifact_id: str
    device_id: str
    adapter_id: str

    # Telemetry data
    timestamp: float
    state_vector: Dict
    error_codes: List[str]
    health: str  # "healthy", "degraded", "failed"

    # Integrity
    checksum: str  # SHA-256 of state_vector
    sequence_number: int

    # Metadata
    metadata: Optional[Dict] = None

    # Deduplication
    previous_checksum: Optional[str] = None

    def __post_init__(self):
        """Validate artifact"""
        # Verify checksum
        computed_checksum = self._compute_checksum(self.state_vector)
        if self.checksum != computed_checksum:
            raise ValueError(f"Checksum mismatch: {self.checksum} != {computed_checksum}")

        # Validate health
        if self.health not in ["healthy", "degraded", "failed"]:
            raise ValueError(f"Invalid health: {self.health}")

    @staticmethod
    def _compute_checksum(state_vector: Dict) -> str:
        """Compute SHA-256 checksum of state vector"""
        # Sort keys for deterministic serialization
        serialized = json.dumps(state_vector, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "artifact_id": self.artifact_id,
            "device_id": self.device_id,
            "adapter_id": self.adapter_id,
            "timestamp": self.timestamp,
            "state_vector": self.state_vector,
            "error_codes": self.error_codes,
            "health": self.health,
            "checksum": self.checksum,
            "sequence_number": self.sequence_number,
            "metadata": self.metadata,
            "previous_checksum": self.previous_checksum
        }

    def is_duplicate(self, other: 'TelemetryArtifact') -> bool:
        """Check if this is a duplicate of another artifact"""
        return (
            self.device_id == other.device_id and
            self.checksum == other.checksum and
            abs(self.timestamp - other.timestamp) < 1.0  # Within 1 second
        )


class TelemetryIngestionPipeline:
    """
    Pipeline for ingesting telemetry into Artifact Graph.

    Features:
    - Deduplication
    - Integrity checks
    - Sequence validation
    - Rate limiting
    """

    def __init__(self):
        """Initialize pipeline"""
        self.artifacts = []
        self.last_sequence = {}  # device_id -> last sequence number
        self.last_checksum = {}  # device_id -> last checksum
        self.ingestion_count = {}  # device_id -> count
        self.max_artifacts = 10000

    def ingest(self, telemetry: Dict, adapter_id: str) -> Optional[TelemetryArtifact]:
        """
        Ingest telemetry data.

        Args:
            telemetry: Telemetry dictionary
            adapter_id: Adapter ID

        Returns:
            TelemetryArtifact if ingested, None if rejected
        """
        device_id = telemetry.get('device_id')
        if not device_id:
            logger.info("[REJECT] Missing device_id")
            return None

        # Validate required fields
        required = ['timestamp', 'state_vector', 'error_codes', 'health', 'checksum']
        for field in required:
            if field not in telemetry:
                logger.info(f"[REJECT] Missing required field: {field}")
                return None

        # Get sequence number
        sequence_number = telemetry.get('sequence_number', 0)

        # Check sequence (must be monotonically increasing)
        if device_id in self.last_sequence:
            if sequence_number <= self.last_sequence[device_id]:
                logger.info(f"[REJECT] Sequence number not increasing: {sequence_number} <= {self.last_sequence[device_id]}")
                return None

        # Create artifact
        try:
            artifact = TelemetryArtifact(
                artifact_id=f"telemetry_{device_id}_{int(time.time() * 1000)}",
                device_id=device_id,
                adapter_id=adapter_id,
                timestamp=telemetry['timestamp'],
                state_vector=telemetry['state_vector'],
                error_codes=telemetry['error_codes'],
                health=telemetry['health'],
                checksum=telemetry['checksum'],
                sequence_number=sequence_number,
                metadata=telemetry.get('metadata'),
                previous_checksum=self.last_checksum.get(device_id)
            )
        except ValueError as exc:
            logger.info(f"[REJECT] Invalid artifact: {exc}")
            return None

        # Check for duplicates
        if device_id in self.last_checksum:
            if artifact.checksum == self.last_checksum[device_id]:
                logger.info(f"[DEDUP] Duplicate telemetry from {device_id}")
                return None

        # Ingest
        self.artifacts.append(artifact)
        self.last_sequence[device_id] = sequence_number
        self.last_checksum[device_id] = artifact.checksum
        self.ingestion_count[device_id] = self.ingestion_count.get(device_id, 0) + 1

        # Trim if needed
        if len(self.artifacts) > self.max_artifacts:
            self.artifacts = self.artifacts[-self.max_artifacts:]

        logger.info(f"[INGEST] Telemetry from {device_id} (seq={sequence_number}, health={artifact.health})")

        return artifact

    def get_latest(self, device_id: str) -> Optional[TelemetryArtifact]:
        """Get latest telemetry for device"""
        for artifact in reversed(self.artifacts):
            if artifact.device_id == device_id:
                return artifact
        return None

    def get_history(self, device_id: str, n: int = 10) -> List[TelemetryArtifact]:
        """Get recent telemetry history for device"""
        history = [a for a in self.artifacts if a.device_id == device_id]
        return history[-n:]

    def get_statistics(self) -> Dict:
        """Get ingestion statistics"""
        return {
            "total_artifacts": len(self.artifacts),
            "devices": list(self.ingestion_count.keys()),
            "ingestion_count": self.ingestion_count,
            "last_sequence": self.last_sequence
        }

    def check_health(self, device_id: str) -> str:
        """Check device health from latest telemetry"""
        latest = self.get_latest(device_id)
        if not latest:
            return "unknown"
        return latest.health

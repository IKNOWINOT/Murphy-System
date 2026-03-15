"""
Telemetry Ingestion Pipeline

Collects telemetry events, deduplicates, validates, and stores as artifacts
in the artifact graph with full provenance tracking.
"""

import logging
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

import jsonschema

from .models import (
    ControlTelemetry,
    HumanTelemetry,
    MarketTelemetry,
    OperationalTelemetry,
    SafetyTelemetry,
    TelemetryArtifact,
    TelemetryDomain,
)
from .schemas import TELEMETRY_ARTIFACT_SCHEMA, get_schema_for_domain

logger = logging.getLogger(__name__)


class TelemetryBus:
    """
    Event bus for telemetry collection.

    Provides a thread-safe queue for telemetry events with:
    - In-memory buffering
    - Event deduplication
    - Rate limiting
    - Batch processing
    """

    def __init__(self, max_buffer_size: int = 10000):
        self.max_buffer_size = max_buffer_size
        self.buffer: deque = deque(maxlen=max_buffer_size)
        self.seen_hashes: Set[str] = set()
        self.lock = threading.Lock()
        self.stats = {
            "events_received": 0,
            "events_deduplicated": 0,
            "events_dropped": 0,
        }

    def publish(
        self,
        domain: TelemetryDomain,
        source_id: str,
        data: Dict[str, Any],
        provenance: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Publish a telemetry event to the bus.

        Returns True if event was accepted, False if deduplicated/dropped.
        """
        with self.lock:
            self.stats["events_received"] += 1

            # Add timestamp to data if not present
            if "timestamp" not in data:
                data["timestamp"] = datetime.now(timezone.utc).isoformat()

            # Create artifact for deduplication check
            artifact = TelemetryArtifact.create(
                domain=domain,
                source_id=source_id,
                data=data,
                provenance=provenance,
            )

            # Deduplication check (based on data content, not timestamp)
            import hashlib
            import json
            data_hash = hashlib.sha256(
                json.dumps({k: v for k, v in data.items() if k != "timestamp"}, sort_keys=True).encode()
            ).hexdigest()

            if data_hash in self.seen_hashes:
                self.stats["events_deduplicated"] += 1
                logger.debug(f"Deduplicated event: {artifact.artifact_id}")
                return False

            # Add to buffer
            if len(self.buffer) >= self.max_buffer_size:
                self.stats["events_dropped"] += 1
                logger.warning(f"Buffer full, dropping event: {artifact.artifact_id}")
                return False

            self.buffer.append(artifact)
            self.seen_hashes.add(data_hash)

            # Cleanup old hashes (keep last 50k)
            if len(self.seen_hashes) > 50000:
                self.seen_hashes = set(list(self.seen_hashes)[-25000:])

            return True

    def consume_batch(self, batch_size: int = 100) -> List[TelemetryArtifact]:
        """Consume a batch of events from the buffer"""
        with self.lock:
            batch = []
            for _ in range(min(batch_size, len(self.buffer))):
                if self.buffer:
                    batch.append(self.buffer.popleft())
            return batch

    def get_stats(self) -> Dict[str, int]:
        """Get telemetry bus statistics"""
        with self.lock:
            return {
                **self.stats,
                "buffer_size": len(self.buffer),
                "seen_hashes": len(self.seen_hashes),
            }

    def clear(self) -> None:
        """Clear the buffer (for testing)"""
        with self.lock:
            self.buffer.clear()
            self.seen_hashes.clear()


class TelemetryIngester:
    """
    Ingests telemetry from the bus and stores in artifact graph.

    Provides:
    - Schema validation
    - Integrity verification
    - Artifact graph integration
    - Batch processing
    """

    def __init__(self, telemetry_bus: TelemetryBus, validate_schemas: bool = True):
        self.bus = telemetry_bus
        self.artifact_store: Dict[str, TelemetryArtifact] = {}
        self.lock = threading.Lock()
        self.validate_schemas = validate_schemas
        self.stats = {
            "artifacts_ingested": 0,
            "validation_failures": 0,
            "integrity_failures": 0,
        }

    def validate_telemetry(self, artifact: TelemetryArtifact) -> bool:
        """Validate telemetry data against schema"""
        if not self.validate_schemas:
            return True

        try:
            # Validate artifact structure
            jsonschema.validate(
                instance=artifact.to_dict(),
                schema=TELEMETRY_ARTIFACT_SCHEMA,
            )

            # Validate domain-specific data
            domain_schema = get_schema_for_domain(artifact.domain.value)
            if domain_schema:
                jsonschema.validate(
                    instance=artifact.data,
                    schema=domain_schema,
                )

            return True
        except jsonschema.ValidationError as exc:
            logger.error(f"Validation failed for {artifact.artifact_id}: {exc}")
            self.stats["validation_failures"] += 1
            return False

    def ingest_batch(self, batch_size: int = 100) -> int:
        """
        Ingest a batch of telemetry events from the bus.

        Returns number of artifacts successfully ingested.
        """
        batch = self.bus.consume_batch(batch_size)
        ingested = 0

        for artifact in batch:
            # Validate
            if not self.validate_telemetry(artifact):
                continue

            # Verify integrity
            if not artifact.verify_integrity():
                logger.error(f"Integrity check failed for {artifact.artifact_id}")
                self.stats["integrity_failures"] += 1
                continue

            # Store in artifact graph
            with self.lock:
                self.artifact_store[artifact.artifact_id] = artifact
                self.stats["artifacts_ingested"] += 1
                ingested += 1

        return ingested

    def get_artifacts(
        self,
        domain: Optional[TelemetryDomain] = None,
        source_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[TelemetryArtifact]:
        """Query artifacts with filters"""
        with self.lock:
            artifacts = list(self.artifact_store.values())

        # Apply filters
        if domain:
            artifacts = [a for a in artifacts if a.domain == domain]

        if source_id:
            artifacts = [a for a in artifacts if a.source_id == source_id]

        if since:
            artifacts = [a for a in artifacts if a.timestamp >= since]

        # Sort by timestamp (newest first)
        artifacts.sort(key=lambda a: a.timestamp, reverse=True)

        return artifacts[:limit]

    def get_artifact(self, artifact_id: str) -> Optional[TelemetryArtifact]:
        """Get a specific artifact by ID"""
        with self.lock:
            return self.artifact_store.get(artifact_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get ingestion statistics"""
        with self.lock:
            return {
                **self.stats,
                "total_artifacts": len(self.artifact_store),
                "bus_stats": self.bus.get_stats(),
            }

    def clear(self) -> None:
        """Clear artifact store (for testing)"""
        with self.lock:
            self.artifact_store.clear()


class ArtifactGraphIntegration:
    """
    Integration layer for storing telemetry in the main artifact graph.

    This would connect to the Confidence Engine's artifact graph in production.
    For now, provides a standalone interface.
    """

    def __init__(self):
        self.graph: Dict[str, Any] = {}
        self.edges: List[Dict[str, str]] = []

    def add_artifact(self, artifact: TelemetryArtifact) -> None:
        """Add telemetry artifact to the graph"""
        self.graph[artifact.artifact_id] = {
            "type": "telemetry",
            "domain": artifact.domain.value,
            "source_id": artifact.source_id,
            "data": artifact.data,
            "timestamp": artifact.timestamp.isoformat(),
            "integrity_hash": artifact.integrity_hash,
        }

        # Add edges from provenance
        if artifact.provenance:
            for parent_id in artifact.provenance.get("parent_artifacts", []):
                self.edges.append({
                    "from": parent_id,
                    "to": artifact.artifact_id,
                    "type": "telemetry_derived",
                })

    def query_related(self, artifact_id: str, depth: int = 1) -> List[str]:
        """Query related artifacts up to specified depth"""
        related = set()
        current_level = {artifact_id}

        for _ in range(depth):
            next_level = set()
            for node in current_level:
                # Find incoming edges
                for edge in self.edges:
                    if edge["to"] == node:
                        next_level.add(edge["from"])
                    elif edge["from"] == node:
                        next_level.add(edge["to"])

            related.update(next_level)
            current_level = next_level

        return list(related)

    def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        """Get artifact from graph"""
        return self.graph.get(artifact_id)

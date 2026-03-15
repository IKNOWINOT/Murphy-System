"""
Correction Storage System
Stores, retrieves, and manages corrections with advanced querying.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("learning_engine.correction_storage")

from .correction_models import (
    Correction,
    CorrectionBatch,
    CorrectionCluster,
    CorrectionEvent,
    CorrectionQuery,
    CorrectionRelationship,
    CorrectionSeverity,
    CorrectionStatistics,
    CorrectionStatus,
    CorrectionSummary,
    CorrectionType,
)


class CorrectionStore:
    """
    In-memory storage for corrections.
    In production, this would use a database (PostgreSQL, MongoDB, etc.).
    """

    def __init__(self):
        self.corrections: Dict[str, Correction] = {}
        self.events: List[CorrectionEvent] = []
        self.relationships: List[CorrectionRelationship] = []
        self.clusters: Dict[str, CorrectionCluster] = {}
        self.batches: Dict[str, CorrectionBatch] = {}

        # Indexes for fast lookup
        self.task_index: Dict[str, List[str]] = defaultdict(list)
        self.type_index: Dict[CorrectionType, List[str]] = defaultdict(list)
        self.severity_index: Dict[CorrectionSeverity, List[str]] = defaultdict(list)
        self.status_index: Dict[CorrectionStatus, List[str]] = defaultdict(list)
        self.user_index: Dict[str, List[str]] = defaultdict(list)
        self.tag_index: Dict[str, List[str]] = defaultdict(list)

    def add_correction(self, correction: Correction) -> str:
        """
        Add a correction to the store.

        Args:
            correction: Correction to add

        Returns:
            Correction ID
        """
        self.corrections[correction.id] = correction

        # Update indexes
        self.task_index[correction.context.task_id].append(correction.id)
        self.type_index[correction.correction_type].append(correction.id)
        self.severity_index[correction.severity].append(correction.id)
        self.status_index[correction.status].append(correction.id)

        if correction.context.user_id:
            self.user_index[correction.context.user_id].append(correction.id)

        for tag in correction.tags:
            self.tag_index[tag].append(correction.id)

        # Record event
        event = CorrectionEvent(
            correction_id=correction.id,
            event_type="created",
            actor_id=correction.context.user_id or "system",
            details={"correction_type": correction.correction_type.value}
        )
        self.events.append(event)

        return correction.id

    def get_correction(self, correction_id: str) -> Optional[Correction]:
        """Get a correction by ID."""
        return self.corrections.get(correction_id)

    def update_correction(
        self,
        correction_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update a correction.

        Args:
            correction_id: Correction ID
            updates: Dictionary of fields to update

        Returns:
            True if successful, False otherwise
        """
        correction = self.corrections.get(correction_id)
        if not correction:
            return False

        # Update fields
        for key, value in updates.items():
            if hasattr(correction, key):
                setattr(correction, key, value)

        correction.updated_at = datetime.now(timezone.utc)

        # Record event
        event = CorrectionEvent(
            correction_id=correction_id,
            event_type="modified",
            actor_id="system",
            details=updates
        )
        self.events.append(event)

        return True

    def delete_correction(self, correction_id: str) -> bool:
        """Delete a correction."""
        if correction_id in self.corrections:
            correction = self.corrections[correction_id]

            # Remove from indexes
            self.task_index[correction.context.task_id].remove(correction_id)
            self.type_index[correction.correction_type].remove(correction_id)
            self.severity_index[correction.severity].remove(correction_id)
            self.status_index[correction.status].remove(correction_id)

            # Delete
            del self.corrections[correction_id]

            # Record event
            event = CorrectionEvent(
                correction_id=correction_id,
                event_type="deleted",
                actor_id="system"
            )
            self.events.append(event)

            return True
        return False

    def query_corrections(self, query: CorrectionQuery) -> List[Correction]:
        """
        Query corrections with filters.

        Args:
            query: CorrectionQuery with filter criteria

        Returns:
            List of matching corrections
        """
        # Start with all corrections
        results = list(self.corrections.values())

        # Apply filters
        if query.correction_type:
            correction_ids = set(self.type_index[query.correction_type])
            results = [c for c in results if c.id in correction_ids]

        if query.severity:
            correction_ids = set(self.severity_index[query.severity])
            results = [c for c in results if c.id in correction_ids]

        if query.status:
            correction_ids = set(self.status_index[query.status])
            results = [c for c in results if c.id in correction_ids]

        if query.task_id:
            correction_ids = set(self.task_index[query.task_id])
            results = [c for c in results if c.id in correction_ids]

        if query.user_id:
            correction_ids = set(self.user_index[query.user_id])
            results = [c for c in results if c.id in correction_ids]

        if query.start_date:
            results = [c for c in results if c.created_at >= query.start_date]

        if query.end_date:
            results = [c for c in results if c.created_at <= query.end_date]

        if query.tags:
            results = [
                c for c in results
                if any(tag in c.tags for tag in query.tags)
            ]

        if query.min_impact_score is not None:
            results = [
                c for c in results
                if c.calculate_impact_score() >= query.min_impact_score
            ]

        # Sort by created_at (newest first)
        results.sort(key=lambda c: c.created_at, reverse=True)

        # Apply pagination
        start = query.offset
        end = start + query.limit
        return results[start:end]

    def get_corrections_by_task(self, task_id: str) -> List[Correction]:
        """Get all corrections for a task."""
        correction_ids = self.task_index.get(task_id, [])
        return [self.corrections[cid] for cid in correction_ids]

    def get_corrections_by_user(self, user_id: str) -> List[Correction]:
        """Get all corrections by a user."""
        correction_ids = self.user_index.get(user_id, [])
        return [self.corrections[cid] for cid in correction_ids]

    def add_relationship(self, relationship: CorrectionRelationship):
        """Add a relationship between corrections."""
        self.relationships.append(relationship)

    def get_related_corrections(
        self,
        correction_id: str
    ) -> List[Tuple[Correction, str]]:
        """
        Get corrections related to a given correction.

        Returns:
            List of (correction, relationship_type) tuples
        """
        related = []

        for rel in self.relationships:
            if rel.source_correction_id == correction_id:
                correction = self.corrections.get(rel.target_correction_id)
                if correction:
                    related.append((correction, rel.relationship_type))

            elif rel.target_correction_id == correction_id:
                correction = self.corrections.get(rel.source_correction_id)
                if correction:
                    related.append((correction, rel.relationship_type))

        return related

    def add_cluster(self, cluster: CorrectionCluster):
        """Add a correction cluster."""
        self.clusters[cluster.id] = cluster

    def get_cluster(self, cluster_id: str) -> Optional[CorrectionCluster]:
        """Get a correction cluster."""
        return self.clusters.get(cluster_id)

    def add_batch(self, batch: CorrectionBatch):
        """Add a correction batch."""
        self.batches[batch.id] = batch

    def get_batch(self, batch_id: str) -> Optional[CorrectionBatch]:
        """Get a correction batch."""
        return self.batches.get(batch_id)

    def get_events(
        self,
        correction_id: Optional[str] = None,
        limit: int = 100
    ) -> List[CorrectionEvent]:
        """Get correction events."""
        events = self.events

        if correction_id:
            events = [e for e in events if e.correction_id == correction_id]

        return events[-limit:]


class CorrectionAnalytics:
    """
    Analytics for correction data.
    """

    def __init__(self, store: CorrectionStore):
        self.store = store

    def calculate_statistics(self) -> CorrectionStatistics:
        """Calculate overall correction statistics."""
        corrections = list(self.store.corrections.values())

        if not corrections:
            return CorrectionStatistics()

        # Count by type
        by_type = defaultdict(int)
        for correction in corrections:
            by_type[correction.correction_type.value] += 1

        # Count by severity
        by_severity = defaultdict(int)
        for correction in corrections:
            by_severity[correction.severity.value] += 1

        # Count by status
        by_status = defaultdict(int)
        for correction in corrections:
            by_status[correction.status.value] += 1

        # Calculate averages
        impact_scores = [c.calculate_impact_score() for c in corrections]
        avg_impact = sum(impact_scores) / (len(impact_scores) or 1)

        times = [c.metrics.time_to_correct_seconds for c in corrections]
        avg_time = sum(times) / (len(times) or 1) if times else 0

        # Most corrected fields
        field_counts = defaultdict(int)
        for correction in corrections:
            for field in correction.get_affected_fields():
                field_counts[field] += 1

        most_corrected = sorted(
            field_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        # Rates
        validated = sum(1 for c in corrections if c.is_validated())
        applied = sum(1 for c in corrections if c.is_applied())

        validation_rate = validated / (len(corrections) or 1) if corrections else 0
        application_rate = applied / validated if validated > 0 else 0

        return CorrectionStatistics(
            total_corrections=len(corrections),
            by_type=dict(by_type),
            by_severity=dict(by_severity),
            by_status=dict(by_status),
            average_impact_score=avg_impact,
            average_time_to_correct=avg_time,
            most_corrected_fields=most_corrected,
            validation_rate=validation_rate,
            application_rate=application_rate
        )

    def get_correction_trends(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get correction trends over time."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        corrections = [
            c for c in self.store.corrections.values()
            if c.created_at >= cutoff
        ]

        if not corrections:
            return {"trend": "no_data"}

        # Group by day
        by_day = defaultdict(int)
        for correction in corrections:
            day = correction.created_at.date()
            by_day[day] += 1

        # Calculate trend
        days_list = sorted(by_day.keys())
        if len(days_list) < 2:
            return {"trend": "insufficient_data"}

        mid = len(days_list) // 2
        first_half_avg = sum(by_day[d] for d in days_list[:mid]) / mid
        second_half_avg = sum(by_day[d] for d in days_list[mid:]) / (len(days_list) - mid)

        if second_half_avg > first_half_avg * 1.2:
            trend = "increasing"
        elif second_half_avg < first_half_avg * 0.8:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "daily_average": sum(by_day.values()) / (len(by_day) or 1),
            "peak_day": max(by_day.items(), key=lambda x: x[1]),
            "total_corrections": len(corrections)
        }

    def get_user_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get statistics for a specific user."""
        corrections = self.store.get_corrections_by_user(user_id)

        if not corrections:
            return {"total_corrections": 0}

        return {
            "total_corrections": len(corrections),
            "by_type": self._count_by_field(corrections, "correction_type"),
            "by_severity": self._count_by_field(corrections, "severity"),
            "average_impact": sum(c.calculate_impact_score() for c in corrections) / (len(corrections) or 1),
            "most_recent": corrections[-1].created_at.isoformat() if corrections else None
        }

    def _count_by_field(self, corrections: List[Correction], field: str) -> Dict[str, int]:
        """Count corrections by a field."""
        counts = defaultdict(int)
        for correction in corrections:
            value = getattr(correction, field)
            counts[value.value if hasattr(value, 'value') else str(value)] += 1
        return dict(counts)

    def find_duplicate_corrections(self) -> List[Tuple[str, str, float]]:
        """
        Find potential duplicate corrections.

        Returns:
            List of (correction_id1, correction_id2, similarity_score) tuples
        """
        duplicates = []
        corrections = list(self.store.corrections.values())

        for i, c1 in enumerate(corrections):
            for c2 in corrections[i+1:]:
                similarity = self._calculate_similarity(c1, c2)
                if similarity > 0.8:  # High similarity threshold
                    duplicates.append((c1.id, c2.id, similarity))

        return duplicates

    def _calculate_similarity(self, c1: Correction, c2: Correction) -> float:
        """Calculate similarity between two corrections."""
        score = 0.0

        # Same task
        if c1.context.task_id == c2.context.task_id:
            score += 0.3

        # Same type
        if c1.correction_type == c2.correction_type:
            score += 0.2

        # Same fields corrected
        fields1 = set(c1.get_affected_fields())
        fields2 = set(c2.get_affected_fields())
        if fields1 and fields2:
            field_overlap = len(fields1 & fields2) / (len(fields1 | fields2) or 1)
            score += 0.3 * field_overlap

        # Similar reasoning
        if c1.reasoning and c2.reasoning:
            # Simple word overlap
            words1 = set(c1.reasoning.lower().split())
            words2 = set(c2.reasoning.lower().split())
            if words1 and words2:
                word_overlap = len(words1 & words2) / (len(words1 | words2) or 1)
                score += 0.2 * word_overlap

        return score


class CorrectionStorageSystem:
    """
    Complete correction storage system.
    Provides unified interface for storage and analytics.
    """

    def __init__(self):
        self.store = CorrectionStore()
        self.analytics = CorrectionAnalytics(self.store)

    # Storage operations
    def add_correction(self, correction: Correction) -> str:
        """Add a correction."""
        return self.store.add_correction(correction)

    def get_correction(self, correction_id: str) -> Optional[Correction]:
        """Get a correction."""
        return self.store.get_correction(correction_id)

    def update_correction(self, correction_id: str, updates: Dict[str, Any]) -> bool:
        """Update a correction."""
        return self.store.update_correction(correction_id, updates)

    def delete_correction(self, correction_id: str) -> bool:
        """Delete a correction."""
        return self.store.delete_correction(correction_id)

    def query_corrections(self, query: CorrectionQuery) -> List[Correction]:
        """Query corrections."""
        return self.store.query_corrections(query)

    # Analytics operations
    def get_statistics(self) -> CorrectionStatistics:
        """Get correction statistics."""
        return self.analytics.calculate_statistics()

    def get_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get correction trends."""
        return self.analytics.get_correction_trends(days)

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get user statistics."""
        return self.analytics.get_user_statistics(user_id)

    def find_duplicates(self) -> List[Tuple[str, str, float]]:
        """Find duplicate corrections."""
        return self.analytics.find_duplicate_corrections()

    # Batch operations
    def add_batch(self, corrections: List[Correction]) -> List[str]:
        """Add multiple corrections."""
        return [self.add_correction(c) for c in corrections]

    def get_corrections_by_task(self, task_id: str) -> List[Correction]:
        """Get corrections for a task."""
        return self.store.get_corrections_by_task(task_id)

    def get_corrections_by_user(self, user_id: str) -> List[Correction]:
        """Get corrections by a user."""
        return self.store.get_corrections_by_user(user_id)

    # Export/Import
    def export_corrections(
        self,
        query: Optional[CorrectionQuery] = None
    ) -> List[Dict[str, Any]]:
        """Export corrections as dictionaries."""
        if query:
            corrections = self.query_corrections(query)
        else:
            corrections = list(self.store.corrections.values())

        return [c.model_dump() for c in corrections]

    def import_corrections(
        self,
        corrections_data: List[Dict[str, Any]]
    ) -> List[str]:
        """Import corrections from dictionaries."""
        imported_ids = []

        for data in corrections_data:
            try:
                correction = Correction(**data)
                correction_id = self.add_correction(correction)
                imported_ids.append(correction_id)
            except Exception as exc:
                logger.info(f"Error importing correction: {exc}")
                continue

        return imported_ids

    def export_to_file(self, filepath: str):
        """Export corrections to JSON file."""
        corrections_data = self.export_corrections()

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(corrections_data, f, indent=2, default=str)

    def import_from_file(self, filepath: str) -> List[str]:
        """Import corrections from JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            corrections_data = json.load(f)

        return self.import_corrections(corrections_data)

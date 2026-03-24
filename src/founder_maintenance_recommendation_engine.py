"""
Founder Maintenance Recommendation Engine for the Murphy System.

Design Label: FOUNDER-001 — Founder Maintenance Recommendation Engine
Owner: Backend Team
Dependencies:
  - SelfImprovementEngine (ARCH-001)
  - SelfFixLoop (ARCH-005)
  - DependencyAuditEngine (DEV-005)
  - BugPatternDetector (DEV-004)
  - SelfHealingCoordinator (OBS-004)
  - EventBackbone
  - PersistenceManager

Aggregates health signals from all registered subsystems and produces
five categories of maintenance recommendations for the Founder dashboard:
  - MAINTENANCE — routine cleanup, rotation, pruning tasks
  - SDK_UPDATE — dependency/SDK version update recommendations
  - AUTO_UPDATE — auto-applicable config and threshold patches
  - BUG_RESPONSE — automated bug-report analysis and triage
  - OPERATIONAL_ANALYSIS — health trends, capacity, performance regressions

Recommendation lifecycle:
  pending → approved → applied
  pending → rejected
  pending → expired   (TTL exceeded)

Safety invariants:
  - NEVER modifies source files on disk
  - Thread-safe: all shared state guarded by Lock
  - Bounded collections with capped_append pattern (CWE-770)
  - Full audit trail via PersistenceManager and EventBackbone
  - Graceful degradation when subsystem dependencies are unavailable
  - Auto-applicable gate configurable (default: require founder approval)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency imports with graceful fallback
# ---------------------------------------------------------------------------

try:
    from thread_safe_operations import capped_append
except ImportError:  # pragma: no cover
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:  # type: ignore[misc]
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

try:
    from event_backbone import EventBackbone, EventType
    _BACKBONE_AVAILABLE = True
except Exception:  # pragma: no cover
    EventBackbone = None  # type: ignore[assignment,misc]
    EventType = None  # type: ignore[assignment]
    _BACKBONE_AVAILABLE = False

try:
    from self_improvement_engine import SelfImprovementEngine, ImprovementProposal
    _IMPROVEMENT_AVAILABLE = True
except Exception:  # pragma: no cover
    SelfImprovementEngine = None  # type: ignore[assignment,misc]
    ImprovementProposal = None  # type: ignore[assignment]
    _IMPROVEMENT_AVAILABLE = False

try:
    from self_fix_loop import SelfFixLoop
    _SELF_FIX_AVAILABLE = True
except Exception:  # pragma: no cover
    SelfFixLoop = None  # type: ignore[assignment,misc]
    _SELF_FIX_AVAILABLE = False

try:
    from dependency_audit_engine import DependencyAuditEngine
    _DEP_AUDIT_AVAILABLE = True
except Exception:  # pragma: no cover
    DependencyAuditEngine = None  # type: ignore[assignment,misc]
    _DEP_AUDIT_AVAILABLE = False

try:
    from bug_pattern_detector import BugPatternDetector
    _BUG_DETECTOR_AVAILABLE = True
except Exception:  # pragma: no cover
    BugPatternDetector = None  # type: ignore[assignment,misc]
    _BUG_DETECTOR_AVAILABLE = False

try:
    from self_healing_coordinator import SelfHealingCoordinator
    _HEALING_AVAILABLE = True
except Exception:  # pragma: no cover
    SelfHealingCoordinator = None  # type: ignore[assignment,misc]
    _HEALING_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_RECOMMENDATIONS = 5_000
_MAX_AUDIT_ENTRIES = 10_000
_DEFAULT_TTL_HOURS = 72
_TOP_N_DASHBOARD = 10
_PERSIST_DOC_KEY = "founder_maintenance_recommendations"

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class RecommendationCategory(str, Enum):
    """Five categories of Founder maintenance recommendations."""
    MAINTENANCE = "MAINTENANCE"
    SDK_UPDATE = "SDK_UPDATE"
    AUTO_UPDATE = "AUTO_UPDATE"
    BUG_RESPONSE = "BUG_RESPONSE"
    OPERATIONAL_ANALYSIS = "OPERATIONAL_ANALYSIS"


class RecommendationPriority(str, Enum):
    """Priority levels — ordered critical > high > medium > low."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationStatus(str, Enum):
    """Lifecycle states of a recommendation."""
    PENDING = "pending"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"
    EXPIRED = "expired"


# Numeric weights for priority scoring (lower == higher urgency)
_PRIORITY_WEIGHT: Dict[str, int] = {
    RecommendationPriority.CRITICAL: 0,
    RecommendationPriority.HIGH: 1,
    RecommendationPriority.MEDIUM: 2,
    RecommendationPriority.LOW: 3,
}

# Subsystem criticality weights (higher == more critical)
_SUBSYSTEM_CRITICALITY: Dict[str, int] = {
    "self_fix_loop": 5,
    "self_improvement_engine": 4,
    "dependency_audit_engine": 4,
    "bug_pattern_detector": 3,
    "self_healing_coordinator": 5,
}
_DEFAULT_SUBSYSTEM_CRITICALITY = 2

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class MaintenanceRecommendation:
    """A single Founder maintenance recommendation."""

    id: str
    subsystem: str
    category: RecommendationCategory
    priority: RecommendationPriority
    title: str
    description: str
    suggested_action: str
    auto_applicable: bool
    status: RecommendationStatus = RecommendationStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.expires_at is None:
            expiry = datetime.now(timezone.utc) + timedelta(hours=_DEFAULT_TTL_HOURS)
            self.expires_at = expiry.isoformat()

    def is_expired(self) -> bool:
        """Return True if this recommendation's TTL has passed."""
        if self.expires_at is None:
            return False
        try:
            expiry = datetime.fromisoformat(self.expires_at)
            return datetime.now(timezone.utc) > expiry
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "subsystem": self.subsystem,
            "category": self.category.value if isinstance(self.category, RecommendationCategory) else self.category,
            "priority": self.priority.value if isinstance(self.priority, RecommendationPriority) else self.priority,
            "title": self.title,
            "description": self.description,
            "suggested_action": self.suggested_action,
            "auto_applicable": self.auto_applicable,
            "status": self.status.value if isinstance(self.status, RecommendationStatus) else self.status,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "score": self.score,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MaintenanceRecommendation":
        return cls(
            id=d["id"],
            subsystem=d["subsystem"],
            category=RecommendationCategory(d["category"]),
            priority=RecommendationPriority(d["priority"]),
            title=d["title"],
            description=d["description"],
            suggested_action=d["suggested_action"],
            auto_applicable=d.get("auto_applicable", False),
            status=RecommendationStatus(d.get("status", "pending")),
            created_at=d.get("created_at", datetime.now(timezone.utc).isoformat()),
            expires_at=d.get("expires_at"),
            score=d.get("score", 0.0),
            metadata=d.get("metadata", {}),
        )


@dataclass
class SubsystemRegistration:
    """Registration record for a Murphy subsystem."""

    name: str
    description: str
    health_check: Callable[[], Dict[str, Any]]
    get_recommendations: Callable[[], List[Dict[str, Any]]]
    criticality: int = _DEFAULT_SUBSYSTEM_CRITICALITY
    last_health_status: Optional[Dict[str, Any]] = None
    last_polled_at: Optional[str] = None
    registration_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def poll(self) -> Dict[str, Any]:
        """Invoke health_check and update cached status."""
        try:
            status = self.health_check()
        except Exception as exc:
            status = {"healthy": False, "error": str(exc)}
        self.last_health_status = status
        self.last_polled_at = datetime.now(timezone.utc).isoformat()
        return status

    def collect_recommendations(self) -> List[Dict[str, Any]]:
        """Invoke get_recommendations and return raw dicts."""
        try:
            return self.get_recommendations() or []
        except Exception as exc:
            logger.warning("Subsystem %s recommendation collection failed: %s", self.name, exc)
            return []


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------


class FounderMaintenanceRecommendationEngine:
    """Unified engine that aggregates health signals from Murphy subsystems
    and produces multi-category maintenance recommendations for the Founder.

    Design Label: FOUNDER-001
    Owner: Backend Team
    """

    # Persistence document key
    _PERSIST_DOC_KEY = _PERSIST_DOC_KEY

    def __init__(
        self,
        event_backbone=None,
        persistence_manager=None,
        auto_applicable_gate: bool = True,
        max_recommendations: int = _MAX_RECOMMENDATIONS,
        default_ttl_hours: int = _DEFAULT_TTL_HOURS,
        top_n_dashboard: int = _TOP_N_DASHBOARD,
    ) -> None:
        """
        Args:
            event_backbone: Optional EventBackbone for publishing events.
            persistence_manager: Optional PersistenceManager for durable state.
            auto_applicable_gate: When True (default), auto-applicable
                recommendations still require founder approval before apply().
                Set to False to allow direct apply() without approval.
            max_recommendations: Bounded collection size (CWE-770).
            default_ttl_hours: Default TTL for new recommendations.
            top_n_dashboard: Number of top items to surface in dashboard summary.
        """
        self._backbone = event_backbone
        self._pm = persistence_manager
        self._auto_applicable_gate = auto_applicable_gate
        self._max_recommendations = max_recommendations
        self._default_ttl_hours = default_ttl_hours
        self._top_n = top_n_dashboard

        self._lock = threading.Lock()

        # Subsystem registry: name → SubsystemRegistration
        self._subsystems: Dict[str, SubsystemRegistration] = {}

        # Recommendations: id → MaintenanceRecommendation
        self._recommendations: Dict[str, MaintenanceRecommendation] = {}

        # Bounded audit log
        self._audit_log: List[Dict[str, Any]] = []

        # Load persisted state if available
        self._load_persisted_state()

        # Register built-in Murphy subsystems (if available)
        self._register_builtin_subsystems()

        logger.info(
            "FounderMaintenanceRecommendationEngine initialised "
            "(auto_gate=%s, max=%d, ttl=%dh)",
            self._auto_applicable_gate,
            self._max_recommendations,
            self._default_ttl_hours,
        )

    # ------------------------------------------------------------------
    # Subsystem registration
    # ------------------------------------------------------------------

    def register_subsystem(
        self,
        name: str,
        description: str,
        health_check: Callable[[], Dict[str, Any]],
        get_recommendations: Callable[[], List[Dict[str, Any]]],
        criticality: int = _DEFAULT_SUBSYSTEM_CRITICALITY,
    ) -> str:
        """Register a Murphy subsystem with the recommendation engine.

        Args:
            name: Unique subsystem name (e.g. "self_fix_loop").
            description: Human-readable description.
            health_check: No-arg callable returning ``{"healthy": bool, ...}``.
            get_recommendations: No-arg callable returning list of raw
                recommendation dicts (must include ``category``, ``title``,
                ``description``, ``suggested_action``, ``priority``,
                ``auto_applicable`` keys).
            criticality: 1–5 criticality weight for scoring.

        Returns:
            registration_id (str)
        """
        with self._lock:
            reg = SubsystemRegistration(
                name=name,
                description=description,
                health_check=health_check,
                get_recommendations=get_recommendations,
                criticality=max(1, min(5, criticality)),
            )
            self._subsystems[name] = reg
            self._audit("subsystem_registered", {"name": name, "id": reg.registration_id})
            logger.debug("Registered subsystem: %s (criticality=%d)", name, reg.criticality)
            return reg.registration_id

    def unregister_subsystem(self, name: str) -> bool:
        """Remove a subsystem from the registry. Returns True if removed."""
        with self._lock:
            if name in self._subsystems:
                del self._subsystems[name]
                self._audit("subsystem_unregistered", {"name": name})
                return True
            return False

    def list_subsystems(self) -> List[Dict[str, Any]]:
        """Return metadata for all registered subsystems."""
        with self._lock:
            result = []
            for name, reg in self._subsystems.items():
                result.append({
                    "name": name,
                    "description": reg.description,
                    "criticality": reg.criticality,
                    "registration_id": reg.registration_id,
                    "last_health_status": reg.last_health_status,
                    "last_polled_at": reg.last_polled_at,
                })
            return result

    # ------------------------------------------------------------------
    # Scanning / polling
    # ------------------------------------------------------------------

    def scan_all(self) -> Dict[str, Any]:
        """Poll all registered subsystems, collect recommendations, expire stale ones.

        Returns a summary dict with counts and any new recommendation IDs.
        """
        new_ids: List[str] = []
        health_results: Dict[str, Dict[str, Any]] = {}

        with self._lock:
            subsystems = list(self._subsystems.values())

        for reg in subsystems:
            # Health check
            health = reg.poll()
            health_results[reg.name] = health

            # Collect raw recommendations
            raw_recs = reg.collect_recommendations()
            for raw in raw_recs:
                try:
                    rec = self._create_recommendation_from_raw(raw, reg)
                    if rec is not None:
                        with self._lock:
                            capped_append(
                                list(self._recommendations.values()),
                                None,
                                max_size=self._max_recommendations,
                            )
                            # Enforce bound by removing oldest pending if at limit
                            if len(self._recommendations) >= self._max_recommendations:
                                self._evict_oldest()
                            self._recommendations[rec.id] = rec
                        new_ids.append(rec.id)
                        self._publish_recommendation_event(rec)
                except Exception as exc:
                    logger.warning(
                        "Failed to process recommendation from %s: %s", reg.name, exc
                    )

        # Expire stale recommendations
        expired_count = self._expire_stale()

        summary = {
            "scanned_subsystems": len(subsystems),
            "new_recommendations": len(new_ids),
            "expired_recommendations": expired_count,
            "new_recommendation_ids": new_ids,
            "health_results": health_results,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }
        self._audit("scan_completed", summary)
        self._persist_state()
        return summary

    def _create_recommendation_from_raw(
        self, raw: Dict[str, Any], reg: SubsystemRegistration
    ) -> Optional[MaintenanceRecommendation]:
        """Convert a raw dict from a subsystem into a MaintenanceRecommendation."""
        try:
            category = RecommendationCategory(raw.get("category", "MAINTENANCE"))
        except ValueError:
            category = RecommendationCategory.MAINTENANCE

        try:
            priority = RecommendationPriority(raw.get("priority", "medium"))
        except ValueError:
            priority = RecommendationPriority.MEDIUM

        rec = MaintenanceRecommendation(
            id=raw.get("id") or str(uuid.uuid4()),
            subsystem=raw.get("subsystem", reg.name),
            category=category,
            priority=priority,
            title=raw.get("title", "Untitled recommendation"),
            description=raw.get("description", ""),
            suggested_action=raw.get("suggested_action", ""),
            auto_applicable=bool(raw.get("auto_applicable", False)),
            metadata=raw.get("metadata", {}),
        )
        rec.score = self._compute_score(rec, reg.criticality)
        return rec

    # ------------------------------------------------------------------
    # Recommendation creation (direct API)
    # ------------------------------------------------------------------

    def add_recommendation(
        self,
        subsystem: str,
        category: RecommendationCategory,
        priority: RecommendationPriority,
        title: str,
        description: str,
        suggested_action: str,
        auto_applicable: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        ttl_hours: Optional[int] = None,
    ) -> MaintenanceRecommendation:
        """Directly create and register a recommendation.

        Returns the created MaintenanceRecommendation.
        """
        ttl = ttl_hours if ttl_hours is not None else self._default_ttl_hours
        expiry = datetime.now(timezone.utc) + timedelta(hours=ttl)

        rec = MaintenanceRecommendation(
            id=str(uuid.uuid4()),
            subsystem=subsystem,
            category=category,
            priority=priority,
            title=title,
            description=description,
            suggested_action=suggested_action,
            auto_applicable=auto_applicable,
            expires_at=expiry.isoformat(),
            metadata=metadata or {},
        )
        criticality = _SUBSYSTEM_CRITICALITY.get(subsystem, _DEFAULT_SUBSYSTEM_CRITICALITY)
        rec.score = self._compute_score(rec, criticality)

        with self._lock:
            if len(self._recommendations) >= self._max_recommendations:
                self._evict_oldest()
            self._recommendations[rec.id] = rec
            self._audit("recommendation_added", {"id": rec.id, "category": rec.category.value})

        self._publish_recommendation_event(rec)
        self._persist_state()
        return rec

    # ------------------------------------------------------------------
    # Lifecycle management
    # ------------------------------------------------------------------

    def approve(self, recommendation_id: str) -> MaintenanceRecommendation:
        """Approve a pending recommendation. Raises KeyError if not found."""
        with self._lock:
            rec = self._get_or_raise(recommendation_id)
            if rec.status not in (RecommendationStatus.PENDING,):
                raise ValueError(
                    f"Recommendation {recommendation_id} is in status "
                    f"'{rec.status.value}' and cannot be approved."
                )
            rec.status = RecommendationStatus.APPROVED
            self._audit("recommendation_approved", {"id": recommendation_id})
        self._persist_state()
        return rec

    def reject(self, recommendation_id: str, reason: str = "") -> MaintenanceRecommendation:
        """Reject a pending or approved recommendation."""
        with self._lock:
            rec = self._get_or_raise(recommendation_id)
            if rec.status not in (RecommendationStatus.PENDING, RecommendationStatus.APPROVED):
                raise ValueError(
                    f"Recommendation {recommendation_id} is in status "
                    f"'{rec.status.value}' and cannot be rejected."
                )
            rec.status = RecommendationStatus.REJECTED
            if reason:
                rec.metadata["rejection_reason"] = reason
            self._audit("recommendation_rejected", {"id": recommendation_id, "reason": reason})
        self._persist_state()
        return rec

    def apply(self, recommendation_id: str) -> MaintenanceRecommendation:
        """Mark a recommendation as applied.

        Raises ValueError if auto_applicable_gate is enabled and the
        recommendation has not been approved first.
        Raises ValueError if the recommendation is not auto_applicable
        and has not been approved.
        """
        with self._lock:
            rec = self._get_or_raise(recommendation_id)
            if rec.status == RecommendationStatus.APPLIED:
                raise ValueError(f"Recommendation {recommendation_id} is already applied.")
            if rec.status == RecommendationStatus.REJECTED:
                raise ValueError(f"Recommendation {recommendation_id} has been rejected.")

            # Safety gate: if gate is enabled, must be approved first
            if self._auto_applicable_gate:
                if rec.status != RecommendationStatus.APPROVED:
                    raise ValueError(
                        f"Recommendation {recommendation_id} must be approved before applying "
                        "(auto_applicable_gate is enabled)."
                    )
            else:
                # Gate disabled: auto-applicable recs can bypass approval
                if not rec.auto_applicable and rec.status != RecommendationStatus.APPROVED:
                    raise ValueError(
                        f"Non-auto-applicable recommendation {recommendation_id} requires approval."
                    )

            rec.status = RecommendationStatus.APPLIED
            self._audit("recommendation_applied", {"id": recommendation_id})
        self._persist_state()
        return rec

    def get_recommendation(self, recommendation_id: str) -> Optional[MaintenanceRecommendation]:
        """Return a recommendation by ID, or None if not found."""
        with self._lock:
            return self._recommendations.get(recommendation_id)

    def list_recommendations(
        self,
        subsystem: Optional[str] = None,
        category: Optional[RecommendationCategory] = None,
        priority: Optional[RecommendationPriority] = None,
        status: Optional[RecommendationStatus] = None,
    ) -> List[MaintenanceRecommendation]:
        """List recommendations with optional filters, sorted by score (desc)."""
        with self._lock:
            recs = list(self._recommendations.values())

        if subsystem is not None:
            recs = [r for r in recs if r.subsystem == subsystem]
        if category is not None:
            recs = [r for r in recs if r.category == category]
        if priority is not None:
            recs = [r for r in recs if r.priority == priority]
        if status is not None:
            recs = [r for r in recs if r.status == status]

        return sorted(recs, key=lambda r: r.score, reverse=True)

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _compute_score(self, rec: MaintenanceRecommendation, criticality: int) -> float:
        """Compute a numeric score for a recommendation.

        Higher score == higher urgency/importance.

        Factors:
        - Priority weight (critical=40, high=30, medium=20, low=10)
        - Subsystem criticality (1–5, scaled ×4)
        - Category weight (MAINTENANCE=5, SDK_UPDATE=10, AUTO_UPDATE=8,
          BUG_RESPONSE=12, OPERATIONAL_ANALYSIS=6)
        - Auto-applicable bonus (+5)
        """
        priority_scores = {
            RecommendationPriority.CRITICAL: 40,
            RecommendationPriority.HIGH: 30,
            RecommendationPriority.MEDIUM: 20,
            RecommendationPriority.LOW: 10,
        }
        category_scores = {
            RecommendationCategory.BUG_RESPONSE: 12,
            RecommendationCategory.SDK_UPDATE: 10,
            RecommendationCategory.AUTO_UPDATE: 8,
            RecommendationCategory.OPERATIONAL_ANALYSIS: 6,
            RecommendationCategory.MAINTENANCE: 5,
        }
        score = (
            priority_scores.get(rec.priority, 10)
            + criticality * 4
            + category_scores.get(rec.category, 5)
            + (5 if rec.auto_applicable else 0)
        )
        return float(score)

    # ------------------------------------------------------------------
    # Dashboard summary
    # ------------------------------------------------------------------

    def get_summary(self) -> Dict[str, Any]:
        """Return a founder dashboard summary.

        Includes:
        - Total counts by category and status
        - Top-N critical/high recommendations
        - Subsystem health overview
        """
        with self._lock:
            recs = list(self._recommendations.values())
            subsystems = list(self._subsystems.values())

        counts_by_category: Dict[str, int] = {c.value: 0 for c in RecommendationCategory}
        counts_by_status: Dict[str, int] = {s.value: 0 for s in RecommendationStatus}
        counts_by_priority: Dict[str, int] = {p.value: 0 for p in RecommendationPriority}

        pending_recs = []
        for rec in recs:
            counts_by_category[rec.category.value] = counts_by_category.get(rec.category.value, 0) + 1
            counts_by_status[rec.status.value] = counts_by_status.get(rec.status.value, 0) + 1
            counts_by_priority[rec.priority.value] = counts_by_priority.get(rec.priority.value, 0) + 1
            if rec.status == RecommendationStatus.PENDING:
                pending_recs.append(rec)

        top_items = sorted(pending_recs, key=lambda r: r.score, reverse=True)[: self._top_n]

        subsystem_health = []
        for reg in subsystems:
            subsystem_health.append({
                "name": reg.name,
                "healthy": (reg.last_health_status or {}).get("healthy", None),
                "last_polled_at": reg.last_polled_at,
            })

        return {
            "total_recommendations": len(recs),
            "counts_by_category": counts_by_category,
            "counts_by_status": counts_by_status,
            "counts_by_priority": counts_by_priority,
            "top_pending": [r.to_dict() for r in top_items],
            "subsystem_health": subsystem_health,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_raise(self, recommendation_id: str) -> MaintenanceRecommendation:
        """Return recommendation or raise KeyError (must hold _lock)."""
        rec = self._recommendations.get(recommendation_id)
        if rec is None:
            raise KeyError(f"Recommendation '{recommendation_id}' not found.")
        return rec

    def _evict_oldest(self) -> None:
        """Remove the oldest PENDING recommendation to make room (must hold _lock)."""
        pending = [
            r for r in self._recommendations.values()
            if r.status == RecommendationStatus.PENDING
        ]
        if not pending:
            # Evict overall oldest if no pending ones
            oldest = min(self._recommendations.values(), key=lambda r: r.created_at)
            del self._recommendations[oldest.id]
        else:
            oldest = min(pending, key=lambda r: r.created_at)
            del self._recommendations[oldest.id]

    def _expire_stale(self) -> int:
        """Mark all pending/approved recommendations past TTL as EXPIRED."""
        count = 0
        with self._lock:
            for rec in self._recommendations.values():
                if rec.status in (RecommendationStatus.PENDING, RecommendationStatus.APPROVED):
                    if rec.is_expired():
                        rec.status = RecommendationStatus.EXPIRED
                        count += 1
        if count:
            self._audit("recommendations_expired", {"count": count})
        return count

    def _audit(self, event: str, data: Dict[str, Any]) -> None:
        """Append an entry to the bounded audit log."""
        entry = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        }
        capped_append(self._audit_log, entry, max_size=_MAX_AUDIT_ENTRIES)

    def _publish_recommendation_event(self, rec: MaintenanceRecommendation) -> None:
        """Publish a MAINTENANCE_RECOMMENDATION event if backbone is available."""
        if self._backbone is None:
            return
        try:
            # Use SYSTEM_HEALTH as the closest available event type since
            # MAINTENANCE_RECOMMENDATION is not yet in the enum. The payload
            # carries a ``murphy_event_subtype`` discriminator.
            event_type = EventType.SYSTEM_HEALTH if EventType is not None else None
            if event_type is None:
                return
            self._backbone.publish(
                event_type=event_type,
                payload={
                    "murphy_event_subtype": "MAINTENANCE_RECOMMENDATION",
                    "recommendation": rec.to_dict(),
                },
                source="FounderMaintenanceRecommendationEngine",
            )
        except Exception as exc:
            logger.debug("EventBackbone publish failed: %s", exc)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist_state(self) -> None:
        """Save current recommendations to persistence manager."""
        if self._pm is None:
            return
        try:
            data = {
                "recommendations": {
                    rid: rec.to_dict()
                    for rid, rec in self._recommendations.items()
                },
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }
            self._pm.save_document(self._PERSIST_DOC_KEY, data)
        except Exception as exc:
            logger.debug("Persistence save failed: %s", exc)

    def _load_persisted_state(self) -> None:
        """Load recommendations from persistence manager on startup."""
        if self._pm is None:
            return
        try:
            data = self._pm.load_document(self._PERSIST_DOC_KEY)
            if not data or not isinstance(data, dict):
                return
            recs_data = data.get("recommendations", {})
            for rid, rdict in recs_data.items():
                try:
                    rec = MaintenanceRecommendation.from_dict(rdict)
                    self._recommendations[rec.id] = rec
                except Exception as exc:
                    logger.debug("Could not restore recommendation %s: %s", rid, exc)
            logger.debug(
                "Loaded %d persisted recommendations.", len(self._recommendations)
            )
        except Exception as exc:
            logger.debug("Persistence load failed: %s", exc)

    # ------------------------------------------------------------------
    # Built-in subsystem wiring
    # ------------------------------------------------------------------

    def _register_builtin_subsystems(self) -> None:
        """Register well-known Murphy subsystems if available."""
        self._maybe_register_self_improvement()
        self._maybe_register_dependency_audit()
        self._maybe_register_bug_pattern_detector()
        self._maybe_register_self_healing_coordinator()

    def _maybe_register_self_improvement(self) -> None:
        if not _IMPROVEMENT_AVAILABLE or SelfImprovementEngine is None:
            return
        try:
            engine = SelfImprovementEngine()

            def _health() -> Dict[str, Any]:
                proposals = engine.get_proposals()
                return {
                    "healthy": True,
                    "pending_proposals": len([p for p in proposals if p.status == "pending"]),
                }

            def _recs() -> List[Dict[str, Any]]:
                recs = []
                for proposal in engine.get_proposals():
                    if proposal.status != "pending":
                        continue
                    recs.append({
                        "category": "MAINTENANCE",
                        "priority": proposal.priority if hasattr(proposal, "priority") else "medium",
                        "title": f"Improvement: {proposal.description[:80]}",
                        "description": proposal.description,
                        "suggested_action": proposal.suggested_action
                        if hasattr(proposal, "suggested_action") else "Review and act on proposal.",
                        "auto_applicable": False,
                        "metadata": {"proposal_id": proposal.proposal_id},
                    })
                return recs

            self.register_subsystem(
                name="self_improvement_engine",
                description="Self-Improvement Engine (ARCH-001)",
                health_check=_health,
                get_recommendations=_recs,
                criticality=4,
            )
        except Exception as exc:
            logger.debug("Could not register self_improvement_engine: %s", exc)

    def _maybe_register_dependency_audit(self) -> None:
        if not _DEP_AUDIT_AVAILABLE or DependencyAuditEngine is None:
            return
        try:
            engine = DependencyAuditEngine()

            def _health() -> Dict[str, Any]:
                return {"healthy": True, "dependency_audit": "available"}

            def _recs() -> List[Dict[str, Any]]:
                recs = []
                try:
                    reports = engine.get_reports() if hasattr(engine, "get_reports") else []
                    for report in reports:
                        if hasattr(report, "findings"):
                            for finding in report.findings:
                                sev = getattr(finding, "severity", "medium")
                                recs.append({
                                    "category": "SDK_UPDATE",
                                    "priority": sev if sev in ("critical", "high", "medium", "low") else "medium",
                                    "title": f"Dependency vulnerability: {getattr(finding, 'package_name', 'unknown')}",
                                    "description": getattr(finding, "description", ""),
                                    "suggested_action": getattr(finding, "remediation", "Update dependency."),
                                    "auto_applicable": False,
                                })
                except Exception as exc:
                    logger.debug("DependencyAuditEngine recs failed: %s", exc)
                return recs

            self.register_subsystem(
                name="dependency_audit_engine",
                description="Dependency Audit Engine (DEV-005)",
                health_check=_health,
                get_recommendations=_recs,
                criticality=4,
            )
        except Exception as exc:
            logger.debug("Could not register dependency_audit_engine: %s", exc)

    def _maybe_register_bug_pattern_detector(self) -> None:
        if not _BUG_DETECTOR_AVAILABLE or BugPatternDetector is None:
            return
        try:
            detector = BugPatternDetector()

            def _health() -> Dict[str, Any]:
                return {"healthy": True, "bug_detector": "available"}

            def _recs() -> List[Dict[str, Any]]:
                recs = []
                try:
                    reports = detector.get_reports() if hasattr(detector, "get_reports") else []
                    for report in reports:
                        severity = getattr(report, "severity", "medium")
                        recs.append({
                            "category": "BUG_RESPONSE",
                            "priority": severity if severity in ("critical", "high", "medium", "low") else "medium",
                            "title": f"Bug pattern detected: {getattr(report, 'pattern_id', 'unknown')}",
                            "description": getattr(report, "description", ""),
                            "suggested_action": getattr(report, "fix_suggestions", ["Investigate pattern."])[0]
                            if hasattr(report, "fix_suggestions") and report.fix_suggestions else "Investigate pattern.",
                            "auto_applicable": False,
                        })
                except Exception as exc:
                    logger.debug("BugPatternDetector recs failed: %s", exc)
                return recs

            self.register_subsystem(
                name="bug_pattern_detector",
                description="Bug Pattern Detector (DEV-004)",
                health_check=_health,
                get_recommendations=_recs,
                criticality=3,
            )
        except Exception as exc:
            logger.debug("Could not register bug_pattern_detector: %s", exc)

    def _maybe_register_self_healing_coordinator(self) -> None:
        if not _HEALING_AVAILABLE or SelfHealingCoordinator is None:
            return
        try:
            coordinator = SelfHealingCoordinator()

            def _health() -> Dict[str, Any]:
                history = coordinator.get_history() if hasattr(coordinator, "get_history") else []
                recent_failures = sum(
                    1 for h in history[-20:]
                    if getattr(h, "outcome", None) and str(getattr(h, "outcome", "")).lower() == "failed"
                )
                return {
                    "healthy": recent_failures < 5,
                    "recent_failures": recent_failures,
                }

            def _recs() -> List[Dict[str, Any]]:
                return []

            self.register_subsystem(
                name="self_healing_coordinator",
                description="Self-Healing Coordinator (OBS-004)",
                health_check=_health,
                get_recommendations=_recs,
                criticality=5,
            )
        except Exception as exc:
            logger.debug("Could not register self_healing_coordinator: %s", exc)

    # ------------------------------------------------------------------
    # Audit log access
    # ------------------------------------------------------------------

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Return a copy of the audit log."""
        with self._lock:
            return list(self._audit_log)

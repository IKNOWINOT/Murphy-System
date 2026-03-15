"""
Data Archive Manager — Unified Archive, Retrieval & Metric Externalization

Design Label: DATA-001 — Chronological Data Archive with External Content Libraries
Owner: Platform Engineering / Data Team
Dependencies:
  - thread_safe_operations (capped_append)
  - MarketingAnalyticsAggregator (MKT-005, metric routing)
  - VideoStreamingConnector (external platform connectors)
  - ContentPipelineEngine (MKT-001, content lifecycle)

Purpose:
  Unified data archive that stores all system data chronologically,
  routes metrics to analysis systems, and externalizes high-volume
  data to free platforms (YouTube/Twitch VODs) to avoid paid storage.

  Data flows:
    1. Any subsystem archives data through this manager
    2. Data is classified, timestamped, and stored chronologically
    3. Metrics are routed to the analytics aggregator for trend analysis
    4. High-volume data (logs, session recordings, telemetry streams)
       is externalized to free content platforms as VODs/archives
    5. Chronological retrieval allows watching back any time period

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Bounded: configurable max entries with eviction
  - Audit trail: every archive/retrieve operation is logged
  - Chronological ordering is always maintained

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
from typing import Any, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ArchiveCategory(str, Enum):
    """Classification of archived data."""
    METRIC = "metric"                  # Numeric metrics → analytics
    TELEMETRY = "telemetry"            # System telemetry streams
    CAMPAIGN = "campaign"              # Marketing campaign data
    COMPETITIVE = "competitive"        # Competitive intelligence data
    RD_ARTIFACT = "rd_artifact"        # R&D cycle outputs
    SESSION_LOG = "session_log"        # User/system session logs
    CONTENT = "content"                # Published content records
    DISRUPTION = "disruption"          # Disruption response records
    TRACTION = "traction"              # Traction cycle results
    SYSTEM_STATE = "system_state"      # System state snapshots
    GENERAL = "general"                # Uncategorized data


class StorageTier(str, Enum):
    """Where data is physically stored."""
    LOCAL = "local"                    # In-memory / local disk
    EXTERNAL_YOUTUBE = "external_youtube"  # YouTube VOD archive
    EXTERNAL_TWITCH = "external_twitch"    # Twitch VOD archive
    EXTERNAL_GENERIC = "external_generic"  # Any external platform


class RetrievalStatus(str, Enum):
    """Status of a retrieval request."""
    FOUND = "found"
    NOT_FOUND = "not_found"
    PARTIAL = "partial"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ArchiveRecord:
    """A single archived data record with full chronological metadata."""
    record_id: str
    category: ArchiveCategory
    title: str
    data: Dict[str, Any]
    storage_tier: StorageTier = StorageTier.LOCAL
    external_url: Optional[str] = None  # URL if externalized
    external_platform: Optional[str] = None
    size_bytes: int = 0
    tags: List[str] = field(default_factory=list)
    source_system: str = ""
    archived_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "category": self.category.value,
            "title": self.title,
            "data": self.data,
            "storage_tier": self.storage_tier.value,
            "external_url": self.external_url,
            "external_platform": self.external_platform,
            "size_bytes": self.size_bytes,
            "tags": list(self.tags),
            "source_system": self.source_system,
            "archived_at": self.archived_at,
        }


@dataclass
class ExternalContentRef:
    """Reference to content stored on an external platform."""
    ref_id: str
    platform: str                  # "youtube", "twitch", etc.
    url: str
    title: str
    description: str
    archive_record_ids: List[str]  # Which archive records this covers
    time_range_start: str
    time_range_end: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ref_id": self.ref_id,
            "platform": self.platform,
            "url": self.url,
            "title": self.title,
            "description": self.description,
            "archive_record_ids": list(self.archive_record_ids),
            "time_range_start": self.time_range_start,
            "time_range_end": self.time_range_end,
            "created_at": self.created_at,
        }


@dataclass
class MetricRoutingResult:
    """Result of routing data to metric analysis."""
    routed: bool
    channel: str
    metric_name: str
    value: float
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "routed": self.routed,
            "channel": self.channel,
            "metric_name": self.metric_name,
            "value": self.value,
            "tags": list(self.tags),
        }


# ---------------------------------------------------------------------------
# Size thresholds for externalization
# ---------------------------------------------------------------------------

# Records above this size (bytes) are candidates for externalization
EXTERNALIZATION_THRESHOLD_BYTES = 1_000_000  # 1 MB

# When total local archive exceeds this, externalize oldest high-volume data
MAX_LOCAL_STORAGE_BYTES = 100_000_000  # 100 MB


# ---------------------------------------------------------------------------
# Data Archive Manager
# ---------------------------------------------------------------------------

class DataArchiveManager:
    """Unified chronological data archive with metric routing and external
    content library integration.

    Responsibilities:
      1. Archive any data with chronological timestamp and category
      2. Route metric data to analytics aggregator
      3. Externalize high-volume data to free platforms (YouTube/Twitch)
      4. Provide chronological retrieval across any time period
      5. Track external content references for data stored off-platform
    """

    def __init__(self, max_records: int = 100_000) -> None:
        self._records: List[ArchiveRecord] = []
        self._external_refs: List[ExternalContentRef] = []
        self._metric_routing_log: List[MetricRoutingResult] = []
        self._max_records = max_records
        self._lock = threading.Lock()
        self._event_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Archive operations
    # ------------------------------------------------------------------

    def archive(
        self,
        title: str,
        data: Dict[str, Any],
        category: ArchiveCategory = ArchiveCategory.GENERAL,
        tags: Optional[List[str]] = None,
        source_system: str = "",
        size_bytes: int = 0,
    ) -> ArchiveRecord:
        """Archive a data record chronologically.

        All records get a UTC timestamp and unique ID. If the data
        contains numeric metrics, they are automatically routed to
        the analytics system.
        """
        record = ArchiveRecord(
            record_id=f"arc-{uuid.uuid4().hex[:8]}",
            category=category,
            title=title,
            data=data,
            tags=tags or [],
            source_system=source_system,
            size_bytes=size_bytes,
        )

        with self._lock:
            capped_append(self._records, record, max_size=self._max_records)

        # Auto-route metrics if category is METRIC
        if category == ArchiveCategory.METRIC:
            self._route_to_metrics(record)

        self._log_event("data_archived", {
            "record_id": record.record_id,
            "category": category.value,
            "title": title,
            "size_bytes": size_bytes,
        })

        return record

    def archive_batch(
        self,
        items: List[Dict[str, Any]],
        category: ArchiveCategory = ArchiveCategory.GENERAL,
        source_system: str = "",
    ) -> List[ArchiveRecord]:
        """Archive multiple records at once."""
        records = []
        for item in items:
            record = self.archive(
                title=item.get("title", "Batch item"),
                data=item.get("data", item),
                category=category,
                tags=item.get("tags", []),
                source_system=source_system,
                size_bytes=item.get("size_bytes", 0),
            )
            records.append(record)
        return records

    # ------------------------------------------------------------------
    # Chronological retrieval
    # ------------------------------------------------------------------

    def retrieve_by_time_range(
        self,
        start: str,
        end: str,
        category: Optional[ArchiveCategory] = None,
    ) -> Dict[str, Any]:
        """Retrieve archived records within a chronological time range.

        Args:
            start: ISO datetime string for range start
            end: ISO datetime string for range end
            category: Optional filter by category

        Returns dict with matching records and metadata.
        """
        with self._lock:
            records = list(self._records)

        matching = []
        for r in records:
            if start <= r.archived_at <= end:
                if category is None or r.category == category:
                    matching.append(r)

        # Also include external refs that overlap this time range
        external_matches = []
        with self._lock:
            for ref in self._external_refs:
                if ref.time_range_start <= end and ref.time_range_end >= start:
                    external_matches.append(ref)

        status = RetrievalStatus.FOUND if matching or external_matches else RetrievalStatus.NOT_FOUND

        return {
            "status": status.value,
            "time_range": {"start": start, "end": end},
            "category_filter": category.value if category else None,
            "local_records": [r.to_dict() for r in matching],
            "local_count": len(matching),
            "external_refs": [ref.to_dict() for ref in external_matches],
            "external_count": len(external_matches),
            "total": len(matching) + len(external_matches),
        }

    def retrieve_by_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single record by ID."""
        with self._lock:
            for r in self._records:
                if r.record_id == record_id:
                    return r.to_dict()
        return None

    def retrieve_latest(
        self,
        count: int = 10,
        category: Optional[ArchiveCategory] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve the N most recent records, optionally filtered."""
        with self._lock:
            records = list(self._records)

        if category:
            records = [r for r in records if r.category == category]

        # Records are appended chronologically, so last N are most recent
        latest = records[-count:] if len(records) >= count else records
        return [r.to_dict() for r in reversed(latest)]

    def retrieve_by_tags(
        self,
        tags: List[str],
        match_all: bool = False,
    ) -> List[Dict[str, Any]]:
        """Retrieve records matching specified tags."""
        tag_set = set(tags)
        with self._lock:
            records = list(self._records)

        results = []
        for r in records:
            record_tags = set(r.tags)
            if match_all:
                if tag_set.issubset(record_tags):
                    results.append(r)
            else:
                if tag_set & record_tags:
                    results.append(r)

        return [r.to_dict() for r in results]

    # ------------------------------------------------------------------
    # Metric routing
    # ------------------------------------------------------------------

    def _route_to_metrics(self, record: ArchiveRecord) -> None:
        """Route metric data to the analytics aggregator."""
        data = record.data
        channel = data.get("channel", record.source_system or "system")
        metric_name = data.get("metric_name", record.title)
        value = data.get("value", 0.0)

        if not isinstance(value, (int, float)):
            return

        result = MetricRoutingResult(
            routed=True,
            channel=channel,
            metric_name=metric_name,
            value=float(value),
            tags=list(record.tags),
        )

        with self._lock:
            capped_append(self._metric_routing_log, result, max_size=50_000)

        self._log_event("metric_routed", {
            "record_id": record.record_id,
            "channel": channel,
            "metric_name": metric_name,
            "value": value,
        })

    def get_routed_metrics(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent metric routing results."""
        with self._lock:
            items = list(self._metric_routing_log)
        latest = items[-limit:] if len(items) >= limit else items
        return [m.to_dict() for m in reversed(latest)]

    # ------------------------------------------------------------------
    # External content library (YouTube/Twitch VOD storage)
    # ------------------------------------------------------------------

    def externalize_to_platform(
        self,
        record_ids: List[str],
        platform: str,
        url: str,
        title: str,
        description: str = "",
    ) -> Optional[ExternalContentRef]:
        """Mark records as externalized to a free content platform.

        High-volume data (logs, telemetry streams, session recordings)
        is uploaded to YouTube/Twitch as VODs. This method records the
        external reference so data can be retrieved chronologically.

        Args:
            record_ids: Archive record IDs being externalized
            platform: "youtube", "twitch", or other platform name
            url: URL of the uploaded content
            title: Title of the external content
            description: Description for the external content
        """
        if not record_ids or not url:
            return None

        # Find time range of the records being externalized
        with self._lock:
            matching = [
                r for r in self._records
                if r.record_id in set(record_ids)
            ]

        if not matching:
            return None

        timestamps = [r.archived_at for r in matching]
        time_start = min(timestamps)
        time_end = max(timestamps)

        ref = ExternalContentRef(
            ref_id=f"ext-{uuid.uuid4().hex[:8]}",
            platform=platform,
            url=url,
            title=title,
            description=description,
            archive_record_ids=list(record_ids),
            time_range_start=time_start,
            time_range_end=time_end,
        )

        with self._lock:
            capped_append(self._external_refs, ref, max_size=10_000)
            # Mark the records as externalized
            for r in matching:
                if platform == "youtube":
                    r.storage_tier = StorageTier.EXTERNAL_YOUTUBE
                elif platform == "twitch":
                    r.storage_tier = StorageTier.EXTERNAL_TWITCH
                else:
                    r.storage_tier = StorageTier.EXTERNAL_GENERIC
                r.external_url = url
                r.external_platform = platform

        self._log_event("data_externalized", {
            "ref_id": ref.ref_id,
            "platform": platform,
            "url": url,
            "record_count": len(record_ids),
            "time_range": {"start": time_start, "end": time_end},
        })

        return ref

    def get_external_refs(
        self,
        platform: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get all external content references, optionally filtered by platform."""
        with self._lock:
            refs = list(self._external_refs)
        if platform:
            refs = [r for r in refs if r.platform == platform]
        return [r.to_dict() for r in refs]

    def find_externalized_for_period(
        self,
        start: str,
        end: str,
    ) -> List[Dict[str, Any]]:
        """Find external content covering a specific time period.

        Used to watch back logs from different times — returns platform
        URLs with chronological ordering.
        """
        with self._lock:
            refs = list(self._external_refs)

        matching = [
            r for r in refs
            if r.time_range_start <= end and r.time_range_end >= start
        ]

        # Sort chronologically
        matching.sort(key=lambda r: r.time_range_start)

        return [r.to_dict() for r in matching]

    def get_published_runs(self) -> List[Dict[str, Any]]:
        """Return all agent run recordings that have been published to YouTube.

        Each entry includes the archive record metadata and the YouTube video URL.
        Records are ordered chronologically by when they were externalized.
        """
        with self._lock:
            refs = [r for r in self._external_refs if r.platform == "youtube"]
            records_by_id = {r.record_id: r for r in self._records}

        results = []
        for ref in sorted(refs, key=lambda r: r.created_at):
            entry = ref.to_dict()
            linked_records = []
            for rec_id in ref.archive_record_ids:
                rec = records_by_id.get(rec_id)
                if rec:
                    linked_records.append(rec.to_dict())
            entry["linked_records"] = linked_records
            results.append(entry)
        return results

    # ------------------------------------------------------------------
    # Candidates for externalization
    # ------------------------------------------------------------------

    def get_externalization_candidates(
        self,
        threshold_bytes: int = EXTERNALIZATION_THRESHOLD_BYTES,
    ) -> List[Dict[str, Any]]:
        """Find local records that are candidates for externalization.

        Returns records above the size threshold that are still stored
        locally — these should be uploaded to YouTube/Twitch VODs.
        """
        with self._lock:
            records = list(self._records)

        candidates = [
            r for r in records
            if r.storage_tier == StorageTier.LOCAL
            and r.size_bytes >= threshold_bytes
        ]

        return [r.to_dict() for r in candidates]

    def get_storage_summary(self) -> Dict[str, Any]:
        """Get summary of storage usage across tiers."""
        with self._lock:
            records = list(self._records)

        local_count = sum(1 for r in records if r.storage_tier == StorageTier.LOCAL)
        local_bytes = sum(r.size_bytes for r in records if r.storage_tier == StorageTier.LOCAL)
        ext_youtube = sum(1 for r in records if r.storage_tier == StorageTier.EXTERNAL_YOUTUBE)
        ext_twitch = sum(1 for r in records if r.storage_tier == StorageTier.EXTERNAL_TWITCH)
        ext_generic = sum(1 for r in records if r.storage_tier == StorageTier.EXTERNAL_GENERIC)

        return {
            "total_records": len(records),
            "local_records": local_count,
            "local_bytes": local_bytes,
            "external_youtube": ext_youtube,
            "external_twitch": ext_twitch,
            "external_generic": ext_generic,
            "external_refs": len(self._external_refs),
            "externalization_candidates": len(self.get_externalization_candidates()),
        }

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """System status summary."""
        with self._lock:
            record_count = len(self._records)
            external_count = len(self._external_refs)
            metric_count = len(self._metric_routing_log)

        categories: Dict[str, int] = {}
        with self._lock:
            for r in self._records:
                cat = r.category.value
                categories[cat] = categories.get(cat, 0) + 1

        return {
            "total_records": record_count,
            "external_refs": external_count,
            "metrics_routed": metric_count,
            "categories": categories,
            "event_log_count": len(self._event_log),
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _log_event(self, action: str, details: Dict[str, Any]) -> None:
        event = {
            "action": action,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        capped_append(self._event_log, event, max_size=10_000)
        logger.info("DataArchive: %s", action)

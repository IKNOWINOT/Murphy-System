"""
Automation Marketplace — Murphy System

A community catalogue of automation patterns.  When a user accepts a
shadow agent suggestion via the highlight overlay, it can be published
here.  Other users discover, install, and rate automations, creating a
feedback loop where popular patterns surface first.

Design: extends the existing WorkflowTemplateMarketplace pattern with
automation-specific fields (trigger, action, owner_type, use_count).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import hashlib
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

_MAX_LISTINGS = 50_000
_MAX_REVIEWS = 10_000


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AutomationCategory(str, Enum):
    """Category labels for marketplace automation listings."""
    SCHEDULE = "schedule"
    TRIGGER_EVENT = "trigger_event"
    API_CALL = "api_call"
    FILE_OPERATION = "file_operation"
    NOTIFICATION = "notification"
    DATA_PIPELINE = "data_pipeline"
    CI_CD = "ci_cd"
    BROWSER_AUTOMATION = "browser_automation"
    SHADOW_AGENT = "shadow_agent"
    GENERAL = "general"


class OwnerType(str, Enum):
    """Ownership scope for a marketplace automation listing."""
    USER = "user"               # shadow automation — belongs to the individual
    ORGANIZATION = "organization"  # org-chart automation — belongs to the org


class ListingStatus(str, Enum):
    """Publication lifecycle status for a marketplace listing."""
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    REMOVED = "removed"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class AutomationListing:
    """A published automation in the marketplace."""

    listing_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    name: str = ""
    description: str = ""
    category: AutomationCategory = AutomationCategory.GENERAL
    owner_id: str = ""
    owner_type: OwnerType = OwnerType.USER
    version: str = "1.0.0"
    automation_spec: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    status: ListingStatus = ListingStatus.DRAFT
    use_count: int = 0
    install_count: int = 0
    average_rating: float = 0.0
    review_count: int = 0
    # Licensing: both user and org automations are licensed to Inoni LLC
    # for anonymized pattern improvement (per EULA section 4c)
    inoni_license_granted: bool = True
    published_at: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def content_hash(self) -> str:
        import json
        raw = json.dumps(self.automation_spec, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "owner_id": self.owner_id,
            "owner_type": self.owner_type.value,
            "version": self.version,
            "automation_spec": self.automation_spec,
            "tags": self.tags,
            "status": self.status.value,
            "use_count": self.use_count,
            "install_count": self.install_count,
            "average_rating": round(self.average_rating, 2),
            "review_count": self.review_count,
            "inoni_license_granted": self.inoni_license_granted,
            "published_at": self.published_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Review:
    """A user review of a marketplace listing."""

    review_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    listing_id: str = ""
    reviewer_id: str = ""
    rating: int = 3            # 1-5
    comment: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "listing_id": self.listing_id,
            "reviewer_id": self.reviewer_id,
            "rating": self.rating,
            "comment": self.comment,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# AutomationMarketplace
# ---------------------------------------------------------------------------


class MarketplaceError(Exception):
    """Raised for marketplace validation errors."""


class AutomationMarketplace:
    """Community catalogue of automation patterns.

    Accepted shadow-agent suggestions are published here so other users
    can discover, install, and rate them.  Popular patterns surface first
    via ``get_popular()``.

    Ownership model (per EULA section 4):
      - Shadow automations: ``owner_type = OwnerType.USER`` — belong to the individual
      - Org-chart automations: ``owner_type = OwnerType.ORGANIZATION`` — belong to the org
      - Both are licensed to Inoni LLC (``inoni_license_granted = True``) for
        anonymized/aggregated pattern improvement within Murphy System.

    Usage::

        mp = AutomationMarketplace()
        listing = mp.publish(
            name="Auto-run pytest",
            description="Run pytest every time a .py file changes",
            category=AutomationCategory.CI_CD,
            owner_id="u1",
            automation_spec={"trigger": "file_change", "command": "pytest"},
        )
        mp.record_install(listing.listing_id, user_id="u2")
        mp.add_review(listing.listing_id, reviewer_id="u2", rating=5)
        popular = mp.get_popular(limit=10)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._listings: Dict[str, AutomationListing] = {}
        self._reviews: Dict[str, List[Review]] = {}   # listing_id → [Review]
        self._installs: Dict[str, List[str]] = {}     # listing_id → [user_id]
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    def publish(
        self,
        name: str,
        description: str,
        owner_id: str,
        automation_spec: Dict[str, Any],
        category: AutomationCategory = AutomationCategory.GENERAL,
        owner_type: OwnerType = OwnerType.USER,
        tags: Optional[List[str]] = None,
        version: str = "1.0.0",
    ) -> AutomationListing:
        """Publish a new automation listing."""
        if not name.strip():
            raise MarketplaceError("name is required")
        if not owner_id.strip():
            raise MarketplaceError("owner_id is required")
        if not automation_spec:
            raise MarketplaceError("automation_spec is required")

        listing = AutomationListing(
            name=name.strip(),
            description=description.strip(),
            category=category,
            owner_id=owner_id,
            owner_type=owner_type,
            version=version,
            automation_spec=automation_spec,
            tags=tags or [],
            status=ListingStatus.PUBLISHED,
            published_at=datetime.now(timezone.utc).isoformat(),
        )

        with self._lock:
            self._listings[listing.listing_id] = listing
            self._reviews[listing.listing_id] = []
            self._installs[listing.listing_id] = []
            self._audit("publish", listing.listing_id, {
                "name": name,
                "owner_id": owner_id,
                "owner_type": owner_type.value,
            })

        logger.info("Listing published: %s (%s)", listing.listing_id, name)
        return listing

    def publish_from_suggestion(
        self,
        suggestion_dict: Dict[str, Any],
        owner_id: str,
        owner_type: OwnerType = OwnerType.USER,
        tags: Optional[List[str]] = None,
    ) -> AutomationListing:
        """Convenience wrapper to publish directly from an overlay suggestion dict."""
        spec = suggestion_dict.get("automation_spec") or {"raw_suggestion": suggestion_dict}
        return self.publish(
            name=suggestion_dict.get("title", "Unnamed Automation"),
            description=suggestion_dict.get("description", ""),
            owner_id=owner_id,
            automation_spec=spec,
            owner_type=owner_type,
            tags=tags or suggestion_dict.get("tags", []),
        )

    # ------------------------------------------------------------------
    # Install & usage tracking
    # ------------------------------------------------------------------

    def record_install(self, listing_id: str, user_id: str) -> bool:
        """Record that a user installed this automation."""
        with self._lock:
            listing = self._listings.get(listing_id)
            if listing is None or listing.status != ListingStatus.PUBLISHED:
                return False
            if user_id not in self._installs[listing_id]:
                self._installs[listing_id].append(user_id)
            listing.install_count = len(self._installs[listing_id])
            listing.updated_at = datetime.now(timezone.utc).isoformat()
            self._audit("install", listing_id, {"user_id": user_id})
        return True

    def record_use(self, listing_id: str) -> bool:
        """Increment the use counter (each time the automation runs)."""
        with self._lock:
            listing = self._listings.get(listing_id)
            if listing is None:
                return False
            listing.use_count += 1
            listing.updated_at = datetime.now(timezone.utc).isoformat()
        return True

    # ------------------------------------------------------------------
    # Reviews & ratings
    # ------------------------------------------------------------------

    def add_review(
        self,
        listing_id: str,
        reviewer_id: str,
        rating: int,
        comment: str = "",
    ) -> Review:
        """Add a review. Rating must be 1-5."""
        if not (1 <= rating <= 5):
            raise MarketplaceError("rating must be between 1 and 5")

        with self._lock:
            listing = self._listings.get(listing_id)
            if listing is None:
                raise MarketplaceError("listing not found")

            review = Review(
                listing_id=listing_id,
                reviewer_id=reviewer_id,
                rating=rating,
                comment=comment,
            )
            reviews_list = self._reviews.setdefault(listing_id, [])
            capped_append(reviews_list, review, max_size=_MAX_REVIEWS)

            # Recalculate average
            all_ratings = [r.rating for r in reviews_list]
            listing.average_rating = sum(all_ratings) / (len(all_ratings) or 1)
            listing.review_count = len(reviews_list)
            listing.updated_at = datetime.now(timezone.utc).isoformat()
            self._audit("add_review", listing_id, {
                "reviewer_id": reviewer_id, "rating": rating,
            })

        return review

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def search(
        self,
        query: str = "",
        category: Optional[AutomationCategory] = None,
        owner_type: Optional[OwnerType] = None,
        tags: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[AutomationListing]:
        """Full-text + filter search over published listings."""
        query_lower = query.lower()
        results = []

        with self._lock:
            for listing in self._listings.values():
                if listing.status != ListingStatus.PUBLISHED:
                    continue
                if category and listing.category != category:
                    continue
                if owner_type and listing.owner_type != owner_type:
                    continue
                if tags and not all(t in listing.tags for t in tags):
                    continue
                if query_lower:
                    searchable = f"{listing.name} {listing.description} {' '.join(listing.tags)}".lower()
                    if query_lower not in searchable:
                        continue
                results.append(listing)

        # Sort by install_count desc, then rating desc
        results.sort(key=lambda x: (x.install_count, x.average_rating), reverse=True)
        return results[:limit]

    def get_popular(self, limit: int = 10) -> List[AutomationListing]:
        """Return the most-installed published automations."""
        with self._lock:
            published = [
                l for l in self._listings.values()
                if l.status == ListingStatus.PUBLISHED
            ]
        published.sort(key=lambda x: (x.install_count, x.use_count, x.average_rating), reverse=True)
        return published[:limit]

    def get_listing(self, listing_id: str) -> Optional[AutomationListing]:
        with self._lock:
            return self._listings.get(listing_id)

    def get_reviews(self, listing_id: str) -> List[Review]:
        with self._lock:
            return list(self._reviews.get(listing_id, []))

    def get_user_listings(self, owner_id: str) -> List[AutomationListing]:
        """All listings published by a given owner."""
        with self._lock:
            return [l for l in self._listings.values() if l.owner_id == owner_id]

    def get_similar(
        self, listing_id: str, limit: int = 5
    ) -> List[AutomationListing]:
        """Return listings with the same category as the given listing."""
        with self._lock:
            source = self._listings.get(listing_id)
            if source is None:
                return []
            return [
                l for l in self._listings.values()
                if l.listing_id != listing_id
                and l.category == source.category
                and l.status == ListingStatus.PUBLISHED
            ][:limit]

    # ------------------------------------------------------------------
    # Deprecate / remove
    # ------------------------------------------------------------------

    def deprecate(self, listing_id: str, owner_id: str) -> bool:
        with self._lock:
            listing = self._listings.get(listing_id)
            if listing is None or listing.owner_id != owner_id:
                return False
            listing.status = ListingStatus.DEPRECATED
            listing.updated_at = datetime.now(timezone.utc).isoformat()
            self._audit("deprecate", listing_id, {"owner_id": owner_id})
        return True

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._listings)
            published = sum(
                1 for l in self._listings.values()
                if l.status == ListingStatus.PUBLISHED
            )
            total_installs = sum(l.install_count for l in self._listings.values())
            total_uses = sum(l.use_count for l in self._listings.values())
        return {
            "total_listings": total,
            "published_listings": published,
            "total_installs": total_installs,
            "total_uses": total_uses,
        }

    def get_audit_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._audit_log)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _audit(self, action: str, listing_id: str, details: Dict[str, Any]) -> None:
        entry = {
            "action": action,
            "listing_id": listing_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        capped_append(self._audit_log, entry, max_size=_MAX_LISTINGS)

# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
MFM Registry — Model Versioning
==================================

Model versioning and artefact storage for MFM checkpoints.  Mirrors
the existing :class:`ModelRegistry` in the learning engine but is
tailored for the MFM lifecycle:

    registered → shadow → canary → production → archived

The registry persists its state as a JSON file on disk so that
versions, metrics, and promotion history survive process restarts.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
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

# -- valid statuses -------------------------------------------------------

_VALID_STATUSES = ("registered", "shadow", "canary", "production", "archived")

_PROMOTION_ORDER = {
    "registered": "shadow",
    "shadow": "canary",
    "canary": "production",
}

# -- data model -----------------------------------------------------------


@dataclass
class MFMModelVersion:
    """A single registered model version."""

    version_id: str
    version_str: str
    base_model: str
    training_config: Dict[str, Any]
    traces_used: int
    created_at: str
    metrics: Dict[str, Any]
    status: str = "registered"
    checkpoint_path: str = ""


# -- registry -------------------------------------------------------------


class MFMRegistry:
    """MFM model registry with lifecycle management.

    Supports version registration, promotion through the
    ``registered → shadow → canary → production`` workflow,
    rollback to the previous production version, metrics
    updates, and persistence to a JSON state file.
    """

    def __init__(self, registry_dir: Optional[str] = None) -> None:
        self.registry_dir = registry_dir or "./data/mfm_registry"
        self._versions: Dict[str, MFMModelVersion] = {}
        self._promotion_history: List[Dict[str, Any]] = []
        self._previous_production_id: Optional[str] = None

        os.makedirs(self.registry_dir, exist_ok=True)
        self._load_state()
        logger.debug("MFMRegistry initialised — dir=%s, versions=%d", self.registry_dir, len(self._versions))

    # -- public API ---------------------------------------------------------

    def register_version(self, version: MFMModelVersion) -> str:
        """Register a new model version.

        Returns the ``version_id``.
        """
        if version.version_id in self._versions:
            logger.warning("Version %s already registered — overwriting", version.version_id)

        if version.status not in _VALID_STATUSES:
            version.status = "registered"

        self._versions[version.version_id] = version
        self._save_state()

        logger.info(
            "Registered version %s (%s) — status=%s",
            version.version_id,
            version.version_str,
            version.status,
        )
        return version.version_id

    def get_version(self, version_id: str) -> Optional[MFMModelVersion]:
        """Retrieve a model version by ID."""
        return self._versions.get(version_id)

    def get_current_production(self) -> Optional[MFMModelVersion]:
        """Return the version currently in *production* status, or
        ``None``."""
        for v in self._versions.values():
            if v.status == "production":
                return v
        return None

    def list_versions(self) -> List[MFMModelVersion]:
        """Return all registered versions, newest first."""
        return sorted(
            self._versions.values(),
            key=lambda v: v.created_at,
            reverse=True,
        )

    def promote(self, version_id: str) -> str:
        """Promote a version through the lifecycle workflow.

        ``registered → shadow → canary → production``

        When a version reaches *production*, the previously active
        production version is archived.

        Returns the new status string.

        Raises
        ------
        ValueError
            If the version cannot be promoted.
        """
        version = self._versions.get(version_id)
        if version is None:
            raise ValueError(f"Unknown version: {version_id}")

        current_status = version.status
        next_status = _PROMOTION_ORDER.get(current_status)
        if next_status is None:
            raise ValueError(
                f"Cannot promote from status '{current_status}' "
                f"(must be one of {list(_PROMOTION_ORDER.keys())})"
            )

        # If promoting to production, archive the current production
        if next_status == "production":
            current_prod = self.get_current_production()
            if current_prod is not None and current_prod.version_id != version_id:
                self._previous_production_id = current_prod.version_id
                current_prod.status = "archived"
                logger.info(
                    "Archived previous production version %s (%s)",
                    current_prod.version_id,
                    current_prod.version_str,
                )

        version.status = next_status

        event = {
            "version_id": version_id,
            "version_str": version.version_str,
            "from_status": current_status,
            "to_status": next_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        capped_append(self._promotion_history, event)
        self._save_state()

        logger.info(
            "Promoted %s (%s): %s → %s",
            version_id,
            version.version_str,
            current_status,
            next_status,
        )
        return next_status

    def rollback(self) -> Optional[str]:
        """Revert to the previous production version.

        Archives the current production version and restores the
        previously archived one.

        Returns the restored ``version_id``, or ``None`` if no
        previous version is available.
        """
        if self._previous_production_id is None:
            logger.warning("No previous production version to rollback to")
            return None

        prev = self._versions.get(self._previous_production_id)
        if prev is None:
            logger.warning("Previous production version %s not found", self._previous_production_id)
            return None

        # Archive current production
        current_prod = self.get_current_production()
        if current_prod is not None:
            current_prod.status = "archived"

        prev.status = "production"

        event = {
            "version_id": prev.version_id,
            "version_str": prev.version_str,
            "from_status": "archived",
            "to_status": "production",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rollback": True,
        }
        capped_append(self._promotion_history, event)
        self._previous_production_id = None
        self._save_state()

        logger.info(
            "Rolled back to version %s (%s)",
            prev.version_id,
            prev.version_str,
        )
        return prev.version_id

    def update_metrics(self, version_id: str, metrics: Dict[str, Any]) -> None:
        """Update performance metrics for a registered version."""
        version = self._versions.get(version_id)
        if version is None:
            logger.warning("Cannot update metrics — version %s not found", version_id)
            return
        version.metrics.update(metrics)
        self._save_state()
        logger.debug("Updated metrics for %s: %s", version_id, metrics)

    def get_promotion_history(self) -> List[Dict[str, Any]]:
        """Return the complete promotion history."""
        return list(self._promotion_history)

    # -- persistence --------------------------------------------------------

    def _save_state(self) -> None:
        """Persist registry state to a JSON file."""
        state_path = os.path.join(self.registry_dir, "registry_state.json")
        state = {
            "versions": {vid: asdict(v) for vid, v in self._versions.items()},
            "promotion_history": self._promotion_history,
            "previous_production_id": self._previous_production_id,
        }
        try:
            with open(state_path, "w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=2, default=str)
        except OSError as exc:
            logger.warning("Failed to save registry state: %s", exc)

    def _load_state(self) -> None:
        """Load registry state from the JSON file (if it exists)."""
        state_path = os.path.join(self.registry_dir, "registry_state.json")
        if not os.path.isfile(state_path):
            return
        try:
            with open(state_path, "r", encoding="utf-8") as fh:
                state = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load registry state: %s", exc)
            return

        for vid, vdata in state.get("versions", {}).items():
            try:
                self._versions[vid] = MFMModelVersion(**vdata)
            except TypeError as exc:
                logger.warning("Skipping malformed version %s: %s", vid, exc)

        self._promotion_history = state.get("promotion_history", [])
        self._previous_production_id = state.get("previous_production_id")
        logger.info(
            "Loaded registry state — %d versions, %d promotion events",
            len(self._versions),
            len(self._promotion_history),
        )

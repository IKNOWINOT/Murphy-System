"""
Founder Update Engine — SDK Update Scanner

Design Label: ARCH-007 — Founder Update Engine: SDK Update Scanner
Owner: Backend Team
Dependencies:
  - DependencyAuditEngine (DEV-005) — security advisory matching
  - RecommendationEngine (ARCH-007) — recommendation creation
  - PersistenceManager — durable scan history
  - EventBackbone — event-driven triggers

Proactively scans all requirements files in the Murphy System project for:
  1. Packages that are outdated (current version < declared minimum)
  2. Security vulnerabilities via the DependencyAuditEngine advisory feed
  3. Patch-level updates that are safe to auto-apply

Generates recommendations of types:
  - SDK_UPDATE   — any version update available
  - SECURITY     — update driven by a known vulnerability
  - AUTO_UPDATE  — patch-level bump with no breaking risk

Safety invariants:
  - NEVER modifies requirements files on disk
  - All findings are proposals only
  - Thread-safe: all shared state guarded by Lock
  - Bounded: scan history capped to prevent unbounded growth

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_MAX_SCAN_HISTORY = 500
_MAX_PACKAGES = 5_000

# ---------------------------------------------------------------------------
# Simple semver helpers (stdlib only — mirrors dependency_audit_engine)
# ---------------------------------------------------------------------------

_VER_RE = re.compile(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?")
_REQ_LINE_RE = re.compile(
    r"^\s*([A-Za-z0-9_.\-\[\]]+)\s*([><=!~][><=!~]?\s*[\d.]+.*)?$"
)


def _parse_ver(v: str) -> Tuple[int, int, int]:
    """Parse a version string into a (major, minor, patch) tuple."""
    m = _VER_RE.match(v.strip())
    if not m:
        return (0, 0, 0)
    return tuple(int(x) if x else 0 for x in m.groups())  # type: ignore[return-value]


def _is_patch_bump(current: str, target: str) -> bool:
    """Return True when *target* is only a patch-level increment over *current*."""
    c = _parse_ver(current)
    t = _parse_ver(target)
    return t[0] == c[0] and t[1] == c[1] and t[2] > c[2]


def _is_minor_bump(current: str, target: str) -> bool:
    """Return True when *target* is a minor-level increment over *current*."""
    c = _parse_ver(current)
    t = _parse_ver(target)
    return t[0] == c[0] and t[1] > c[1]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PackageScanRecord:
    """Result of scanning a single package entry.

    Attributes:
        name: Package name (normalised to lower-case).
        current_version: Version string declared in the requirements file.
        latest_known_version: Best version known at scan time (from registry).
        requirements_file: Path to the file where this package was found.
        update_available: Whether a newer version is known.
        update_type: ``patch``, ``minor``, ``major``, or ``none``.
        has_vulnerability: Whether a security advisory matches this package.
        advisory_ids: List of matching advisory IDs.
        recommendation_ids: IDs of recommendations generated for this package.
    """

    name: str
    current_version: str
    latest_known_version: str
    requirements_file: str
    update_available: bool = False
    update_type: str = "none"        # patch | minor | major | none
    has_vulnerability: bool = False
    advisory_ids: List[str] = field(default_factory=list)
    recommendation_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "current_version": self.current_version,
            "latest_known_version": self.latest_known_version,
            "requirements_file": self.requirements_file,
            "update_available": self.update_available,
            "update_type": self.update_type,
            "has_vulnerability": self.has_vulnerability,
            "advisory_ids": self.advisory_ids,
            "recommendation_ids": self.recommendation_ids,
        }


@dataclass
class SdkScanReport:
    """Aggregate report for one full scan cycle.

    Attributes:
        scan_id: Unique identifier.
        requirements_files_scanned: Number of files processed.
        packages_scanned: Total packages examined.
        updates_available: Packages with a newer version.
        vulnerable_packages: Packages with security findings.
        recommendations_generated: Number of new recommendations created.
        scan_records: Per-package detail.
        scanned_at: UTC timestamp of the scan.
    """

    scan_id: str
    requirements_files_scanned: int
    packages_scanned: int
    updates_available: int
    vulnerable_packages: int
    recommendations_generated: int
    scan_records: List[PackageScanRecord]
    scanned_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "requirements_files_scanned": self.requirements_files_scanned,
            "packages_scanned": self.packages_scanned,
            "updates_available": self.updates_available,
            "vulnerable_packages": self.vulnerable_packages,
            "recommendations_generated": self.recommendations_generated,
            "scan_records": [r.to_dict() for r in self.scan_records],
            "scanned_at": self.scanned_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class SdkUpdateScanner:
    """Proactively scans Murphy System requirements files for SDK updates.

    Design Label: ARCH-007
    Owner: Backend Team

    Extends the raw advisory matching of DependencyAuditEngine with:
    - Multi-file requirements scanning (all requirements*.txt in project root)
    - Known-version registry so the caller can teach the scanner about newer
      versions without needing live network access
    - Update-type classification (patch / minor / major)
    - AUTO_UPDATE recommendations for patch-level safe updates
    - SECURITY recommendations driven by advisory findings

    Usage::

        scanner = SdkUpdateScanner(
            recommendation_engine=rec_engine,
            dependency_audit=dep_audit,
            project_root="/path/to/Murphy-System",
            persistence_manager=pm,
        )
        scanner.register_known_version("requests", "2.32.0")
        report = scanner.run_scan()
    """

    _PERSISTENCE_DOC_KEY = "founder_update_engine_sdk_scanner"

    def __init__(
        self,
        recommendation_engine=None,
        dependency_audit=None,
        event_backbone=None,
        persistence_manager=None,
        project_root: Optional[str] = None,
    ) -> None:
        self._rec_engine = recommendation_engine
        self._dep_audit = dependency_audit
        self._event_backbone = event_backbone
        self._persistence = persistence_manager
        self._project_root = project_root  # resolved lazily

        # name -> latest_known_version string
        self._known_versions: Dict[str, str] = {}
        self._scan_history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

        self._load_state()

    # ------------------------------------------------------------------
    # Known-version registry
    # ------------------------------------------------------------------

    def register_known_version(self, package_name: str, version: str) -> None:
        """Teach the scanner about the latest available version of *package_name*.

        This does not require network access — callers populate this registry
        from any source (PyPI metadata, internal mirrors, manual override).

        Args:
            package_name: Normalised package name (case-insensitive).
            version: Latest known version string (e.g. ``"2.32.0"``).
        """
        with self._lock:
            if len(self._known_versions) >= _MAX_PACKAGES:
                logger.warning("SdkUpdateScanner: known-version registry full (%d)", _MAX_PACKAGES)
                return
            self._known_versions[package_name.lower().strip()] = version.strip()

    def get_known_version(self, package_name: str) -> Optional[str]:
        """Return the registered latest version for *package_name*, or ``None``."""
        with self._lock:
            return self._known_versions.get(package_name.lower().strip())

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    def run_scan(self) -> SdkScanReport:
        """Scan all requirements files and generate update recommendations.

        Steps:
        1. Discover requirements files in the project root.
        2. Parse each file into ``(package_name, current_version)`` pairs.
        3. For each package, check against the known-version registry.
        4. Run the DependencyAuditEngine (if available) to find vulnerabilities.
        5. Classify the update type (patch / minor / major).
        6. Generate recommendations via the RecommendationEngine.

        Returns:
            :class:`SdkScanReport` summarising the scan.
        """
        req_files = self._discover_requirements_files()
        all_packages: List[Tuple[str, str, str]] = []  # (name, version, filepath)

        for filepath in req_files:
            parsed = self._parse_requirements_file(filepath)
            for name, version in parsed:
                all_packages.append((name, version, filepath))

        # Run advisory scan if dep_audit is available
        advisory_map: Dict[str, List[str]] = {}  # package_name -> [advisory_ids]
        if self._dep_audit is not None:
            try:
                # Register all found packages so the audit engine knows about them
                for name, version, _ in all_packages:
                    try:
                        self._dep_audit.register_dependency(name=name, version=version)
                    except Exception:
                        pass
                audit_report = self._dep_audit.run_audit_cycle()
                for finding in audit_report.findings:
                    advisory_map.setdefault(finding.dep_name, []).append(finding.advisory_id)
            except Exception as exc:
                logger.debug("SdkUpdateScanner: dep_audit unavailable: %s", exc)

        scan_records: List[PackageScanRecord] = []
        recs_generated = 0

        for name, current_ver, filepath in all_packages:
            norm_name = name.lower()
            latest = self._known_versions.get(norm_name)
            vuln_advisories = advisory_map.get(norm_name, [])

            update_available = False
            update_type = "none"

            if latest and _parse_ver(latest) > _parse_ver(current_ver):
                update_available = True
                if _is_patch_bump(current_ver, latest):
                    update_type = "patch"
                elif _is_minor_bump(current_ver, latest):
                    update_type = "minor"
                else:
                    update_type = "major"

            record = PackageScanRecord(
                name=norm_name,
                current_version=current_ver,
                latest_known_version=latest or current_ver,
                requirements_file=filepath,
                update_available=update_available,
                update_type=update_type,
                has_vulnerability=bool(vuln_advisories),
                advisory_ids=vuln_advisories,
            )

            if self._rec_engine is not None:
                new_recs = self._generate_package_recommendations(record)
                record.recommendation_ids = [r.id for r in new_recs]
                recs_generated += len(new_recs)

            scan_records.append(record)

        report = SdkScanReport(
            scan_id=f"sdk-{uuid.uuid4().hex[:8]}",
            requirements_files_scanned=len(req_files),
            packages_scanned=len(all_packages),
            updates_available=sum(1 for r in scan_records if r.update_available),
            vulnerable_packages=sum(1 for r in scan_records if r.has_vulnerability),
            recommendations_generated=recs_generated,
            scan_records=scan_records,
            scanned_at=datetime.now(timezone.utc),
        )

        with self._lock:
            if len(self._scan_history) >= _MAX_SCAN_HISTORY:
                self._scan_history = self._scan_history[-(_MAX_SCAN_HISTORY - 1):]
            self._scan_history.append(report.to_dict())

        self._save_state()
        self._publish_event(report)

        logger.info(
            "SdkUpdateScanner: scanned %d packages across %d files → "
            "%d updates, %d vulnerabilities, %d recs",
            report.packages_scanned,
            report.requirements_files_scanned,
            report.updates_available,
            report.vulnerable_packages,
            report.recommendations_generated,
        )
        return report

    def get_scan_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return the most recent scan reports (newest first).

        Args:
            limit: Maximum number of reports to return.

        Returns:
            List of scan report dicts.
        """
        with self._lock:
            return list(reversed(self._scan_history[-limit:]))

    def get_status(self) -> Dict[str, Any]:
        """Return summary statistics for the scanner."""
        with self._lock:
            total_scans = len(self._scan_history)
            last_scan = self._scan_history[-1] if self._scan_history else None
            known_count = len(self._known_versions)
        return {
            "total_scans": total_scans,
            "known_versions_registered": known_count,
            "last_scan": last_scan,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _discover_requirements_files(self) -> List[str]:
        """Find all requirements*.txt files in the project root."""
        root = self._resolve_project_root()
        if root is None:
            return []
        result: List[str] = []
        for path in sorted(Path(root).glob("requirements*.txt")):
            result.append(str(path))
        return result

    def _parse_requirements_file(self, filepath: str) -> List[Tuple[str, str]]:
        """Parse a requirements file into (package_name, version) pairs.

        Only lines with an explicit version specifier are returned; bare
        package names without versions are skipped.

        Args:
            filepath: Absolute path to the requirements file.

        Returns:
            List of ``(name, version)`` tuples.
        """
        results: List[Tuple[str, str]] = []
        try:
            text = Path(filepath).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.debug("SdkUpdateScanner: cannot read %s: %s", filepath, exc)
            return results

        for raw_line in text.splitlines():
            line = raw_line.strip()
            # Strip inline comments
            if "#" in line:
                line = line[: line.index("#")].strip()
            if not line or line.startswith(("-", "http")):
                continue
            m = _REQ_LINE_RE.match(line)
            if not m:
                continue
            pkg_raw = m.group(1)
            # Strip extras like [standard]
            pkg_name = re.sub(r"\[.*?\]", "", pkg_raw).strip().lower()
            spec = (m.group(2) or "").strip()
            if not spec:
                continue
            # Extract the first numeric version from the specifier
            ver_match = re.search(r"(\d+(?:\.\d+)*)", spec)
            if ver_match:
                results.append((pkg_name, ver_match.group(1)))

        return results

    def _generate_package_recommendations(
        self, record: PackageScanRecord
    ) -> list:
        """Generate appropriate recommendations for *record*.

        Returns:
            List of :class:`~recommendation_engine.Recommendation` objects.
        """
        from .recommendation_engine import (
            RecommendationType,
            RecommendationPriority,
            Recommendation,
        )

        recs = []

        # Security recommendation — highest priority
        if record.has_vulnerability:
            rec = self._rec_engine._make_recommendation(
                subsystem=record.name,
                rec_type=RecommendationType.SECURITY,
                priority=RecommendationPriority.HIGH,
                title=f"Security: update {record.name} from {record.current_version}",
                description=(
                    f"{record.name} {record.current_version} has known vulnerabilities "
                    f"({', '.join(record.advisory_ids)}). "
                    f"Latest known version: {record.latest_known_version}."
                ),
                rationale=f"Security advisories: {', '.join(record.advisory_ids)}",
                actions=[
                    {
                        "action": "update_package",
                        "package": record.name,
                        "from_version": record.current_version,
                        "to_version": record.latest_known_version,
                        "requirements_file": record.requirements_file,
                    }
                ],
                impact={"risk": "high", "effort": "low", "benefit": "security"},
                auto_applicable=False,
                requires_founder_approval=True,
                source={
                    "engine": "SdkUpdateScanner",
                    "advisory_ids": record.advisory_ids,
                    "requirements_file": record.requirements_file,
                },
            )
            recs.append(rec)

        # SDK update recommendation — any version bump
        if record.update_available and not record.has_vulnerability:
            priority = {
                "patch": RecommendationPriority.LOW,
                "minor": RecommendationPriority.MEDIUM,
                "major": RecommendationPriority.HIGH,
            }.get(record.update_type, RecommendationPriority.LOW)

            rec = self._rec_engine._make_recommendation(
                subsystem=record.name,
                rec_type=RecommendationType.SDK_UPDATE,
                priority=priority,
                title=f"SDK update: {record.name} {record.current_version} → {record.latest_known_version}",
                description=(
                    f"{record.name} can be updated from {record.current_version} to "
                    f"{record.latest_known_version} ({record.update_type}-level change)."
                ),
                rationale=f"Newer version available ({record.update_type} bump).",
                actions=[
                    {
                        "action": "update_package",
                        "package": record.name,
                        "from_version": record.current_version,
                        "to_version": record.latest_known_version,
                        "requirements_file": record.requirements_file,
                    }
                ],
                impact={
                    "risk": record.update_type,
                    "effort": "low",
                    "benefit": "maintenance",
                },
                auto_applicable=record.update_type == "patch",
                requires_founder_approval=record.update_type == "major",
                source={
                    "engine": "SdkUpdateScanner",
                    "update_type": record.update_type,
                    "requirements_file": record.requirements_file,
                },
            )
            recs.append(rec)

        # Auto-update recommendation — patch bumps only
        if record.update_available and record.update_type == "patch":
            rec = self._rec_engine._make_recommendation(
                subsystem=record.name,
                rec_type=RecommendationType.AUTO_UPDATE,
                priority=RecommendationPriority.LOW,
                title=f"Auto-update eligible: {record.name} {record.current_version} → {record.latest_known_version}",
                description=(
                    f"{record.name} patch update ({record.current_version} → "
                    f"{record.latest_known_version}) is safe to auto-apply."
                ),
                rationale="Patch-level updates are backwards-compatible by semver convention.",
                actions=[
                    {
                        "action": "auto_update_package",
                        "package": record.name,
                        "from_version": record.current_version,
                        "to_version": record.latest_known_version,
                        "requirements_file": record.requirements_file,
                    }
                ],
                impact={"risk": "low", "effort": "none", "benefit": "maintenance"},
                auto_applicable=True,
                requires_founder_approval=False,
                source={
                    "engine": "SdkUpdateScanner",
                    "update_type": "patch",
                    "requirements_file": record.requirements_file,
                },
            )
            recs.append(rec)

        # Store generated recs in the engine
        if recs and self._rec_engine is not None:
            import threading as _threading
            with self._rec_engine._lock:
                for r in recs:
                    self._rec_engine._recommendations[r.id] = r

        return recs

    def _resolve_project_root(self) -> Optional[str]:
        """Walk up from this file to find the project root (contains requirements*.txt)."""
        if self._project_root is not None:
            return self._project_root if Path(self._project_root).is_dir() else None
        here = Path(__file__).resolve()
        for candidate in [here.parent.parent.parent, here.parent.parent]:
            if list(candidate.glob("requirements*.txt")):
                return str(candidate)
        return None

    def _save_state(self) -> None:
        if self._persistence is None:
            return
        try:
            with self._lock:
                data = {
                    "known_versions": dict(self._known_versions),
                    "scan_history": list(self._scan_history),
                }
            self._persistence.save_document(self._PERSISTENCE_DOC_KEY, data)
        except Exception as exc:
            logger.debug("SdkUpdateScanner: failed to save state: %s", exc)

    def _load_state(self) -> None:
        if self._persistence is None:
            return
        try:
            data = self._persistence.load_document(self._PERSISTENCE_DOC_KEY)
            if data:
                with self._lock:
                    self._known_versions = dict(data.get("known_versions", {}))
                    self._scan_history = list(data.get("scan_history", []))
        except Exception as exc:
            logger.debug("SdkUpdateScanner: failed to load state: %s", exc)

    def _publish_event(self, report: SdkScanReport) -> None:
        if self._event_backbone is None:
            return
        try:
            from event_backbone import EventType  # type: ignore

            self._event_backbone.publish(
                EventType.SYSTEM_HEALTH,
                {
                    "source": "SdkUpdateScanner",
                    "scan_id": report.scan_id,
                    "updates_available": report.updates_available,
                    "vulnerable_packages": report.vulnerable_packages,
                    "recommendations_generated": report.recommendations_generated,
                },
            )
        except Exception as exc:
            logger.debug("SdkUpdateScanner: event publish failed: %s", exc)

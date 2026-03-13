"""
Dependency Audit Engine for Murphy System.

Design Label: DEV-005 — Automated Dependency Security Auditing & Update Tracking
Owner: QA Team / Platform Engineering
Dependencies:
  - PersistenceManager (for durable audit history)
  - EventBackbone (publishes LEARNING_FEEDBACK on audit cycles)
  - SelfImprovementEngine (ARCH-001, optional, for remediation proposals)

Implements Phase 2 — Development Automation (continued):
  Tracks project dependencies, detects known security vulnerabilities
  via configurable advisory feeds, identifies outdated packages, and
  generates remediation proposals that can be injected into the
  SelfImprovementEngine pipeline.

Flow:
  1. Register project dependencies (name, version, ecosystem)
  2. Ingest vulnerability advisories (CVE/advisory data)
  3. Run audit cycle: match advisories against registered deps
  4. Classify findings by severity (critical/high/medium/low)
  5. Generate remediation proposals for affected dependencies
  6. Persist audit reports and publish LEARNING_FEEDBACK events

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Read-only analysis: never modifies actual dependency files
  - Bounded: configurable max dependencies and advisories
  - Conservative: flags any version overlap as potentially affected
  - Audit trail: every audit cycle is logged

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
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_DEPENDENCIES = 10_000
_MAX_ADVISORIES = 50_000
_MAX_REPORTS = 1_000


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Dependency:
    """A registered project dependency."""
    dep_id: str
    name: str
    version: str
    ecosystem: str = "pip"          # pip | npm | go | cargo | …
    direct: bool = True
    locked: bool = False
    registered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dep_id": self.dep_id,
            "name": self.name,
            "version": self.version,
            "ecosystem": self.ecosystem,
            "direct": self.direct,
            "locked": self.locked,
            "registered_at": self.registered_at,
        }


@dataclass
class Advisory:
    """A vulnerability advisory record."""
    advisory_id: str
    cve_id: str
    package_name: str
    affected_versions: str          # semver range string, e.g. ">=1.0,<1.5"
    severity: str = "medium"        # critical | high | medium | low
    title: str = ""
    description: str = ""
    fixed_version: str = ""
    published_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "advisory_id": self.advisory_id,
            "cve_id": self.cve_id,
            "package_name": self.package_name,
            "affected_versions": self.affected_versions,
            "severity": self.severity,
            "title": self.title,
            "description": self.description[:500],
            "fixed_version": self.fixed_version,
            "published_at": self.published_at,
        }


@dataclass
class AuditFinding:
    """A single dependency-audit finding."""
    finding_id: str
    dep_id: str
    dep_name: str
    dep_version: str
    advisory_id: str
    cve_id: str
    severity: str
    title: str
    fixed_version: str = ""
    found_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "dep_id": self.dep_id,
            "dep_name": self.dep_name,
            "dep_version": self.dep_version,
            "advisory_id": self.advisory_id,
            "cve_id": self.cve_id,
            "severity": self.severity,
            "title": self.title,
            "fixed_version": self.fixed_version,
            "found_at": self.found_at,
        }


@dataclass
class DependencyAuditReport:
    """Summary of an audit cycle."""
    report_id: str
    dependencies_scanned: int
    advisories_checked: int
    total_findings: int
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    findings: List[AuditFinding] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "dependencies_scanned": self.dependencies_scanned,
            "advisories_checked": self.advisories_checked,
            "total_findings": self.total_findings,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "findings": [f.to_dict() for f in self.findings],
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# Lightweight semver helpers (stdlib only)
# ---------------------------------------------------------------------------

_VER_RE = re.compile(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?")


def _parse_ver(v: str):
    m = _VER_RE.match(v.strip())
    if not m:
        return (0, 0, 0)
    return tuple(int(x) if x else 0 for x in m.groups())


def _in_range(version: str, spec: str) -> bool:
    """Very simple range check: supports >=X,<Y and ==X and *."""
    if spec.strip() in ("*", ""):
        return True
    ver = _parse_ver(version)
    for part in spec.split(","):
        part = part.strip()
        if part.startswith(">="):
            if ver < _parse_ver(part[2:]):
                return False
        elif part.startswith(">"):
            if ver <= _parse_ver(part[1:]):
                return False
        elif part.startswith("<="):
            if ver > _parse_ver(part[2:]):
                return False
        elif part.startswith("<"):
            if ver >= _parse_ver(part[1:]):
                return False
        elif part.startswith("=="):
            if ver != _parse_ver(part[2:]):
                return False
        elif part.startswith("!="):
            if ver == _parse_ver(part[2:]):
                return False
    return True


# ---------------------------------------------------------------------------
# DependencyAuditEngine
# ---------------------------------------------------------------------------

class DependencyAuditEngine:
    """Automated dependency security auditing and update tracking.

    Design Label: DEV-005
    Owner: QA Team / Platform Engineering

    Usage::

        engine = DependencyAuditEngine(persistence_manager=pm, event_backbone=bb)
        engine.register_dependency("requests", "2.28.0")
        engine.ingest_advisory("CVE-2023-0001", "requests", ">=2.0,<2.29", severity="high")
        report = engine.run_audit_cycle()
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        improvement_engine=None,
        max_dependencies: int = _MAX_DEPENDENCIES,
        max_advisories: int = _MAX_ADVISORIES,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._improvement = improvement_engine
        self._deps: Dict[str, Dependency] = {}
        self._advisories: List[Advisory] = []
        self._reports: List[DependencyAuditReport] = []
        self._max_deps = max_dependencies
        self._max_advisories = max_advisories

    # ------------------------------------------------------------------
    # Dependency management
    # ------------------------------------------------------------------

    def register_dependency(
        self,
        name: str,
        version: str,
        ecosystem: str = "pip",
        direct: bool = True,
    ) -> Dependency:
        """Register a project dependency."""
        dep = Dependency(
            dep_id=f"dep-{uuid.uuid4().hex[:8]}",
            name=name.lower().strip(),
            version=version.strip(),
            ecosystem=ecosystem,
            direct=direct,
        )
        with self._lock:
            if len(self._deps) >= self._max_deps:
                logger.warning("Max dependencies reached (%d)", self._max_deps)
                return dep
            self._deps[dep.dep_id] = dep
        logger.info("Registered dependency %s==%s (%s)", name, version, dep.dep_id)
        return dep

    def remove_dependency(self, dep_id: str) -> bool:
        with self._lock:
            return self._deps.pop(dep_id, None) is not None

    # ------------------------------------------------------------------
    # Advisory ingestion
    # ------------------------------------------------------------------

    def ingest_advisory(
        self,
        cve_id: str,
        package_name: str,
        affected_versions: str,
        severity: str = "medium",
        title: str = "",
        description: str = "",
        fixed_version: str = "",
    ) -> Advisory:
        """Ingest a vulnerability advisory."""
        adv = Advisory(
            advisory_id=f"adv-{uuid.uuid4().hex[:8]}",
            cve_id=cve_id,
            package_name=package_name.lower().strip(),
            affected_versions=affected_versions,
            severity=severity,
            title=title or cve_id,
            description=description,
            fixed_version=fixed_version,
        )
        with self._lock:
            if len(self._advisories) >= self._max_advisories:
                evict = max(1, self._max_advisories // 10)
                self._advisories = self._advisories[evict:]
            self._advisories.append(adv)
        return adv

    # ------------------------------------------------------------------
    # Audit cycle
    # ------------------------------------------------------------------

    def run_audit_cycle(self) -> DependencyAuditReport:
        """Match advisories against registered dependencies."""
        with self._lock:
            deps = list(self._deps.values())
            advisories = list(self._advisories)

        findings: List[AuditFinding] = []
        for dep in deps:
            for adv in advisories:
                if adv.package_name != dep.name:
                    continue
                if not _in_range(dep.version, adv.affected_versions):
                    continue
                findings.append(AuditFinding(
                    finding_id=f"daf-{uuid.uuid4().hex[:8]}",
                    dep_id=dep.dep_id,
                    dep_name=dep.name,
                    dep_version=dep.version,
                    advisory_id=adv.advisory_id,
                    cve_id=adv.cve_id,
                    severity=adv.severity,
                    title=adv.title,
                    fixed_version=adv.fixed_version,
                ))

        report = DependencyAuditReport(
            report_id=f"dar-{uuid.uuid4().hex[:8]}",
            dependencies_scanned=len(deps),
            advisories_checked=len(advisories),
            total_findings=len(findings),
            critical_count=sum(1 for f in findings if f.severity == "critical"),
            high_count=sum(1 for f in findings if f.severity == "high"),
            medium_count=sum(1 for f in findings if f.severity == "medium"),
            low_count=sum(1 for f in findings if f.severity == "low"),
            findings=findings,
        )

        with self._lock:
            if len(self._reports) >= _MAX_REPORTS:
                self._reports = self._reports[_MAX_REPORTS // 10:]
            self._reports.append(report)

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=report.report_id, document=report.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        # Publish event
        if self._backbone is not None:
            self._publish_event(report)

        logger.info(
            "Dependency audit: %d deps, %d advisories → %d findings (C=%d H=%d M=%d L=%d)",
            report.dependencies_scanned, report.advisories_checked,
            report.total_findings, report.critical_count, report.high_count,
            report.medium_count, report.low_count,
        )
        return report

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list_dependencies(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            deps = list(self._deps.values())
        return [d.to_dict() for d in deps[:limit]]

    def get_reports(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            reports = list(self._reports)
        return [r.to_dict() for r in reports[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_dependencies": len(self._deps),
                "total_advisories": len(self._advisories),
                "total_reports": len(self._reports),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_event(self, report: DependencyAuditReport) -> None:
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.LEARNING_FEEDBACK,
                payload={
                    "source": "dependency_audit_engine",
                    "action": "audit_cycle_complete",
                    "report_id": report.report_id,
                    "total_findings": report.total_findings,
                    "critical_count": report.critical_count,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="dependency_audit_engine",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)

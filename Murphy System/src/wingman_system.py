# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Wingman System for Murphy System Runtime

Validates *anything* that is created by Murphy System.  The validation
library is always internal — it is never serialised or exposed through
any external API surface.

Architecture
------------

World Model Calibration Sensors
    Six sensors observe a single artifact from independent angles:

    VisibilitySensor      — can the artifact be seen / read at all?
    StructureSensor       — does it carry the expected structural markers?
    ContentDensitySensor  — is the information density adequate?
    SemanticCoherenceSensor — is the content internally consistent?
    ComplianceSensor      — are branding / licence notices present?
    TemporalSensor        — is there a valid timestamp and is it fresh?

    Each sensor produces a SensorReading with a normalised value (0–1)
    and a status: "ok" | "warn" | "alert".

WorldModelCalibrator
    Runs all registered sensors against an artifact and aggregates the
    readings into a WorldModelSnapshot.

ValidationTrigger
    Inspects the snapshot and decides which severity level to activate:
      ALERT on any sensor  →  BLOCK-level validation rules fire
      WARN on any sensor   →  WARN-level rules fire
      All OK               →  INFO-level rules fire

WingmanValidationModule
    One module is created per registered domain (deliverable, workflow,
    compliance, hr, finance, invoice, …).  Each module holds:
      - its own WorldModelCalibrator
      - a runbook built from trigger-selected rules plus any custom rules
      - a validate() method that runs calibration → trigger → rules

WingmanSystem
    Top-level entry point.  The _internal_library dict is intentionally
    private and is never included in any serialised output.

    register_module()   — creates a WingmanValidationModule and writes a
                          knowledge entry to the Librarian.
    validate()          — runs the module's validator, then logs the
                          result back to the Librarian so that validation
                          history accumulates in the knowledge layers.
    get_status()        — returns aggregate counts only; the library
                          itself is not exposed.
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sensor output types
# ---------------------------------------------------------------------------

class SensorStatus:
    OK    = "ok"
    WARN  = "warn"
    ALERT = "alert"


@dataclass
class SensorReading:
    """Output from a single world-model calibration sensor."""
    sensor_id: str
    dimension: str          # human label, e.g. "visibility"
    value: float            # normalised 0.0 – 1.0 (higher = healthier)
    status: str             # SensorStatus constant
    detail: str             # human-readable finding


@dataclass
class WorldModelSnapshot:
    """Aggregated sensor readings for one artifact."""
    artifact_id: str
    readings: List[SensorReading] = field(default_factory=list)
    captured_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def overall_status(self) -> str:
        """Worst sensor status across all readings."""
        statuses = [r.status for r in self.readings]
        if SensorStatus.ALERT in statuses:
            return SensorStatus.ALERT
        if SensorStatus.WARN in statuses:
            return SensorStatus.WARN
        return SensorStatus.OK

    def sensor(self, sensor_id: str) -> Optional[SensorReading]:
        return next((r for r in self.readings if r.sensor_id == sensor_id), None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "overall_status": self.overall_status,
            "readings": [
                {
                    "sensor_id": r.sensor_id,
                    "dimension": r.dimension,
                    "value": r.value,
                    "status": r.status,
                    "detail": r.detail,
                }
                for r in self.readings
            ],
            "captured_at": self.captured_at,
        }


# ---------------------------------------------------------------------------
# World Model Calibration Sensors
# ---------------------------------------------------------------------------

class VisibilitySensor:
    """Can the artifact be seen / read at all?

    Checks that the primary content field is non-empty and long enough to
    carry meaningful information.  Very short or absent content is the
    most fundamental failure — the wingman cannot validate what it cannot see.
    """
    SENSOR_ID = "visibility"
    MIN_VISIBLE_CHARS = 50

    def read(self, artifact: Dict[str, Any]) -> SensorReading:
        content = artifact.get("content") or artifact.get("result") or ""
        length = len(str(content).strip())
        if length == 0:
            return SensorReading(
                sensor_id=self.SENSOR_ID, dimension="visibility",
                value=0.0, status=SensorStatus.ALERT,
                detail="Artifact has no visible content.",
            )
        if length < self.MIN_VISIBLE_CHARS:
            return SensorReading(
                sensor_id=self.SENSOR_ID, dimension="visibility",
                value=round(length / self.MIN_VISIBLE_CHARS, 2),
                status=SensorStatus.WARN,
                detail=f"Content is very short ({length} chars); minimum visibility threshold is {self.MIN_VISIBLE_CHARS}.",
            )
        return SensorReading(
            sensor_id=self.SENSOR_ID, dimension="visibility",
            value=1.0, status=SensorStatus.OK,
            detail=f"Content visible ({length} chars).",
        )


class StructureSensor:
    """Does the artifact carry the expected structural markers?

    Checks for the presence of section delimiters or headings that indicate
    the output was actually structured rather than raw/incomplete.
    """
    SENSOR_ID = "structure"
    # At least one of these patterns must appear for structure to be "ok"
    STRUCTURE_PATTERNS = [
        r"^■\s",         # Murphy section bullet
        r"^═+$",         # Murphy separator bar
        r"^SECTION\s",   # Explicit section heading
        r"^─+$",         # Thin rule
        r"\n■\s",        # Murphy section bullet in body
        r"\n═",          # Separator in body
    ]

    def read(self, artifact: Dict[str, Any]) -> SensorReading:
        content = str(artifact.get("content") or artifact.get("result") or "")
        found = sum(
            1 for pattern in self.STRUCTURE_PATTERNS
            if re.search(pattern, content, re.MULTILINE)
        )
        if found == 0:
            return SensorReading(
                sensor_id=self.SENSOR_ID, dimension="structure",
                value=0.0, status=SensorStatus.WARN,
                detail="No structural markers detected; output may be unformatted.",
            )
        score = min(1.0, found / 3)
        return SensorReading(
            sensor_id=self.SENSOR_ID, dimension="structure",
            value=round(score, 2), status=SensorStatus.OK,
            detail=f"{found} structural marker(s) found.",
        )


class ContentDensitySensor:
    """Is the information density adequate?

    A deliverable with too few words or sentences is likely a placeholder
    or truncated output.
    """
    SENSOR_ID = "content_density"
    MIN_WORDS = 30
    GOOD_WORDS = 150

    def read(self, artifact: Dict[str, Any]) -> SensorReading:
        content = str(artifact.get("content") or artifact.get("result") or "")
        word_count = len(content.split())
        if word_count < self.MIN_WORDS:
            return SensorReading(
                sensor_id=self.SENSOR_ID, dimension="content_density",
                value=round(word_count / self.MIN_WORDS, 2),
                status=SensorStatus.ALERT,
                detail=f"Only {word_count} words; minimum for meaningful content is {self.MIN_WORDS}.",
            )
        if word_count < self.GOOD_WORDS:
            return SensorReading(
                sensor_id=self.SENSOR_ID, dimension="content_density",
                value=round(word_count / self.GOOD_WORDS, 2),
                status=SensorStatus.WARN,
                detail=f"{word_count} words; content may be sparse (good threshold: {self.GOOD_WORDS}).",
            )
        return SensorReading(
            sensor_id=self.SENSOR_ID, dimension="content_density",
            value=1.0, status=SensorStatus.OK,
            detail=f"{word_count} words; density is adequate.",
        )


class SemanticCoherenceSensor:
    """Is the content internally consistent?

    Detects degenerate outputs such as all-whitespace, repeated-character
    runs that indicate a generation failure, or truncation markers.
    """
    SENSOR_ID = "semantic_coherence"
    # Patterns that strongly suggest broken / truncated output
    DEGENERATE_PATTERNS = [
        r"([a-zA-Z0-9])\1{20,}",            # 20+ repeated alphanumeric chars (not box-drawing)
        r"\[TRUNCATED\]",
        r"\[ERROR\]",
        r"\.\.\.\s*$",                       # ends with ellipsis
        r"<PLACEHOLDER>",
    ]
    TRUNCATION_HINT = r"\[Local Medium Model\] Analyzing request:"  # LLM log leak

    def read(self, artifact: Dict[str, Any]) -> SensorReading:
        content = str(artifact.get("content") or artifact.get("result") or "")
        stripped = content.strip()
        if not stripped:
            return SensorReading(
                sensor_id=self.SENSOR_ID, dimension="semantic_coherence",
                value=0.0, status=SensorStatus.ALERT,
                detail="Content is empty after stripping whitespace.",
            )
        for pattern in self.DEGENERATE_PATTERNS:
            if re.search(pattern, stripped):
                return SensorReading(
                    sensor_id=self.SENSOR_ID, dimension="semantic_coherence",
                    value=0.1, status=SensorStatus.ALERT,
                    detail=f"Degenerate content pattern detected: {pattern!r}",
                )
        if re.search(self.TRUNCATION_HINT, stripped):
            return SensorReading(
                sensor_id=self.SENSOR_ID, dimension="semantic_coherence",
                value=0.4, status=SensorStatus.WARN,
                detail="LLM processing note leaked into content; generation may be incomplete.",
            )
        return SensorReading(
            sensor_id=self.SENSOR_ID, dimension="semantic_coherence",
            value=1.0, status=SensorStatus.OK,
            detail="No degenerate patterns detected.",
        )


class ComplianceSensor:
    """Are the required branding and licence notices present?

    Murphy deliverables must always carry the BSL / Apache notice and the
    murphy.systems attribution.  Missing either indicates the content was
    tampered with or generation was incomplete.
    """
    SENSOR_ID = "compliance"
    REQUIRED_MARKERS: List[Tuple[str, str]] = [
        ("murphy.systems", "murphy.systems attribution"),
        ("Inoni", "Inoni LLC attribution"),
        ("Apache License", "Apache Licence notice"),
        ("BSL", "BSL 1.1 reference"),
    ]

    def read(self, artifact: Dict[str, Any]) -> SensorReading:
        content = str(artifact.get("content") or artifact.get("result") or "")
        missing = [
            label
            for marker, label in self.REQUIRED_MARKERS
            if marker not in content
        ]
        if not missing:
            return SensorReading(
                sensor_id=self.SENSOR_ID, dimension="compliance",
                value=1.0, status=SensorStatus.OK,
                detail="All required compliance markers present.",
            )
        ratio_present = (len(self.REQUIRED_MARKERS) - len(missing)) / len(self.REQUIRED_MARKERS)
        status = SensorStatus.ALERT if len(missing) >= 2 else SensorStatus.WARN
        return SensorReading(
            sensor_id=self.SENSOR_ID, dimension="compliance",
            value=round(ratio_present, 2), status=status,
            detail=f"Missing compliance markers: {', '.join(missing)}.",
        )


class TemporalSensor:
    """Is there a valid timestamp and is the content temporally grounded?

    Checks for a generated-at timestamp in the artifact metadata.  A missing
    timestamp does not block delivery but is worth noting.
    """
    SENSOR_ID = "temporal"
    TIMESTAMP_PATTERNS = [
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC",   # ISO-like with UTC
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",        # ISO 8601
        r"Generated:\s+\d{4}",
    ]

    def read(self, artifact: Dict[str, Any]) -> SensorReading:
        # Check metadata field first
        generated_at = artifact.get("generated_at") or artifact.get("timestamp")
        content = str(artifact.get("content") or artifact.get("result") or "")
        if generated_at:
            return SensorReading(
                sensor_id=self.SENSOR_ID, dimension="temporal",
                value=1.0, status=SensorStatus.OK,
                detail=f"Timestamp present in metadata: {generated_at}",
            )
        for pattern in self.TIMESTAMP_PATTERNS:
            if re.search(pattern, content):
                return SensorReading(
                    sensor_id=self.SENSOR_ID, dimension="temporal",
                    value=0.8, status=SensorStatus.OK,
                    detail="Timestamp found in artifact content.",
                )
        return SensorReading(
            sensor_id=self.SENSOR_ID, dimension="temporal",
            value=0.5, status=SensorStatus.WARN,
            detail="No timestamp found; content may not be temporally grounded.",
        )


# ---------------------------------------------------------------------------
# World Model Calibrator
# ---------------------------------------------------------------------------

class WorldModelCalibrator:
    """Runs all six sensors against an artifact and returns a WorldModelSnapshot.

    Additional sensors can be registered at runtime via add_sensor().
    """

    def __init__(self) -> None:
        self._sensors: List[Any] = [
            VisibilitySensor(),
            StructureSensor(),
            ContentDensitySensor(),
            SemanticCoherenceSensor(),
            ComplianceSensor(),
            TemporalSensor(),
        ]

    def add_sensor(self, sensor: Any) -> None:
        """Register an additional calibration sensor."""
        self._sensors.append(sensor)

    def calibrate(self, artifact: Dict[str, Any]) -> WorldModelSnapshot:
        """Run all sensors and return a WorldModelSnapshot."""
        artifact_id = artifact.get("id") or artifact.get("artifact_id") or str(uuid.uuid4())[:8]
        snapshot = WorldModelSnapshot(artifact_id=artifact_id)
        for sensor in self._sensors:
            try:
                reading = sensor.read(artifact)
                snapshot.readings.append(reading)
            except Exception as exc:
                logger.debug("Sensor %s failed: %s", getattr(sensor, "SENSOR_ID", "?"), exc)
                snapshot.readings.append(SensorReading(
                    sensor_id=getattr(sensor, "SENSOR_ID", "unknown"),
                    dimension="unknown",
                    value=0.0,
                    status=SensorStatus.WARN,
                    detail=f"Sensor error: {exc}",
                ))
        logger.debug(
            "WorldModelCalibrator: artifact=%s overall=%s readings=%d",
            artifact_id, snapshot.overall_status, len(snapshot.readings),
        )
        return snapshot


# ---------------------------------------------------------------------------
# Validation Trigger
# ---------------------------------------------------------------------------

class ValidationTrigger:
    """Maps world-model sensor status to the severity level that should be run.

    Rules:
        Any ALERT sensor  →  fire BLOCK rules (most restrictive)
        Any WARN sensor   →  fire WARN rules
        All OK            →  fire INFO rules (lightest touch)

    The trigger does not select specific rules — that is the runbook's job.
    It informs the WingmanValidationModule which severity tier to treat as
    the active enforcement level for this run.
    """

    @staticmethod
    def decide(snapshot: WorldModelSnapshot) -> str:
        """Return "block", "warn", or "info" based on the snapshot."""
        overall = snapshot.overall_status
        if overall == SensorStatus.ALERT:
            return "block"
        if overall == SensorStatus.WARN:
            return "warn"
        return "info"

    @staticmethod
    def triggered_sensors(snapshot: WorldModelSnapshot, level: str) -> List[str]:
        """Return the sensor IDs that triggered at or above the given level."""
        thresholds = {"block": [SensorStatus.ALERT], "warn": [SensorStatus.ALERT, SensorStatus.WARN]}
        watch = thresholds.get(level, [])
        return [r.sensor_id for r in snapshot.readings if r.status in watch]


# ---------------------------------------------------------------------------
# Validation result types (module-level)
# ---------------------------------------------------------------------------

@dataclass
class ModuleValidationResult:
    """The result of running a WingmanValidationModule against one artifact."""
    module_id: str
    artifact_id: str
    approved: bool
    trigger_level: str              # "block" | "warn" | "info"
    triggered_sensors: List[str]    # sensor IDs that fired
    snapshot: WorldModelSnapshot
    findings: List[Dict[str, Any]]  # per-sensor findings surfaced as issues
    validated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "artifact_id": self.artifact_id,
            "approved": self.approved,
            "trigger_level": self.trigger_level,
            "triggered_sensors": self.triggered_sensors,
            "findings": self.findings,
            "snapshot": self.snapshot.to_dict(),
            "validated_at": self.validated_at,
        }


# ---------------------------------------------------------------------------
# Per-module Validator
# ---------------------------------------------------------------------------

class WingmanValidationModule:
    """Validates artifacts for one registered domain / module.

    Built by WingmanSystem.register_module().  Each instance holds:
      - a WorldModelCalibrator (sensors)
      - a ValidationTrigger
      - custom severity-mapped rules supplied at registration time

    The internal structure is intentionally not exposed outside this class.
    """

    def __init__(
        self,
        module_id: str,
        domain: str,
        custom_rules: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.module_id = module_id
        self.domain = domain
        # Custom rules keyed by severity: {"block": [...], "warn": [...], "info": [...]}
        self._rules: Dict[str, List[str]] = {"block": [], "warn": [], "info": []}
        for rule in (custom_rules or []):
            level = rule.get("severity", "warn")
            desc = rule.get("description", rule.get("rule_id", ""))
            if level in self._rules:
                self._rules[level].append(desc)
        self._calibrator = WorldModelCalibrator()
        self._trigger = ValidationTrigger()
        self._history: List[ModuleValidationResult] = []
        self._lock = threading.Lock()

    def validate(self, artifact: Dict[str, Any]) -> ModuleValidationResult:
        """Calibrate the artifact, activate the trigger, run domain rules."""
        snapshot = self._calibrator.calibrate(artifact)
        level = self._trigger.decide(snapshot)
        triggered = self._trigger.triggered_sensors(snapshot, level)

        # Build findings from readings that are not OK
        findings: List[Dict[str, Any]] = []
        for reading in snapshot.readings:
            if reading.status != SensorStatus.OK:
                findings.append({
                    "sensor_id": reading.sensor_id,
                    "dimension": reading.dimension,
                    "status": reading.status,
                    "value": reading.value,
                    "detail": reading.detail,
                })
        # Add any custom domain rules for this trigger level
        for rule_desc in self._rules.get(level, []):
            findings.append({
                "sensor_id": "domain_rule",
                "dimension": self.domain,
                "status": level,
                "value": 0.0,
                "detail": rule_desc,
            })

        # Approved if trigger level is not "block"
        approved = (level != "block")

        result = ModuleValidationResult(
            module_id=self.module_id,
            artifact_id=snapshot.artifact_id,
            approved=approved,
            trigger_level=level,
            triggered_sensors=triggered,
            snapshot=snapshot,
            findings=findings,
        )
        with self._lock:
            self._history.append(result)
        logger.info(
            "WingmanValidation module=%s artifact=%s approved=%s level=%s",
            self.module_id, snapshot.artifact_id, approved, level,
        )
        return result

    def history(self) -> List[ModuleValidationResult]:
        with self._lock:
            return list(self._history)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._history)
            approved = sum(1 for r in self._history if r.approved)
        return {
            "module_id": self.module_id,
            "domain": self.domain,
            "total_validations": total,
            "approved": approved,
            "rejected": total - approved,
        }


# ---------------------------------------------------------------------------
# WingmanSystem — top-level entry point
# ---------------------------------------------------------------------------

# Pre-registered domains — each gets a WingmanValidationModule automatically
_DEFAULT_DOMAINS: List[Tuple[str, str]] = [
    ("deliverable", "content_generation"),
    ("workflow",    "automation"),
    ("compliance",  "regulatory"),
    ("hr",          "human_resources"),
    ("finance",     "financial"),
    ("invoice",     "accounts_payable"),
]


class WingmanSystem:
    """Top-level Wingman System.

    Validates anything created by Murphy System.  The _internal_library is
    private and is never included in any serialised or API response.

    All module registrations and validation results are written back to the
    Librarian, building up the validation knowledge layers over time.
    """

    def __init__(self, librarian: Optional[Any] = None) -> None:
        self._librarian = librarian
        self._lock = threading.Lock()
        # Private internal library — never exposed externally
        self._internal_library: Dict[str, WingmanValidationModule] = {}
        self._total_validations: int = 0
        self._total_approved: int = 0

        # Pre-register all default domain modules and inform the librarian
        for module_id, domain in _DEFAULT_DOMAINS:
            self._register_module_internal(module_id, domain, custom_rules=None)

        logger.info(
            "WingmanSystem initialised with %d pre-registered modules",
            len(self._internal_library),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _register_module_internal(
        self,
        module_id: str,
        domain: str,
        custom_rules: Optional[List[Dict[str, Any]]],
    ) -> None:
        """Create and store a validation module; never raises."""
        module = WingmanValidationModule(module_id, domain, custom_rules)
        with self._lock:
            self._internal_library[module_id] = module
        self._write_librarian_registration(module_id, domain, custom_rules or [])

    def _write_librarian_registration(
        self,
        module_id: str,
        domain: str,
        custom_rules: List[Dict[str, Any]],
    ) -> None:
        """Record module registration in the Librarian knowledge layers."""
        if not self._librarian:
            return
        try:
            self._librarian.add_knowledge_entry({
                "category": "wingman_validation",
                "topic": f"Wingman Validation Module: {module_id}",
                "description": (
                    f"WingmanSystem validation module for domain '{domain}'. "
                    f"Uses 6 world-model calibration sensors (visibility, structure, "
                    f"content_density, semantic_coherence, compliance, temporal) and a "
                    f"sensor-driven trigger ({len(custom_rules)} custom rule(s) registered). "
                    f"Validation results are always recorded back to the Librarian."
                ),
                "related_modules": ["wingman_system", module_id],
                "related_functions": ["validate", "register_module", "get_status"],
                "references": ["world_model_calibrator", "validation_trigger", "librarian_layers"],
            })
        except Exception as exc:
            logger.debug("Librarian registration for %s skipped: %s", module_id, exc)

    def _write_librarian_validation_result(
        self,
        result: ModuleValidationResult,
    ) -> None:
        """Record validation outcome in the Librarian knowledge layers."""
        if not self._librarian:
            return
        try:
            status_word = "APPROVED" if result.approved else "REJECTED"
            findings_summary = "; ".join(
                f"{f['sensor_id']}={f['status']}" for f in result.findings[:4]
            ) or "none"
            self._librarian.add_knowledge_entry({
                "category": "wingman_validation_result",
                "topic": (
                    f"Validation {status_word}: {result.module_id} "
                    f"artifact={result.artifact_id}"
                ),
                "description": (
                    f"Wingman validated artifact '{result.artifact_id}' against module "
                    f"'{result.module_id}'. Outcome: {status_word}. "
                    f"Trigger level: {result.trigger_level}. "
                    f"Findings: {findings_summary}. "
                    f"Validated at: {result.validated_at}."
                ),
                "related_modules": ["wingman_system", result.module_id],
                "related_functions": ["validate"],
                "references": [
                    f"artifact:{result.artifact_id}",
                    f"trigger:{result.trigger_level}",
                ],
            })
        except Exception as exc:
            logger.debug("Librarian validation result write skipped: %s", exc)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def register_module(
        self,
        module_id: str,
        domain: str,
        custom_rules: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Register a new validation module for the given domain.

        The module is added to the private internal library and a knowledge
        entry is written to the Librarian.  If a module with the same id
        already exists it is replaced.
        """
        self._register_module_internal(module_id, domain, custom_rules or [])
        logger.info("WingmanSystem: registered module '%s' (domain=%s)", module_id, domain)

    def validate(
        self,
        artifact: Dict[str, Any],
        module_id: str = "deliverable",
    ) -> ModuleValidationResult:
        """Validate an artifact through the named module.

        Calibrates world-model sensors → activates trigger → runs rules →
        writes result back to Librarian.  Falls back to the "deliverable"
        module if the named module is not registered.

        Always returns a ModuleValidationResult — never raises.
        """
        with self._lock:
            module = (
                self._internal_library.get(module_id)
                or self._internal_library.get("deliverable")
            )

        if module is None:
            # Absolute fallback: ad-hoc module
            module = WingmanValidationModule(module_id, "general")

        try:
            result = module.validate(artifact)
        except Exception as exc:
            logger.warning("WingmanSystem.validate error: %s", exc)
            # Return a minimal rejected result so callers always get something
            from dataclasses import asdict  # noqa: PLC0415
            snap = WorldModelSnapshot(artifact_id="error")
            result = ModuleValidationResult(
                module_id=module_id,
                artifact_id="error",
                approved=False,
                trigger_level="block",
                triggered_sensors=[],
                snapshot=snap,
                findings=[{"sensor_id": "system", "dimension": "error",
                           "status": SensorStatus.ALERT, "value": 0.0,
                           "detail": str(exc)}],
            )

        with self._lock:
            self._total_validations += 1
            if result.approved:
                self._total_approved += 1

        self._write_librarian_validation_result(result)
        return result

    def get_status(self) -> Dict[str, Any]:
        """Return aggregate status.  The internal library is never included."""
        with self._lock:
            module_count = len(self._internal_library)
            module_ids = list(self._internal_library.keys())
            total = self._total_validations
            approved = self._total_approved
            per_module = {
                mid: mod.stats()
                for mid, mod in self._internal_library.items()
            }
        return {
            "status": "active",
            "registered_modules": module_count,
            "module_domains": module_ids,
            "total_validations": total,
            "total_approved": approved,
            "total_rejected": total - approved,
            "approval_rate": round(approved / total, 3) if total else None,
            "per_module": per_module,
        }

    def list_module_ids(self) -> List[str]:
        """Return the list of registered module IDs (not the modules themselves)."""
        with self._lock:
            return list(self._internal_library.keys())

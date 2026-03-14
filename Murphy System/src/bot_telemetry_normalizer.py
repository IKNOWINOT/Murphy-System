"""
Bot Telemetry Normalizer — Murphy System Section 15.3.5

Standardizes triage/rubix bot event payloads into the Murphy
observability ingestion schema so legacy telemetry flows through
a single, well-typed pipeline.
"""

import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append_paired
except ImportError:
    def capped_append_paired(*lists_and_items: Any, max_size: int = 10_000) -> None:
        """Fallback bounded paired append (CWE-770)."""
        pairs = list(zip(lists_and_items[::2], lists_and_items[1::2]))
        if not pairs:
            return
        ref_list = pairs[0][0]
        if len(ref_list) >= max_size:
            trim = max_size // 10
            for lst, _ in pairs:
                del lst[:trim]
        for lst, item in pairs:
            lst.append(item)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Severity(Enum):
    """Event severity levels for Murphy observability."""
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class Category(Enum):
    """Event category for Murphy observability."""
    EXECUTION = "EXECUTION"
    GOVERNANCE = "GOVERNANCE"
    COMPLIANCE = "COMPLIANCE"
    TELEMETRY = "TELEMETRY"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class NormalizationRule:
    """Describes how a source event maps into the Murphy schema."""
    rule_id: str
    source_pattern: str
    source_event_type: str
    murphy_event_type: str
    field_mappings: Dict[str, str] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TelemetryEvent:
    """A single telemetry event, before and after normalisation."""
    event_id: str
    source: str
    event_type: str
    timestamp: float
    payload: Dict[str, Any] = field(default_factory=dict)
    normalized: bool = False
    murphy_event_type: Optional[str] = None
    murphy_payload: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NormalizationResult:
    """Outcome of normalising a single event."""
    event_id: str
    success: bool
    original_type: str
    normalized_type: Optional[str] = None
    fields_mapped: int = 0
    fields_dropped: int = 0
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Normalizer
# ---------------------------------------------------------------------------


class BotTelemetryNormalizer:
    """Transforms triage / rubix bot telemetry into the Murphy
    observability ingestion schema (Section 15.3.5).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rules: Dict[str, NormalizationRule] = {}
        self._events: List[TelemetryEvent] = []
        self._results: List[NormalizationResult] = []
        self._rule_counter: int = 0
        logger.info("BotTelemetryNormalizer initialised")

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def register_rule(
        self,
        source_pattern: str,
        source_event_type: str,
        murphy_event_type: str,
        field_mappings: Optional[Dict[str, str]] = None,
        description: str = "",
    ) -> NormalizationRule:
        """Register a mapping rule and return it."""
        with self._lock:
            self._rule_counter += 1
            rule_id = f"rule-{self._rule_counter:04d}"
            rule = NormalizationRule(
                rule_id=rule_id,
                source_pattern=source_pattern,
                source_event_type=source_event_type,
                murphy_event_type=murphy_event_type,
                field_mappings=field_mappings or {},
                description=description,
            )
            key = f"{source_pattern}::{source_event_type}"
            self._rules[key] = rule
            logger.info("Registered rule %s  %s -> %s", rule_id, key, murphy_event_type)
            return rule

    # ------------------------------------------------------------------
    # Default rule sets
    # ------------------------------------------------------------------

    def register_default_triage_rules(self) -> List[NormalizationRule]:
        """Pre-built rules for triage bot events."""
        rules: List[NormalizationRule] = []

        rules.append(self.register_rule(
            source_pattern="triage",
            source_event_type="rollcall_complete",
            murphy_event_type="murphy.triage.rollcall_complete",
            field_mappings={
                "participants": "payload.participants",
                "quorum_met": "payload.quorum_met",
                "duration_ms": "payload.duration_ms",
            },
            description="Triage rollcall completion event",
        ))

        rules.append(self.register_rule(
            source_pattern="triage",
            source_event_type="candidate_selected",
            murphy_event_type="murphy.triage.candidate_selected",
            field_mappings={
                "candidate_id": "payload.candidate_id",
                "score": "payload.score",
                "reason": "payload.reason",
            },
            description="Triage candidate selection event",
        ))

        rules.append(self.register_rule(
            source_pattern="triage",
            source_event_type="confidence_probe",
            murphy_event_type="murphy.triage.confidence_probe",
            field_mappings={
                "probe_id": "payload.probe_id",
                "confidence": "payload.confidence",
                "threshold": "payload.threshold",
            },
            description="Triage confidence probe event",
        ))

        rules.append(self.register_rule(
            source_pattern="triage",
            source_event_type="swarm_expanded",
            murphy_event_type="murphy.triage.swarm_expanded",
            field_mappings={
                "swarm_id": "payload.swarm_id",
                "new_agents": "payload.new_agents",
                "total_agents": "payload.total_agents",
            },
            description="Triage swarm expansion event",
        ))

        logger.info("Registered %d default triage rules", len(rules))
        return rules

    def register_default_rubix_rules(self) -> List[NormalizationRule]:
        """Pre-built rules for rubix bot events."""
        rules: List[NormalizationRule] = []

        rules.append(self.register_rule(
            source_pattern="rubix",
            source_event_type="evidence_check",
            murphy_event_type="murphy.rubix.evidence_check",
            field_mappings={
                "evidence_id": "payload.evidence_id",
                "check_result": "payload.check_result",
                "confidence": "payload.confidence",
            },
            description="Rubix evidence validation check",
        ))

        rules.append(self.register_rule(
            source_pattern="rubix",
            source_event_type="hypothesis_updated",
            murphy_event_type="murphy.rubix.hypothesis_updated",
            field_mappings={
                "hypothesis_id": "payload.hypothesis_id",
                "prior": "payload.prior",
                "posterior": "payload.posterior",
                "evidence_count": "payload.evidence_count",
            },
            description="Rubix hypothesis Bayesian update",
        ))

        rules.append(self.register_rule(
            source_pattern="rubix",
            source_event_type="ci_computed",
            murphy_event_type="murphy.rubix.ci_computed",
            field_mappings={
                "metric": "payload.metric",
                "lower": "payload.ci_lower",
                "upper": "payload.ci_upper",
                "alpha": "payload.alpha",
            },
            description="Rubix confidence interval computation",
        ))

        rules.append(self.register_rule(
            source_pattern="rubix",
            source_event_type="monte_carlo_complete",
            murphy_event_type="murphy.rubix.monte_carlo_complete",
            field_mappings={
                "iterations": "payload.iterations",
                "mean": "payload.mean",
                "std_dev": "payload.std_dev",
                "p95": "payload.p95",
            },
            description="Rubix Monte-Carlo simulation result",
        ))

        rules.append(self.register_rule(
            source_pattern="rubix",
            source_event_type="forecast_generated",
            murphy_event_type="murphy.rubix.forecast_generated",
            field_mappings={
                "forecast_id": "payload.forecast_id",
                "horizon": "payload.horizon",
                "prediction": "payload.prediction",
                "confidence": "payload.confidence",
            },
            description="Rubix forecast generation event",
        ))

        logger.info("Registered %d default rubix rules", len(rules))
        return rules

    # ------------------------------------------------------------------
    # Normalisation logic
    # ------------------------------------------------------------------

    def _find_rule(self, source: str, event_type: str) -> Optional[NormalizationRule]:
        key = f"{source}::{event_type}"
        return self._rules.get(key)

    def _apply_field_mappings(
        self,
        payload: Dict[str, Any],
        mappings: Dict[str, str],
    ) -> tuple:
        """Map source payload fields into Murphy payload.

        Returns (murphy_payload, fields_mapped, fields_dropped, warnings).
        """
        murphy_payload: Dict[str, Any] = {}
        fields_mapped = 0
        fields_dropped = 0
        warnings: List[str] = []

        for src_field, dest_path in mappings.items():
            if src_field in payload:
                # dest_path looks like "payload.foo" – store under the last segment
                dest_key = dest_path.rsplit(".", 1)[-1]
                murphy_payload[dest_key] = payload[src_field]
                fields_mapped += 1
            else:
                fields_dropped += 1
                warnings.append(f"Source field '{src_field}' not present in payload")

        # Carry over unmapped fields in a sub-dict so nothing is silently lost
        unmapped = {k: v for k, v in payload.items() if k not in mappings}
        if unmapped:
            murphy_payload["_unmapped"] = unmapped

        return murphy_payload, fields_mapped, fields_dropped, warnings

    @staticmethod
    def _infer_severity(event_type: str, payload: Dict[str, Any]) -> Severity:
        if "error" in event_type.lower() or payload.get("error"):
            return Severity.ERROR
        if "warn" in event_type.lower() or payload.get("warning"):
            return Severity.WARN
        return Severity.INFO

    @staticmethod
    def _infer_category(event_type: str) -> Category:
        lower = event_type.lower()
        if "governance" in lower or "gate" in lower:
            return Category.GOVERNANCE
        if "compliance" in lower or "audit" in lower:
            return Category.COMPLIANCE
        if "telemetry" in lower or "metric" in lower:
            return Category.TELEMETRY
        return Category.EXECUTION

    def normalize_event(
        self,
        source: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> TelemetryEvent:
        """Normalise a single event into the Murphy observability schema."""
        event_id = str(uuid.uuid4())
        now = time.time()
        rule = self._find_rule(source, event_type)

        if rule is None:
            event = TelemetryEvent(
                event_id=event_id,
                source=source,
                event_type=event_type,
                timestamp=now,
                payload=dict(payload),
                normalized=False,
            )
            result = NormalizationResult(
                event_id=event_id,
                success=False,
                original_type=event_type,
                warnings=[f"No rule matched for {source}::{event_type}"],
            )
            with self._lock:
                capped_append_paired(self._events, event, self._results, result)
            logger.warning("No normalisation rule for %s::%s", source, event_type)
            return event

        mapped_payload, fields_mapped, fields_dropped, warnings = (
            self._apply_field_mappings(payload, rule.field_mappings)
        )

        severity = self._infer_severity(event_type, payload)
        category = self._infer_category(event_type)

        murphy_payload: Dict[str, Any] = {
            "event_id": event_id,
            "murphy_event_type": rule.murphy_event_type,
            "timestamp": now,
            "source_system": source,
            "severity": severity.value,
            "category": category.value,
            "payload": mapped_payload,
            "correlation_id": payload.get("correlation_id"),
        }

        event = TelemetryEvent(
            event_id=event_id,
            source=source,
            event_type=event_type,
            timestamp=now,
            payload=dict(payload),
            normalized=True,
            murphy_event_type=rule.murphy_event_type,
            murphy_payload=murphy_payload,
        )

        result = NormalizationResult(
            event_id=event_id,
            success=True,
            original_type=event_type,
            normalized_type=rule.murphy_event_type,
            fields_mapped=fields_mapped,
            fields_dropped=fields_dropped,
            warnings=warnings,
        )

        with self._lock:
            capped_append_paired(self._events, event, self._results, result)

        logger.info(
            "Normalised %s::%s -> %s  (mapped=%d dropped=%d)",
            source, event_type, rule.murphy_event_type,
            fields_mapped, fields_dropped,
        )
        return event

    def normalize_batch(self, events: List[Dict[str, Any]]) -> List[TelemetryEvent]:
        """Normalise a list of raw event dicts.

        Each dict must contain ``source``, ``event_type``, and ``payload`` keys.
        """
        results: List[TelemetryEvent] = []
        for raw in events:
            source = raw.get("source", "unknown")
            event_type = raw.get("event_type", "unknown")
            payload = raw.get("payload", {})
            results.append(self.normalize_event(source, event_type, payload))
        return results

    # ------------------------------------------------------------------
    # Reporting / queries
    # ------------------------------------------------------------------

    def get_normalization_report(self) -> Dict[str, Any]:
        """Return statistics on normalisation success/failure rates."""
        with self._lock:
            total = len(self._results)
            success = sum(1 for r in self._results if r.success)
            failure = total - success
            total_mapped = sum(r.fields_mapped for r in self._results)
            total_dropped = sum(r.fields_dropped for r in self._results)
            all_warnings = [w for r in self._results for w in r.warnings]

        return {
            "total_events": total,
            "successful": success,
            "failed": failure,
            "success_rate": round(success / total, 4) if total else 0.0,
            "fields_mapped": total_mapped,
            "fields_dropped": total_dropped,
            "warnings_count": len(all_warnings),
            "registered_rules": len(self._rules),
        }

    def get_event_history(
        self,
        source: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[TelemetryEvent]:
        """Retrieve recent events, optionally filtered."""
        with self._lock:
            filtered = list(self._events)

        if source is not None:
            filtered = [e for e in filtered if e.source == source]
        if event_type is not None:
            filtered = [e for e in filtered if e.event_type == event_type]

        return filtered[-limit:]

    def get_unmapped_events(self) -> List[TelemetryEvent]:
        """Return events that could not be normalised."""
        with self._lock:
            return [e for e in self._events if not e.normalized]

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Get current normalizer status summary."""
        with self._lock:
            total = len(self._events)
            normalized = sum(1 for e in self._events if e.normalized)
            unmapped = total - normalized

        return {
            "registered_rules": len(self._rules),
            "total_events_processed": total,
            "normalized_events": normalized,
            "unmapped_events": unmapped,
            "success_rate": round(normalized / total, 4) if total else 0.0,
        }

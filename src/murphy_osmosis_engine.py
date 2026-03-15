"""
Murphy System - Murphy Osmosis Engine
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

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

class ImplementationStatus(str, Enum):
    """ImplementationStatus enumeration."""
    OBSERVED = "observed"
    ANALYZING = "analyzing"
    SANDBOX_TESTING = "sandbox_testing"
    VALIDATED = "validated"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SoftwareCapability(BaseModel):
    """SoftwareCapability — software capability definition."""
    capability_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_software: str
    capability_name: str
    description: str
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    core_algorithm: str = ""
    murphy_implementation_status: ImplementationStatus = ImplementationStatus.OBSERVED
    observed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    validation_score: float = 0.0
    io_pairs: List[Dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Capability Observer
# ---------------------------------------------------------------------------

class CapabilityObserver:
    """Watch an external API/tool's inputs and outputs over time, build a behavioral model."""

    def __init__(self, source_software: str, capability_name: str) -> None:
        self.source_software = source_software
        self.capability_name = capability_name
        self._observations: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def observe(self, input_data: Any, output_data: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record an input/output observation."""
        with self._lock:
            capped_append(self._observations, {
                "observation_id": str(uuid.uuid4()),
                "input": input_data,
                "output": output_data,
                "metadata": metadata or {},
                "observed_at": datetime.now(timezone.utc).isoformat(),
            })

    def get_observations(self) -> List[Dict[str, Any]]:
        """Return all recorded observations."""
        with self._lock:
            return list(self._observations)

    def get_observation_count(self) -> int:
        with self._lock:
            return len(self._observations)


# ---------------------------------------------------------------------------
# Pattern Extractor
# ---------------------------------------------------------------------------

class PatternExtractor:
    """From observed I/O pairs, extract the core transformation pattern."""

    def extract(self, observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze observations to derive the core algorithm description.
        Returns a pattern dict with: input_types, output_types, core_algorithm_description.
        """
        if not observations:
            return {
                "input_types": [],
                "output_types": [],
                "core_algorithm_description": "No observations available",
                "sample_count": 0,
            }

        input_types = list({type(o["input"]).__name__ for o in observations})
        output_types = list({type(o["output"]).__name__ for o in observations})

        # Simple heuristic: numeric in → numeric out suggests transformation
        numeric_in = all(isinstance(o["input"], (int, float)) for o in observations)
        numeric_out = all(isinstance(o["output"], (int, float)) for o in observations)

        if numeric_in and numeric_out:
            # Attempt to find a ratio
            ratios = []
            for obs in observations:
                inp = float(obs["input"])
                out = float(obs["output"])
                if inp != 0:
                    ratios.append(out / inp)
            if ratios:
                avg_ratio = sum(ratios) / (len(ratios) or 1)
                core_desc = f"Numeric transformation: output ≈ input × {avg_ratio:.4f}"
            else:
                core_desc = "Numeric transformation (ratio indeterminate)"
        elif all(isinstance(o["input"], str) for o in observations):
            core_desc = "String processing transformation"
        elif all(isinstance(o["input"], dict) for o in observations):
            core_desc = "Dictionary/object transformation"
        else:
            core_desc = "General transformation pattern"

        return {
            "input_types": input_types,
            "output_types": output_types,
            "core_algorithm_description": core_desc,
            "sample_count": len(observations),
        }


# ---------------------------------------------------------------------------
# Murphy Implementation Builder
# ---------------------------------------------------------------------------

class MurphyImplementationBuilder:
    """Generate a Murphy-native implementation of the observed capability."""

    def build(
        self,
        capability: SoftwareCapability,
        pattern: Dict[str, Any],
    ) -> Callable[..., Any]:
        """
        Build a Python callable that implements the observed capability.
        Returns a function that takes input and produces output.
        """
        algo_desc = pattern.get("core_algorithm_description", "")

        if "× " in algo_desc:
            # Extract ratio from description
            try:
                ratio_str = algo_desc.split("× ")[-1].strip()
                ratio = float(ratio_str)
            except (ValueError, IndexError):
                ratio = 1.0

            def numeric_transform(x: Any, _ratio: float = ratio) -> Any:
                try:
                    return float(x) * _ratio
                except (TypeError, ValueError):
                    return x

            return numeric_transform

        elif "String" in algo_desc:
            def string_transform(x: Any) -> str:
                return str(x)
            return string_transform

        else:
            def identity_transform(x: Any) -> Any:
                return x
            return identity_transform


# ---------------------------------------------------------------------------
# Osmosis Candidate
# ---------------------------------------------------------------------------

@dataclass
class OsmosisCandidate:
    """Package the Murphy implementation as a CandidateAction for the Causality Sandbox."""

    candidate_id: str
    capability: SoftwareCapability
    implementation_fn: Callable[..., Any]
    test_cases: List[Dict[str, Any]] = field(default_factory=list)
    effectiveness_score: float = 0.0
    sandbox_tested: bool = False
    sandbox_passed: bool = False

    def run_test_cases(self) -> Dict[str, Any]:
        """Execute all test cases against the implementation and compute effectiveness."""
        passed = 0
        failed = 0
        failures: List[str] = []
        for tc in self.test_cases:
            try:
                result = self.implementation_fn(tc["input"])
                expected = tc.get("expected_output")
                if expected is not None:
                    if abs(float(result) - float(expected)) < 1e-6:
                        passed += 1
                    else:
                        failed += 1
                        failures.append(f"input={tc['input']} expected={expected} got={result}")
                else:
                    passed += 1
            except Exception as exc:
                failed += 1
                failures.append(f"Exception: {exc}")

        total = passed + failed
        self.effectiveness_score = passed / (total or 1)
        self.sandbox_tested = True
        self.sandbox_passed = self.effectiveness_score >= 0.7
        return {
            "passed": passed,
            "failed": failed,
            "effectiveness_score": self.effectiveness_score,
            "failures": failures,
        }


# ---------------------------------------------------------------------------
# Absorbed Capability Registry
# ---------------------------------------------------------------------------

class AbsorbedCapabilityRegistry:
    """Track all capabilities Murphy has absorbed."""

    def __init__(self) -> None:
        self._capabilities: Dict[str, SoftwareCapability] = {}
        self._lock = threading.Lock()

    def register(self, capability: SoftwareCapability) -> str:
        with self._lock:
            self._capabilities[capability.capability_id] = capability
        return capability.capability_id

    def get(self, capability_id: str) -> Optional[SoftwareCapability]:
        return self._capabilities.get(capability_id)

    def list_by_status(self, status: ImplementationStatus) -> List[SoftwareCapability]:
        return [c for c in self._capabilities.values() if c.murphy_implementation_status == status]

    def list_all(self) -> List[SoftwareCapability]:
        return list(self._capabilities.values())

    def update_status(self, capability_id: str, status: ImplementationStatus) -> bool:
        cred = self._capabilities.get(capability_id)
        if cred is None:
            return False
        try:
            updated = cred.model_copy(update={"murphy_implementation_status": status})
        except AttributeError:
            updated = cred.copy(update={"murphy_implementation_status": status})
        self._capabilities[capability_id] = updated
        return True


# ---------------------------------------------------------------------------
# Insight Extractor
# ---------------------------------------------------------------------------

class InsightExtractor:
    """From HITL interactions, extract patterns of what humans actually care about."""

    def __init__(self) -> None:
        self._interactions: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def record_interaction(
        self,
        action: str,
        outcome: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a human interaction (approval/rejection/modification)."""
        with self._lock:
            capped_append(self._interactions, {
                "interaction_id": str(uuid.uuid4()),
                "action": action,
                "outcome": outcome,
                "context": context or {},
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            })

    def extract_insights(self) -> Dict[str, Any]:
        """Summarize patterns from recorded interactions."""
        with self._lock:
            interactions = list(self._interactions)
        if not interactions:
            return {"total": 0, "approval_rate": 0.0, "top_rejection_reasons": []}

        approved = [i for i in interactions if i["outcome"] == "approved"]
        rejected = [i for i in interactions if i["outcome"] == "rejected"]
        total = len(interactions)
        approval_rate = len(approved) / (total or 1)

        rejection_reasons: Dict[str, int] = {}
        for i in rejected:
            reason = i.get("context", {}).get("reason", "unspecified")
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

        top_reasons = sorted(rejection_reasons.items(), key=lambda x: x[1], reverse=True)[:5]
        return {
            "total": total,
            "approved": len(approved),
            "rejected": len(rejected),
            "approval_rate": round(approval_rate, 4),
            "top_rejection_reasons": [{"reason": r, "count": c} for r, c in top_reasons],
        }


# ---------------------------------------------------------------------------
# Osmosis Pipeline
# ---------------------------------------------------------------------------

class OsmosisPipeline:
    """Full pipeline: Observe → Extract → Build → Sandbox → Validate → Deploy."""

    EFFECTIVENESS_THRESHOLD = 0.7

    def __init__(self) -> None:
        self._registry = AbsorbedCapabilityRegistry()
        self._extractor = PatternExtractor()
        self._builder = MurphyImplementationBuilder()
        self._candidates: Dict[str, OsmosisCandidate] = {}
        self._lock = threading.Lock()

    def absorb(
        self,
        source_software: str,
        capability_name: str,
        description: str,
        observations: List[Dict[str, Any]],
        test_cases: Optional[List[Dict[str, Any]]] = None,
    ) -> SoftwareCapability:
        """
        Run the full osmosis pipeline for a software capability.
        Returns the SoftwareCapability object (with final status set).
        """
        # Step 1: Create capability record
        capability = SoftwareCapability(
            source_software=source_software,
            capability_name=capability_name,
            description=description,
            murphy_implementation_status=ImplementationStatus.OBSERVED,
            io_pairs=observations,
        )
        self._registry.register(capability)

        # Step 2: Extract pattern
        self._registry.update_status(capability.capability_id, ImplementationStatus.ANALYZING)
        pattern = self._extractor.extract(observations)
        try:
            updated = capability.model_copy(update={"core_algorithm": pattern["core_algorithm_description"]})
        except AttributeError:
            updated = capability.copy(update={"core_algorithm": pattern["core_algorithm_description"]})
        capability = updated
        self._registry.register(capability)

        # Step 3: Build Murphy-native implementation
        impl_fn = self._builder.build(capability, pattern)

        # Step 4: Create osmosis candidate and sandbox-test it
        candidate = OsmosisCandidate(
            candidate_id=str(uuid.uuid4()),
            capability=capability,
            implementation_fn=impl_fn,
            test_cases=test_cases or [],
        )
        self._registry.update_status(capability.capability_id, ImplementationStatus.SANDBOX_TESTING)

        test_result = candidate.run_test_cases()
        logger.debug("OsmosisPipeline: sandbox test result: %s", test_result)

        # Step 5: Validate & decide status
        if candidate.sandbox_passed:
            final_status = ImplementationStatus.VALIDATED
        else:
            final_status = ImplementationStatus.OBSERVED  # Back to observed; needs more data

        self._registry.update_status(capability.capability_id, final_status)
        try:
            capability = capability.model_copy(update={
                "murphy_implementation_status": final_status,
                "validation_score": candidate.effectiveness_score,
            })
        except AttributeError:
            capability = capability.copy(update={
                "murphy_implementation_status": final_status,
                "validation_score": candidate.effectiveness_score,
            })

        with self._lock:
            self._candidates[candidate.candidate_id] = candidate

        return capability

    def promote_to_production(self, capability_id: str) -> bool:
        """Promote a validated capability to production."""
        cap = self._registry.get(capability_id)
        if cap is None:
            return False
        if cap.murphy_implementation_status != ImplementationStatus.VALIDATED:
            return False
        return self._registry.update_status(capability_id, ImplementationStatus.PRODUCTION)

    def get_registry(self) -> AbsorbedCapabilityRegistry:
        return self._registry

"""
Integration with Existing Confidence Engine
============================================

Provides optional ML enhancement to existing confidence computation.
Maintains backward compatibility and graceful degradation.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class MLConfig:
    """Configuration for ML integration."""
    enable_ml: bool = False  # Disabled by default
    ml_service_url: str = "http://localhost:8060"
    ml_timeout_ms: int = 100  # Fast timeout for auxiliary signal
    ml_min_confidence: float = 0.8  # Only use high-confidence predictions
    ml_weight: float = 0.2  # Weight for ML signal in fusion (γ_t)
    ml_fallback_on_error: bool = True  # Always fallback to heuristics


@dataclass
class MLSignal:
    """ML prediction signal."""
    H_ml: float  # Instability estimate [0,1]
    D_ml: float  # Grounding estimate [0,1]
    R_ml: float  # Risk estimate [0,1]
    confidence: float  # Prediction confidence [0,1]
    model_version: str
    inference_time_ms: float


@dataclass
class EnhancedConfidenceResult:
    """Enhanced confidence result with optional ML signals."""
    confidence: float  # Final confidence
    base_confidence: float  # Base confidence (heuristic)
    ml_signal: Optional[MLSignal]  # ML signal (optional, may be None)
    components: Dict[str, Any]  # All components
    murphy_index: float
    authority: str
    used_ml: bool  # Whether ML was used


class MLEnhancedConfidenceEngine:
    """
    Wrapper that adds optional ML enhancement to existing Confidence Engine.

    Key principles:
    1. Additive, not replacement
    2. Graceful degradation
    3. No breaking changes
    4. Optional enhancement
    """

    def __init__(
        self,
        base_confidence_engine,  # Existing ConfidenceEngine instance
        ml_config: Optional[MLConfig] = None
    ):
        self.base_engine = base_confidence_engine
        self.config = ml_config or MLConfig()

        # Statistics
        self.ml_calls = 0
        self.ml_successes = 0
        self.ml_failures = 0
        self.ml_timeouts = 0

    def compute_confidence(
        self,
        artifact_graph,
        verification_evidence: list,
        trust_model,
        phase
    ) -> EnhancedConfidenceResult:
        """
        Compute confidence with optional ML enhancement.

        This method:
        1. Always computes base confidence (existing logic)
        2. Optionally gets ML signal (if enabled and available)
        3. Fuses signals if ML confidence is high
        4. Falls back to base confidence on any error

        Returns:
            EnhancedConfidenceResult with base and optional ML components
        """
        # Step 1: Base computation (ALWAYS EXECUTED)
        base_result = self.base_engine.compute_confidence(
            artifact_graph,
            verification_evidence,
            trust_model,
            phase
        )

        # Step 2: Optional ML enhancement
        ml_signal = None
        used_ml = False

        if self.config.enable_ml:
            ml_signal = self._get_ml_signal_safe(
                artifact_graph,
                verification_evidence,
                phase
            )

            # Step 3: Fusion (if ML available and confident)
            if ml_signal and ml_signal.confidence >= self.config.ml_min_confidence:
                final_confidence = self._fuse_confidence(base_result, ml_signal)
                used_ml = True
            else:
                final_confidence = base_result.confidence
        else:
            final_confidence = base_result.confidence

        # Build enhanced result
        return EnhancedConfidenceResult(
            confidence=final_confidence,
            base_confidence=base_result.confidence,
            ml_signal=ml_signal,
            components={
                "generative": base_result.generative_adequacy,
                "deterministic": base_result.deterministic_grounding,
                "ml_instability": ml_signal.H_ml if ml_signal else None,
                "ml_grounding": ml_signal.D_ml if ml_signal else None,
                "ml_risk": ml_signal.R_ml if ml_signal else None
            },
            murphy_index=base_result.murphy_index,
            authority=base_result.authority,
            used_ml=used_ml
        )

    def _get_ml_signal_safe(
        self,
        artifact_graph,
        verification_evidence: list,
        phase
    ) -> Optional[MLSignal]:
        """
        Get ML signal with timeout and error handling.

        Returns None if ML unavailable or fails.
        This ensures graceful degradation.
        """
        self.ml_calls += 1

        try:
            response = requests.post(
                f"{self.config.ml_service_url}/predict/confidence",
                json={
                    "artifact_graph": self._serialize_graph(artifact_graph),
                    "verification_evidence": [
                        self._serialize_evidence(exc) for e in verification_evidence
                    ],
                    "current_phase": phase.value if hasattr(phase, 'value') else str(phase)
                },
                timeout=self.config.ml_timeout_ms / 1000
            )

            if response.status_code == 200:
                data = response.json()
                self.ml_successes += 1

                return MLSignal(
                    H_ml=data["H_ml"],
                    D_ml=data["D_ml"],
                    R_ml=data["R_ml"],
                    confidence=data["prediction_confidence"],
                    model_version=data["model_version"],
                    inference_time_ms=data["inference_time_ms"]
                )
            else:
                logger.warning(f"ML service returned status {response.status_code}")
                self.ml_failures += 1

        except requests.Timeout:
            logger.warning(f"ML service timeout ({self.config.ml_timeout_ms}ms)")
            self.ml_timeouts += 1

        except Exception as exc:
            logger.warning(f"ML signal unavailable: {exc}")
            self.ml_failures += 1

        return None  # Graceful degradation

    def _fuse_confidence(
        self,
        base_result,
        ml_signal: MLSignal
    ) -> float:
        """
        Fuse base confidence with ML signal.

        Formula: c_t = α_t·G(x) + β_t·D(x) + γ_t·ML(x)

        Where:
        - α_t, β_t are phase weights (from base engine)
        - γ_t is ML weight (bounded, typically 0.2)
        - ML(x) combines H_ml, D_ml, R_ml
        """
        # Get phase weights from base engine
        alpha_t = self._get_phase_weight("generative", base_result.phase)
        beta_t = self._get_phase_weight("deterministic", base_result.phase)
        gamma_t = self.config.ml_weight

        # Ensure weights sum to 1
        total_weight = alpha_t + beta_t + gamma_t
        alpha_t /= total_weight
        beta_t /= total_weight
        gamma_t /= total_weight

        # Base confidence components
        G_x = base_result.generative_adequacy
        D_x = base_result.deterministic_grounding

        # ML signal (combine H, D, R)
        ML_x = (
            0.4 * (1 - ml_signal.H_ml) +  # Lower instability = higher confidence
            0.4 * ml_signal.D_ml +          # Higher grounding = higher confidence
            0.2 * (1 - ml_signal.R_ml)      # Lower risk = higher confidence
        )

        # Fused confidence
        fused_c = alpha_t * G_x + beta_t * D_x + gamma_t * ML_x

        # Normalize to [0, 1]
        return min(1.0, max(0.0, fused_c))

    def _get_phase_weight(self, component: str, phase) -> float:
        """Get phase weight for component."""
        # Simplified - in practice, get from base engine
        if component == "generative":
            return 0.6 if str(phase) == "generative" else 0.3
        elif component == "deterministic":
            return 0.3 if str(phase) == "generative" else 0.6
        return 0.1

    def _serialize_graph(self, artifact_graph) -> Dict[str, Any]:
        """Serialize artifact graph for ML service."""
        # Simplified serialization
        if hasattr(artifact_graph, 'to_dict'):
            return artifact_graph.to_dict()
        return {}

    def _serialize_evidence(self, evidence) -> Dict[str, Any]:
        """Serialize verification evidence for ML service."""
        if hasattr(evidence, 'to_dict'):
            return evidence.to_dict()
        return {}

    def get_statistics(self) -> Dict[str, Any]:
        """Get ML usage statistics."""
        success_rate = (
            self.ml_successes / self.ml_calls if self.ml_calls > 0 else 0.0
        )

        return {
            "ml_enabled": self.config.enable_ml,
            "ml_calls": self.ml_calls,
            "ml_successes": self.ml_successes,
            "ml_failures": self.ml_failures,
            "ml_timeouts": self.ml_timeouts,
            "success_rate": success_rate,
            "ml_weight": self.config.ml_weight,
            "ml_min_confidence": self.config.ml_min_confidence
        }

    def enable_ml(self, enable: bool = True):
        """Enable or disable ML enhancement."""
        self.config.enable_ml = enable
        logger.info(f"ML enhancement {'enabled' if enable else 'disabled'}")

    def set_ml_weight(self, weight: float):
        """
        Set ML weight (bounded to [0, 0.3]).

        ML weight is bounded to ensure base confidence always has majority influence.
        """
        if not 0 <= weight <= 0.3:
            raise ValueError("ML weight must be in [0, 0.3]")

        self.config.ml_weight = weight
        logger.info(f"ML weight set to {weight}")


# Backward-compatible wrapper
class ConfidenceEngineWithML:
    """
    Drop-in replacement for ConfidenceEngine with optional ML.

    Usage:
        # Without ML (backward compatible)
        engine = ConfidenceEngineWithML(base_engine)
        result = engine.compute_confidence(...)

        # With ML (opt-in)
        ml_config = MLConfig(enable_ml=True)
        engine = ConfidenceEngineWithML(base_engine, ml_config)
        result = engine.compute_confidence(...)
    """

    def __init__(
        self,
        base_engine,
        ml_config: Optional[MLConfig] = None
    ):
        self.enhanced_engine = MLEnhancedConfidenceEngine(base_engine, ml_config)

    def compute_confidence(self, *args, **kwargs):
        """Compute confidence (with optional ML)."""
        return self.enhanced_engine.compute_confidence(*args, **kwargs)

    def enable_ml(self, enable: bool = True):
        """Enable or disable ML."""
        self.enhanced_engine.enable_ml(enable)

    def get_statistics(self):
        """Get statistics."""
        return self.enhanced_engine.get_statistics()

    # Forward all other methods to base engine
    def __getattr__(self, name):
        return getattr(self.enhanced_engine.base_engine, name)


# Example usage
if __name__ == "__main__":
    # This demonstrates how to integrate with existing Confidence Engine

    # Assume we have existing ConfidenceEngine
    # from src.confidence_engine import ConfidenceEngine
    # base_engine = ConfidenceEngine()

    # Option 1: Without ML (backward compatible)
    # engine = ConfidenceEngineWithML(base_engine)

    # Option 2: With ML (opt-in)
    # ml_config = MLConfig(
    #     enable_ml=True,
    #     ml_service_url="http://localhost:8060",
    #     ml_weight=0.2
    # )
    # engine = ConfidenceEngineWithML(base_engine, ml_config)

    # Use exactly like before
    # result = engine.compute_confidence(
    #     artifact_graph,
    #     verification_evidence,
    #     trust_model,
    #     phase
    # )

    # Check if ML was used
    # if result.used_ml:
    #     print(f"ML signal: H={result.ml_signal.H_ml}, D={result.ml_signal.D_ml}")

    logger.info("Integration module loaded successfully")

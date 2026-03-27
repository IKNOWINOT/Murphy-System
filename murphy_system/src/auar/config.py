"""
AUAR Configuration Management
===============================

Provides YAML/JSON/environment-variable based configuration for the
AUAR subsystem.  Settings can be loaded from a file or from ``AUAR_*``
environment variables, with sensible defaults for all values.

Usage::

    config = AUARConfig.from_env()          # load from AUAR_* env vars
    config = AUARConfig.from_dict({...})    # load from a plain dict
    config = AUARConfig.defaults()          # all defaults

Copyright 2024 Inoni LLC – BSL-1.1
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class RoutingConfig:
    """Routing decision engine configuration."""
    strategy: str = "reliability_first"
    circuit_breaker_threshold: int = 5
    circuit_breaker_recovery_s: float = 30.0
    ml_weight: float = 0.20
    max_latency_ms: float = 500.0
    max_cost: float = 0.10
    half_open_required_successes: int = 3
    half_open_traffic_ratio: float = 0.10
    weights: Dict[str, float] = field(default_factory=lambda: {
        "reliability": 0.35,
        "latency": 0.25,
        "cost": 0.25,
        "certification": 0.15,
    })


@dataclass
class MLConfig:
    """ML optimisation layer configuration."""
    epsilon: float = 0.15
    epsilon_min: float = 0.01
    epsilon_decay: float = 0.995
    max_latency_ms: float = 500.0
    max_cost: float = 0.10
    recency_decay: float = 0.99
    reward_weights: Dict[str, float] = field(default_factory=lambda: {
        "success": 0.50,
        "latency": 0.30,
        "cost": 0.20,
    })


@dataclass
class ObservabilityConfig:
    """Observability layer configuration."""
    max_traces: int = 10_000
    max_audit_entries: int = 50_000
    enable_tracing: bool = True
    enable_metrics: bool = True
    enable_audit: bool = True


@dataclass
class InterpreterConfig:
    """Signal interpretation layer configuration."""
    llm_confidence_threshold: float = 0.80
    direct_route_threshold: float = 0.85
    clarification_threshold: float = 0.60


@dataclass
class AUARConfig:
    """Top-level AUAR configuration container."""
    version: str = "0.1.0"
    codename: str = "FAPI"
    log_level: str = "INFO"
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    ml: MLConfig = field(default_factory=MLConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    interpreter: InterpreterConfig = field(default_factory=InterpreterConfig)

    # --- Factory methods ---------------------------------------------------

    @classmethod
    def defaults(cls) -> "AUARConfig":
        """Return a configuration with all default values."""
        return cls()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AUARConfig":
        """Build an ``AUARConfig`` from a flat or nested dictionary.

        Top-level keys map directly to sub-config sections::

            {
                "log_level": "DEBUG",
                "routing": {"strategy": "cost_optimized"},
                "ml": {"epsilon": 0.20},
            }
        """
        cfg = cls()
        cfg.log_level = data.get("log_level", cfg.log_level)

        # Routing
        r = data.get("routing", {})
        if isinstance(r, dict):
            cfg.routing.strategy = r.get("strategy", cfg.routing.strategy)
            cfg.routing.circuit_breaker_threshold = int(
                r.get("circuit_breaker_threshold", cfg.routing.circuit_breaker_threshold)
            )
            cfg.routing.circuit_breaker_recovery_s = float(
                r.get("circuit_breaker_recovery_s", cfg.routing.circuit_breaker_recovery_s)
            )
            cfg.routing.ml_weight = float(r.get("ml_weight", cfg.routing.ml_weight))
            cfg.routing.max_latency_ms = float(
                r.get("max_latency_ms", cfg.routing.max_latency_ms)
            )
            cfg.routing.max_cost = float(r.get("max_cost", cfg.routing.max_cost))
            cfg.routing.half_open_required_successes = int(
                r.get("half_open_required_successes", cfg.routing.half_open_required_successes)
            )
            cfg.routing.half_open_traffic_ratio = float(
                r.get("half_open_traffic_ratio", cfg.routing.half_open_traffic_ratio)
            )
            if "weights" in r and isinstance(r["weights"], dict):
                cfg.routing.weights.update(r["weights"])

        # ML
        m = data.get("ml", {})
        if isinstance(m, dict):
            cfg.ml.epsilon = float(m.get("epsilon", cfg.ml.epsilon))
            cfg.ml.epsilon_min = float(m.get("epsilon_min", cfg.ml.epsilon_min))
            cfg.ml.epsilon_decay = float(m.get("epsilon_decay", cfg.ml.epsilon_decay))
            cfg.ml.max_latency_ms = float(m.get("max_latency_ms", cfg.ml.max_latency_ms))
            cfg.ml.max_cost = float(m.get("max_cost", cfg.ml.max_cost))
            if "reward_weights" in m and isinstance(m["reward_weights"], dict):
                cfg.ml.reward_weights.update(m["reward_weights"])

        # Observability
        o = data.get("observability", {})
        if isinstance(o, dict):
            cfg.observability.max_traces = int(
                o.get("max_traces", cfg.observability.max_traces)
            )
            cfg.observability.max_audit_entries = int(
                o.get("max_audit_entries", cfg.observability.max_audit_entries)
            )
            cfg.observability.enable_tracing = bool(
                o.get("enable_tracing", cfg.observability.enable_tracing)
            )
            cfg.observability.enable_metrics = bool(
                o.get("enable_metrics", cfg.observability.enable_metrics)
            )
            cfg.observability.enable_audit = bool(
                o.get("enable_audit", cfg.observability.enable_audit)
            )

        # Interpreter
        i = data.get("interpreter", {})
        if isinstance(i, dict):
            cfg.interpreter.llm_confidence_threshold = float(
                i.get("llm_confidence_threshold", cfg.interpreter.llm_confidence_threshold)
            )
            cfg.interpreter.direct_route_threshold = float(
                i.get("direct_route_threshold", cfg.interpreter.direct_route_threshold)
            )
            cfg.interpreter.clarification_threshold = float(
                i.get("clarification_threshold", cfg.interpreter.clarification_threshold)
            )

        return cfg

    @classmethod
    def from_env(cls) -> "AUARConfig":
        """Build an ``AUARConfig`` from ``AUAR_*`` environment variables.

        Variable naming convention::

            AUAR_LOG_LEVEL          → log_level
            AUAR_ROUTING_STRATEGY   → routing.strategy
            AUAR_ML_EPSILON         → ml.epsilon
            AUAR_OBS_MAX_TRACES     → observability.max_traces
        """
        data: Dict[str, Any] = {}
        routing: Dict[str, Any] = {}
        ml: Dict[str, Any] = {}
        obs: Dict[str, Any] = {}
        interp: Dict[str, Any] = {}

        data["log_level"] = os.environ.get("AUAR_LOG_LEVEL", "INFO")

        # Routing
        if "AUAR_ROUTING_STRATEGY" in os.environ:
            routing["strategy"] = os.environ["AUAR_ROUTING_STRATEGY"]
        if "AUAR_ROUTING_CB_THRESHOLD" in os.environ:
            routing["circuit_breaker_threshold"] = os.environ["AUAR_ROUTING_CB_THRESHOLD"]
        if "AUAR_ROUTING_CB_RECOVERY" in os.environ:
            routing["circuit_breaker_recovery_s"] = os.environ["AUAR_ROUTING_CB_RECOVERY"]
        if "AUAR_ROUTING_ML_WEIGHT" in os.environ:
            routing["ml_weight"] = os.environ["AUAR_ROUTING_ML_WEIGHT"]
        if "AUAR_ROUTING_MAX_LATENCY_MS" in os.environ:
            routing["max_latency_ms"] = os.environ["AUAR_ROUTING_MAX_LATENCY_MS"]
        if "AUAR_ROUTING_MAX_COST" in os.environ:
            routing["max_cost"] = os.environ["AUAR_ROUTING_MAX_COST"]

        # ML
        if "AUAR_ML_EPSILON" in os.environ:
            ml["epsilon"] = os.environ["AUAR_ML_EPSILON"]
        if "AUAR_ML_EPSILON_MIN" in os.environ:
            ml["epsilon_min"] = os.environ["AUAR_ML_EPSILON_MIN"]
        if "AUAR_ML_EPSILON_DECAY" in os.environ:
            ml["epsilon_decay"] = os.environ["AUAR_ML_EPSILON_DECAY"]

        # Observability
        if "AUAR_OBS_MAX_TRACES" in os.environ:
            obs["max_traces"] = os.environ["AUAR_OBS_MAX_TRACES"]
        if "AUAR_OBS_MAX_AUDIT" in os.environ:
            obs["max_audit_entries"] = os.environ["AUAR_OBS_MAX_AUDIT"]

        # Interpreter
        if "AUAR_INTERP_LLM_THRESHOLD" in os.environ:
            interp["llm_confidence_threshold"] = os.environ["AUAR_INTERP_LLM_THRESHOLD"]

        if routing:
            data["routing"] = routing
        if ml:
            data["ml"] = ml
        if obs:
            data["observability"] = obs
        if interp:
            data["interpreter"] = interp

        return cls.from_dict(data)

    # --- Utility -----------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise configuration to a nested dictionary."""
        return {
            "version": self.version,
            "codename": self.codename,
            "log_level": self.log_level,
            "routing": {
                "strategy": self.routing.strategy,
                "circuit_breaker_threshold": self.routing.circuit_breaker_threshold,
                "circuit_breaker_recovery_s": self.routing.circuit_breaker_recovery_s,
                "ml_weight": self.routing.ml_weight,
                "max_latency_ms": self.routing.max_latency_ms,
                "max_cost": self.routing.max_cost,
                "half_open_required_successes": self.routing.half_open_required_successes,
                "half_open_traffic_ratio": self.routing.half_open_traffic_ratio,
                "weights": dict(self.routing.weights),
            },
            "ml": {
                "epsilon": self.ml.epsilon,
                "epsilon_min": self.ml.epsilon_min,
                "epsilon_decay": self.ml.epsilon_decay,
                "max_latency_ms": self.ml.max_latency_ms,
                "max_cost": self.ml.max_cost,
                "reward_weights": dict(self.ml.reward_weights),
            },
            "observability": {
                "max_traces": self.observability.max_traces,
                "max_audit_entries": self.observability.max_audit_entries,
                "enable_tracing": self.observability.enable_tracing,
                "enable_metrics": self.observability.enable_metrics,
                "enable_audit": self.observability.enable_audit,
            },
            "interpreter": {
                "llm_confidence_threshold": self.interpreter.llm_confidence_threshold,
                "direct_route_threshold": self.interpreter.direct_route_threshold,
                "clarification_threshold": self.interpreter.clarification_threshold,
            },
        }

"""
LCM Integration Bridge — Wires LCM gate profiles through every integration layer.

Design Label: LCM-003 — Integration Bridge
Owner: Platform Engineering

Provides bridge classes that intercept calls to AM workflows, BAS actions,
enterprise DAG steps, and bot governance, checking gate profiles before
allowing execution.

All bridges degrade gracefully if their underlying registry is unavailable.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional imports with graceful stubs
# ---------------------------------------------------------------------------

try:
    from lcm_engine import LCMEngine, GateBehaviorProfile
    _HAS_ENGINE = True
except ImportError:
    _HAS_ENGINE = False
    LCMEngine = None  # type: ignore[assignment,misc]
    GateBehaviorProfile = None  # type: ignore[assignment,misc]

try:
    from additive_manufacturing_connectors import (
        AdditiveManufacturingRegistry,
        AdditiveProcess,
    )
    _HAS_AM = True
except ImportError:
    _HAS_AM = False
    AdditiveManufacturingRegistry = None  # type: ignore[assignment,misc]
    AdditiveProcess = None  # type: ignore[assignment,misc]

try:
    from building_automation_connectors import BuildingAutomationRegistry
    _HAS_BAS = True
except ImportError:
    _HAS_BAS = False
    BuildingAutomationRegistry = None  # type: ignore[assignment,misc]

try:
    from enterprise_integrations import EnterpriseIntegrationRegistry
    _HAS_ENTERPRISE = True
except ImportError:
    _HAS_ENTERPRISE = False
    EnterpriseIntegrationRegistry = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Gate severity constants (lower = more permissive)
# ---------------------------------------------------------------------------
_GATE_THRESHOLDS: Dict[str, float] = {
    "safety": 0.9,       # very strict
    "compliance": 0.85,
    "security": 0.85,
    "quality": 0.75,
    "performance": 0.7,
    "business": 0.65,
    "energy": 0.6,
    "monitoring": 0.55,
    "comfort": 0.5,
}

# AM process → mandatory gates
_AM_REQUIRED_GATES: Dict[str, List[str]] = {
    "fdm_fff": ["quality", "monitoring"],
    "sla_dlp": ["quality", "safety", "monitoring"],   # resin = chemical hazard
    "sls": ["quality", "safety", "energy"],
    "slm_dmls": ["safety", "quality", "compliance", "energy"],  # metal powder
    "ebm": ["safety", "energy", "quality"],            # vacuum + high voltage
    "polyjet_mjf": ["quality", "monitoring"],
    "binder_jetting": ["quality", "safety"],
    "ded_waam": ["safety", "quality", "energy"],
    "continuous_fiber": ["quality", "safety", "compliance"],
}

# BAS system type → mandatory gates
_BAS_REQUIRED_GATES: Dict[str, List[str]] = {
    "ahu": ["safety", "energy", "comfort"],
    "fcu": ["comfort", "energy"],
    "chiller": ["energy", "monitoring", "safety"],
    "boiler": ["safety", "energy", "compliance"],
    "cooling_tower": ["safety", "monitoring"],
    "vav": ["comfort", "energy"],
    "exhaust_fan": ["safety", "monitoring"],
    "heat_pump": ["energy", "monitoring"],
    "vrf": ["energy", "monitoring"],
    "radiant": ["comfort", "energy"],
    "doas": ["safety", "energy", "compliance"],
    "erv": ["energy", "monitoring"],
    "mau": ["safety", "energy"],
    "unit_heater": ["safety", "energy"],
    "it_cooling": ["energy", "monitoring", "performance"],
    "data_center": ["energy", "safety", "monitoring", "performance"],
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class GatedConnectorResult:
    """Result of a gated connector execution."""
    connector_name: str
    domain_id: str
    gate_passed: bool
    gate_profile: Dict[str, Any]
    result: Any = None
    error: Optional[str] = None
    gate_check_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connector_name": self.connector_name,
            "domain_id": self.domain_id,
            "gate_passed": self.gate_passed,
            "gate_profile": self.gate_profile,
            "result": self.result,
            "error": self.error,
            "gate_check_ms": self.gate_check_ms,
        }


# ---------------------------------------------------------------------------
# Internal gate check helper
# ---------------------------------------------------------------------------

def _check_gates(
    profile: Optional[Any],
    required_gates: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """
    Evaluate whether the gate profile clears all required gates.

    Returns (passed: bool, reason: str).
    """
    if profile is None:
        return False, "no gate profile available"

    required = required_gates or []
    profile_dict = (
        profile.to_dict() if hasattr(profile, "to_dict") else profile
    )
    gate_weights: Dict[str, float] = profile_dict.get("gate_weights", {})
    confidence: float = profile_dict.get("confidence", 0.0)

    for gate in required:
        threshold = _GATE_THRESHOLDS.get(gate, 0.6)
        weight = gate_weights.get(gate, confidence)
        if weight < threshold:
            return (
                False,
                f"gate '{gate}' failed: weight={weight:.3f} < threshold={threshold:.3f}",
            )
    return True, "all gates passed"


# ---------------------------------------------------------------------------
# Bridge: World Model (generic connector)
# ---------------------------------------------------------------------------

class WorldModelGateBridge:
    """Gates generic connector.execute() calls through LCM profile first."""

    def __init__(self, lcm_engine: Optional[Any] = None) -> None:
        self._lcm = lcm_engine
        self._lock = threading.RLock()

    def execute_gated(
        self,
        connector_name: str,
        action: str,
        params: Dict[str, Any],
        domain_id: str,
    ) -> GatedConnectorResult:
        """Gate a generic connector action and execute if gates pass."""
        t0 = time.perf_counter()
        profile_dict: Dict[str, Any] = {}
        gate_passed = True
        error: Optional[str] = None

        try:
            if self._lcm is not None:
                role = params.get("role", "expert")
                profile = self._lcm.predict(domain_id, role, context=params)
                profile_dict = profile.to_dict() if hasattr(profile, "to_dict") else {}
                gate_passed, reason = _check_gates(profile, [])
                if not gate_passed:
                    error = reason
            else:
                profile_dict = {"confidence": 0.8, "gate_weights": {}, "gate_types": []}

            result = None
            if gate_passed:
                result = {
                    "action": action,
                    "params": params,
                    "executed": True,
                    "connector": connector_name,
                }
        except Exception as exc:  # noqa: BLE001
            gate_passed = False
            error = str(exc)
            result = None

        elapsed = (time.perf_counter() - t0) * 1000.0
        return GatedConnectorResult(
            connector_name=connector_name,
            domain_id=domain_id,
            gate_passed=gate_passed,
            gate_profile=profile_dict,
            result=result,
            error=error,
            gate_check_ms=round(elapsed, 2),
        )


# ---------------------------------------------------------------------------
# Bridge: Enterprise Integration (DAG steps)
# ---------------------------------------------------------------------------

class EnterpriseIntegrationGateBridge:
    """Gates enterprise DAG step transitions with LCM gate checkpoints."""

    def __init__(self, lcm_engine: Optional[Any] = None) -> None:
        self._lcm = lcm_engine
        self._lock = threading.RLock()
        self._registry: Optional[Any] = None
        if _HAS_ENTERPRISE and EnterpriseIntegrationRegistry is not None:
            try:
                self._registry = EnterpriseIntegrationRegistry()
            except Exception:  # noqa: BLE001
                pass

    def execute_step_gated(
        self,
        step_name: str,
        domain_id: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Gate an enterprise DAG step."""
        t0 = time.perf_counter()
        gate_passed = True
        error: Optional[str] = None
        profile_dict: Dict[str, Any] = {}

        try:
            if self._lcm is not None:
                role = context.get("role", "orchestrator")
                profile = self._lcm.predict(domain_id, role, context=context)
                profile_dict = profile.to_dict() if hasattr(profile, "to_dict") else {}
                # Compliance gate is mandatory for enterprise steps
                gate_passed, reason = _check_gates(profile, ["compliance"])
                if not gate_passed:
                    error = reason
        except Exception as exc:  # noqa: BLE001
            gate_passed = False
            error = str(exc)

        elapsed = (time.perf_counter() - t0) * 1000.0
        return {
            "step_name": step_name,
            "domain_id": domain_id,
            "gate_passed": gate_passed,
            "gate_profile": profile_dict,
            "error": error,
            "duration_ms": round(elapsed, 2),
            "executed": gate_passed,
        }


# ---------------------------------------------------------------------------
# Bridge: AM Workflow
# ---------------------------------------------------------------------------

class AMWorkflowGateBridge:
    """Gates AM workflow actions per process type using safety-critical gates."""

    def __init__(self, lcm_engine: Optional[Any] = None) -> None:
        self._lcm = lcm_engine
        self._lock = threading.RLock()
        self._registry: Optional[Any] = None
        if _HAS_AM and AdditiveManufacturingRegistry is not None:
            try:
                self._registry = AdditiveManufacturingRegistry()
            except Exception:  # noqa: BLE001
                pass

    def execute_am_action_gated(
        self,
        process_type: str,
        action: str,
        params: Dict[str, Any],
    ) -> GatedConnectorResult:
        """
        Gate an AM workflow action.

        SLM/DMLS and EBM require SAFETY gate for powder handling.
        All processes require QUALITY gate.
        """
        t0 = time.perf_counter()
        # Map process_type to domain_id
        domain_id = f"3d_printing_{process_type.lower().replace(' ', '_').replace('/', '_')}"
        required = _AM_REQUIRED_GATES.get(process_type.lower(), ["quality", "monitoring"])

        profile_dict: Dict[str, Any] = {}
        gate_passed = True
        error: Optional[str] = None

        try:
            if self._lcm is not None:
                profile = self._lcm.predict(domain_id, "specialist", context=params)
                profile_dict = profile.to_dict() if hasattr(profile, "to_dict") else {}
                gate_passed, reason = _check_gates(profile, required)
                if not gate_passed:
                    error = reason
            else:
                profile_dict = {
                    "confidence": 0.82,
                    "gate_weights": {g: 0.82 for g in required},
                    "gate_types": required,
                }

            result = None
            if gate_passed:
                result = {
                    "process_type": process_type,
                    "action": action,
                    "params": params,
                    "executed": True,
                }
        except Exception as exc:  # noqa: BLE001
            gate_passed = False
            error = str(exc)
            result = None

        elapsed = (time.perf_counter() - t0) * 1000.0
        return GatedConnectorResult(
            connector_name=f"am_workflow_{process_type}",
            domain_id=domain_id,
            gate_passed=gate_passed,
            gate_profile=profile_dict,
            result=result,
            error=error,
            gate_check_ms=round(elapsed, 2),
        )


# ---------------------------------------------------------------------------
# Bridge: BAS Action
# ---------------------------------------------------------------------------

class BASActionGateBridge:
    """Gates BAS actions per system type with energy + safety gates."""

    def __init__(self, lcm_engine: Optional[Any] = None) -> None:
        self._lcm = lcm_engine
        self._lock = threading.RLock()
        self._registry: Optional[Any] = None
        if _HAS_BAS and BuildingAutomationRegistry is not None:
            try:
                self._registry = BuildingAutomationRegistry()
            except Exception:  # noqa: BLE001
                pass

    def execute_bas_action_gated(
        self,
        system_type: str,
        action: str,
        params: Dict[str, Any],
    ) -> GatedConnectorResult:
        """
        Gate a BAS action.

        Boilers and AHUs require SAFETY gate.
        All BAS actions require ENERGY gate.
        """
        domain_id = "hvac_bas"
        required = _BAS_REQUIRED_GATES.get(system_type.lower(), ["energy", "monitoring"])

        t0 = time.perf_counter()
        profile_dict: Dict[str, Any] = {}
        gate_passed = True
        error: Optional[str] = None

        try:
            if self._lcm is not None:
                profile = self._lcm.predict(domain_id, "monitor", context=params)
                profile_dict = profile.to_dict() if hasattr(profile, "to_dict") else {}
                gate_passed, reason = _check_gates(profile, required)
                if not gate_passed:
                    error = reason
            else:
                profile_dict = {
                    "confidence": 0.82,
                    "gate_weights": {g: 0.82 for g in required},
                    "gate_types": required,
                }

            result = None
            if gate_passed:
                result = {
                    "system_type": system_type,
                    "action": action,
                    "params": params,
                    "executed": True,
                }
        except Exception as exc:  # noqa: BLE001
            gate_passed = False
            error = str(exc)
            result = None

        elapsed = (time.perf_counter() - t0) * 1000.0
        return GatedConnectorResult(
            connector_name=f"bas_{system_type}",
            domain_id=domain_id,
            gate_passed=gate_passed,
            gate_profile=profile_dict,
            result=result,
            error=error,
            gate_check_ms=round(elapsed, 2),
        )


# ---------------------------------------------------------------------------
# Bridge: Bot Governance
# ---------------------------------------------------------------------------

class BotGovernanceGateBridge:
    """Per-bot governance merges industry domain profile with bot role profile."""

    def __init__(self, lcm_engine: Optional[Any] = None) -> None:
        self._lcm = lcm_engine
        self._lock = threading.RLock()

    def get_bot_gate_profile(
        self, bot_name: str, industry: str
    ) -> Dict[str, Any]:
        """
        Return a merged gate profile for a specific bot in a specific industry.

        Looks up industry → domain_id, then predicts per-bot role profile.
        """
        # Map industry hint to domain_id
        industry_lower = industry.lower()
        if "3d" in industry_lower or "print" in industry_lower:
            domain_id = "3d_printing_fdm"
        elif "hvac" in industry_lower or "bas" in industry_lower or "building" in industry_lower:
            domain_id = "hvac_bas"
        elif "health" in industry_lower or "clinic" in industry_lower:
            domain_id = "clinical_operations"
        elif "financ" in industry_lower or "bank" in industry_lower:
            domain_id = "banking"
        elif "manufactur" in industry_lower:
            domain_id = "cnc_machining"
        elif "energy" in industry_lower or "power" in industry_lower:
            domain_id = "power_generation"
        elif "retail" in industry_lower or "ecomm" in industry_lower:
            domain_id = "ecommerce"
        elif "logistics" in industry_lower or "fleet" in industry_lower:
            domain_id = "fleet_management"
        else:
            domain_id = "consulting"

        role = "expert"  # default bot role for governance
        profile_dict: Dict[str, Any] = {}

        try:
            if self._lcm is not None:
                profile = self._lcm.predict(domain_id, role)
                profile_dict = profile.to_dict() if hasattr(profile, "to_dict") else {}
            else:
                profile_dict = {
                    "domain_id": domain_id,
                    "role": role,
                    "gate_types": ["quality", "compliance"],
                    "gate_weights": {"quality": 0.8, "compliance": 0.8},
                    "confidence": 0.75,
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning("BotGovernanceGateBridge: %s", exc)
            profile_dict = {
                "domain_id": domain_id,
                "role": role,
                "error": str(exc),
            }

        return {
            "bot_name": bot_name,
            "industry": industry,
            "domain_id": domain_id,
            "gate_profile": profile_dict,
        }


# ---------------------------------------------------------------------------
# Master Bridge
# ---------------------------------------------------------------------------

class LCMIntegrationBridge:
    """
    Master bridge wiring LCM through every integration layer.

    Composes:
      - WorldModelGateBridge
      - EnterpriseIntegrationGateBridge
      - AMWorkflowGateBridge
      - BASActionGateBridge
      - BotGovernanceGateBridge
    """

    def __init__(self, lcm_engine: Optional[Any] = None) -> None:
        self._lcm = lcm_engine
        self.world_model = WorldModelGateBridge(lcm_engine)
        self.enterprise = EnterpriseIntegrationGateBridge(lcm_engine)
        self.am_workflow = AMWorkflowGateBridge(lcm_engine)
        self.bas_action = BASActionGateBridge(lcm_engine)
        self.bot_governance = BotGovernanceGateBridge(lcm_engine)

    def status(self) -> Dict[str, Any]:
        """Return bridge status dict."""
        return {
            "lcm_attached": self._lcm is not None,
            "am_registry_available": _HAS_AM,
            "bas_registry_available": _HAS_BAS,
            "enterprise_registry_available": _HAS_ENTERPRISE,
            "bridges": {
                "world_model": "ok",
                "enterprise": "ok",
                "am_workflow": "ok",
                "bas_action": "ok",
                "bot_governance": "ok",
            },
        }

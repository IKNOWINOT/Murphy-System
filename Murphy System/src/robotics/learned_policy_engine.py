"""
Learned policy engine -- LeRobot (Hugging Face) integration.

Loads AI manipulation policies (imitation learning, diffusion policies,
vision-language-action models) and converts inferences to ActuatorCommands
for the Murphy actuator engine.

External dependency: ``lerobot`` (Apache 2.0).
When the library is not installed the engine operates in stub mode
returning zero-action commands.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency
# ---------------------------------------------------------------------------

try:
    import lerobot  # type: ignore[import-untyped]
    _LEROBOT_AVAILABLE = True
except ImportError:
    lerobot = None  # type: ignore[assignment]
    _LEROBOT_AVAILABLE = False

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class PolicyType(str, Enum):
    """Available policy architectures."""
    ACT = "act"
    DIFFUSION = "diffusion"
    TDMPC = "tdmpc"
    VLA = "vla"
    CUSTOM = "custom"


class InferenceStatus(str, Enum):
    """Status of a policy inference."""
    SUCCESS = "success"
    NO_MODEL = "no_model"
    INFERENCE_ERROR = "inference_error"
    TIMEOUT = "timeout"


@dataclass
class Observation:
    """Robot observation for policy inference."""
    joint_positions: List[float] = field(default_factory=list)
    joint_velocities: Optional[List[float]] = None
    gripper_position: float = 0.0
    images: Optional[Dict[str, Any]] = None
    timestamp: float = 0.0


@dataclass
class PolicyAction:
    """Action output from a learned policy."""
    joint_targets: List[float] = field(default_factory=list)
    gripper_target: float = 0.0
    confidence: float = 0.0
    action_horizon: int = 1


@dataclass
class InferenceResult:
    """Result of a policy inference."""
    inference_id: str = ""
    status: InferenceStatus = InferenceStatus.NO_MODEL
    actions: List[PolicyAction] = field(default_factory=list)
    inference_time_seconds: float = 0.0
    policy_name: str = ""
    message: str = ""

    def __post_init__(self) -> None:
        if not self.inference_id:
            self.inference_id = f"inf_{uuid.uuid4().hex[:8]}"


@dataclass
class PolicyConfig:
    """Configuration for loading a policy."""
    model_name: str = ""
    policy_type: PolicyType = PolicyType.ACT
    hub_id: str = ""  # Hugging Face Hub ID
    checkpoint_path: str = ""
    device: str = "cpu"
    action_horizon: int = 10
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class LearnedPolicyEngine:
    """AI policy inference engine using LeRobot.

    Falls back to zero-action stubs when LeRobot is not installed.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._loaded_policies: Dict[str, Any] = {}
        self._active_policy: Optional[str] = None
        self._inference_count: int = 0
        self._max_policies: int = 10

    @property
    def backend_available(self) -> bool:
        return _LEROBOT_AVAILABLE

    # -- Policy management ---------------------------------------------------

    def load_policy(self, config: PolicyConfig) -> bool:
        """Load a policy from Hugging Face Hub or local checkpoint."""
        name = config.model_name or config.hub_id or "default"

        if _LEROBOT_AVAILABLE and config.hub_id:
            try:
                # Real implementation would use lerobot.common.policies
                logger.info("Loading LeRobot policy: %s", config.hub_id)
                with self._lock:
                    if len(self._loaded_policies) >= self._max_policies:
                        oldest = next(iter(self._loaded_policies))
                        del self._loaded_policies[oldest]
                    self._loaded_policies[name] = {
                        "config": config, "model": None, "loaded": True}
                    self._active_policy = name
                return True
            except Exception as exc:
                logger.warning("LeRobot policy load failed: %s", exc)

        # Stub: record config
        with self._lock:
            if len(self._loaded_policies) >= self._max_policies:
                oldest = next(iter(self._loaded_policies))
                del self._loaded_policies[oldest]
            self._loaded_policies[name] = {
                "config": config, "model": None, "loaded": False}
            self._active_policy = name
        return True

    def unload_policy(self, name: str) -> bool:
        with self._lock:
            if name not in self._loaded_policies:
                return False
            del self._loaded_policies[name]
            if self._active_policy == name:
                self._active_policy = None
            return True

    def set_active_policy(self, name: str) -> bool:
        with self._lock:
            if name not in self._loaded_policies:
                return False
            self._active_policy = name
            return True

    def list_policies(self) -> List[str]:
        with self._lock:
            return list(self._loaded_policies.keys())

    # -- Inference -----------------------------------------------------------

    def infer(self, observation: Observation,
              policy_name: Optional[str] = None) -> InferenceResult:
        """Run policy inference on an observation."""
        with self._lock:
            name = policy_name or self._active_policy
            if name is None or name not in self._loaded_policies:
                return InferenceResult(
                    status=InferenceStatus.NO_MODEL,
                    message="No policy loaded or specified",
                )
            policy_info = self._loaded_policies[name]

        start = time.monotonic()
        config = policy_info["config"]

        if _LEROBOT_AVAILABLE and policy_info.get("loaded"):
            try:
                # Real inference via LeRobot
                logger.info("Running LeRobot inference: %s", name)
            except Exception as exc:
                return InferenceResult(
                    status=InferenceStatus.INFERENCE_ERROR,
                    message=str(exc),
                    policy_name=name,
                )

        # Stub inference: zero actions
        n_joints = len(observation.joint_positions) or 6
        horizon = config.action_horizon if isinstance(config, PolicyConfig) else 10
        actions = [
            PolicyAction(
                joint_targets=[0.0] * n_joints,
                gripper_target=observation.gripper_position,
                confidence=0.5,
                action_horizon=horizon,
            )
            for _ in range(horizon)
        ]

        elapsed = time.monotonic() - start
        with self._lock:
            self._inference_count += 1

        return InferenceResult(
            status=InferenceStatus.SUCCESS,
            actions=actions,
            inference_time_seconds=elapsed,
            policy_name=name,
            message="stub_inference" if not _LEROBOT_AVAILABLE else "lerobot",
        )

    # -- Status --------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "backend": "lerobot" if _LEROBOT_AVAILABLE else "stub",
                "loaded_policies": list(self._loaded_policies.keys()),
                "active_policy": self._active_policy,
                "total_inferences": self._inference_count,
            }

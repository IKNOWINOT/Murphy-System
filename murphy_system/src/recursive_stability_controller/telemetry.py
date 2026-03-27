"""
Stability Telemetry System

Every control cycle logs:
- Rₜ (recursion energy)
- S(t) (stability score)
- ΔVₜ (Lyapunov change)
- Dominant instability contributor
- Enforcement actions taken

Used for:
- Offline audits
- Predictor training
- Early collapse detection
"""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("recursive_stability_controller.telemetry")


@dataclass
class TelemetryRecord:
    """Single telemetry record for one control cycle"""

    # Cycle info
    cycle_id: int
    timestamp: float

    # State variables (normalized)
    A_t: float  # Active agents
    G_t: float  # Active gates
    E_t: float  # Feedback entropy
    C_t: float  # Confidence
    M_t: float  # Murphy index

    # Recursion energy
    R_t: float
    recursion_energy_breakdown: Dict

    # Stability score
    S_t: float
    stability_level: str

    # Lyapunov
    V_t: float
    delta_V: Optional[float]
    lyapunov_stable: bool

    # Control signal
    control_mode: str
    allow_agent_spawn: bool
    allow_gate_synthesis: bool
    max_authority: str

    # Enforcement actions
    enforcement_actions: List[str]

    # Violations
    lyapunov_violations: int
    isolation_violations: int

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp,
            "state": {
                "A_t": self.A_t,
                "G_t": self.G_t,
                "E_t": self.E_t,
                "C_t": self.C_t,
                "M_t": self.M_t
            },
            "recursion_energy": {
                "R_t": self.R_t,
                "breakdown": self.recursion_energy_breakdown
            },
            "stability": {
                "S_t": self.S_t,
                "level": self.stability_level
            },
            "lyapunov": {
                "V_t": self.V_t,
                "delta_V": self.delta_V,
                "stable": self.lyapunov_stable
            },
            "control": {
                "mode": self.control_mode,
                "allow_agent_spawn": self.allow_agent_spawn,
                "allow_gate_synthesis": self.allow_gate_synthesis,
                "max_authority": self.max_authority
            },
            "enforcement_actions": self.enforcement_actions,
            "violations": {
                "lyapunov": self.lyapunov_violations,
                "isolation": self.isolation_violations
            }
        }


class StabilityTelemetry:
    """
    Telemetry system for recursive stability control.

    Maintains:
    - In-memory circular buffer (last 1000 cycles)
    - JSON append-only logs (for audit/replay)
    - Optional Prometheus-style export
    """

    def __init__(
        self,
        log_dir: str = "logs/stability",
        buffer_size: int = 1000
    ):
        """
        Initialize telemetry system.

        Args:
            log_dir: Directory for log files
            buffer_size: Size of in-memory buffer
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.buffer_size = buffer_size
        self.buffer: List[TelemetryRecord] = []

        # Current log file
        self.current_log_file = self.log_dir / f"stability_{int(time.time())}.jsonl"

        # Statistics
        self.total_cycles = 0
        self.total_violations = 0
        self.total_freezes = 0

    def record(self, record: TelemetryRecord):
        """
        Record telemetry for a control cycle.

        Args:
            record: Telemetry record
        """
        # Add to buffer
        self.buffer.append(record)

        # Trim buffer if needed
        if len(self.buffer) > self.buffer_size:
            self.buffer = self.buffer[-self.buffer_size:]

        # Write to log file
        self._write_to_log(record)

        # Update statistics
        self.total_cycles += 1
        self.total_violations += (
            record.lyapunov_violations + record.isolation_violations
        )
        if record.control_mode == "emergency":
            self.total_freezes += 1

    def _write_to_log(self, record: TelemetryRecord):
        """Write record to JSON log file"""
        try:
            with open(self.current_log_file, 'a', encoding='utf-8') as f:
                json.dump(record.to_dict(), f)
                f.write('\n')
        except Exception as exc:
            logger.info(f"[ERROR] Failed to write telemetry: {exc}")

    def get_recent(self, n: int = 10) -> List[TelemetryRecord]:
        """
        Get recent telemetry records.

        Args:
            n: Number of recent records

        Returns:
            List of recent records
        """
        return self.buffer[-n:]

    def get_all(self) -> List[TelemetryRecord]:
        """Get all buffered records"""
        return self.buffer

    def get_statistics(self) -> Dict:
        """
        Get telemetry statistics.

        Returns:
            Dictionary with statistics
        """
        if not self.buffer:
            return {
                "total_cycles": self.total_cycles,
                "total_violations": self.total_violations,
                "total_freezes": self.total_freezes,
                "buffer_size": 0,
                "mean_stability": 0.0,
                "mean_recursion_energy": 0.0
            }

        import numpy as np

        stability_scores = [r.S_t for r in self.buffer]
        recursion_energies = [r.R_t for r in self.buffer]

        return {
            "total_cycles": self.total_cycles,
            "total_violations": self.total_violations,
            "total_freezes": self.total_freezes,
            "buffer_size": len(self.buffer),
            "mean_stability": np.mean(stability_scores),
            "std_stability": np.std(stability_scores),
            "min_stability": np.min(stability_scores),
            "max_stability": np.max(stability_scores),
            "mean_recursion_energy": np.mean(recursion_energies),
            "std_recursion_energy": np.std(recursion_energies)
        }

    def export_prometheus_metrics(self) -> str:
        """
        Export metrics in Prometheus format.

        Returns:
            Prometheus-formatted metrics string
        """
        if not self.buffer:
            return ""

        latest = self.buffer[-1]

        metrics = []

        # Stability score
        metrics.append(f"stability_score {latest.S_t}")

        # Recursion energy
        metrics.append(f"recursion_energy {latest.R_t}")

        # Lyapunov function
        metrics.append(f"lyapunov_function {latest.V_t}")

        # State variables
        metrics.append(f"active_agents {latest.A_t}")
        metrics.append(f"active_gates {latest.G_t}")
        metrics.append(f"feedback_entropy {latest.E_t}")
        metrics.append(f"confidence {latest.C_t}")
        metrics.append(f"murphy_index {latest.M_t}")

        # Control mode (as numeric)
        mode_map = {"emergency": 0, "contraction": 1, "normal": 2, "expansion": 3}
        metrics.append(f"control_mode {mode_map.get(latest.control_mode, 2)}")

        # Violations
        metrics.append(f"total_violations {self.total_violations}")
        metrics.append(f"total_freezes {self.total_freezes}")

        return '\n'.join(metrics)

    def detect_early_collapse(self, window_size: int = 10) -> Optional[Dict]:
        """
        Detect early signs of system collapse.

        Indicators:
        - Stability score trending down
        - Recursion energy trending up
        - Frequent Lyapunov violations
        - Increasing entropy

        Args:
            window_size: Window for trend analysis

        Returns:
            Warning dict if collapse detected, None otherwise
        """
        if len(self.buffer) < window_size:
            return None

        import numpy as np

        recent = self.buffer[-window_size:]

        # Check stability trend
        stability_scores = [r.S_t for r in recent]
        stability_trend = np.polyfit(range(len(stability_scores)), stability_scores, 1)[0]

        # Check recursion energy trend
        recursion_energies = [r.R_t for r in recent]
        energy_trend = np.polyfit(range(len(recursion_energies)), recursion_energies, 1)[0]

        # Check Lyapunov violations
        lyapunov_violations = sum(1 for r in recent if not r.lyapunov_stable)

        # Check entropy trend
        entropies = [r.E_t for r in recent]
        entropy_trend = np.polyfit(range(len(entropies)), entropies, 1)[0]

        # Detect collapse
        warnings = []

        if stability_trend < -0.01:
            warnings.append(f"Stability declining (trend: {stability_trend:.4f})")

        if energy_trend > 0.01:
            warnings.append(f"Recursion energy increasing (trend: {energy_trend:.4f})")

        if lyapunov_violations > window_size * 0.3:
            warnings.append(f"Frequent Lyapunov violations ({lyapunov_violations}/{window_size})")

        if entropy_trend > 0.01:
            warnings.append(f"Entropy increasing (trend: {entropy_trend:.4f})")

        if warnings:
            return {
                "severity": "high" if len(warnings) >= 3 else "medium",
                "warnings": warnings,
                "current_stability": stability_scores[-1],
                "current_energy": recursion_energies[-1]
            }

        return None

    def rotate_log_file(self):
        """Rotate log file (start new file)"""
        self.current_log_file = self.log_dir / f"stability_{int(time.time())}.jsonl"
        logger.info(f"[INFO] Log file rotated: {self.current_log_file}")

    def clear_buffer(self):
        """Clear in-memory buffer (use with caution)"""
        self.buffer = []
        logger.info("[INFO] Telemetry buffer cleared")

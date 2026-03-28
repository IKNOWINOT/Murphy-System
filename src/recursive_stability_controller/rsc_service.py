"""
Recursive Stability Controller Service

Main service that integrates all components and provides REST API.

Port: 8061
"""

import logging
import time
from typing import Dict, Optional

from flask import Flask, jsonify, request

logger = logging.getLogger("recursive_stability_controller.rsc_service")

from .control_signals import ControlSignalGenerator
from .feedback_isolation import Artifact, Entity, EvaluationRequest, FeedbackIsolationRouter
from .gate_damping import GateDampingController, GateSynthesisRequest
from .lyapunov_monitor import LyapunovMonitor
from .recursion_energy import RecursionEnergyCoefficients, RecursionEnergyEstimator
from .spawn_controller import SpawnRateController, SpawnRequest
from .stability_score import StabilityScoreCalculator
from .state_variables import StateCollector, StateNormalizer
from .telemetry import StabilityTelemetry, TelemetryRecord


class RecursiveStabilityController:
    """
    Main Recursive Stability Controller.

    Integrates all control components and provides:
    - Continuous stability monitoring
    - Control signal generation
    - Telemetry collection
    - REST API
    """

    def __init__(
        self,
        confidence_engine_url: str = "http://localhost:8055",
        gate_synthesis_url: str = "http://localhost:8056",
        orchestrator_url: str = "http://localhost:8058",
        control_cycle_seconds: float = 5.0
    ):
        """
        Initialize Recursive Stability Controller.

        Args:
            confidence_engine_url: Confidence Engine URL
            gate_synthesis_url: Gate Synthesis Engine URL
            orchestrator_url: Execution Orchestrator URL
            control_cycle_seconds: Control cycle period
        """
        # Component URLs
        self.confidence_engine_url = confidence_engine_url
        self.gate_synthesis_url = gate_synthesis_url
        self.orchestrator_url = orchestrator_url

        # Control cycle period
        self.control_cycle_seconds = control_cycle_seconds

        # Initialize components
        self.state_collector = StateCollector(
            confidence_engine_url,
            gate_synthesis_url,
            orchestrator_url
        )
        self.state_normalizer = StateNormalizer()
        self.energy_estimator = RecursionEnergyEstimator()
        self.stability_calculator = StabilityScoreCalculator()
        self.lyapunov_monitor = LyapunovMonitor()
        self.spawn_controller = SpawnRateController()
        self.gate_damping = GateDampingController()
        self.feedback_isolation = FeedbackIsolationRouter()
        self.control_generator = ControlSignalGenerator()
        self.telemetry = StabilityTelemetry()

        # State
        self.running = False
        self.cycle_count = 0
        self.last_control_signal = None

        logger.info("[INIT] Recursive Stability Controller initialized")

    def run_control_cycle(self) -> Dict:
        """
        Run one control cycle.

        Returns:
            Dictionary with cycle results
        """
        self.cycle_count += 1

        # Step 1: Collect state variables
        raw_state = self.state_collector.collect_mock()  # Use mock for now
        if raw_state is None:
            logger.info("[ERROR] Failed to collect state")
            return {"error": "Failed to collect state"}

        # Step 2: Normalize state
        normalized_state = self.state_normalizer.normalize(raw_state)
        if normalized_state is None:
            logger.info("[ERROR] Failed to normalize state")
            return {"error": "Failed to normalize state"}

        # Step 3: Estimate recursion energy
        energy_breakdown = self.energy_estimator.estimate_with_breakdown(normalized_state)
        R_t = energy_breakdown["R_t"]

        # Step 4: Calculate stability score
        stability_score = self.stability_calculator.calculate(
            R_t,
            normalized_state.timestamp,
            normalized_state.cycle_id
        )

        # Step 5: Update Lyapunov monitor
        lyapunov_state = self.lyapunov_monitor.update(
            R_t,
            normalized_state.timestamp,
            normalized_state.cycle_id
        )

        # Step 6: Generate control signal
        control_signal = self.control_generator.generate_signal(
            stability_score.score,
            lyapunov_state.is_stable,
            True,  # Assume entropy decreasing for now
            self.spawn_controller.unresolved_failures,
            self.stability_calculator.s_min,
            normalized_state.timestamp,
            normalized_state.cycle_id
        )

        self.last_control_signal = control_signal

        # Step 7: Record telemetry
        telemetry_record = TelemetryRecord(
            cycle_id=normalized_state.cycle_id,
            timestamp=normalized_state.timestamp,
            A_t=normalized_state.A_t,
            G_t=normalized_state.G_t,
            E_t=normalized_state.E_t,
            C_t=normalized_state.C_t,
            M_t=normalized_state.M_t,
            R_t=R_t,
            recursion_energy_breakdown=energy_breakdown,
            S_t=stability_score.score,
            stability_level=self.stability_calculator.get_stability_level(stability_score.score),
            V_t=lyapunov_state.V_t,
            delta_V=lyapunov_state.delta_V,
            lyapunov_stable=lyapunov_state.is_stable,
            control_mode=control_signal.mode.value,
            allow_agent_spawn=control_signal.allow_agent_spawn,
            allow_gate_synthesis=control_signal.allow_gate_synthesis,
            max_authority=control_signal.max_authority,
            enforcement_actions=control_signal.reasons,
            lyapunov_violations=self.lyapunov_monitor.consecutive_violations,
            isolation_violations=len(self.feedback_isolation.get_violations(n=1))
        )

        self.telemetry.record(telemetry_record)

        # Step 8: Check for early collapse
        collapse_warning = self.telemetry.detect_early_collapse()
        if collapse_warning:
            logger.info(f"[WARNING] Early collapse detected: {collapse_warning}")

        return {
            "cycle_id": normalized_state.cycle_id,
            "timestamp": normalized_state.timestamp,
            "state": normalized_state.to_dict(),
            "recursion_energy": energy_breakdown,
            "stability_score": stability_score.to_dict(),
            "lyapunov": lyapunov_state.to_dict(),
            "control_signal": control_signal.to_dict(),
            "collapse_warning": collapse_warning
        }

    def get_status(self) -> Dict:
        """Get controller status"""
        return {
            "running": self.running,
            "cycle_count": self.cycle_count,
            "control_cycle_seconds": self.control_cycle_seconds,
            "current_mode": self.control_generator.current_mode.value if self.last_control_signal else "unknown",
            "components": {
                "state_collector": "operational",
                "energy_estimator": "operational",
                "stability_calculator": "operational",
                "lyapunov_monitor": "operational",
                "spawn_controller": "operational",
                "gate_damping": "operational",
                "feedback_isolation": "operational",
                "control_generator": "operational",
                "telemetry": "operational"
            }
        }

    async def shutdown(self):
        """Gracefully shutdown the controller."""
        self.running = False

    async def get_system_performance_metrics(self) -> Dict:
        """Return system performance metrics."""
        return {
            "confidence_computation": 50,
            "gate_synthesis": 100,
            "packet_execution": 25,
        }


# Flask application
app = Flask(__name__)
from src.flask_security import configure_secure_app

configure_secure_app(app, service_name="recursive-stability-controller")

# Global controller instance
controller: Optional[RecursiveStabilityController] = None


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Recursive Stability Controller",
        "version": "1.0.0"
    })


@app.route('/status', methods=['GET'])
def status():
    """Get controller status"""
    if controller is None:
        return jsonify({"error": "Controller not initialized"}), 500

    return jsonify(controller.get_status())


@app.route('/control-cycle', methods=['POST'])
def control_cycle():
    """Run one control cycle"""
    if controller is None:
        return jsonify({"error": "Controller not initialized"}), 500

    result = controller.run_control_cycle()
    return jsonify(result)


@app.route('/control-signal', methods=['GET'])
def get_control_signal():
    """Get current control signal"""
    if controller is None:
        return jsonify({"error": "Controller not initialized"}), 500

    if controller.last_control_signal is None:
        return jsonify({"error": "No control signal available"}), 404

    return jsonify(controller.last_control_signal.to_dict())


@app.route('/spawn/request', methods=['POST'])
def spawn_request():
    """Request agent spawn"""
    if controller is None:
        return jsonify({"error": "Controller not initialized"}), 500

    data = request.json

    spawn_req = SpawnRequest(
        request_id=data.get("request_id"),
        agent_type=data.get("agent_type"),
        priority=data.get("priority", 0),
        timestamp=time.time(),
        cycle_id=controller.cycle_count,
        requester=data.get("requester", "unknown")
    )

    # Get current state for evaluation
    current_state = {
        "lyapunov_stable": controller.lyapunov_monitor.check_stability(),
        "entropy": 0.0,  # initial entropy value
        "confidence": 0.5,  # initial confidence level
        "recursion_energy": 0.0,  # initial recursion energy
        "estimated_spawn_impact": data.get("estimated_impact", 0.0)
    }

    response = controller.spawn_controller.request_spawn(spawn_req, current_state)

    return jsonify(response.to_dict())


@app.route('/spawn/queue', methods=['GET'])
def spawn_queue():
    """Get spawn queue status"""
    if controller is None:
        return jsonify({"error": "Controller not initialized"}), 500

    return jsonify(controller.spawn_controller.get_queue_status())


@app.route('/gate/request', methods=['POST'])
def gate_request():
    """Request gate synthesis"""
    if controller is None:
        return jsonify({"error": "Controller not initialized"}), 500

    data = request.json

    gate_req = GateSynthesisRequest(
        request_id=data.get("request_id"),
        gate_type=data.get("gate_type"),
        num_gates=data.get("num_gates", 1),
        timestamp=time.time(),
        cycle_id=controller.cycle_count,
        requester=data.get("requester", "unknown")
    )

    response = controller.gate_damping.request_synthesis(
        gate_req,
        data.get("confidence", 0.5)
    )

    return jsonify(response.to_dict())


@app.route('/gate/capacity', methods=['GET'])
def gate_capacity():
    """Get gate capacity"""
    if controller is None:
        return jsonify({"error": "Controller not initialized"}), 500

    return jsonify(controller.gate_damping.get_capacity())


@app.route('/isolation/check', methods=['POST'])
def isolation_check():
    """Check evaluation for feedback isolation"""
    if controller is None:
        return jsonify({"error": "Controller not initialized"}), 500

    data = request.json

    eval_req = EvaluationRequest(
        request_id=data.get("request_id"),
        evaluator_id=data.get("evaluator_id"),
        artifact_id=data.get("artifact_id"),
        timestamp=time.time()
    )

    is_allowed, violation = controller.feedback_isolation.check_evaluation(eval_req)

    return jsonify({
        "allowed": is_allowed,
        "violation": violation.to_dict() if violation else None
    })


@app.route('/telemetry/recent', methods=['GET'])
def telemetry_recent():
    """Get recent telemetry"""
    if controller is None:
        return jsonify({"error": "Controller not initialized"}), 500

    n = request.args.get('n', default=10, type=int)
    recent = controller.telemetry.get_recent(n)

    return jsonify({
        "count": len(recent),
        "records": [r.to_dict() for r in recent]
    })


@app.route('/telemetry/statistics', methods=['GET'])
def telemetry_statistics():
    """Get telemetry statistics"""
    if controller is None:
        return jsonify({"error": "Controller not initialized"}), 500

    return jsonify(controller.telemetry.get_statistics())


@app.route('/telemetry/metrics', methods=['GET'])
def telemetry_metrics():
    """Get Prometheus metrics"""
    if controller is None:
        return "# Controller not initialized\n", 500

    metrics = controller.telemetry.export_prometheus_metrics()
    return metrics, 200, {'Content-Type': 'text/plain; charset=utf-8'}


@app.route('/statistics', methods=['GET'])
def statistics():
    """Get comprehensive statistics"""
    if controller is None:
        return jsonify({"error": "Controller not initialized"}), 500

    return jsonify({
        "recursion_energy": controller.energy_estimator.get_statistics(),
        "stability_score": controller.stability_calculator.get_statistics(),
        "lyapunov": controller.lyapunov_monitor.get_statistics(),
        "spawn_controller": controller.spawn_controller.get_statistics(),
        "gate_damping": controller.gate_damping.get_statistics(),
        "feedback_isolation": controller.feedback_isolation.get_statistics(),
        "control_signals": controller.control_generator.get_statistics(),
        "telemetry": controller.telemetry.get_statistics()
    })


def create_app(
    confidence_engine_url: str = "http://localhost:8055",
    gate_synthesis_url: str = "http://localhost:8056",
    orchestrator_url: str = "http://localhost:8058"
) -> Flask:
    """
    Create Flask application.

    Args:
        confidence_engine_url: Confidence Engine URL
        gate_synthesis_url: Gate Synthesis Engine URL
        orchestrator_url: Execution Orchestrator URL

    Returns:
        Flask application
    """
    global controller

    controller = RecursiveStabilityController(
        confidence_engine_url,
        gate_synthesis_url,
        orchestrator_url
    )

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=8061, debug=False)

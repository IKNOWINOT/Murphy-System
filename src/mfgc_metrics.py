"""
MFGC Metrics and Monitoring
Track execution metrics for analysis and optimization
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from mfgc_core import Phase, SystemState

logger = logging.getLogger(__name__)


@dataclass
class PhaseMetrics:
    """Metrics for a single phase execution"""
    phase: str
    start_time: float
    end_time: float
    duration: float
    confidence_start: float
    confidence_end: float
    confidence_delta: float
    murphy_index: float
    gates_added: int
    candidates_generated: int


@dataclass
class ExecutionMetrics:
    """Complete execution metrics"""
    task: str
    start_time: float
    end_time: float
    total_duration: float

    # Phase metrics
    phase_metrics: List[PhaseMetrics] = field(default_factory=list)

    # Overall metrics
    initial_confidence: float = 0.0
    final_confidence: float = 0.0
    confidence_gain: float = 0.0

    peak_murphy_index: float = 0.0
    total_gates_synthesized: int = 0
    total_candidates_generated: int = 0

    # Success indicators
    all_phases_completed: bool = False
    murphy_threshold_exceeded: bool = False
    confidence_threshold_met: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'task': self.task,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'total_duration': self.total_duration,
            'phase_metrics': [
                {
                    'phase': pm.phase,
                    'duration': pm.duration,
                    'confidence_start': pm.confidence_start,
                    'confidence_end': pm.confidence_end,
                    'confidence_delta': pm.confidence_delta,
                    'murphy_index': pm.murphy_index,
                    'gates_added': pm.gates_added,
                    'candidates_generated': pm.candidates_generated
                }
                for pm in self.phase_metrics
            ],
            'initial_confidence': self.initial_confidence,
            'final_confidence': self.final_confidence,
            'confidence_gain': self.confidence_gain,
            'peak_murphy_index': self.peak_murphy_index,
            'total_gates_synthesized': self.total_gates_synthesized,
            'total_candidates_generated': self.total_candidates_generated,
            'all_phases_completed': self.all_phases_completed,
            'murphy_threshold_exceeded': self.murphy_threshold_exceeded,
            'confidence_threshold_met': self.confidence_threshold_met
        }


class MFGCMetricsCollector:
    """Collect and analyze MFGC execution metrics"""

    def __init__(self):
        self.executions: List[ExecutionMetrics] = []

    def collect_from_state(self, state: SystemState) -> ExecutionMetrics:
        """
        Collect metrics from completed execution state

        Args:
            state: Completed SystemState

        Returns:
            ExecutionMetrics object
        """
        # Extract timing from events
        start_event = next((e for e in state.events if e['type'] == 'execution_start'), None)
        end_event = next((e for e in state.events if e['type'] == 'execution_complete'), None)

        start_time = start_event['timestamp'] if start_event else time.time()
        end_time = end_event['timestamp'] if end_event else time.time()

        metrics = ExecutionMetrics(
            task=state.x_t.get('task', 'Unknown'),
            start_time=start_time,
            end_time=end_time,
            total_duration=end_time - start_time
        )

        # Collect phase metrics
        phase_events = [e for e in state.events if e['type'] in ['phase_start', 'phase_complete']]

        current_phase_start = None
        current_phase_name = None
        current_confidence_start = 0.0

        for event in phase_events:
            if event['type'] == 'phase_start':
                current_phase_start = event['timestamp']
                current_phase_name = event['phase']
                current_confidence_start = event.get('confidence', 0.0)

            elif event['type'] == 'phase_complete' and current_phase_start:
                phase_metric = PhaseMetrics(
                    phase=event['phase'],
                    start_time=current_phase_start,
                    end_time=event['timestamp'],
                    duration=event['timestamp'] - current_phase_start,
                    confidence_start=current_confidence_start,
                    confidence_end=event['confidence'],
                    confidence_delta=event['confidence'] - current_confidence_start,
                    murphy_index=event['murphy_index'],
                    gates_added=event.get('gates_added', 0),
                    candidates_generated=len(state.candidates)
                )
                metrics.phase_metrics.append(phase_metric)

        # Overall metrics
        if state.confidence_history:
            metrics.initial_confidence = state.confidence_history[0]
            metrics.final_confidence = state.confidence_history[-1]
            metrics.confidence_gain = metrics.final_confidence - metrics.initial_confidence

        if state.murphy_history:
            metrics.peak_murphy_index = max(state.murphy_history)

        metrics.total_gates_synthesized = len(state.G_t)
        metrics.total_candidates_generated = sum(pm.candidates_generated for pm in metrics.phase_metrics)

        # Success indicators
        metrics.all_phases_completed = len(state.phase_history) == 7
        metrics.murphy_threshold_exceeded = metrics.peak_murphy_index > 0.3
        metrics.confidence_threshold_met = metrics.final_confidence >= 0.85

        # Store
        self.executions.append(metrics)

        return metrics

    def get_aggregate_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics across all executions"""
        if not self.executions:
            return {'error': 'No executions recorded'}

        return {
            'total_executions': len(self.executions),
            'average_duration': sum(e.total_duration for e in self.executions) / (len(self.executions) or 1),
            'average_confidence_gain': sum(e.confidence_gain for e in self.executions) / (len(self.executions) or 1),
            'average_final_confidence': sum(e.final_confidence for e in self.executions) / (len(self.executions) or 1),
            'average_murphy_index': sum(e.peak_murphy_index for e in self.executions) / (len(self.executions) or 1),
            'average_gates_synthesized': sum(e.total_gates_synthesized for e in self.executions) / (len(self.executions) or 1),
            'success_rate': sum(1 for e in self.executions if e.all_phases_completed) / (len(self.executions) or 1),
            'murphy_violations': sum(1 for e in self.executions if e.murphy_threshold_exceeded),
            'phase_durations': self._get_average_phase_durations()
        }

    def _get_average_phase_durations(self) -> Dict[str, float]:
        """Get average duration for each phase"""
        phase_durations = {}
        phase_counts = {}

        for execution in self.executions:
            for phase_metric in execution.phase_metrics:
                phase = phase_metric.phase
                if phase not in phase_durations:
                    phase_durations[phase] = 0.0
                    phase_counts[phase] = 0

                phase_durations[phase] += phase_metric.duration
                phase_counts[phase] += 1

        return {
            phase: duration / phase_counts[phase]
            for phase, duration in phase_durations.items()
        }

    def export_to_json(self, filepath: str):
        """Export all metrics to JSON file"""
        data = {
            'executions': [e.to_dict() for e in self.executions],
            'aggregate_stats': self.get_aggregate_stats()
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def get_phase_analysis(self, phase_name: str) -> Dict[str, Any]:
        """Analyze specific phase across all executions"""
        phase_metrics = []

        for execution in self.executions:
            for pm in execution.phase_metrics:
                if pm.phase == phase_name:
                    phase_metrics.append(pm)

        if not phase_metrics:
            return {'error': f'No data for phase {phase_name}'}

        return {
            'phase': phase_name,
            'executions': len(phase_metrics),
            'average_duration': sum(pm.duration for pm in phase_metrics) / (len(phase_metrics) or 1),
            'average_confidence_delta': sum(pm.confidence_delta for pm in phase_metrics) / (len(phase_metrics) or 1),
            'average_murphy_index': sum(pm.murphy_index for pm in phase_metrics) / (len(phase_metrics) or 1),
            'average_gates_added': sum(pm.gates_added for pm in phase_metrics) / (len(phase_metrics) or 1),
            'min_duration': min(pm.duration for pm in phase_metrics),
            'max_duration': max(pm.duration for pm in phase_metrics)
        }

    def get_confidence_trajectory_analysis(self) -> Dict[str, Any]:
        """Analyze confidence evolution patterns"""
        if not self.executions:
            return {'error': 'No executions recorded'}

        trajectories = []

        for execution in self.executions:
            trajectory = [pm.confidence_end for pm in execution.phase_metrics]
            trajectories.append(trajectory)

        # Average trajectory
        max_len = max(len(t) for t in trajectories)
        avg_trajectory = []

        for i in range(max_len):
            values = [t[i] for t in trajectories if i < len(t)]
            avg_trajectory.append(sum(values) / (len(values) or 1))

        return {
            'average_trajectory': avg_trajectory,
            'initial_confidence': avg_trajectory[0] if avg_trajectory else 0.0,
            'final_confidence': avg_trajectory[-1] if avg_trajectory else 0.0,
            'total_gain': avg_trajectory[-1] - avg_trajectory[0] if avg_trajectory else 0.0,
            'monotonic_increase': all(avg_trajectory[i] <= avg_trajectory[i+1]
                                     for i in range(len(avg_trajectory)-1))
        }

    def get_murphy_index_analysis(self) -> Dict[str, Any]:
        """Analyze Murphy index patterns"""
        if not self.executions:
            return {'error': 'No executions recorded'}

        return {
            'peak_values': [e.peak_murphy_index for e in self.executions],
            'average_peak': sum(e.peak_murphy_index for e in self.executions) / (len(self.executions) or 1),
            'max_peak': max(e.peak_murphy_index for e in self.executions),
            'threshold_violations': sum(1 for e in self.executions if e.murphy_threshold_exceeded),
            'violation_rate': sum(1 for e in self.executions if e.murphy_threshold_exceeded) / (len(self.executions) or 1),
            'safe_executions': sum(1 for e in self.executions if not e.murphy_threshold_exceeded)
        }

    def get_gate_synthesis_analysis(self) -> Dict[str, Any]:
        """Analyze gate synthesis patterns"""
        if not self.executions:
            return {'error': 'No executions recorded'}

        return {
            'total_gates_all_executions': sum(e.total_gates_synthesized for e in self.executions),
            'average_gates_per_execution': sum(e.total_gates_synthesized for e in self.executions) / (len(self.executions) or 1),
            'min_gates': min(e.total_gates_synthesized for e in self.executions),
            'max_gates': max(e.total_gates_synthesized for e in self.executions),
            'gates_by_phase': self._get_gates_by_phase()
        }

    def _get_gates_by_phase(self) -> Dict[str, float]:
        """Get average gates added per phase"""
        phase_gates = {}
        phase_counts = {}

        for execution in self.executions:
            for phase_metric in execution.phase_metrics:
                phase = phase_metric.phase
                if phase not in phase_gates:
                    phase_gates[phase] = 0
                    phase_counts[phase] = 0

                phase_gates[phase] += phase_metric.gates_added
                phase_counts[phase] += 1

        return {
            phase: gates / phase_counts[phase]
            for phase, gates in phase_gates.items()
        }
